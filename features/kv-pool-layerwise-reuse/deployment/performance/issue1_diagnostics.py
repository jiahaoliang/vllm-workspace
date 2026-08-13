from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

_CAPACITY_PATTERN = re.compile(r"GPU KV cache size:\s+([\d,]+) tokens")
_ITERATION_PATTERN = re.compile(
    r"Iteration\((?P<iteration>\d+)\):\s+"
    r"(?P<context_requests>\d+) context requests,\s+"
    r"(?P<context_tokens>\d+) context tokens,\s+"
    r"(?P<generation_requests>\d+) generation requests,\s+"
    r"(?P<generation_tokens>\d+) generation tokens, iteration elapsed time:\s+"
    r"(?P<elapsed_ms>[\d.]+) ms"
)
_PROMETHEUS_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?P<labels>\{[^}]*\})?\s+(?P<value>[-+\deE.]+)(?:\s+\d+)?$"
)
_TE_LINE_PATTERN = re.compile(r"\[Metrics\] Transfer Engine Stats .*$")
_TE_THROUGHPUT_PATTERN = re.compile(r"Throughput:\s+([\d.]+) MB/s")
_TE_COUNT_PATTERN = re.compile(r"Latency Distribution \(count=(\d+)\)")
_RANGE_DEBUG_MARKER = "[KVPOOL_RANGE_DEBUG]"
MIN_TIMING_EXPLAINED_FRACTION = 0.5


def parse_kv_capacity_tokens(text: str) -> int:
    values = [int(match.group(1).replace(",", "")) for match in _CAPACITY_PATTERN.finditer(text)]
    if not values:
        raise ValueError("Prefill log lacks GPU KV cache size")
    if len(set(values)) != 1:
        raise ValueError(f"Prefill log contains conflicting KV capacities: {values}")
    return values[0]


def parse_iteration_details(text: str) -> tuple[dict[str, int | float], ...]:
    return tuple(
        {
            "iteration": int(match.group("iteration")),
            "context_requests": int(match.group("context_requests")),
            "context_tokens": int(match.group("context_tokens")),
            "generation_requests": int(match.group("generation_requests")),
            "generation_tokens": int(match.group("generation_tokens")),
            "elapsed_ms": float(match.group("elapsed_ms")),
        }
        for match in _ITERATION_PATTERN.finditer(text)
    )


def _labels(text: str | None) -> dict[str, str]:
    if text is None:
        return {}
    return {
        key: value
        for key, value in re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', text)
    }


def parse_prometheus_timeseries(text: str) -> dict[str, object]:
    samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    timestamp = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TIMESTAMP "):
            timestamp = line.removeprefix("TIMESTAMP ")
            continue
        match = _PROMETHEUS_PATTERN.fullmatch(line)
        if match is None:
            continue
        name = match.group("name")
        if name not in {
            "vllm:num_requests_running",
            "vllm:num_requests_waiting",
            "vllm:num_requests_waiting_by_reason",
            "vllm:kv_cache_usage_perc",
            "vllm:num_preemptions",
            "vllm:num_preemptions_total",
            "vllm:request_queue_time_seconds_sum",
            "vllm:request_queue_time_seconds_count",
            "vllm:request_inference_time_seconds_sum",
            "vllm:request_inference_time_seconds_count",
            "vllm:request_prefill_time_seconds_sum",
            "vllm:request_prefill_time_seconds_count",
        }:
            continue
        samples[name].append(
            {
                "timestamp": timestamp,
                "labels": _labels(match.group("labels")),
                "value": float(match.group("value")),
            }
        )

    def maximum(name: str, reason: str | None = None) -> float:
        values = [
            float(sample["value"])
            for sample in samples.get(name, [])
            if reason is None
            or isinstance(sample["labels"], dict)
            and sample["labels"].get("reason") == reason
        ]
        return max(values, default=0.0)

    def values(name: str, reason: str | None = None) -> list[float]:
        return [
            float(sample["value"])
            for sample in samples.get(name, [])
            if reason is None
            or isinstance(sample["labels"], dict)
            and sample["labels"].get("reason") == reason
        ]

    running_values = values("vllm:num_requests_running")
    active_running_values = [value for value in running_values if value > 0]
    capacity_waiting_values = values(
        "vllm:num_requests_waiting_by_reason", "capacity"
    )
    positive_capacity_waiting_values = [
        value for value in capacity_waiting_values if value > 0
    ]
    preemption_values = values("vllm:num_preemptions")
    if not preemption_values:
        preemption_values = values("vllm:num_preemptions_total")

    def delta(name: str) -> float:
        counter_values = values(name)
        return (
            max(counter_values) - min(counter_values)
            if counter_values
            else 0.0
        )

    return {
        "schema_version": 1,
        "max_running": maximum("vllm:num_requests_running"),
        "mean_active_running": (
            sum(active_running_values) / len(active_running_values)
            if active_running_values
            else 0.0
        ),
        "active_running_samples": len(active_running_values),
        "max_waiting": maximum("vllm:num_requests_waiting"),
        "max_waiting_capacity": maximum(
            "vllm:num_requests_waiting_by_reason", "capacity"
        ),
        "capacity_waiting_sample_sum": sum(capacity_waiting_values),
        "capacity_waiting_positive_samples": len(
            positive_capacity_waiting_values
        ),
        "mean_positive_capacity_waiting": (
            sum(positive_capacity_waiting_values)
            / len(positive_capacity_waiting_values)
            if positive_capacity_waiting_values
            else 0.0
        ),
        "max_waiting_deferred": maximum(
            "vllm:num_requests_waiting_by_reason", "deferred"
        ),
        "max_kv_cache_usage_perc": maximum("vllm:kv_cache_usage_perc"),
        "max_preemptions": maximum("vllm:num_preemptions"),
        "preemption_delta": (
            max(preemption_values) - min(preemption_values)
            if preemption_values
            else 0.0
        ),
        "queue_time_sum_delta": delta("vllm:request_queue_time_seconds_sum"),
        "queue_time_count_delta": delta(
            "vllm:request_queue_time_seconds_count"
        ),
        "inference_time_sum_delta": delta(
            "vllm:request_inference_time_seconds_sum"
        ),
        "inference_time_count_delta": delta(
            "vllm:request_inference_time_seconds_count"
        ),
        "prefill_time_sum_delta": delta(
            "vllm:request_prefill_time_seconds_sum"
        ),
        "prefill_time_count_delta": delta(
            "vllm:request_prefill_time_seconds_count"
        ),
        "samples": dict(samples),
    }


