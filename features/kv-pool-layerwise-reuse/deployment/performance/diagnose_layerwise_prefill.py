from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path


ITERATION_RE = re.compile(
    r"Iteration\((?P<iteration>\d+)\): "
    r"(?P<context_requests>\d+) context requests, "
    r"(?P<context_tokens>\d+) context tokens, "
    r"(?P<generation_requests>\d+) generation requests, "
    r"(?P<generation_tokens>\d+) generation tokens, "
    r"iteration elapsed time: (?P<elapsed_ms>[\d.]+) ms"
)


@dataclass(frozen=True)
class IterationStats:
    count: int
    first_iteration: int
    last_iteration: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    total_ms: float


@dataclass(frozen=True)
class SawtoothStats:
    intercept_ms: float
    slope_ms_per_prior_key: float
    r_squared: float


def _formal_prefill_samples(
    path: Path,
    *,
    expected_iterations: int,
    context_tokens: int,
) -> list[tuple[int, float]]:
    samples: list[tuple[int, float]] = []
    for match in ITERATION_RE.finditer(path.read_text(errors="replace")):
        fields = {key: int(match.group(key)) for key in (
            "iteration",
            "context_requests",
            "context_tokens",
            "generation_requests",
            "generation_tokens",
        )}
        if (
            fields["context_requests"] == 1
            and fields["context_tokens"] == context_tokens
            and fields["generation_requests"] == 0
            and fields["generation_tokens"] == 0
        ):
            samples.append((fields["iteration"], float(match.group("elapsed_ms"))))

    if len(samples) < expected_iterations:
        raise ValueError(
            f"{path}: found {len(samples)} matching iterations, "
            f"expected at least {expected_iterations}"
        )

    formal = samples[-expected_iterations:]
    iteration_ids = [iteration_id for iteration_id, _ in formal]
    expected_ids = list(range(iteration_ids[0], iteration_ids[0] + expected_iterations))
    if iteration_ids != expected_ids:
        raise ValueError(f"{path}: formal iteration IDs are not contiguous")
    return formal


def parse_formal_prefill(
    path: Path,
    *,
    expected_iterations: int,
    context_tokens: int,
) -> IterationStats:
    formal = _formal_prefill_samples(
        path,
        expected_iterations=expected_iterations,
        context_tokens=context_tokens,
    )
    iteration_ids = [iteration_id for iteration_id, _ in formal]

    elapsed = [elapsed_ms for _, elapsed_ms in formal]
    sorted_elapsed = sorted(elapsed)
    p95_index = max(0, round(0.95 * len(sorted_elapsed) + 0.5) - 1)
    return IterationStats(
        count=len(elapsed),
        first_iteration=iteration_ids[0],
        last_iteration=iteration_ids[-1],
        mean_ms=statistics.fmean(elapsed),
        median_ms=statistics.median(elapsed),
        p95_ms=sorted_elapsed[p95_index],
        total_ms=sum(elapsed),
    )


def parse_sawtooth(
    path: Path,
    *,
    expected_iterations: int,
    context_tokens: int,
    baseline_path: Path | None = None,
    chunks_per_request: int = 16,
    keys_per_chunk: int = 8,
) -> SawtoothStats:
    formal = _formal_prefill_samples(
        path,
        expected_iterations=expected_iterations,
        context_tokens=context_tokens,
    )
    x = [(index % chunks_per_request) * keys_per_chunk for index in range(len(formal))]
    y = [elapsed_ms for _, elapsed_ms in formal]
    if baseline_path is not None:
        baseline = _formal_prefill_samples(
            baseline_path,
            expected_iterations=expected_iterations,
            context_tokens=context_tokens,
        )
        y = [
            elapsed_ms - baseline_elapsed_ms
            for (_, elapsed_ms), (_, baseline_elapsed_ms) in zip(formal, baseline)
        ]
    grouped = {
        x_value: statistics.fmean(
            y_value
            for grouped_x, y_value in zip(x, y)
            if grouped_x == x_value
        )
        for x_value in sorted(set(x))
    }
    x = list(grouped)
    y = list(grouped.values())
    x_mean = statistics.fmean(x)
    y_mean = statistics.fmean(y)
    denominator = sum((value - x_mean) ** 2 for value in x)
    slope = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in zip(x, y)
    ) / denominator
    intercept = y_mean - slope * x_mean
    residual = sum(
        (y_value - (intercept + slope * x_value)) ** 2
        for x_value, y_value in zip(x, y)
    )
    total = sum((value - y_mean) ** 2 for value in y)
    return SawtoothStats(
        intercept_ms=intercept,
        slope_ms_per_prior_key=slope,
        r_squared=1.0 - residual / total if total else 1.0,
    )


def _metrics(path: Path) -> dict[str, float]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            values[fields[0]] = float(fields[1])
        except ValueError:
            continue
    return values


def _data_root(root: Path) -> Path:
    if (root / "points").is_dir() and (root / "variants").is_dir():
        return root
    if (root / "raw/points").is_dir() and (root / "raw/variants").is_dir():
        return root / "raw"
    raise ValueError(f"{root}: performance data root is unavailable")


