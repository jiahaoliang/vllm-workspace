from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from performance.contract import WorkloadPoint, build_matrix, point_id

REQUIRED_ROOT_FILES = (
    "handoff.json",
    "source-identity.json",
    "client-identity.json",
    "run-contract.json",
    "restoration.json",
)
POINT_PATTERN = re.compile(
    r"^(?P<topology>dp[12])-(?P<input>\d+)-(?P<variant>[a-z0-9]+)"
    r"-o(?P<output>\d+)-c(?P<concurrency>\d+)$"
)
METRICS = (
    "Input Token Throughput",
    "Request Throughput",
    "TTFT Median",
    "TTFT Max",
    "TTFT P95",
    "E2EL Median",
    "E2EL Max",
    "E2EL P95",
    "Achieved Concurrency",
    "Output Token Throughput",
    "TPOT P95",
    "ITL P95",
)


@dataclass(frozen=True)
class ResultRow:
    point_id: str
    topology: str
    input_tokens: int
    output_tokens: int
    variant: str
    concurrency: int
    repetition: int
    metrics: dict[str, float]


@dataclass(frozen=True)
class RequestResultRow:
    point_id: str
    repetition: int
    request: int
    data_id: str
    uuid: str
    success: bool
    input_tokens: int
    output_tokens: int


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return value


def _metric_number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.match(r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", str(value))
    if match is None:
        raise ValueError(f"metric value is not numeric: {value!r}")
    return float(match.group(1))


def _stage_value(common: dict[str, object], name: str, stage: str = "total") -> float:
    stages = common.get(name)
    if not isinstance(stages, dict) or stage not in stages:
        raise ValueError(f"AISBench common metric lacks {stage} stage: {name}")
    return _metric_number(stages[stage])


def summarize_aisbench_attempt(
    raw: Path,
    point: WorkloadPoint,
    request_count: int,
    image_digest: str,
) -> dict[str, object]:
    common_paths = [path for path in raw.rglob(f"{point.variant}.json") if "performances" in path.parts]
    csv_paths = [path for path in raw.rglob(f"{point.variant}.csv") if "performances" in path.parts]
    detail_paths = list(raw.rglob(f"{point.variant}_details.jsonl"))
    errors: list[str] = []
    if len(common_paths) != 1:
        errors.append(f"expected one AISBench common JSON, got {len(common_paths)}")
    if len(csv_paths) != 1:
        errors.append(f"expected one AISBench request CSV, got {len(csv_paths)}")
    if len(detail_paths) != 1:
        errors.append(f"expected one AISBench details JSONL, got {len(detail_paths)}")
    if errors:
        return {
            "valid": False,
            "image_digest": image_digest,
            "errors": errors,
            "metrics": {},
        }
    common = _load_json(common_paths[0])
    metrics: dict[str, float] = {}
    for source, target in (
        ("Input Token Throughput", "Input Token Throughput"),
        ("Request Throughput", "Request Throughput"),
        ("Concurrency", "Achieved Concurrency"),
        ("Output Token Throughput", "Output Token Throughput"),
    ):
        try:
            metrics[target] = _stage_value(common, source)
        except ValueError as error:
            errors.append(str(error))
    try:
        duration_ms = _stage_value(common, "Benchmark Duration")
        total_requests = _stage_value(common, "Total Requests")
        failed_requests = _stage_value(common, "Failed Requests")
        success_requests = _stage_value(common, "Success Requests")
    except ValueError as error:
        errors.append(str(error))
        duration_ms = 0.0
        total_requests = -1.0
        failed_requests = -1.0
        success_requests = -1.0
    request_metrics: dict[str, dict[str, str]] = {}
    with csv_paths[0].open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("Stage") == "total":
                request_metrics[row.get("Performance Parameters", "")] = row
    for source in ("TTFT", "E2EL", "TPOT", "ITL"):
        row = request_metrics.get(source)
        if row is None:
            continue
        for statistic in ("Median", "Max", "P95"):
            value = row.get(statistic)
            if value not in (None, ""):
                metrics[f"{source} {statistic}"] = _metric_number(value)
    e2el = request_metrics.get("E2EL", {})
    max_e2el_ms = _metric_number(e2el.get("Max", 0))
    detail_count = 0
    success_count = 0
    with detail_paths[0].open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                detail = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"malformed AISBench detail line {line_number}")
                continue
            detail_count += 1
            if detail.get("success") is True:
                success_count += 1
            if detail.get("input_tokens") != point.input_tokens:
                errors.append(f"input token mismatch in detail line {line_number}")
            if detail.get("output_tokens") != point.output_tokens:
                errors.append(f"output token mismatch in detail line {line_number}")
    if detail_count != request_count:
        errors.append(f"AISBench detail count mismatch: expected {request_count}, got {detail_count}")
    if success_count != request_count:
        errors.append(f"AISBench success count mismatch: expected {request_count}, got {success_count}")
    common_counts = (total_requests, failed_requests, success_requests)
    if (
        any(value != int(value) for value in common_counts)
        or failed_requests != 0
        or total_requests != request_count
        or success_requests != request_count
    ):
        errors.append("AISBench common request counts do not match the attempt contract")
    return {
        "valid": not errors,
        "image_digest": image_digest,
        "errors": errors,
        "metrics": metrics,
        "request_count": request_count,
        "measurement_stage": "total",
        "single_wave": True,
        "stage_request_count": int(total_requests),
        "detail_count": detail_count,
        "success_count": success_count,
        "benchmark_duration_ms": duration_ms,
        "max_e2el_ms": max_e2el_ms,
        "raw_common": str(common_paths[0].relative_to(raw)),
        "raw_request_metrics": str(csv_paths[0].relative_to(raw)),
        "raw_details": str(detail_paths[0].relative_to(raw)),
    }