def parse_kvpool_metrics(text: str) -> dict[str, dict[str, float | int]]:
    events: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "count": 0,
            "bytes": 0,
            "sum_ms": 0.0,
            "exclusive_sum_ms": 0.0,
            "max_ms": 0.0,
            "max_p50_ms": 0.0,
            "max_p95_ms": 0.0,
            "sample_count": 0,
        }
    )
    for line in text.splitlines():
        marker = line.find("KVPOOL_PERF_METRICS ")
        if marker < 0:
            continue
        payload_text = line[marker + len("KVPOOL_PERF_METRICS ") :].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        payload_events = payload.get("events")
        if not isinstance(payload_events, dict):
            continue
        for name, raw in payload_events.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                continue
            event = events[name]
            event["count"] = int(event["count"]) + int(raw.get("count", 0))
            event["bytes"] = int(event["bytes"]) + int(raw.get("bytes", 0))
            event["sum_ms"] = float(event["sum_ms"]) + float(raw.get("sum_ms", 0))
            event["exclusive_sum_ms"] = float(event["exclusive_sum_ms"]) + float(
                raw.get("exclusive_sum_ms", raw.get("sum_ms", 0))
            )
            event["max_ms"] = max(float(event["max_ms"]), float(raw.get("max_ms", 0)))
            event["max_p50_ms"] = max(
                float(event["max_p50_ms"]), float(raw.get("p50_ms", 0))
            )
            event["max_p95_ms"] = max(
                float(event["max_p95_ms"]), float(raw.get("p95_ms", 0))
            )
            event["sample_count"] = int(event["sample_count"]) + int(
                raw.get("sample_count", 0)
            )
    return dict(events)


def parse_kvpool_metric_metadata(text: str) -> dict[str, object]:
    schema_versions: set[int] = set()
    intervals = 0
    event_count = 0
    missing_exclusive_events = 0
    malformed_lines = 0
    for line in text.splitlines():
        marker = line.find("KVPOOL_PERF_METRICS ")
        if marker < 0:
            continue
        payload_text = line[marker + len("KVPOOL_PERF_METRICS ") :].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        payload_events = payload.get("events") if isinstance(payload, dict) else None
        schema_version = (
            payload.get("schema_version") if isinstance(payload, dict) else None
        )
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or not isinstance(payload_events, dict)
        ):
            malformed_lines += 1
            continue
        intervals += 1
        schema_versions.add(schema_version)
        for raw in payload_events.values():
            event_count += 1
            if not isinstance(raw, dict) or not isinstance(
                raw.get("exclusive_sum_ms"), (int, float)
            ):
                missing_exclusive_events += 1
    return {
        "intervals": intervals,
        "schema_versions": sorted(schema_versions),
        "events": event_count,
        "missing_exclusive_events": missing_exclusive_events,
        "malformed_lines": malformed_lines,
    }


def parse_te_metrics(text: str) -> dict[str, float | int]:
    throughputs: list[float] = []
    tasks = 0
    metric_lines = 0
    latency_intervals = 0
    for line in text.splitlines():
        if _TE_LINE_PATTERN.search(line) is None:
            continue
        metric_lines += 1
        throughput = _TE_THROUGHPUT_PATTERN.search(line)
        count = _TE_COUNT_PATTERN.search(line)
        if throughput is not None:
            throughputs.append(float(throughput.group(1)))
        if count is not None:
            latency_intervals += 1
            tasks += int(count.group(1))
    return {
        "intervals": metric_lines,
        "metric_lines": metric_lines,
        "throughput_intervals": len(throughputs),
        "latency_intervals": latency_intervals,
        "mean_throughput_mb_s": (
            sum(throughputs) / len(throughputs) if throughputs else 0.0
        ),
        "max_throughput_mb_s": max(throughputs, default=0.0),
        "task_count": tasks,
    }