def _metric_delta(root: Path) -> dict[str, int]:
    point = _data_root(root) / "points/dp1-16384-layerwise-o1-c8"
    warmup = _metrics(point / "warmup/attempt-1/raw/mooncake.metrics")
    formal = _metrics(point / "formal-1/attempt-1/raw/mooncake.metrics")
    names = {
        "requests": "master_batch_get_replica_list_requests_total",
        "items": "master_batch_get_replica_list_items_total",
        "failures": "master_batch_get_replica_list_failures_total",
        "failed_items": "master_batch_get_replica_list_failed_items_total",
    }
    return {
        label: int(formal.get(metric, 0) - warmup.get(metric, 0))
        for label, metric in names.items()
    }


def _summary(root: Path) -> dict[str, object]:
    path = (
        _data_root(root)
        / "points/dp1-16384-layerwise-o1-c8/formal-1/attempt-1/raw/summary.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay Prefill iteration logs and detect the layerwise regression."
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-iterations", type=int, default=1024)
    parser.add_argument("--context-tokens", type=int, default=1024)
    parser.add_argument("--regression-ratio", type=float, default=1.25)
    parser.add_argument(
        "--candidate",
        type=Path,
        help="single-point candidate root produced by run_layerwise_self_load_ab",
    )
    args = parser.parse_args()

    stats = {}
    logs = {}
    evidence_data = _data_root(args.evidence)
    for variant in ("bulk", "layerwise"):
        log = evidence_data / "variants" / variant / "raw" / "vllm-prefill.log"
        logs[variant] = log
        stats[variant] = parse_formal_prefill(
            log,
            expected_iterations=args.expected_iterations,
            context_tokens=args.context_tokens,
        )

    ratio = stats["layerwise"].mean_ms / stats["bulk"].mean_ms
    if args.candidate is not None:
        control_log = logs["layerwise"]
        bulk_log = logs["bulk"]
        candidate_log = (
            _data_root(args.candidate) / "variants/layerwise/raw/vllm-prefill.log"
        )
        candidate_stats = parse_formal_prefill(
            candidate_log,
            expected_iterations=args.expected_iterations,
            context_tokens=args.context_tokens,
        )
        original_gap = stats["layerwise"].mean_ms - stats["bulk"].mean_ms
        recovered = stats["layerwise"].mean_ms - candidate_stats.mean_ms
        explained_fraction = recovered / original_gap if original_gap > 0 else 0.0
        control_get = _metric_delta(args.evidence)
        candidate_get = _metric_delta(args.candidate)
        candidate_summary = _summary(args.candidate)
        exact_decode_only_gets = (
            candidate_get["requests"] == 128
            and candidate_get["items"] == 16384
            and candidate_get["failures"] == 0
            and candidate_get["failed_items"] == 0
        )
        valid_requests = (
            candidate_summary.get("valid") is True
            and candidate_summary.get("success_count") == 64
            and candidate_summary.get("request_count") == 64
        )
        latency_improved = recovered > 0
        primary = exact_decode_only_gets and valid_requests and explained_fraction >= 0.5
        partial = exact_decode_only_gets and valid_requests and latency_improved
        verdict = (
            "PRIMARY_CAUSE_CONFIRMED"
            if primary
            else "PARTIAL_CAUSE_CONFIRMED"
            if partial
            else "NOT_CONFIRMED"
        )
        print(
            json.dumps(
                {
                    "bulk": asdict(stats["bulk"]),
                    "control_layerwise": asdict(stats["layerwise"]),
                    "candidate_layerwise": asdict(candidate_stats),
                    "control_sawtooth": asdict(
                        parse_sawtooth(
                            control_log,
                            expected_iterations=args.expected_iterations,
                            context_tokens=args.context_tokens,
                            baseline_path=bulk_log,
                        )
                    ),
                    "candidate_sawtooth": asdict(
                        parse_sawtooth(
                            candidate_log,
                            expected_iterations=args.expected_iterations,
                            context_tokens=args.context_tokens,
                            baseline_path=bulk_log,
                        )
                    ),
                    "candidate_over_control": candidate_stats.mean_ms
                    / stats["layerwise"].mean_ms,
                    "candidate_over_bulk": candidate_stats.mean_ms
                    / stats["bulk"].mean_ms,
                    "recovered_ms_per_iteration": recovered,
                    "original_gap_explained_fraction": explained_fraction,
                    "control_batch_get_replica_list_delta": control_get,
                    "candidate_batch_get_replica_list_delta": candidate_get,
                    "candidate_aisbench": candidate_summary,
                    "verdict": verdict,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if primary else 1

    regression = ratio >= args.regression_ratio
    print(json.dumps(
        {
            "bulk": asdict(stats["bulk"]),
            "layerwise": asdict(stats["layerwise"]),
            "layerwise_over_bulk": ratio,
            "regression_ratio": args.regression_ratio,
            "verdict": "REGRESSION" if regression else "NO_REGRESSION",
        },
        indent=2,
        sort_keys=True,
    ))
    return 1 if regression else 0


if __name__ == "__main__":
    raise SystemExit(main())
