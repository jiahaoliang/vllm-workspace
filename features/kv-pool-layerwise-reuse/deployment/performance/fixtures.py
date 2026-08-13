from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from performance.contract import (
    INPUT_TOKENS,
    SEED_TOKENS,
    WorkloadPoint,
    point_id,
    sample_counts,
)

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
    seed_ids: tuple[str, ...]
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


def _token_ids_digest(token_ids: list[int] | tuple[int, ...]) -> str:
    encoded = json.dumps(token_ids, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _record_from_token_ids(
    tokenizer: Any,
    token_ids: list[int],
    request_id: str,
    seed: int,
) -> PromptRecord:
    text = _decode(tokenizer, token_ids)
    if _encode(tokenizer, text) != token_ids:
        raise ValueError("decoded prompt does not round-trip to the exact token sequence")
    first_block = json.dumps(token_ids[:BLOCK_SIZE], separators=(",", ":"))
    return PromptRecord(
        request_id=request_id,
        seed=seed,
        input_tokens=len(token_ids),
        text=text,
        token_ids=tuple(token_ids),
        tokenizer_identity=str(
            getattr(tokenizer, "name_or_path", type(tokenizer).__name__)
        ),
        prompt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        first_block_sha256=hashlib.sha256(first_block.encode("ascii")).hexdigest(),
    )


def _shared_suffix(
    stable: tuple[int, ...],
    length: int,
    request_index: int,
    seed: int,
) -> list[int]:
    if length < 16:
        raise ValueError("shared-prefix suffix must contain at least 16 tokens")
    token_ids = _index_prefix(request_index, stable)
    randomizer = random.Random(f"shared:{seed}:{length}:{request_index}")
    token_ids.extend(
        stable[randomizer.randrange(len(stable))]
        for _ in range(length - len(token_ids))
    )
    return token_ids


def write_fixture(
    tokenizer: Any,
    input_tokens: int,
    concurrency: int,
    seed: int,
    output_dir: Path,
    stable_tokens: tuple[int, ...] | None = None,
    seed_tokens: int = SEED_TOKENS,
    warmup_count: int | None = None,
    formal_count: int | None = None,
    seed_request_count: int | None = None,
    admission_count: int = 0,
    shared_prefix: bool = False,
    repetitions: int | None = None,
) -> FixtureManifest:
    if warmup_count is None or formal_count is None:
        default_warmup, default_formal, default_repetitions = sample_counts(
            concurrency
        )
        warmup_count = default_warmup if warmup_count is None else warmup_count
        formal_count = default_formal if formal_count is None else formal_count
    else:
        default_repetitions = 1
    repetitions = default_repetitions if repetitions is None else repetitions
    seed_request_count = formal_count if seed_request_count is None else seed_request_count
    if (
        warmup_count <= 0
        or formal_count <= 0
        or seed_request_count <= 0
        or admission_count < 0
    ):
        raise ValueError("fixture request counts must be positive")
    if repetitions != 1:
        raise ValueError("paired-prefix fixture requires exactly one formal partition")
    if shared_prefix and seed_request_count != 1:
        raise ValueError("shared-prefix fixture requires exactly one seed request")
    if not shared_prefix and seed_request_count != formal_count:
        raise ValueError("paired-prefix fixture requires seed count to match formal count")
    if seed_tokens < BLOCK_SIZE or seed_tokens % BLOCK_SIZE:
        raise ValueError(f"seed_tokens must be a positive multiple of {BLOCK_SIZE}")
    if input_tokens <= seed_tokens:
        raise ValueError(f"input_tokens must be greater than seed tokens ({seed_tokens})")
    root = output_dir / f"tokens-{input_tokens}-c{concurrency}"
    root.mkdir(parents=True, exist_ok=False)
    partition_files: dict[str, Path] = {}
    partition_ids: dict[str, tuple[str, ...]] = {}
    metadata_file = root / "metadata.jsonl"
    request_index = 0
    stable = stable_tokens or find_roundtrip_tokens(tokenizer)
    with metadata_file.open("x", encoding="utf-8") as metadata_stream:
        def write_metadata(record: PromptRecord, partition: str) -> None:
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

        warmup_path = root / "warmup.jsonl"
        warmup_ids: list[str] = []
        with warmup_path.open("x", encoding="utf-8") as warmup_stream:
            for _ in range(warmup_count):
                record = build_prompt(
                    tokenizer,
                    input_tokens,
                    request_index,
                    seed,
                    stable_tokens=stable,
                )
                request_index += 1
                warmup_ids.append(record.request_id)
                warmup_stream.write(
                    json.dumps(
                        {"question": record.text, "answer": "", "request_id": record.request_id},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
                write_metadata(record, "warmup")
        partition_files["warmup"] = warmup_path
        partition_ids["warmup"] = tuple(warmup_ids)

        seed_path = root / "seed.jsonl"
        admission_path = root / "admission.jsonl"
        formal_path = root / "formal-1.jsonl"
        seed_ids: list[str] = []
        formal_ids: list[str] = []
        seed_formal_pairs: list[dict[str, str]] = []
        with seed_path.open("x", encoding="utf-8") as seed_stream, formal_path.open(
            "x", encoding="utf-8"
        ) as formal_stream:
            if shared_prefix:
                shared = build_prompt(
                    tokenizer,
                    seed_tokens,
                    request_index,
                    seed,
                    stable_tokens=stable,
                )
                request_index += 1
                shared = _record_from_token_ids(
                    tokenizer,
                    list(shared.token_ids),
                    f"shared-seed-{shared.request_id}",
                    seed,
                )
                seed_ids.append(shared.request_id)
                seed_stream.write(
                    json.dumps(
                        {
                            "question": shared.text,
                            "answer": "",
                            "request_id": shared.request_id,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
                write_metadata(shared, "seed")
                shared_digest = _token_ids_digest(shared.token_ids)
                for formal_index in range(formal_count):
                    suffix = _shared_suffix(
                        stable,
                        input_tokens - seed_tokens,
                        formal_index + 1,
                        seed,
                    )
                    formal = _record_from_token_ids(
                        tokenizer,
                        [*shared.token_ids, *suffix],
                        f"formal-p{input_tokens}-s{seed}-r{formal_index:06d}",
                        seed,
                    )
                    formal_ids.append(formal.request_id)
                    seed_formal_pairs.append(
                        {
                            "seed_request_id": shared.request_id,
                            "formal_request_id": formal.request_id,
                            "seed_token_ids_sha256": shared_digest,
                            "formal_prefix_token_ids_sha256": _token_ids_digest(
                                formal.token_ids[:seed_tokens]
                            ),
                            "formal_token_ids_sha256": _token_ids_digest(
                                formal.token_ids
                            ),
                        }
                    )
                    formal_stream.write(
                        json.dumps(
                            {
                                "question": formal.text,
                                "answer": "",
                                "request_id": formal.request_id,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    write_metadata(formal, "formal-1")
            else:
                for _ in range(seed_request_count):
                    formal = build_prompt(
                        tokenizer,
                        input_tokens,
                        request_index,
                        seed,
                        stable_tokens=stable,
                    )
                    request_index += 1
                    seed_token_ids = list(formal.token_ids[:seed_tokens])
                    seed_text = _decode(tokenizer, seed_token_ids)
                    if _encode(tokenizer, seed_text) != seed_token_ids:
                        raise ValueError(
                            "seed prefix does not round-trip to the exact token sequence"
                        )
                    seed_request_id = f"seed-{formal.request_id}"
                    seed_record = _record_from_token_ids(
                        tokenizer, seed_token_ids, seed_request_id, seed
                    )
                    seed_ids.append(seed_record.request_id)
                    formal_ids.append(formal.request_id)
                    seed_formal_pairs.append(
                        {
                            "seed_request_id": seed_record.request_id,
                            "formal_request_id": formal.request_id,
                            "seed_token_ids_sha256": _token_ids_digest(
                                seed_record.token_ids
                            ),
                            "formal_prefix_token_ids_sha256": _token_ids_digest(
                                formal.token_ids[:seed_tokens]
                            ),
                            "formal_token_ids_sha256": _token_ids_digest(
                                formal.token_ids
                            ),
                        }
                    )
                    for stream, record in (
                        (seed_stream, seed_record),
                        (formal_stream, formal),
                    ):
                        stream.write(
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
                    write_metadata(seed_record, "seed")
                    write_metadata(formal, "formal-1")
        partition_files["seed"] = seed_path
        partition_files["formal-1"] = formal_path
        partition_ids["seed"] = tuple(seed_ids)
        partition_ids["formal-1"] = tuple(formal_ids)
        if admission_count:
            admission_ids: list[str] = []
            if not shared_prefix:
                raise ValueError("admission partition requires a shared-prefix fixture")
            with admission_path.open("x", encoding="utf-8") as admission_stream:
                for admission_index in range(admission_count):
                    suffix = _shared_suffix(
                        stable,
                        input_tokens - seed_tokens,
                        formal_count + admission_index + 1,
                        seed,
                    )
                    admission = _record_from_token_ids(
                        tokenizer,
                        [*shared.token_ids, *suffix],
                        f"admission-p{input_tokens}-s{seed}-r{admission_index:06d}",
                        seed,
                    )
                    admission_ids.append(admission.request_id)
                    admission_stream.write(
                        json.dumps(
                            {
                                "question": admission.text,
                                "answer": "",
                                "request_id": admission.request_id,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    write_metadata(admission, "admission")
            partition_files["admission"] = admission_path
            partition_ids["admission"] = tuple(admission_ids)
    checksum_paths = [*partition_files.values(), metadata_file]
    checksums = {path.name: _digest(path) for path in checksum_paths}
    manifest_file = root / "manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "input_tokens": input_tokens,
                "formal_tokens": input_tokens,
                "seed_tokens": seed_tokens,
                "expected_hit_rate": seed_tokens / input_tokens,
                "prefix_mode": "shared" if shared_prefix else "paired",
                "concurrency": concurrency,
                "seed": seed,
                "tokenizer_identity": str(getattr(tokenizer, "name_or_path", type(tokenizer).__name__)),
                "warmup_ids": partition_ids["warmup"],
                "seed_ids": partition_ids["seed"],
                "admission_ids": partition_ids.get("admission", ()),
                "formal_ids": [partition_ids[f"formal-{index}"] for index in range(1, repetitions + 1)],
                "seed_formal_pairs": seed_formal_pairs,
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
        seed_ids=partition_ids["seed"],
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
    if phase not in {"warmup", "seed", "admission", "formal-1"}:
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
    elif phase == "seed":
        expected_ids = manifest.get("seed_ids")
    elif phase == "admission":
        expected_ids = manifest.get("admission_ids")
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
    manifest_seed_tokens = manifest.get("seed_tokens")
    if not isinstance(manifest_seed_tokens, int):
        raise ValueError("fixture manifest lacks integer seed_tokens")
    attempt_input_tokens = manifest_seed_tokens if phase == "seed" else point.input_tokens
    return {
        "schema_version": 1,
        "phase": phase,
        "point_id": point_id(point),
        "topology": point.topology,
        "variant": point.variant,
        "input_tokens": attempt_input_tokens,
        "formal_input_tokens": point.input_tokens,
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
    generate.add_argument("--input-tokens", type=int, action="append")
    generate.add_argument("--seed-tokens", type=int)
    generate.add_argument("--warmup-count", type=int)
    generate.add_argument("--formal-count", type=int)
    generate.add_argument("--seed-request-count", type=int)
    generate.add_argument("--admission-count", type=int, default=0)
    generate.add_argument("--shared-prefix", action="store_true")
    config = subparsers.add_parser("config")
    config.add_argument("--topology", choices=("dp1", "dp2"), required=True)
    config.add_argument("--input-tokens", type=int, required=True)
    config.add_argument("--output-tokens", type=int, required=True)
    config.add_argument("--variant", choices=("bulk", "layerwise", "reuse3"), required=True)
    config.add_argument("--concurrency", type=int, required=True)
    config.add_argument("--dataset", type=Path, required=True)
    config.add_argument("--request-count", type=int, required=True)
    config.add_argument(
        "--phase",
        choices=("warmup", "seed", "admission", "formal-1"),
        required=True,
    )
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
    input_lengths = tuple(args.input_tokens) if args.input_tokens else INPUT_TOKENS
    for input_tokens in input_lengths:
        write_fixture(
            tokenizer,
            input_tokens,
            args.concurrency,
            args.seed,
            args.output,
            stable_tokens=stable_tokens,
            seed_tokens=args.seed_tokens if args.seed_tokens is not None else SEED_TOKENS,
            warmup_count=args.warmup_count,
            formal_count=args.formal_count,
            seed_request_count=args.seed_request_count,
            admission_count=args.admission_count,
            shared_prefix=args.shared_prefix,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