def validate_observability(attempt: dict[str, Any]) -> dict[str, object]:
    errors: list[str] = []
    kvpool_by_role = attempt.get("kvpool_events_by_role")
    kvpool_metadata_by_role = attempt.get("kvpool_metric_metadata_by_role")
    te_by_role = attempt.get("te_metrics_by_role")
    for role in ("prefill", "decode"):
        label = role.capitalize()
        kvpool = kvpool_by_role.get(role) if isinstance(kvpool_by_role, dict) else None
        if not isinstance(kvpool, dict) or not kvpool:
            errors.append(f"{label} emitted no KVPool performance events")
        metadata = (
            kvpool_metadata_by_role.get(role)
            if isinstance(kvpool_metadata_by_role, dict)
            else None
        )
        if (
            not isinstance(metadata, dict)
            or int(metadata.get("intervals", 0)) <= 0
            or metadata.get("schema_versions") != [2]
            or int(metadata.get("events", 0)) <= 0
            or int(metadata.get("missing_exclusive_events", 0)) != 0
            or int(metadata.get("malformed_lines", 0)) != 0
        ):
            errors.append(f"{label} KVPool metric schema v2 evidence is invalid")
        te = te_by_role.get(role) if isinstance(te_by_role, dict) else None
        if not isinstance(te, dict) or int(te.get("metric_lines", 0)) <= 0:
            errors.append(f"{label} emitted no Transfer Engine metrics")
    return {"valid": not errors, "errors": errors}


def parse_range_debug_metrics(text: str) -> dict[str, object]:
    result: dict[str, object] = {
        "total_events": 0,
        "malformed_events": 0,
        "range_events": 0,
        "commit_events": 0,
        "whole_key_events": 0,
        "requested_bytes": 0,
        "key_count": 0,
        "failed_results": 0,
        "directions": {},
        "layers": {},
    }
    directions: dict[str, int] = defaultdict(int)
    layers: dict[str, int] = defaultdict(int)
    valid_counters = {"range_events", "commit_events", "whole_key_events"}
    for line in text.splitlines():
        marker = line.find(_RANGE_DEBUG_MARKER)
        if marker < 0:
            continue
        payload_text = line[marker + len(_RANGE_DEBUG_MARKER) :].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            result["malformed_events"] = int(result["malformed_events"]) + 1
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
            result["malformed_events"] = int(result["malformed_events"]) + 1
            continue
        counter = f"{payload['event']}_events"
        if counter not in valid_counters:
            result["malformed_events"] = int(result["malformed_events"]) + 1
            continue
        result["total_events"] = int(result["total_events"]) + 1
        result[counter] = int(result[counter]) + 1
        result["key_count"] = int(result["key_count"]) + int(
            payload.get("key_count", 0)
        )
        requested = payload.get("requested_bytes", [])
        if isinstance(requested, list):
            result["requested_bytes"] = int(result["requested_bytes"]) + sum(
                int(value) for value in requested
            )
        raw_results = payload.get("results", [])
        if isinstance(raw_results, list):
            result["failed_results"] = int(result["failed_results"]) + sum(
                int(value) < 0 for value in raw_results
            )
        direction = payload.get("direction")
        if isinstance(direction, str):
            directions[direction] += 1
        layer = payload.get("layer_id")
        if isinstance(layer, int):
            layers[str(layer)] += 1
    result["directions"] = dict(sorted(directions.items()))
    result["layers"] = dict(sorted(layers.items(), key=lambda item: int(item[0])))
    return result


def fingerprint_predictions(path: Path, expected_count: int) -> dict[str, object]:
    errors: list[str] = []
    fingerprints: dict[int, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        return {
            "valid": False,
            "errors": [f"cannot read AISBench details: {error}"],
            "request_count": 0,
            "data_ids": [],
            "prediction_sha256_by_data_id": {},
            "digest": "",
        }
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"malformed AISBench detail line {line_number}")
            continue
        if not isinstance(row, dict):
            errors.append(f"AISBench detail line {line_number} is not an object")
            continue
        data_id = row.get("data_id")
        prediction = row.get("prediction")
        if not isinstance(data_id, int) or isinstance(data_id, bool):
            errors.append(f"AISBench detail line {line_number} lacks integer data_id")
            continue
        if data_id in fingerprints:
            errors.append(f"duplicate AISBench data_id: {data_id}")
            continue
        if row.get("success") is not True or not isinstance(prediction, str):
            errors.append(f"AISBench detail line {line_number} lacks a successful prediction")
            continue
        fingerprints[data_id] = hashlib.sha256(prediction.encode("utf-8")).hexdigest()
    if len(fingerprints) != expected_count:
        errors.append(
            f"prediction count mismatch: expected {expected_count}, got {len(fingerprints)}"
        )
    ordered = sorted(fingerprints.items())
    digest = hashlib.sha256(
        "\n".join(f"{data_id}:{value}" for data_id, value in ordered).encode("ascii")
    ).hexdigest()
    return {
        "valid": not errors,
        "errors": errors,
        "request_count": len(fingerprints),
        "data_ids": [data_id for data_id, _ in ordered],
        "prediction_sha256_by_data_id": {
            str(data_id): value for data_id, value in ordered
        },
        "digest": digest,
    }


