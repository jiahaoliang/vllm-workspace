from __future__ import annotations

import argparse
import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


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
    "TTFT P95",
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


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return value


def _validate_checksums(root: Path) -> list[str]:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        return ["missing root evidence: SHA256SUMS"]
    errors: list[str] = []
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), 1
    ):
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
    errors = _validate_checksums(root)
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
        for repetition in range(1, repetitions + 1):
            phase = point_root / f"formal-{repetition}"
            summaries = list(phase.glob("attempt-*/raw/summary.json"))
            if len(summaries) != 1:
                errors.append(f"missing or ambiguous formal repetition {repetition}: {point}")
                continue
            try:
                summary = _load_json(summaries[0])
                if summary.get("image_digest") != contract.get("image_digest"):
                    errors.append(
                        f"image digest drift in formal repetition {repetition}: {point}"
                    )
                if summary.get("valid") is not True:
                    errors.append(f"invalid formal repetition {repetition}: {point}")
            except ValueError as error:
                errors.append(str(error))
    return errors


def load_results(root: Path) -> tuple[ResultRow, ...]:
    errors = validate_evidence(root)
    if errors:
        raise ValueError("invalid evidence: " + "; ".join(errors))
    contract = _load_json(root / "run-contract.json")
    rows: list[ResultRow] = []
    for point_id in contract["expected_points"]:  # type: ignore[index]
        match = POINT_PATTERN.fullmatch(str(point_id))
        if match is None:
            raise ValueError(f"malformed point ID: {point_id}")
        repetitions = int(contract["formal_repetitions"])
        for repetition in range(1, repetitions + 1):
            summaries = list(
                (root / "points" / str(point_id) / f"formal-{repetition}").glob(
                    "attempt-*/raw/summary.json"
                )
            )
            summary = _load_json(summaries[0])
            raw_metrics = summary.get("metrics", {})
            if not isinstance(raw_metrics, dict):
                raise ValueError(f"metrics are not an object: {point_id} repetition {repetition}")
            metrics = {
                name: float(value)
                for name, value in raw_metrics.items()
                if name in METRICS and isinstance(value, (int, float))
            }
            rows.append(
                ResultRow(
                    point_id=str(point_id),
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


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def render_report(root: Path) -> str:
    rows = load_results(root)
    lines = [
        "# Mooncake Layerwise Performance Raw Characterization",
        "",
        "This report retains every formal repetition and presents direct raw comparisons only.",
        "",
        "## Raw Results",
        "",
        "| Topology | Input | Output | Variant | Concurrency | Repetition | "
        + " | ".join(METRICS)
        + " |",
        "| --- | ---: | ---: | --- | ---: | ---: | "
        + " | ".join("---:" for _ in METRICS)
        + " |",
    ]
    for row in rows:
        values = " | ".join(_number(row.metrics.get(metric)) for metric in METRICS)
        lines.append(
            f"| {row.topology} | {row.input_tokens} | {row.output_tokens} | "
            f"{row.variant.upper()} | {row.concurrency} | {row.repetition} | {values} |"
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
