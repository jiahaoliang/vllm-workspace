from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from performance.contract import WorkloadPoint, sample_counts


BLOCK_SIZE = 128


@dataclass(frozen=True)
class PromptRecord:
    request_id: str
    seed: int
    input_tokens: int
    text: str
    token_ids: tuple[int, ...]
    tokenizer_identity: str
    prompt_sha256: str
    first_block_sha256: str


@dataclass(frozen=True)
class FixtureManifest:
    root: Path
    input_tokens: int
    concurrency: int
    seed: int
    warmup_ids: tuple[str, ...]
    formal_ids: tuple[tuple[str, ...], ...]
    partition_files: dict[str, Path]
    metadata_file: Path
    checksum_file: Path
    checksums: dict[str, str]


def _encode(tokenizer: Any, text: str) -> list[int]:
    return list(tokenizer.encode(text, add_special_tokens=False))


def _decode(tokenizer: Any, token_ids: list[int]) -> str:
    return tokenizer.decode(
        token_ids,
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )


def find_roundtrip_tokens(tokenizer: Any, minimum: int = 16) -> tuple[int, ...]:
    special = set(getattr(tokenizer, "all_special_ids", ()))
    stable: list[int] = []
    for token_id in range(int(tokenizer.vocab_size)):
        if token_id in special:
            continue
        text = _decode(tokenizer, [token_id])
        if text and _encode(tokenizer, text) == [token_id]:
            stable.append(token_id)
            if len(stable) == minimum:
                return tuple(stable)
    raise ValueError(f"tokenizer has fewer than {minimum} single-token round trips")


def _index_prefix(index: int, alphabet: tuple[int, ...], width: int = 16) -> list[int]:
    if index < 0:
        raise ValueError("request_index must be non-negative")
    base = len(alphabet)
    digits = [alphabet[0]] * width
    remaining = index
    for position in range(width - 1, -1, -1):
        digits[position] = alphabet[remaining % base]
        remaining //= base
    if remaining:
        raise ValueError("request_index does not fit deterministic prefix")
    return digits


