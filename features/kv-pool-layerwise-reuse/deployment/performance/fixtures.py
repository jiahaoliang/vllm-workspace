from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from performance.contract import INPUT_TOKENS, WorkloadPoint, point_id, sample_counts

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
    manifest_file: Path
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
    candidates: list[int] = []
    for token_id in range(int(tokenizer.vocab_size)):
        if token_id in special:
            continue
        text = _decode(tokenizer, [token_id])
        if (
            len(text) == 1
            and ord(text) > 127
            and _encode(tokenizer, text) == [token_id]
            and _encode(tokenizer, text * 64) == [token_id] * 64
        ):
            candidates.append(token_id)
            if len(candidates) == 512:
                break
    stable: list[int] = []
    for token_id in candidates:
        if all(
            _encode(tokenizer, _decode(tokenizer, [other, token_id])) == [other, token_id]
            and _encode(tokenizer, _decode(tokenizer, [token_id, other])) == [token_id, other]
            for other in stable
        ):
            stable.append(token_id)
            if len(stable) == minimum:
                return tuple(stable)
    raise ValueError(f"tokenizer has fewer than {minimum} sequence-stable tokens")


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
    stable_tokens: tuple[int, ...] | None = None,
) -> PromptRecord:
    if input_tokens < BLOCK_SIZE:
        raise ValueError(f"input_tokens must be at least {BLOCK_SIZE}")
    stable = stable_tokens or find_roundtrip_tokens(tokenizer)
    token_ids = _index_prefix(request_index, stable)
    randomizer = random.Random(f"{seed}:{input_tokens}:{request_index}")
    token_ids.extend(stable[randomizer.randrange(len(stable))] for _ in range(input_tokens - len(token_ids)))
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
    stable_tokens: tuple[int, ...] | None = None,
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
    stable = stable_tokens or find_roundtrip_tokens(tokenizer)
    with metadata_file.open("x", encoding="utf-8") as metadata_stream:
        for partition, count in partition_sizes:
            path = root / f"{partition}.jsonl"
            ids: list[str] = []
            with path.open("x", encoding="utf-8") as partition_stream:
                for _ in range(count):
                    record = build_prompt(
                        tokenizer,
                        input_tokens,
                        request_index,
                        seed,
                        stable_tokens=stable,
                    )
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
    manifest_file = root / "manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "input_tokens": input_tokens,
                "concurrency": concurrency,
                "seed": seed,
                "tokenizer_identity": str(getattr(tokenizer, "name_or_path", type(tokenizer).__name__)),
                "warmup_ids": partition_ids["warmup"],
                "formal_ids": [partition_ids[f"formal-{index}"] for index in range(1, repetitions + 1)],
                "artifact_checksums": checksums,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checksums[manifest_file.name] = _digest(manifest_file)
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
        formal_ids=tuple(partition_ids[f"formal-{index}"] for index in range(1, repetitions + 1)),
        partition_files=partition_files,
        metadata_file=metadata_file,
        manifest_file=manifest_file,
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


def _read_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{description} is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise TypeError(f"{description} is not a JSON object: {path}")
    return value


def build_attempt_contract(
    point: WorkloadPoint,
    phase: str,
    dataset_path: Path,
    fixture_manifest: Path,
    request_count: int,
) -> dict[str, object]:
    if request_count <= 0:
        raise ValueError("request_count must be positive")
    if phase not in {"warmup", "formal-1"}:
        raise ValueError(f"unsupported attempt phase: {phase}")
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)
    if not fixture_manifest.is_file():
        raise FileNotFoundError(fixture_manifest)

    manifest = _read_json_object(fixture_manifest, "fixture manifest")
    if manifest.get("input_tokens") != point.input_tokens:
        raise ValueError(
            "fixture input token mismatch: "
            f"{manifest.get('input_tokens')} != {point.input_tokens}"
        )
    if manifest.get("concurrency") != point.concurrency:
        raise ValueError(
            "fixture concurrency mismatch: "
            f"{manifest.get('concurrency')} != {point.concurrency}"
        )

    expected_ids: object
    if phase == "warmup":
        expected_ids = manifest.get("warmup_ids")
    else:
        formal_ids = manifest.get("formal_ids")
        expected_ids = (
            formal_ids[0] if isinstance(formal_ids, list) and formal_ids else None
        )
    if not isinstance(expected_ids, list) or not all(
        isinstance(value, str) for value in expected_ids
    ):
        raise ValueError(f"fixture manifest lacks request IDs for {phase}")
    if len(expected_ids) != request_count:
        raise ValueError(
            f"fixture request count mismatch: {len(expected_ids)} != {request_count}"
        )

    try:
        dataset_text = dataset_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("dataset is not valid UTF-8") from error
    lines = dataset_text.splitlines()
    if len(lines) != request_count:
        raise ValueError(
            f"dataset line count mismatch: {len(lines)} != {request_count}"
        )
    actual_ids: list[str] = []
    for index, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"dataset row {index} is not valid JSON") from error
        if not isinstance(row, dict):
            raise TypeError(f"dataset row {index} is not a JSON object")
        if not isinstance(row.get("question"), str):
            raise TypeError(f"dataset row {index} lacks a string question")
        request_id = row.get("request_id")
        if not isinstance(request_id, str):
            raise TypeError(f"dataset row {index} lacks a string request_id")
        actual_ids.append(request_id)
    if actual_ids != expected_ids:
        raise ValueError("dataset request IDs do not match fixture manifest")

    dataset_sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    checksums = manifest.get("artifact_checksums")
    expected_checksum = (
        checksums.get(f"{phase}.jsonl") if isinstance(checksums, dict) else None
    )
    if expected_checksum != dataset_sha256:
        raise ValueError(
            f"dataset checksum mismatch: {dataset_sha256} != {expected_checksum}"
        )
    return {
        "schema_version": 1,
        "phase": phase,
        "point_id": point_id(point),
        "topology": point.topology,
        "variant": point.variant,
        "input_tokens": point.input_tokens,
        "output_tokens": point.output_tokens,
        "concurrency": point.concurrency,
        "request_count": request_count,
        "dataset_line_count": len(lines),
        "dataset_sha256": dataset_sha256,
        "fixture_manifest_sha256": hashlib.sha256(
            fixture_manifest.read_bytes()
        ).hexdigest(),
    }