def validate_output_consistency(
    bulk: dict[str, Any], alternative: dict[str, Any]
) -> dict[str, object]:
    bulk_fingerprint = bulk.get("output_fingerprint")
    alternative_fingerprint = alternative.get("output_fingerprint")
    errors: list[str] = []
    if not isinstance(bulk_fingerprint, dict) or bulk_fingerprint.get("valid") is not True:
        errors.append("BULK output fingerprint is invalid")
        bulk_fingerprint = {}
    if (
        not isinstance(alternative_fingerprint, dict)
        or alternative_fingerprint.get("valid") is not True
    ):
        errors.append("alternative output fingerprint is invalid")
        alternative_fingerprint = {}
    bulk_rows = bulk_fingerprint.get("prediction_sha256_by_data_id", {})
    alternative_rows = alternative_fingerprint.get(
        "prediction_sha256_by_data_id", {}
    )
    if not isinstance(bulk_rows, dict) or not isinstance(alternative_rows, dict):
        errors.append("output fingerprint rows are malformed")
        bulk_rows = {}
        alternative_rows = {}
    all_ids = sorted(
        set(bulk_rows) | set(alternative_rows),
        key=lambda value: int(value) if str(value).isdigit() else str(value),
    )
    mismatched = [
        int(data_id) if str(data_id).isdigit() else data_id
        for data_id in all_ids
        if bulk_rows.get(data_id) != alternative_rows.get(data_id)
    ]
    if mismatched:
        errors.append(f"prediction mismatch for data IDs: {mismatched}")
    return {
        "valid": not errors,
        "errors": errors,
        "request_count": len(all_ids),
        "mismatched_data_ids": mismatched,
        "bulk_digest": bulk_fingerprint.get("digest", ""),
        "alternative_digest": alternative_fingerprint.get("digest", ""),
    }


def validate_admission(
    iteration_text: str,
    prometheus_text: str,
    *,
    expected_contexts: int,
    require_capacity_waiting: bool = False,
) -> dict[str, Any]:
    iterations = parse_iteration_details(iteration_text)
    prometheus = parse_prometheus_timeseries(prometheus_text)
    max_contexts = max(
        (int(row["context_requests"]) for row in iterations), default=0
    )
    errors: list[str] = []
    if max_contexts < expected_contexts:
        errors.append(
            f"server admitted at most {max_contexts} context requests; "
            f"expected at least {expected_contexts}"
        )
    if float(prometheus["max_running"]) < min(2, expected_contexts):
        errors.append("Prometheus did not observe multiple running requests")
    if require_capacity_waiting and float(prometheus["max_waiting_capacity"]) <= 0:
        errors.append("Prometheus did not attribute BULK waiting to capacity")
    context_iterations = [
        row for row in iterations if int(row["context_tokens"]) > 0
    ]
    context_tokens = sum(int(row["context_tokens"]) for row in context_iterations)
    context_elapsed_ms = sum(
        float(row["elapsed_ms"]) for row in context_iterations
    )
    return {
        "schema_version": 1,
        "valid": not errors,
        "errors": errors,
        "expected_contexts": expected_contexts,
        "max_context_requests": max_contexts,
        "max_context_tokens": max(
            (int(row["context_tokens"]) for row in iterations), default=0
        ),
        "iteration_count": len(iterations),
        "context_iteration_count": len(context_iterations),
        "context_tokens": context_tokens,
        "context_elapsed_ms": context_elapsed_ms,
        "context_ms_per_1k_tokens": (
            context_elapsed_ms * 1000 / context_tokens if context_tokens else 0.0
        ),
        "prometheus": prometheus,
        "iterations": iterations,
    }


def _event_sum(events: dict[str, dict[str, float | int]], prefix: str) -> float:
    return sum(
        float(values.get("exclusive_sum_ms", values.get("sum_ms", 0.0)))
        for name, values in events.items()
        if name.startswith(prefix)
    )


def _event_sum_many(
    events: dict[str, dict[str, float | int]], prefixes: tuple[str, ...]
) -> float:
    return sum(_event_sum(events, prefix) for prefix in prefixes)


def _event_count(events: dict[str, dict[str, float | int]], prefix: str) -> int:
    return sum(
        int(values.get("count", 0))
        for name, values in events.items()
        if name.startswith(prefix)
    )


def _event_count_many(
    events: dict[str, dict[str, float | int]], prefixes: tuple[str, ...]
) -> int:
    return sum(_event_count(events, prefix) for prefix in prefixes)


def timing_breakdown(events: dict[str, dict[str, float | int]]) -> dict[str, float]:
    return {
        "critical_wait_ms": _event_sum(events, "critical."),
        "layer_gate_ms": _event_sum_many(
            events,
            (
                "layerwise.attention_done_gate",
                "layerwise.pd_transfer_gate",
            ),
        ),
        "reuse_gate_ms": _event_sum_many(
            events,
            (
                "reuse3.wait_for_save_layer",
                "reuse3.attention_start_gate",
            ),
        ),
        "reuse_slot_orchestration_ms": _event_sum(events, "reuse3.slot_reload"),
        "layerwise_orchestration_ms": _event_sum_many(
            events,
            (
                "layerwise.batch_copy_put",
                "layerwise.batch_copy_get",
                "layerwise.batch_commit",
                "layerwise.range_load",
                "layerwise.gva_load",
                "layerwise.gva_save",
            ),
        ),
        "mooncake_api_ms": _event_sum(events, "mooncake."),
    }


def timing_event_counts(
    events: dict[str, dict[str, float | int]],
) -> dict[str, int]:
    return {
        "critical_wait": _event_count(events, "critical."),
        "layer_gate": _event_count_many(
            events,
            ("layerwise.attention_done_gate", "layerwise.pd_transfer_gate"),
        ),
        "reuse_gate": _event_count_many(
            events,
            ("reuse3.wait_for_save_layer", "reuse3.attention_start_gate"),
        ),
        "reuse_slot_reload": _event_count(events, "reuse3.slot_reload"),
        "layerwise_orchestration": _event_count_many(
            events,
            (
                "layerwise.batch_copy_put",
                "layerwise.batch_copy_get",
                "layerwise.batch_commit",
                "layerwise.range_load",
                "layerwise.gva_load",
                "layerwise.gva_save",
            ),
        ),
        "mooncake_api": _event_count(events, "mooncake."),
    }