def build_prompt(
    tokenizer: Any,
    input_tokens: int,
    request_index: int,
    seed: int,
) -> PromptRecord:
    if input_tokens < BLOCK_SIZE:
        raise ValueError(f"input_tokens must be at least {BLOCK_SIZE}")
    stable = find_roundtrip_tokens(tokenizer)
    token_ids = _index_prefix(request_index, stable)
    randomizer = random.Random(f"{seed}:{input_tokens}:{request_index}")
    token_ids.extend(
        stable[randomizer.randrange(len(stable))]
        for _ in range(input_tokens - len(token_ids))
    )
    text = _decode(tokenizer, token_ids)
    replay = _encode(tokenizer, text)
    if replay != token_ids:
        raise ValueError("decoded prompt does not round-trip to the exact token sequence")
    prompt_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    first_block = json.dumps(token_ids[:BLOCK_SIZE], separators=(",", ":"))
    return PromptRecord(
        request_id=f"p{input_tokens}-s{seed}-r{request_index:06d}",
        seed=seed,
        input_tokens=input_tokens,
        text=text,
        token_ids=tuple(token_ids),
        tokenizer_identity=str(getattr(tokenizer, "name_or_path", type(tokenizer).__name__)),
        prompt_sha256=prompt_digest,
        first_block_sha256=hashlib.sha256(first_block.encode("ascii")).hexdigest(),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(
    tokenizer: Any,
    input_tokens: int,
    concurrency: int,
    seed: int,
    output_dir: Path,
) -> FixtureManifest:
    warmup_count, formal_count, repetitions = sample_counts(concurrency)
    root = output_dir / f"tokens-{input_tokens}-c{concurrency}"
    root.mkdir(parents=True, exist_ok=False)
    partition_sizes = [("warmup", warmup_count)] + [
        (f"formal-{index}", formal_count) for index in range(1, repetitions + 1)
    ]
    partition_files: dict[str, Path] = {}
    partition_ids: dict[str, tuple[str, ...]] = {}
    metadata_file = root / "metadata.jsonl"
    request_index = 0
    with metadata_file.open("x", encoding="utf-8") as metadata_stream:
        for partition, count in partition_sizes:
            path = root / f"{partition}.jsonl"
            ids: list[str] = []
            with path.open("x", encoding="utf-8") as partition_stream:
                for _ in range(count):
                    record = build_prompt(tokenizer, input_tokens, request_index, seed)
                    request_index += 1
                    ids.append(record.request_id)
                    partition_stream.write(
                        json.dumps(
                            {
                                "question": record.text,
                                "answer": "",
                                "request_id": record.request_id,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    metadata_stream.write(
                        json.dumps(
                            {
                                "request_id": record.request_id,
                                "partition": partition,
                                "seed": record.seed,
                                "tokenizer_identity": record.tokenizer_identity,
                                "token_count": len(record.token_ids),
                                "token_ids": record.token_ids,
                                "prompt_sha256": record.prompt_sha256,
                                "first_block_sha256": record.first_block_sha256,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    )
            partition_files[partition] = path
            partition_ids[partition] = tuple(ids)
    checksum_paths = [*partition_files.values(), metadata_file]
    checksums = {path.name: _digest(path) for path in checksum_paths}
    checksum_file = root / "SHA256SUMS"
    checksum_file.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())),
        encoding="utf-8",
    )
    return FixtureManifest(
        root=root,
        input_tokens=input_tokens,
        concurrency=concurrency,
        seed=seed,
        warmup_ids=partition_ids["warmup"],
        formal_ids=tuple(
            partition_ids[f"formal-{index}"] for index in range(1, repetitions + 1)
        ),
        partition_files=partition_files,
        metadata_file=metadata_file,
        checksum_file=checksum_file,
        checksums=checksums,
    )


def replay_fixture(manifest: FixtureManifest) -> list[str]:
    errors: list[str] = []
    for name, expected in manifest.checksums.items():
        path = manifest.root / name
        if not path.is_file() or _digest(path) != expected:
            errors.append(f"fixture checksum mismatch: {name}")
    return errors


def write_aisbench_config(
    point: WorkloadPoint,
    dataset_path: Path,
    output_path: Path,
    request_count: int,
    endpoint: str = "http://vllm-proxy-service:8000/",
) -> Path:
    if request_count <= 0:
        raise ValueError("request_count must be positive")
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)
    text = f'''from ais_bench.benchmark.datasets import CustomDataset
from ais_bench.benchmark.models import VLLMCustomAPI
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.partitioners import NaivePartitioner
from ais_bench.benchmark.runners.local_api import LocalAPIRunner
from ais_bench.benchmark.tasks import OpenICLInferTask

mode = "perf"
pressure = True
summarizer = dict(type="stable_stage")
request_count={request_count}

models = [dict(
    attr="service",
    type=VLLMCustomAPI,
    stream=True,
    retry=0,
    url={endpoint!r},
    model="vllm-ascend/DeepSeek-V2-Lite-W8A8",
    path="/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8",
    max_out_len={point.output_tokens},
    batch_size={point.concurrency},
    request_rate=0,
    generation_kwargs=dict(temperature=0, ignore_eos=True),
)]

datasets = [dict(
    type=CustomDataset,
    abbr={point.variant!r},
    path={str(dataset_path.resolve())!r},
    reader_cfg=dict(input_columns=["question"], output_column="answer"),
    infer_cfg=dict(
        prompt_template=dict(type=PromptTemplate, template="{{question}}"),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    ),
)]

infer = dict(
    partitioner=dict(type=NaivePartitioner),
    runner=dict(
        type=LocalAPIRunner,
        max_num_workers={point.concurrency},
        task=dict(type=OpenICLInferTask),
    ),
)
work_dir={str((output_path.parent / "aisbench-output").resolve())!r}
'''
    compile(text, str(output_path), "exec")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path
