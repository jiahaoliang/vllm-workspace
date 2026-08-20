#!/usr/bin/env python3
from __future__ import annotations

import csv
import glob
import json
import math
import re
import sqlite3
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path


ROOT = Path("/tmp/layerwise-issue1-profile-mstx-20260819T184617+0800")
POINTS = (
    "bulk-c1",
    "reuse3-c1",
    "bulk-c20",
    "reuse3-c20",
    "bulk-c20-stable",
    "reuse3-c20-stable",
)
MESSAGE_RE = re.compile(r"([a-z_]+)=([^ ]+)")
DEBUG_PREFIX = "[DEBUG-REUSE3-LOAD] "


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "total": sum(values),
        "mean": sum(values) / len(values) if values else None,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def overlap_ns(merged: list[tuple[int, int]], start: int, end: int) -> int:
    if end <= start or not merged:
        return 0
    starts = [item[0] for item in merged]
    index = max(0, bisect_left(starts, start) - 1)
    total = 0
    while index < len(merged) and merged[index][0] < end:
        left, right = merged[index]
        total += max(0, min(end, right) - max(start, left))
        index += 1
    return total


def parse_message(message: str) -> dict[str, str]:
    return dict(MESSAGE_RE.findall(message))


def rank_from_path(path: Path) -> int:
    match = re.search(r"_rank(\d+)_", str(path))
    if not match:
        raise ValueError(path)
    return int(match.group(1))


