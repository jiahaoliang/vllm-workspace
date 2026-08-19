from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("/tmp/layerwise-issue1-load-timing-20260817T181503+0800")
PREFIX = "[DEBUG-REUSE3-LOAD] "
ITERATION_RE = re.compile(
    r"Iteration\((?P<iteration>\d+)\): "
    r"(?P<context_requests>\d+) context requests, "
    r"(?P<context_tokens>\d+) context tokens, .*?"
    r"iteration elapsed time: (?P<elapsed_ms>[0-9.]+) ms"
)
HIT_RE = re.compile(
    r"Reqid: (?P<request_id>[^,]+), Total tokens (?P<total_tokens>\d+), "
    r"kvpool hit tokens: (?P<hit_tokens>\d+)"
)
NPU_HEADER_RE = re.compile(r"^\|\s*(?P<npu>\d+)\s+910B4\s+\|")
NPU_SAMPLE_RE = re.compile(
    r"^\|\s*0\s+\|\s*[^|]+\|\s*(?P<aicore>\d+)\s+"
    r"\d+\s*/\s*\d+\s+(?P<hbm>\d+)\s*/\s*\d+"
)
FORMAL_WINDOWS = {
    "load-timing-test2-bulk": (
        datetime.fromisoformat("2026-08-17T10:46:51+00:00"),
        datetime.fromisoformat("2026-08-17T10:54:25+00:00"),
    ),
    "load-timing-test2-reuse3": (
        datetime.fromisoformat("2026-08-17T11:24:51+00:00"),
        datetime.fromisoformat("2026-08-17T11:44:40+00:00"),
    ),
}


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, (len(ordered) * percent - 1) // 100)
    return ordered[index]


def stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "sum": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "sum": sum(values),
        "mean": statistics.fmean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def formal_text(point: Path, role: str) -> str:
    offset = int((point / f"{role}-formal-start-offset.txt").read_text().strip())
    with (point / f"{role}-full.log").open("rb") as stream:
        stream.seek(offset)
        return stream.read().decode("utf-8", errors="replace")


def parse_debug_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        marker = line.find(PREFIX)
        if marker < 0:
            continue
        events.append(json.loads(line[marker + len(PREFIX) :]))
    return events


def parse_iterations(text: str) -> list[dict[str, int | float]]:
    return [
        {
            "iteration": int(match.group("iteration")),
            "context_requests": int(match.group("context_requests")),
            "context_tokens": int(match.group("context_tokens")),
            "elapsed_ms": float(match.group("elapsed_ms")),
        }
        for match in ITERATION_RE.finditer(text)
    ]


def summarize_iterations(iterations: list[dict[str, int | float]]) -> dict[str, Any]:
    context = [item for item in iterations if int(item["context_requests"]) > 0]
    by_requests: dict[int, list[float]] = defaultdict(list)
    for item in context:
        by_requests[int(item["context_requests"])].append(float(item["elapsed_ms"]))
    return {
        "context_iteration_count": len(context),
        "elapsed_ms": stats([float(item["elapsed_ms"]) for item in context]),
        "by_context_requests": {
            str(requests): stats(values) for requests, values in sorted(by_requests.items())
        },
    }


def summarize_hits(text: str) -> dict[str, Any]:
    hits_by_request: dict[str, list[int]] = defaultdict(list)
    for match in HIT_RE.finditer(text):
        hits_by_request[match.group("request_id")].append(int(match.group("hit_tokens")))
    first_hits = [values[0] for values in hits_by_request.values()]
    return {
        "log_line_count": sum(len(values) for values in hits_by_request.values()),
        "unique_request_count": len(hits_by_request),
        "first_hit_token_values": sorted(set(first_hits)),
        "requests_with_first_hit_28800": sum(value == 28800 for value in first_hits),
    }