def validate_checksums(root: Path) -> list[str]:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        return ["missing root evidence: SHA256SUMS"]
    errors: list[str] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name:
            errors.append(f"malformed SHA256SUMS line {line_number}")
            continue
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(f"SHA256SUMS path escapes evidence root: {name}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        if actual != digest:
            errors.append(f"SHA256SUMS replay failed: {name}")
    return errors


def validate_evidence(root: Path) -> list[str]:
    errors = validate_checksums(root)
    for name in REQUIRED_ROOT_FILES:
        if not (root / name).is_file():
            errors.append(f"missing root evidence: {name}")
    contract_path = root / "run-contract.json"
    if not contract_path.is_file():
        return errors
    try:
        contract = _load_json(contract_path)
    except ValueError as error:
        errors.append(str(error))
        return errors
    repetitions = int(contract.get("formal_repetitions", 0))
    expected_points = contract.get("expected_points", [])
    if not isinstance(expected_points, list):
        errors.append("run contract expected_points is not a list")
        return errors
    rapid_points = [point_id(point) for point in build_matrix("dp1")]
    if expected_points != rapid_points:
        errors.append("run contract does not match the exact rapid point matrix")
    if repetitions != 1:
        errors.append("run contract formal_repetitions must be 1")
    if contract.get("request_count") != 8:
        errors.append("run contract request_count must be 8")
    if contract.get("calculator") != "total":
        errors.append("run contract calculator must be total")
    if contract.get("single_wave") is not True:
        errors.append("run contract single_wave must be true")
    actual_points = sorted(path.name for path in (root / "points").glob("*") if path.is_dir())
    for point in sorted(set(actual_points) - set(rapid_points)):
        errors.append(f"unexpected point directory: {point}")
    fixture_root = root / "fixtures" / "tokens-16384-c64"
    for filename in ("manifest.json", "warmup.jsonl", "formal-1.jsonl"):
        if not (fixture_root / filename).is_file():
            errors.append(f"missing shared fixture: {filename}")
    for variant in ("bulk", "layerwise", "reuse3"):
        for filename in ("vllm-prefill.log", "vllm-decode.log"):
            if not (root / "variants" / variant / "raw" / filename).is_file():
                errors.append(f"missing variant evidence: {variant}/{filename}")
    for point in expected_points:
        point_root = root / "points" / str(point)
        identity_path = point_root / "identity.json"
        if not identity_path.is_file():
            errors.append(f"missing point identity: {point}")
        else:
            try:
                identity = _load_json(identity_path)
                if identity.get("image_digest") != contract.get("image_digest"):
                    errors.append(f"image digest drift in point identity: {point}")
            except ValueError as error:
                errors.append(str(error))
        if not (point_root / "warmup").is_dir():
            errors.append(f"missing warmup: {point}")
        formal_phases = sorted(path.name for path in point_root.glob("formal-*") if path.is_dir())
        for phase_name in formal_phases:
            if phase_name != "formal-1":
                errors.append(f"unexpected formal phase {phase_name}: {point}")
        for phase_name in ("warmup", "formal-1"):
            attempts = list((point_root / phase_name).glob("attempt-*"))
            if len(attempts) != 1:
                errors.append(f"missing or ambiguous {phase_name} attempt: {point}")
                continue
            reference_path = attempts[0] / "raw" / "fixture-reference.json"
            if not reference_path.is_file():
                errors.append(f"missing fixture reference for {phase_name}: {point}")
                continue
            try:
                reference = _load_json(reference_path)
                relative = reference.get("path")
                expected_relative = f"fixtures/tokens-16384-c64/{phase_name}.jsonl"
                if relative != expected_relative:
                    errors.append(f"fixture reference path drift for {phase_name}: {point}")
                shared = root / expected_relative
                digest = hashlib.sha256(shared.read_bytes()).hexdigest() if shared.is_file() else ""
                if reference.get("sha256") != digest:
                    errors.append(f"fixture reference digest drift for {phase_name}: {point}")
            except ValueError as error:
                errors.append(str(error))
        for repetition in range(1, repetitions + 1):
            phase = point_root / f"formal-{repetition}"
            summaries = list(phase.glob("attempt-*/raw/summary.json"))
            if len(summaries) != 1:
                errors.append(f"missing or ambiguous formal repetition {repetition}: {point}")
                continue
            try:
                summary = _load_json(summaries[0])
                if summary.get("image_digest") != contract.get("image_digest"):
                    errors.append(f"image digest drift in formal repetition {repetition}: {point}")
                if summary.get("valid") is not True:
                    errors.append(f"invalid formal repetition {repetition}: {point}")
                if (
                    summary.get("request_count") != 8
                    or summary.get("stage_request_count") != 8
                    or summary.get("measurement_stage") != "total"
                    or summary.get("single_wave") is not True
                ):
                    errors.append(f"formal summary contract drift: {point}")
            except ValueError as error:
                errors.append(str(error))
    return errors


def load_results(root: Path) -> tuple[ResultRow, ...]:
    errors = validate_evidence(root)
    if errors:
        raise ValueError("invalid evidence: " + "; ".join(errors))
    contract = _load_json(root / "run-contract.json")
    rows: list[ResultRow] = []
    for selected_point_id in contract["expected_points"]:  # type: ignore[index]
        match = POINT_PATTERN.fullmatch(str(selected_point_id))
        if match is None:
            raise ValueError(f"malformed point ID: {selected_point_id}")
        repetitions = int(contract["formal_repetitions"])
        for repetition in range(1, repetitions + 1):
            summaries = list(
                (root / "points" / str(selected_point_id) / f"formal-{repetition}").glob("attempt-*/raw/summary.json")
            )
            summary = _load_json(summaries[0])
            raw_metrics = summary.get("metrics", {})
            if not isinstance(raw_metrics, dict):
                raise ValueError(f"metrics are not an object: {selected_point_id} repetition {repetition}")
            metrics = {
                name: float(value)
                for name, value in raw_metrics.items()
                if name in METRICS and isinstance(value, (int, float))
            }
            rows.append(
                ResultRow(
                    point_id=str(selected_point_id),
                    topology=match.group("topology"),
                    input_tokens=int(match.group("input")),
                    output_tokens=int(match.group("output")),
                    variant=match.group("variant"),
                    concurrency=int(match.group("concurrency")),
                    repetition=repetition,
                    metrics=metrics,
                )
            )
    return tuple(rows)


def load_request_results(root: Path, results: tuple[ResultRow, ...]) -> tuple[RequestResultRow, ...]:
    rows: list[RequestResultRow] = []
    for result in results:
        summaries = list(
            (root / "points" / result.point_id / f"formal-{result.repetition}").glob("attempt-*/raw/summary.json")
        )
        summary = _load_json(summaries[0])
        relative_details = summary.get("raw_details")
        if not isinstance(relative_details, str) or not relative_details:
            raise ValueError(f"formal summary lacks raw_details: {result.point_id}")
        details_path = (summaries[0].parent / relative_details).resolve()
        if not details_path.is_relative_to(root.resolve()) or not details_path.is_file():
            raise ValueError(f"invalid raw_details artifact: {result.point_id}")
        point_rows: list[RequestResultRow] = []
        with details_path.open(encoding="utf-8") as stream:
            for request, line in enumerate(stream, 1):
                try:
                    detail = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"malformed raw_details row {request}: {result.point_id}") from error
                if not isinstance(detail, dict):
                    raise ValueError(f"raw_details row is not an object: {result.point_id}")
                point_rows.append(
                    RequestResultRow(
                        point_id=result.point_id,
                        repetition=result.repetition,
                        request=request,
                        data_id=str(detail.get("data_id", "")),
                        uuid=str(detail.get("uuid", "")),
                        success=detail.get("success") is True,
                        input_tokens=int(detail.get("input_tokens", 0)),
                        output_tokens=int(detail.get("output_tokens", 0)),
                    )
                )
        if len(point_rows) != 8:
            raise ValueError(f"raw_details row count must be 8: {result.point_id}")
        rows.extend(point_rows)
    return tuple(rows)


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def render_report(root: Path) -> str:
    rows = load_results(root)
    request_rows = load_request_results(root, rows)
    lines = [
        "# Mooncake Layerwise Performance Raw Characterization",
        "",
        "Single-wave raw characterization; not a steady-state or statistically significant result.",
        "",
        "## Raw Results",
        "",
        "| Topology | Input | Output | Variant | Concurrency | Repetition | " + " | ".join(METRICS) + " |",
        "| --- | ---: | ---: | --- | ---: | ---: | " + " | ".join("---:" for _ in METRICS) + " |",
    ]
    for row in rows:
        values = " | ".join(_number(row.metrics.get(metric)) for metric in METRICS)
        lines.append(
            f"| {row.topology} | {row.input_tokens} | {row.output_tokens} | "
            f"{row.variant.upper()} | {row.concurrency} | {row.repetition} | {values} |"
        )
    lines.extend(
        (
            "",
            "## Per-Request Results",
            "",
            (
                "These rows retain the stable request identity and correctness fields "
                "from each formal AISBench details artifact."
            ),
            "Complete prompt and prediction payloads remain in the immutable raw evidence.",
            "",
            "| Point | Repetition | Request | Data ID | UUID | Success | Input Tokens | Output Tokens |",
            "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |",
        )
    )
    for row in request_rows:
        lines.append(
            f"| {row.point_id} | {row.repetition} | {row.request} | {row.data_id} | {row.uuid} | "
            f"{str(row.success).lower()} | {row.input_tokens} | {row.output_tokens} |"
        )
    comparisons = (
        ("LAYERWISE / BULK", "layerwise", "bulk"),
        ("REUSE3 / LAYERWISE", "reuse3", "layerwise"),
        ("REUSE3 / BULK", "reuse3", "bulk"),
    )
    indexed = {
        (
            row.topology,
            row.input_tokens,
            row.output_tokens,
            row.concurrency,
            row.repetition,
            row.variant,
        ): row
        for row in rows
    }
    lines.extend(
        (
            "",
            "## Direct Ratios",
            "",
            "| Comparison | Topology | Input | Output | Concurrency | Repetition | Metric | Ratio |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |",
        )
    )
    bases = sorted({key[:-1] for key in indexed})
    for label, numerator_name, denominator_name in comparisons:
        for base in bases:
            numerator = indexed.get((*base, numerator_name))
            denominator = indexed.get((*base, denominator_name))
            if numerator is None or denominator is None:
                continue
            for metric in METRICS:
                numerator_value = numerator.metrics.get(metric)
                denominator_value = denominator.metrics.get(metric)
                if numerator_value is None or not denominator_value:
                    continue
                topology, input_tokens, output_tokens, concurrency, repetition = base
                lines.append(
                    f"| {label} | {topology} | {input_tokens} | {output_tokens} | "
                    f"{concurrency} | {repetition} | {metric} | "
                    f"{numerator_value / denominator_value:.6g} |"
                )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--root", type=Path, required=True)
    check_parser.add_argument("--scope", choices=("dp1", "dp2", "all"), default="all")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--root", type=Path, required=True)
    render_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "check":
        errors = validate_evidence(args.root)
        print(json.dumps({"scope": args.scope, "valid": not errors, "errors": errors}))
        return 0 if not errors else 1
    text = render_report(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