def read_step_trace(output: Path) -> dict[str, float | str]:
    with (output / "step_trace_time.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    result: dict[str, float | str] = {}
    for key, value in row.items():
        try:
            result[key] = float(value)
        except (TypeError, ValueError):
            result[key] = value
    stage = float(result["Stage"])
    result["Computing_pct"] = 100 * float(result["Computing"]) / stage
    result["Communication_not_overlapped_pct"] = (
        100 * float(result["Communication(Not Overlapped)"]) / stage
    )
    result["Free_pct"] = 100 * float(result["Free"]) / stage
    return result


def read_kernel_summary(output: Path) -> dict[str, object]:
    durations: dict[str, list[float]] = defaultdict(list)
    with (output / "kernel_details.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                durations[row["Accelerator Core"]].append(float(row["Duration(us)"]))
            except (KeyError, ValueError):
                pass
    return {core: summarize(values) for core, values in sorted(durations.items())}


def read_ranges(output: Path) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
    db_path = next(output.glob("ascend_pytorch_profiler_*.db"))
    connection = sqlite3.connect(db_path)
    tasks = merge_intervals(
        [(int(start), int(end)) for start, end in connection.execute(
            "SELECT startNs, endNs FROM TASK WHERE endNs > startNs"
        )]
    )
    rows = connection.execute(
        """
        SELECT e.startNs, e.endNs, s.value
        FROM MSTX_EVENTS e
        JOIN STRING_IDS s ON s.id = e.message
        WHERE s.value LIKE 'domain=kvpool_load%'
        ORDER BY e.startNs
        """
    ).fetchall()
    connection.close()

    ranges: list[dict[str, object]] = []
    for start, end, message in rows:
        attrs = parse_message(message)
        duration = max(0, int(end) - int(start))
        busy = overlap_ns(tasks, int(start), int(end)) if duration else 0
        ranges.append(
            {
                **attrs,
                "start_ns": int(start),
                "end_ns": int(end),
                "duration_us": duration / 1000,
                "npu_busy_overlap_us": busy / 1000,
                "npu_idle_overlap_us": (duration - busy) / 1000,
            }
        )
    return ranges, tasks


def range_summary(ranges: list[dict[str, object]]) -> dict[str, object]:
    by_stage: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in ranges:
        by_stage[str(item.get("stage"))].append(item)
    result: dict[str, object] = {}
    for stage, items in sorted(by_stage.items()):
        durations = [float(item["duration_us"]) for item in items]
        busy = sum(float(item["npu_busy_overlap_us"]) for item in items)
        idle = sum(float(item["npu_idle_overlap_us"]) for item in items)
        entry = summarize(durations)
        entry.update(
            {
                "npu_busy_overlap_us": busy,
                "npu_idle_overlap_us": idle,
                "npu_idle_overlap_pct": 100 * idle / (busy + idle) if busy + idle else None,
            }
        )
        if stage == "dequeue":
            entry["queue_wait_us"] = summarize(
                [float(item["queue_wait_us"]) for item in items if "queue_wait_us" in item]
            )
        result[stage] = entry
    return result


def step_summary(ranges: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for item in ranges:
        if "step_id" not in item:
            continue
        grouped[(int(item["step_id"]), str(item.get("stage")))].append(item)
    result: dict[str, dict[str, object]] = defaultdict(dict)
    for (step_id, stage), items in sorted(grouped.items()):
        durations = [float(item["duration_us"]) for item in items]
        busy = sum(float(item["npu_busy_overlap_us"]) for item in items)
        idle = sum(float(item["npu_idle_overlap_us"]) for item in items)
        result[str(step_id)][stage] = {
            "count": len(items),
            "total_us": sum(durations),
            "max_us": max(durations),
            "npu_busy_overlap_us": busy,
            "npu_idle_overlap_us": idle,
            "npu_idle_overlap_pct": 100 * idle / (busy + idle) if busy + idle else None,
        }
        if stage == "dequeue":
            waits = [float(item["queue_wait_us"]) for item in items if "queue_wait_us" in item]
            result[str(step_id)][stage]["queue_wait_us"] = summarize(waits)
    return dict(result)


def read_debug_events(log_path: Path, traced_steps: dict[int, set[int]]) -> dict[str, object]:
    by_rank_stage: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    with log_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if DEBUG_PREFIX not in line:
                continue
            try:
                item = json.loads(line.split(DEBUG_PREFIX, 1)[1])
                rank = int(item["tp_rank"])
                step = int(item["step_id"])
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
            if step not in traced_steps.get(rank, set()):
                continue
            by_rank_stage[(rank, str(item["stage"]))].append(item)

    result: dict[str, dict[str, object]] = defaultdict(dict)
    numeric_fields = (
        "duration_us",
        "queue_wait_us",
        "preparation_us",
        "address_build_us",
        "save_gate_us",
        "attention_gate_us",
        "batch_copy_get_us",
        "requested_bytes",
        "key_count",
        "request_call_count",
    )
    for (rank, stage), items in sorted(by_rank_stage.items()):
        entry: dict[str, object] = {"count": len(items)}
        for field in numeric_fields:
            values = [float(item[field]) for item in items if isinstance(item.get(field), (int, float))]
            if values:
                entry[field] = summarize(values)
        result[str(rank)][stage] = entry
    return dict(result)


def te_summary(log_path: Path) -> dict[str, object]:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    read_rates = [float(value) for value in re.findall(r"Average Read Throughput: ([0-9.]+) MB/s", text)]
    write_rates = [float(value) for value in re.findall(r"Average Write Throughput: ([0-9.]+) MB/s", text)]
    batch_counts = [int(value) for value in re.findall(r"Batch Get: count=(\d+)", text)]
    return {
        "average_read_MBps_nonzero": summarize([value for value in read_rates if value > 0]),
        "average_write_MBps_nonzero": summarize([value for value in write_rates if value > 0]),
        "batch_get_count_reports": summarize([float(value) for value in batch_counts]),
    }


def write_layer_timeline(point: str) -> None:
    point_dir = ROOT / "points" / point
    debug: dict[tuple[int, int, int, str], dict[str, object]] = {}
    with (point_dir / "vllm-prefill.log").open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if DEBUG_PREFIX not in line:
                continue
            try:
                item = json.loads(line.split(DEBUG_PREFIX, 1)[1])
                key = (
                    int(item["tp_rank"]),
                    int(item["step_id"]),
                    int(item["layer_id"]),
                    str(item["stage"]),
                )
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
            debug[key] = item

    ranges: dict[tuple[int, int, int, str], dict[str, object]] = {}
    traced_steps: dict[int, set[int]] = {}
    for output in sorted(point_dir.glob("profile/*/ASCEND_PROFILER_OUTPUT")):
        rank = rank_from_path(output)
        items, _ = read_ranges(output)
        traced_steps[rank] = {
            int(item["step_id"]) for item in items if "step_id" in item
        }
        for item in items:
            if "step_id" not in item or "layer_id" not in item:
                continue
            ranges[(rank, int(item["step_id"]), int(item["layer_id"]), str(item["stage"]))] = item

    keys = sorted(
        {
            (rank, step, layer)
            for rank, step, layer, _ in ranges
            if step in traced_steps.get(rank, set()) and layer >= 0
        }
    )
    fields = [
        "tp_rank",
        "step_id",
        "layer_id",
        "queue_wait_us",
        "address_build_us",
        "address_npu_idle_us",
        "address_npu_idle_pct",
        "batch_copy_get_us",
        "copy_npu_idle_us",
        "copy_npu_idle_pct",
        "layer_task_us",
        "layer_task_npu_idle_us",
        "layer_task_npu_idle_pct",
        "model_wait_us",
        "model_wait_npu_idle_us",
        "model_wait_npu_idle_pct",
        "debug_batch_copy_get_us",
        "request_call_count",
        "key_count",
    ]

    def range_values(item: dict[str, object] | None) -> tuple[object, object, object]:
        if not item:
            return "", "", ""
        duration = float(item["duration_us"])
        idle = float(item["npu_idle_overlap_us"])
        return duration, idle, 100 * idle / duration if duration else ""

    destination = ROOT / "analysis" / f"{point}-layer-timeline.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, step, layer in keys:
            dequeue = ranges.get((rank, step, layer, "dequeue"), {})
            address = range_values(ranges.get((rank, step, layer, "address_build")))
            copy = range_values(ranges.get((rank, step, layer, "batch_copy_get")))
            task = range_values(ranges.get((rank, step, layer, "layer_task_total")))
            wait = range_values(ranges.get((rank, step, layer, "model_wait")))
            layer_debug = debug.get((rank, step, layer, "layer_task"), {})
            writer.writerow(
                {
                    "tp_rank": rank,
                    "step_id": step,
                    "layer_id": layer,
                    "queue_wait_us": dequeue.get("queue_wait_us", ""),
                    "address_build_us": address[0],
                    "address_npu_idle_us": address[1],
                    "address_npu_idle_pct": address[2],
                    "batch_copy_get_us": copy[0],
                    "copy_npu_idle_us": copy[1],
                    "copy_npu_idle_pct": copy[2],
                    "layer_task_us": task[0],
                    "layer_task_npu_idle_us": task[1],
                    "layer_task_npu_idle_pct": task[2],
                    "model_wait_us": wait[0],
                    "model_wait_npu_idle_us": wait[1],
                    "model_wait_npu_idle_pct": wait[2],
                    "debug_batch_copy_get_us": layer_debug.get("batch_copy_get_us", ""),
                    "request_call_count": layer_debug.get("request_call_count", ""),
                    "key_count": layer_debug.get("key_count", ""),
                }
            )


def analyze_point(point: str) -> dict[str, object]:
    point_dir = ROOT / "points" / point
    outputs = sorted(point_dir.glob("profile/*/ASCEND_PROFILER_OUTPUT"))
    ranks: dict[str, object] = {}
    traced_steps: dict[int, set[int]] = {}
    for output in outputs:
        rank = rank_from_path(output)
        ranges, _ = read_ranges(output)
        traced_steps[rank] = {
            int(item["step_id"]) for item in ranges if "step_id" in item
        }
        ranks[str(rank)] = {
            "step_trace": read_step_trace(output),
            "kernel": read_kernel_summary(output),
            "ranges": range_summary(ranges),
            "steps": step_summary(ranges),
            "trace_steps": sorted(traced_steps[rank]),
        }
    wave = json.loads((point_dir / "wave.json").read_text(encoding="utf-8"))
    log_path = point_dir / "vllm-prefill.log"
    return {
        "wave_elapsed_ms": wave["elapsed_ms"],
        "wave_count": wave["count"],
        "wave_valid": wave["valid"],
        "exact_initial_external_hit_count": sum(
            1
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if "Total tokens 32000, kvpool hit tokens: 28800, need to load: 28800" in line
        ),
        "ranks": ranks,
        "debug_events_for_trace_steps": read_debug_events(log_path, traced_steps),
        "te_metrics": te_summary(log_path),
    }


def main() -> None:
    summary = {point: analyze_point(point) for point in POINTS}
    destination = ROOT / "analysis" / "summary.json"
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_layer_timeline("reuse3-c1")
    write_layer_timeline("reuse3-c20-stable")
    print(destination)


if __name__ == "__main__":
    main()