def _timing_attribution(
    bulk_events: dict[str, dict[str, float | int]],
    alternative_events: dict[str, dict[str, float | int]],
) -> dict[str, object]:
    bulk = timing_breakdown(bulk_events)
    alternative = timing_breakdown(alternative_events)
    bulk_counts = timing_event_counts(bulk_events)
    alternative_counts = timing_event_counts(alternative_events)
    deltas = {
        name: alternative[name] - bulk[name]
        for name in bulk
    }
    positive = {name: value for name, value in deltas.items() if value > 0}
    dominant = max(positive, key=positive.get) if positive else "none"
    return {
        "bulk_ms": bulk,
        "alternative_ms": alternative,
        "bulk_counts": bulk_counts,
        "alternative_counts": alternative_counts,
        "delta_ms": deltas,
        "dominant_positive_delta": dominant,
        "dominant_positive_delta_ms": positive.get(dominant, 0.0),
    }


def _role_timing_attribution(
    bulk: dict[str, Any], alternative: dict[str, Any]
) -> dict[str, object]:
    bulk_roles = bulk.get("kvpool_events_by_role")
    alternative_roles = alternative.get("kvpool_events_by_role")
    if not isinstance(bulk_roles, dict) or not isinstance(alternative_roles, dict):
        fallback = _timing_attribution(
            bulk.get("kvpool_events", {}), alternative.get("kvpool_events", {})
        )
        return {
            "by_role": {"combined": fallback},
            "dominant_role": "combined",
            "dominant_positive_delta": fallback["dominant_positive_delta"],
            "dominant_positive_delta_ms": fallback[
                "dominant_positive_delta_ms"
            ],
        }

    roles = sorted(set(bulk_roles) | set(alternative_roles))
    by_role = {
        role: _timing_attribution(
            bulk_roles.get(role, {}), alternative_roles.get(role, {})
        )
        for role in roles
    }
    candidates = [
        (
            float(values["dominant_positive_delta_ms"]),
            role,
            str(values["dominant_positive_delta"]),
        )
        for role, values in by_role.items()
        if float(values["dominant_positive_delta_ms"]) > 0
    ]
    if candidates:
        delta_ms, dominant_role, dominant_category = max(candidates)
    else:
        delta_ms, dominant_role, dominant_category = 0.0, "none", "none"
    return {
        "by_role": by_role,
        "dominant_role": dominant_role,
        "dominant_positive_delta": dominant_category,
        "dominant_positive_delta_ms": delta_ms,
    }