def summarize_npu(path: Path, start: datetime, end: datetime) -> dict[str, Any]:
    current_time: datetime | None = None
    current_npu: int | None = None
    values: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"aicore_percent": [], "hbm_mib": []}
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("2026-"):
            timestamp = line.replace(",", ".")
            timestamp_base, timezone = timestamp.rsplit("+", 1)
            date_time, fraction = timestamp_base.split(".", 1)
            current_time = datetime.fromisoformat(
                f"{date_time}.{fraction[:6]}+{timezone}"
            )
            current_npu = None
            continue
        header = NPU_HEADER_RE.match(line)
        if header:
            current_npu = int(header.group("npu"))
            continue
        sample = NPU_SAMPLE_RE.match(line)
        if (
            sample
            and current_time is not None
            and current_npu is not None
            and start <= current_time <= end
        ):
            values[current_npu]["aicore_percent"].append(float(sample.group("aicore")))
            values[current_npu]["hbm_mib"].append(float(sample.group("hbm")))
    return {
        str(npu): {metric: stats(samples) for metric, samples in metrics.items()}
        for npu, metrics in sorted(values.items())
    }


def summarize_aisbench(point: Path) -> dict[str, Any]:
    detail_files = list(point.glob("aisbench-formal/aisbench-output/*/performances/*/*_details.jsonl"))
    performance_files = list(point.glob("aisbench-formal/aisbench-output/*/performances/*/*.json"))
    if len(detail_files) != 1 or len(performance_files) != 1:
        raise RuntimeError(
            f"Expected one AISBench detail/performance file under {point}, "
            f"got {len(detail_files)}/{len(performance_files)}"
        )
    rows = [json.loads(line) for line in detail_files[0].read_text().splitlines()]
    return {
        "detail_rows": len(rows),
        "success_rows": sum(row.get("success") is True for row in rows),
        "unique_data_ids": len({row.get("data_id") for row in rows}),
        "nonempty_predictions": sum(
            isinstance(row.get("prediction"), str) and bool(row["prediction"])
            for row in rows
        ),
        "input_token_values": sorted({row.get("input_tokens") for row in rows}),
        "output_token_values": sorted({row.get("output_tokens") for row in rows}),
        "error_info_values": sorted({row.get("error_info") for row in rows}),
        "performance": json.loads(performance_files[0].read_text()),
    }


def summarize_bulk(events: list[dict[str, Any]]) -> dict[str, Any]:
    gets = [event for event in events if event.get("stage") == "bulk_get"]
    by_rank: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in gets:
        by_rank[int(event["tp_rank"])].append(event)
    return {
        "event_count": len(gets),
        "by_tp_rank": {
            str(rank): {
                "get_count": len(rank_events),
                "duration_us": stats([float(event["duration_us"]) for event in rank_events]),
                "requested_bytes_total": sum(int(event["requested_bytes"]) for event in rank_events),
                "requested_bytes_per_get": stats(
                    [float(event["requested_bytes"]) for event in rank_events]
                ),
                "key_count_per_get": stats([float(event["key_count"]) for event in rank_events]),
            }
            for rank, rank_events in sorted(by_rank.items())
        },
    }