def write_aisbench_config(
    point: WorkloadPoint,
    dataset_path: Path,
    output_path: Path,
    request_count: int,
    phase: str,
    fixture_manifest: Path,
    endpoint: str = "http://vllm-proxy-service:8000/",
) -> Path:
    attempt_contract = build_attempt_contract(
        point,
        phase,
        dataset_path,
        fixture_manifest,
        request_count,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    (output_path.parent / "attempt-contract.json").write_text(
        json.dumps(attempt_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    dataset_path.with_name(dataset_path.name + ".meta.json").write_text(
        json.dumps(
            {"request_count": request_count, "sampling_mode": "default"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    text = f"""from ais_bench.benchmark.calculators import DefaultPerfMetricCalculator
from ais_bench.benchmark.datasets import CustomDataset
from ais_bench.benchmark.models import VLLMCustomAPI
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.partitioners import NaivePartitioner
from ais_bench.benchmark.runners import LocalRunner
from ais_bench.benchmark.summarizers import DefaultPerfSummarizer
from ais_bench.benchmark.tasks import OpenICLApiInferTask

mode = "perf"
summarizer = dict(
    attr="performance",
    type=DefaultPerfSummarizer,
    calculator=dict(
        type=DefaultPerfMetricCalculator,
        stats_list=["Average", "Min", "Max", "Median", "P75", "P90", "P95", "P99"],
    ),
)

models = [dict(
    abbr={point.variant!r},
    attr="service",
    type=VLLMCustomAPI,
    stream=True,
    retry=1,  # AISBench iterates range(retry); 1 means one total request attempt.
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
        type=LocalRunner,
        max_num_workers={point.concurrency},
        task=dict(type=OpenICLApiInferTask),
    ),
)
work_dir={str((output_path.parent / "aisbench-output").resolve())!r}
"""
    compile(text, str(output_path), "exec")
    output_path.write_text(text, encoding="utf-8")
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--tokenizer", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--concurrency", type=int, default=64)
    generate.add_argument("--seed", type=int, default=20260808)
    config = subparsers.add_parser("config")
    config.add_argument("--topology", choices=("dp1", "dp2"), required=True)
    config.add_argument("--input-tokens", type=int, required=True)
    config.add_argument("--output-tokens", type=int, required=True)
    config.add_argument("--variant", choices=("bulk", "layerwise", "reuse3"), required=True)
    config.add_argument("--concurrency", type=int, required=True)
    config.add_argument("--dataset", type=Path, required=True)
    config.add_argument("--request-count", type=int, required=True)
    config.add_argument("--phase", choices=("warmup", "formal-1"), required=True)
    config.add_argument("--fixture-manifest", type=Path, required=True)
    config.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "config":
        point = WorkloadPoint(
            args.topology,
            args.input_tokens,
            args.output_tokens,
            args.variant,
            args.concurrency,
        )
        write_aisbench_config(
            point,
            args.dataset,
            args.output,
            request_count=args.request_count,
            phase=args.phase,
            fixture_manifest=args.fixture_manifest,
        )
        return 0
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    tokenizer.model_max_length = 65536
    stable_tokens = find_roundtrip_tokens(tokenizer)
    args.output.mkdir(parents=True, exist_ok=True)
    tokenizer_files = sorted(path for path in args.tokenizer.iterdir() if path.is_file())
    (args.output / "tokenizer-identity.json").write_text(
        json.dumps(
            {
                "path": str(args.tokenizer.resolve()),
                "class": type(tokenizer).__name__,
                "vocab_size": tokenizer.vocab_size,
                "model_max_length_for_validation": tokenizer.model_max_length,
                "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in tokenizer_files},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for input_tokens in INPUT_TOKENS:
        write_fixture(
            tokenizer,
            input_tokens,
            args.concurrency,
            args.seed,
            args.output,
            stable_tokens=stable_tokens,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