def classify_slowdown(
    bulk: dict[str, Any],
    alternative: dict[str, Any],
    *,
    alternative_name: str,
) -> dict[str, object]:
    bulk_throughput = float(bulk["request_throughput"])
    alternative_throughput = float(alternative["request_throughput"])
    ratio = alternative_throughput / bulk_throughput
    if ratio >= 1.0:
        return {
            "slower": False,
            "throughput_ratio": ratio,
            "cause": "none",
            "resolved": True,
        }

    bulk_admission = int(bulk["admission"]["max_context_requests"])
    alternative_admission = int(alternative["admission"]["max_context_requests"])
    bulk_prom = bulk["admission"]["prometheus"]
    alternative_prom = alternative["admission"]["prometheus"]
    bulk_decode = bulk.get("decode_prometheus", {})
    alternative_decode = alternative.get("decode_prometheus", {})
    attribution = _role_timing_attribution(bulk, alternative)
    request_count = int(alternative.get("request_count", 0))
    wall_gap_ms = (
        request_count
        * (1 / alternative_throughput - 1 / bulk_throughput)
        * 1000
    )
    bulk_sustained = float(bulk_prom.get("mean_active_running", 0))
    alternative_sustained = float(
        alternative_prom.get("mean_active_running", 0)
    )
    sustained_admission_loss = (
        alternative_admission < bulk_admission
        and alternative_sustained <= bulk_sustained - 1.0
    )
    queue_delta_ms = max(
        0.0,
        (
            float(alternative_prom.get("queue_time_sum_delta", 0))
            - float(bulk_prom.get("queue_time_sum_delta", 0))
        )
        * 1000,
    )
    decode_queue_delta_ms = max(
        0.0,
        (
            float(alternative_decode.get("queue_time_sum_delta", 0))
            - float(bulk_decode.get("queue_time_sum_delta", 0))
        )
        * 1000,
    )

    def is_material(delta_ms: float) -> bool:
        return (
            request_count > 0
            and wall_gap_ms > 0
            and delta_ms / wall_gap_ms >= MIN_TIMING_EXPLAINED_FRACTION
        )

    evidence: dict[str, object] = {}
    resolved = True
    if alternative_admission <= 1 < bulk_admission or sustained_admission_loss:
        cause = "scheduler_admission"
        evidence = {
            "bulk_peak_contexts": bulk_admission,
            "alternative_peak_contexts": alternative_admission,
            "bulk_mean_active_running": bulk_sustained,
            "alternative_mean_active_running": alternative_sustained,
        }
    elif (
        float(alternative_prom.get("max_waiting_deferred", 0))
        > float(bulk_prom.get("max_waiting_deferred", 0))
        and is_material(queue_delta_ms)
    ):
        cause = "kv_transfer_or_scheduler_deferred_wait"
        evidence = {
            "bulk_max_waiting_deferred": float(
                bulk_prom.get("max_waiting_deferred", 0)
            ),
            "alternative_max_waiting_deferred": float(
                alternative_prom.get("max_waiting_deferred", 0)
            ),
            "queue_time_delta_ms": queue_delta_ms,
            "observed_wall_gap_ms": wall_gap_ms,
            "queue_time_explained_fraction": queue_delta_ms / wall_gap_ms,
        }
    elif (
        (
            float(alternative_decode.get("max_waiting_capacity", 0))
            > float(bulk_decode.get("max_waiting_capacity", 0))
            or float(alternative_decode.get("preemption_delta", 0))
            > float(bulk_decode.get("preemption_delta", 0))
        )
        and is_material(decode_queue_delta_ms)
    ):
        cause = "decode_capacity_or_admission"
        evidence = {
            "bulk_decode_max_waiting_capacity": float(
                bulk_decode.get("max_waiting_capacity", 0)
            ),
            "alternative_decode_max_waiting_capacity": float(
                alternative_decode.get("max_waiting_capacity", 0)
            ),
            "bulk_decode_preemption_delta": float(
                bulk_decode.get("preemption_delta", 0)
            ),
            "alternative_decode_preemption_delta": float(
                alternative_decode.get("preemption_delta", 0)
            ),
            "decode_queue_time_delta_ms": decode_queue_delta_ms,
            "observed_wall_gap_ms": wall_gap_ms,
            "decode_queue_time_explained_fraction": (
                decode_queue_delta_ms / wall_gap_ms
            ),
        }
    else:
        dominant = str(attribution["dominant_positive_delta"])
        dominant_role = str(attribution["dominant_role"])
        role_prefix = "" if dominant_role == "combined" else f"{dominant_role}_"
        timing_delta_ms = float(attribution["dominant_positive_delta_ms"])
        explained_fraction = (
            timing_delta_ms / wall_gap_ms if wall_gap_ms > 0 else 0.0
        )
        by_role = attribution.get("by_role", {})
        role_timing = (
            by_role.get(dominant_role, {})
            if isinstance(by_role, dict)
            else {}
        )
        role_deltas = (
            role_timing.get("delta_ms", {})
            if isinstance(role_timing, dict)
            else {}
        )
        critical_path_delta_ms = max(
            0.0,
            float(
                role_deltas.get("critical_wait_ms", 0.0)
                if isinstance(role_deltas, dict)
                else 0.0
            ),
        )
        critical_path_explained_fraction = (
            critical_path_delta_ms / wall_gap_ms if wall_gap_ms > 0 else 0.0
        )
        timing_evidence = {
            "role": dominant_role,
            "timing_category": dominant,
            "delta_ms": timing_delta_ms,
            "observed_wall_gap_ms": wall_gap_ms,
            "aggregated_rank_time_explained_fraction": explained_fraction,
            "critical_path_delta_ms": critical_path_delta_ms,
            "critical_path_explained_fraction": (
                critical_path_explained_fraction
            ),
        }
        timing_is_material = (
            request_count > 0
            and explained_fraction >= MIN_TIMING_EXPLAINED_FRACTION
        )
        critical_path_is_material = (
            request_count > 0
            and critical_path_explained_fraction
            >= MIN_TIMING_EXPLAINED_FRACTION
        )
        background_timing_is_causal = (
            timing_is_material and critical_path_is_material
        )
        if dominant == "critical_wait_ms" and timing_is_material:
            cause = f"{role_prefix}layer_or_reuse_gate_wait"
            evidence = timing_evidence
        elif (
            dominant in {"layer_gate_ms", "reuse_gate_ms"}
            and background_timing_is_causal
        ):
            cause = f"{role_prefix}layer_or_reuse_gate_wait"
            evidence = timing_evidence
        elif (
            dominant == "reuse_slot_orchestration_ms"
            and background_timing_is_causal
        ):
            cause = f"{role_prefix}reuse_slot_reload_overhead"
            evidence = timing_evidence
        elif (
            dominant == "layerwise_orchestration_ms"
            and background_timing_is_causal
        ):
            cause = f"{role_prefix}layerwise_orchestration_overhead"
            evidence = timing_evidence
        elif dominant == "mooncake_api_ms" and background_timing_is_causal:
            cause = f"{role_prefix}mooncake_transfer_or_session_overhead"
            evidence = timing_evidence
        else:
            cause = "unresolved_requires_short_diagnostic"
            resolved = False
            evidence = {
                "candidate_timing": timing_evidence,
                "reuse3_capacity_conversion": (
                    validate_reuse_capacity_advantage(bulk, alternative)
                    if alternative_name == "reuse3"
                    else None
                ),
                "bulk_context_ms_per_1k_tokens": float(
                    bulk["admission"].get("context_ms_per_1k_tokens", 0)
                ),
                "alternative_context_ms_per_1k_tokens": float(
                    alternative["admission"].get(
                        "context_ms_per_1k_tokens", 0
                    )
                ),
                "candidate_scheduler_signals": {
                    "bulk_peak_contexts": bulk_admission,
                    "alternative_peak_contexts": alternative_admission,
                    "bulk_mean_active_running": bulk_sustained,
                    "alternative_mean_active_running": alternative_sustained,
                    "queue_time_delta_ms": queue_delta_ms,
                    "decode_queue_time_delta_ms": decode_queue_delta_ms,
                },
            }
    return {
        "slower": True,
        "throughput_ratio": ratio,
        "cause": cause,
        "bulk_admission": bulk_admission,
        "alternative_admission": alternative_admission,
        "resolved": resolved,
        "evidence": evidence,
        "timing_breakdown": attribution,
    }