def summarize_reuse(events: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = [
        event
        for event in events
        if event.get("stage") == "layer_task" and int(event.get("request_call_count", 0)) > 0
    ]
    waits = [
        event
        for event in events
        if event.get("stage") == "model_wait" and event.get("should_wait") is True
    ]
    tasks_by_rank: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in tasks:
        tasks_by_rank[int(event["tp_rank"])].append(event)
    tp0_by_layer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in tasks_by_rank.get(0, []):
        tp0_by_layer[int(event["layer_id"])].append(event)

    step_rank_tasks: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for event in tasks:
        step_rank_tasks[(int(event["step_id"]), int(event["tp_rank"]))].append(event)

    waits_by_boundary: dict[tuple[int, int], list[float]] = defaultdict(list)
    for event in waits:
        waits_by_boundary[(int(event["step_id"]), int(event["layer_id"]))].append(
            float(event["duration_us"])
        )

    critical_wait_by_step: dict[int, float] = defaultdict(float)
    for (step_id, _layer_id), values in waits_by_boundary.items():
        critical_wait_by_step[step_id] += max(values)

    calls_by_step: dict[int, int] = defaultdict(int)
    bytes_by_step: dict[int, list[int]] = defaultdict(list)
    transfer_by_step: dict[int, list[int]] = defaultdict(list)
    for (step_id, _rank), rank_tasks in step_rank_tasks.items():
        calls_by_step[step_id] = max(
            calls_by_step[step_id],
            max(int(event["request_call_count"]) for event in rank_tasks),
        )
        bytes_by_step[step_id].append(sum(int(event["requested_bytes"]) for event in rank_tasks))
        transfer_by_step[step_id].append(sum(int(event["batch_copy_get_us"]) for event in rank_tasks))

    step_groups: dict[int, list[int]] = defaultdict(list)
    for step_id, call_count in calls_by_step.items():
        step_groups[call_count].append(step_id)

    by_request_calls: dict[str, Any] = {}
    for call_count, step_ids in sorted(step_groups.items()):
        by_request_calls[str(call_count)] = {
            "step_count": len(step_ids),
            "critical_model_wait_us": stats(
                [critical_wait_by_step.get(step_id, 0.0) for step_id in step_ids]
            ),
            "requested_bytes_per_tp_step": stats(
                [float(value) for step_id in step_ids for value in bytes_by_step[step_id]]
            ),
            "batch_copy_get_us_per_tp_step": stats(
                [float(value) for step_id in step_ids for value in transfer_by_step[step_id]]
            ),
        }

    return {
        "active_layer_task_count": len(tasks),
        "active_layer_ids": sorted({int(event["layer_id"]) for event in tasks}),
        "tp0_by_layer": {
            str(layer_id): {
                "event_count": len(layer_events),
                "request_call_count_total": sum(
                    int(event["request_call_count"]) for event in layer_events
                ),
                "requested_bytes_total": sum(
                    int(event["requested_bytes"]) for event in layer_events
                ),
                "batch_copy_get_us_total": sum(
                    int(event["batch_copy_get_us"]) for event in layer_events
                ),
            }
            for layer_id, layer_events in sorted(tp0_by_layer.items())
        },
        "model_wait_count": len(waits),
        "active_step_count": len(calls_by_step),
        "critical_model_wait_us_total": sum(critical_wait_by_step.values()),
        "critical_model_wait_us_per_step": stats(list(critical_wait_by_step.values())),
        "by_request_calls": by_request_calls,
        "by_tp_rank": {
            str(rank): {
                "active_layer_task_count": len(rank_events),
                "step_count": len({int(event["step_id"]) for event in rank_events}),
                "request_call_count_total": sum(
                    int(event["request_call_count"]) for event in rank_events
                ),
                "key_count_total": sum(int(event["key_count"]) for event in rank_events),
                "requested_bytes_total": sum(
                    int(event["requested_bytes"]) for event in rank_events
                ),
                "layer_task_duration_us": stats(
                    [float(event["duration_us"]) for event in rank_events]
                ),
                "queue_wait_us": stats([float(event["queue_wait_us"]) for event in rank_events]),
                "preparation_us": stats([float(event["preparation_us"]) for event in rank_events]),
                "address_build_us": stats([float(event["address_build_us"]) for event in rank_events]),
                "save_gate_us": stats([float(event["save_gate_us"]) for event in rank_events]),
                "attention_gate_us": stats(
                    [float(event["attention_gate_us"]) for event in rank_events]
                ),
                "batch_copy_get_us": stats(
                    [float(event["batch_copy_get_us"]) for event in rank_events]
                ),
                "batch_copy_get_us_total": sum(
                    int(event["batch_copy_get_us"]) for event in rank_events
                ),
                "mean_batch_copy_get_call_us": (
                    sum(int(event["batch_copy_get_us"]) for event in rank_events)
                    / sum(int(event["request_call_count"]) for event in rank_events)
                ),
                "reported_call_p50_us": stats(
                    [float(event["call_p50_us"]) for event in rank_events]
                ),
                "reported_call_p95_us": stats(
                    [float(event["call_p95_us"]) for event in rank_events]
                ),
                "reported_call_max_us": stats(
                    [float(event["call_max_us"]) for event in rank_events]
                ),
            }
            for rank, rank_events in sorted(tasks_by_rank.items())
        },
    }


def analyze_point(name: str) -> dict[str, Any]:
    point = ROOT / name
    prefill_text = formal_text(point, "prefill")
    decode_text = formal_text(point, "decode")
    prefill_events = parse_debug_events(prefill_text)
    decode_events = parse_debug_events(decode_text)
    events = prefill_events + decode_events
    summarize_load = summarize_bulk if name.endswith("bulk") else summarize_reuse
    formal_start, formal_end = FORMAL_WINDOWS[name]
    errors = [
        line
        for text in (prefill_text, decode_text)
        for line in text.splitlines()
        if "Traceback" in line or "ERROR" in line or "507018" in line or "OutOfMemoryError" in line
    ]
    return {
        "name": name,
        "debug_event_count": len(events),
        "formal_error_lines": errors,
        "iterations": summarize_iterations(parse_iterations(prefill_text)),
        "prefill_hit_summary": summarize_hits(prefill_text),
        "iterations_by_role": {
            "prefill": summarize_iterations(parse_iterations(prefill_text)),
            "decode": summarize_iterations(parse_iterations(decode_text)),
        },
        "load": summarize_load(events),
        "load_by_role": {
            "prefill": summarize_load(prefill_events),
            "decode": summarize_load(decode_events),
        },
        "prefill_npu": summarize_npu(
            point / "prefill-npu-timeseries.log", formal_start, formal_end
        ),
        "aisbench": summarize_aisbench(point),
    }


def mib(value: float) -> float:
    return value / 1024 / 1024


def decimal_gbps(byte_count: float, duration_us: float) -> float:
    return byte_count / 1_000_000_000 / (duration_us / 1_000_000)


def main() -> None:
    bulk = analyze_point("load-timing-test2-bulk")
    reuse = analyze_point("load-timing-test2-reuse3")
    result = {"bulk": bulk, "reuse3": reuse}
    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    (analysis_dir / "load-timing-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    bulk_prefill_rank = bulk["load_by_role"]["prefill"]["by_tp_rank"]["0"]
    bulk_decode_rank = bulk["load_by_role"]["decode"]["by_tp_rank"]["0"]
    reuse_prefill = reuse["load_by_role"]["prefill"]
    reuse_decode = reuse["load_by_role"]["decode"]
    reuse_rank = reuse_prefill["by_tp_rank"]["0"]
    reuse_decode_rank = reuse_decode["by_tp_rank"].get(
        "0",
        {"request_call_count_total": 0, "batch_copy_get_us_total": 0},
    )
    forty = reuse_prefill["by_request_calls"]["40"]
    twenty = reuse_prefill["by_request_calls"]["20"]
    bulk_bytes = bulk_prefill_rank["requested_bytes_total"]
    reuse_bytes = reuse_rank["requested_bytes_total"]
    bulk_duration_us = bulk_prefill_rank["duration_us"]["sum"]
    reuse_duration_us = reuse_rank["batch_copy_get_us_total"]
    prefill_iteration_us = reuse["iterations_by_role"]["prefill"]["elapsed_ms"]["sum"] * 1000
    rank_summaries = list(reuse_prefill["by_tp_rank"].values())
    worst_address_us = max(rank["address_build_us"]["sum"] for rank in rank_summaries)
    worst_save_gate_us = max(rank["save_gate_us"]["sum"] for rank in rank_summaries)
    worst_attention_gate_us = max(rank["attention_gate_us"]["sum"] for rank in rank_summaries)
    bulk_npu = bulk["prefill_npu"]
    reuse_npu = reuse["prefill_npu"]
    lines = [
        "# Test 2 load timing summary",
        "",
        "## Throughput context",
        "",
        "- BULK formal: 100/100, 0.2292 req/s, 436371.9513 ms.",
        "- REUSE3 formal: 100/100, 0.0855 req/s, 1170183.1656 ms.",
        "- REUSE3/BULK: 0.3730x.",
        "",
        "## Instrumentation summary",
        "",
        f"- BULK Prefill TP0 whole-key gets: {bulk_prefill_rank['get_count']}; total {bulk_prefill_rank['duration_us']['sum'] / 1_000_000:.3f} s. Decode gets: {bulk_decode_rank['get_count']}; total {bulk_decode_rank['duration_us']['sum'] / 1_000_000:.3f} s.",
        f"- REUSE3 Prefill active steps: {reuse_prefill['active_step_count']}; TP0 request calls: {reuse_rank['request_call_count_total']}; TP0 transfer time: {reuse_rank['batch_copy_get_us_total'] / 1_000_000:.3f} s.",
        f"- REUSE3 Decode active steps: {reuse_decode['active_step_count']}; TP0 request calls: {reuse_decode_rank['request_call_count_total']}; TP0 transfer time: {reuse_decode_rank['batch_copy_get_us_total'] / 1_000_000:.3f} s.",
        f"- REUSE3 TP0 mean `batch_copy_get` call: {reuse_rank['mean_batch_copy_get_call_us'] / 1000:.3f} ms.",
        f"- REUSE3 Prefill critical model wait total: {reuse_prefill['critical_model_wait_us_total'] / 1_000_000:.3f} s; Decode: {reuse_decode['critical_model_wait_us_total'] / 1_000_000:.3f} s.",
        f"- REUSE3 worst-rank address build total: {worst_address_us / 1_000_000:.3f} s; save gate total: {worst_save_gate_us / 1_000_000:.3f} s; attention gate total: {worst_attention_gate_us / 1_000_000:.3f} s.",
        f"- Model critical wait is {reuse_prefill['critical_model_wait_us_total'] / prefill_iteration_us * 100:.1f}% of summed Prefill context iteration time.",
        "",
        "## Mooncake versus orchestration",
        "",
        f"- BULK Prefill TP0 effective load bandwidth: {decimal_gbps(bulk_bytes, bulk_duration_us):.3f} GB/s.",
        f"- REUSE3 Prefill TP0 effective `batch_copy_get` bandwidth: {decimal_gbps(reuse_bytes, reuse_duration_us):.3f} GB/s.",
        f"- REUSE3 transferred {reuse_bytes / bulk_bytes:.2f}x BULK Prefill bytes and issued {reuse_rank['request_call_count_total'] / bulk_prefill_rank['get_count']:.1f}x as many request-scoped calls.",
        "- Layers 1-25 each issued exactly 2,500 TP0 request calls: 100 requests x 25 chunks. Layers 0 and 26 issued 100 calls each.",
        "",
        "## Scaling by requests in one chunk step",
        "",
        f"- 40-call steps: {forty['step_count']}; median transfer per TP/step {forty['batch_copy_get_us_per_tp_step']['p50'] / 1_000_000:.3f} s; median critical model wait {forty['critical_model_wait_us']['p50'] / 1_000_000:.3f} s; median bytes per TP/step {mib(forty['requested_bytes_per_tp_step']['p50']):.1f} MiB.",
        f"- 20-call steps: {twenty['step_count']}; median transfer per TP/step {twenty['batch_copy_get_us_per_tp_step']['p50'] / 1_000_000:.3f} s; median critical model wait {twenty['critical_model_wait_us']['p50'] / 1_000_000:.3f} s; median bytes per TP/step {mib(twenty['requested_bytes_per_tp_step']['p50']):.1f} MiB.",
        "",
        "## Prefill NPU samples",
        "",
        f"- BULK NPU 2/3 mean AICore: {bulk_npu['2']['aicore_percent']['mean']:.1f}% / {bulk_npu['3']['aicore_percent']['mean']:.1f}%.",
        f"- REUSE3 NPU 2/3 mean AICore: {reuse_npu['2']['aicore_percent']['mean']:.1f}% / {reuse_npu['3']['aicore_percent']['mean']:.1f}%.",
        "",
        "## Formal errors",
        "",
        f"- BULK matching error lines: {len(bulk['formal_error_lines'])}.",
        f"- REUSE3 matching error lines: {len(reuse['formal_error_lines'])}.",
        f"- BULK first-hit validation: {bulk['prefill_hit_summary']['requests_with_first_hit_28800']}/{bulk['prefill_hit_summary']['unique_request_count']} requests at 28,800 tokens.",
        f"- REUSE3 first-hit validation: {reuse['prefill_hit_summary']['requests_with_first_hit_28800']}/{reuse['prefill_hit_summary']['unique_request_count']} requests at 28,800 tokens.",
    ]
    (analysis_dir / "load-timing-summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