def validate_reuse_capacity_advantage(
    bulk: dict[str, Any],
    reuse3: dict[str, Any],
) -> dict[str, object]:
    bulk_admission = int(bulk["admission"]["max_context_requests"])
    reuse_admission = int(reuse3["admission"]["max_context_requests"])
    bulk_prom = bulk["admission"]["prometheus"]
    reuse_prom = reuse3["admission"]["prometheus"]
    bulk_sustained = float(bulk_prom.get("mean_active_running", 0.0))
    reuse_sustained = float(reuse_prom.get("mean_active_running", 0.0))
    bulk_preemptions = float(bulk_prom.get("preemption_delta", 0.0))
    reuse_preemptions = float(reuse_prom.get("preemption_delta", 0.0))
    bulk_capacity_waiting = float(bulk_prom.get("max_waiting_capacity", 0.0))
    reuse_capacity_waiting = float(reuse_prom.get("max_waiting_capacity", 0.0))
    bulk_capacity_waiting_sum = float(
        bulk_prom.get("capacity_waiting_sample_sum", bulk_capacity_waiting)
    )
    reuse_capacity_waiting_sum = float(
        reuse_prom.get("capacity_waiting_sample_sum", reuse_capacity_waiting)
    )
    advantages = {
        "higher_peak_contexts": reuse_admission > bulk_admission,
        "higher_sustained_running": reuse_sustained >= bulk_sustained + 1.0,
        "fewer_preemptions": reuse_preemptions <= bulk_preemptions - 1.0,
        "less_capacity_waiting": (
            reuse_capacity_waiting_sum <= bulk_capacity_waiting_sum - 1.0
        ),
    }
    sustained_advantages = {
        name: value
        for name, value in advantages.items()
        if name != "higher_peak_contexts"
    }
    return {
        "valid": any(sustained_advantages.values()),
        "advantages": advantages,
        "bulk": {
            "peak_contexts": bulk_admission,
            "mean_active_running": bulk_sustained,
            "preemption_delta": bulk_preemptions,
            "max_waiting_capacity": bulk_capacity_waiting,
            "capacity_waiting_sample_sum": bulk_capacity_waiting_sum,
        },
        "reuse3": {
            "peak_contexts": reuse_admission,
            "mean_active_running": reuse_sustained,
            "preemption_delta": reuse_preemptions,
            "max_waiting_capacity": reuse_capacity_waiting,
            "capacity_waiting_sample_sum": reuse_capacity_waiting_sum,
        },
    }


def short_diagnostic_spec(
    test: str, result: dict[str, Any]
) -> dict[str, object] | None:
    if result.get("slower") is not True:
        return None
    if test not in {"test1", "test2"}:
        raise ValueError(f"unsupported diagnostic test: {test}")
    direct_causes = {
        "scheduler_admission",
        "kv_transfer_or_scheduler_deferred_wait",
        "decode_capacity_or_admission",
    }
    if result.get("resolved") is True and (
        test == "test1" or result.get("cause") in direct_causes
    ):
        return None
    concurrency = 8 if test == "test1" else 40
    variants = (
        ["bulk", "layerwise"]
        if test == "test1"
        else ["bulk", "layerwise", "reuse3"]
    )
    return {
        "test": test,
        "variants": variants,
        "request_count_per_variant": concurrency,
        "concurrency": concurrency,
        "output_tokens": 128 if test == "test1" else 1,
        "enable_environment": {
            "VLLM_ASCEND_KVPOOL_PERF_METRICS": "1",
            "VLLM_ASCEND_KVPOOL_PERF_METRICS_INTERVAL_SECONDS": "1",
            "VLLM_ASCEND_KVPOOL_RANGE_DEBUG": "1",
            "MC_TE_METRIC": "1",
            "MC_TE_METRIC_INTERVAL_SECONDS": "1",
        },
        "capture": [
            "prefill_and_decode_iteration_details",
            "prefill_and_decode_kvpool_range_events",
            "prefill_and_decode_kvpool_aggregate_events",
            "prefill_and_decode_transfer_engine_metrics",
            "prefill_and_decode_prometheus",
        ],
        "hypothesis": (
            "isolate ordinary layerwise transfer cost from REUSE3 incremental "
            "buffer-reuse cost, then distinguish compute batching from "
            "critical-path transfer and gate overhead"
        ),
        "formal_rerun_required": False,
    }


def _validate_short_diagnostic_point(
    name: str, point: dict[str, Any]
) -> list[str]:
    by_role = point.get("range_debug_by_role")
    if not isinstance(by_role, dict) or set(by_role) != {"prefill", "decode"}:
        return [f"{name} lacks Prefill/Decode range-debug evidence"]
    errors: list[str] = []
    for role in ("prefill", "decode"):
        metrics = by_role.get(role)
        if not isinstance(metrics, dict):
            errors.append(f"{name} {role} range-debug evidence is malformed")
            continue
        if int(metrics.get("total_events", 0)) <= 0:
            errors.append(f"{name} {role} emitted no range-debug events")
        if int(metrics.get("malformed_events", 0)) > 0:
            errors.append(f"{name} {role} emitted malformed range-debug events")
        if int(metrics.get("failed_results", 0)) > 0:
            errors.append(f"{name} {role} range-debug events contain failed results")
    return errors


def resolve_with_short_diagnostic(
    formal: dict[str, Any],
    bulk: dict[str, Any],
    alternative: dict[str, Any],
    *,
    alternative_name: str,
) -> dict[str, object]:
    if formal.get("slower") is not True or formal.get("resolved") is True:
        return dict(formal)

    errors = [
        *_validate_short_diagnostic_point("bulk", bulk),
        *_validate_short_diagnostic_point(alternative_name, alternative),
    ]
    diagnostic: dict[str, object] | None = None
    if not errors:
        diagnostic = classify_slowdown(
            bulk,
            alternative,
            alternative_name=alternative_name,
        )
        if diagnostic.get("slower") is not True:
            errors.append("short diagnostic did not reproduce the slowdown")
        elif diagnostic.get("resolved") is not True:
            errors.append("short diagnostic did not identify a material cause")

    result = dict(formal)
    formal_evidence = formal.get("evidence", {})
    if errors:
        result["evidence"] = {
            "formal": formal_evidence,
            "short_diagnostic_errors": errors,
            "short_diagnostic": diagnostic,
        }
        return result

    assert diagnostic is not None
    result.update(
        {
            "cause": diagnostic["cause"],
            "resolved": True,
            "evidence": {
                "source": "short_diagnostic",
                "formal": formal_evidence,
                "diagnostic_throughput_ratio": diagnostic["throughput_ratio"],
                "diagnostic": diagnostic.get("evidence", {}),
                "range_debug": {
                    "bulk": bulk["range_debug_by_role"],
                    alternative_name: alternative["range_debug_by_role"],
                },
            },
            "timing_breakdown": diagnostic.get("timing_breakdown", {}),
        }
    )
    return result


def resolve_reuse3_with_layerwise_control(
    formal: dict[str, Any],
    bulk: dict[str, Any],
    layerwise: dict[str, Any],
    reuse3: dict[str, Any],
) -> dict[str, object]:
    if formal.get("slower") is not True:
        return dict(formal)

    errors = [
        *_validate_short_diagnostic_point("bulk", bulk),
        *_validate_short_diagnostic_point("layerwise", layerwise),
        *_validate_short_diagnostic_point("reuse3", reuse3),
    ]
    direct: dict[str, object] | None = None
    layerwise_leg: dict[str, object] | None = None
    reuse3_leg: dict[str, object] | None = None
    if not errors:
        direct = classify_slowdown(bulk, reuse3, alternative_name="reuse3")
        layerwise_leg = classify_slowdown(
            bulk,
            layerwise,
            alternative_name="layerwise",
        )
        reuse3_leg = classify_slowdown(
            layerwise,
            reuse3,
            alternative_name="reuse3",
        )
        if direct.get("slower") is not True:
            errors.append("three-point short diagnostic did not reproduce the slowdown")
        for name, leg in (
            ("layerwise_over_bulk", layerwise_leg),
            ("reuse3_over_layerwise", reuse3_leg),
        ):
            if leg.get("slower") is True and leg.get("resolved") is not True:
                errors.append(f"{name} remains unresolved")

    result = dict(formal)
    leg_evidence = {
        "reuse3_over_bulk": direct,
        "layerwise_over_bulk": layerwise_leg,
        "reuse3_over_layerwise": reuse3_leg,
    }
    if errors:
        result.update(
            {
                "cause": "unresolved_requires_short_diagnostic",
                "resolved": False,
                "evidence": {
                    "formal": formal.get("evidence", {}),
                    "short_diagnostic_errors": errors,
                    "differential_legs": leg_evidence,
                },
            }
        )
        return result

    assert direct is not None
    assert layerwise_leg is not None
    assert reuse3_leg is not None
    layerwise_slower = layerwise_leg.get("slower") is True
    reuse3_slower = reuse3_leg.get("slower") is True
    if layerwise_slower and reuse3_slower:
        cause = "layerwise_base_plus_reuse3_incremental_overhead"
    elif reuse3_slower:
        cause = f"reuse3_incremental_{reuse3_leg['cause']}"
    elif layerwise_slower:
        cause = f"layerwise_base_{layerwise_leg['cause']}"
    else:
        result.update(
            {
                "cause": "unresolved_requires_short_diagnostic",
                "resolved": False,
                "evidence": {
                    "formal": formal.get("evidence", {}),
                    "short_diagnostic_errors": [
                        "neither differential leg reproduced a slowdown"
                    ],
                    "differential_legs": leg_evidence,
                },
            }
        )
        return result

    result.update(
        {
            "cause": cause,
            "resolved": True,
            "evidence": {
                "source": "short_diagnostic",
                "formal": formal.get("evidence", {}),
                "differential_legs": leg_evidence,
                "range_debug": {
                    "bulk": bulk["range_debug_by_role"],
                    "layerwise": layerwise["range_debug_by_role"],
                    "reuse3": reuse3["range_debug_by_role"],
                },
            },
            "timing_breakdown": {
                "layerwise_over_bulk": layerwise_leg.get("timing_breakdown", {}),
                "reuse3_over_layerwise": reuse3_leg.get("timing_breakdown", {}),
                "reuse3_over_bulk": direct.get("timing_breakdown", {}),
            },
        }
    )
    return result
