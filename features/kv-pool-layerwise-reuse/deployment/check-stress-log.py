#!/usr/bin/env python3
"""Fail-closed log and topology checker for the KVPool stress profile."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PREFIX = "[KVPOOL_RANGE_DEBUG]"
RANGE_FIELDS = {"event", "direction", "layer_id", "key_count", "requested_bytes", "sizes", "object_offsets", "results"}
COMMIT_FIELDS = {"event", "layer_id", "key_count", "results"}
WHOLE_KEY_FIELDS = {"event", "direction", "key_count"}
ITERATION_RE = re.compile(
    r"Iteration\((?P<iteration>\d+)\):\s*(?P<context_requests>\d+) context requests,\s*"
    r"(?P<context_tokens>\d+) context tokens,\s*(?P<generation_requests>\d+) generation requests,\s*"
    r"(?P<generation_tokens>\d+) generation tokens, iteration elapsed time:\s*(?P<elapsed>[0-9.]+) ms(?P<dummy>\s*\(dummy\))?"
)
DP_RE = re.compile(r"EngineCore_DP(?P<rank>\d+)")


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def read(path: Path, label: str, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except Exception as exc:
        errors.append(f"{label}: cannot read {path}: {exc}")
        return ""


def parse_log(path: Path, role: str, errors: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    text = read(path, role, errors)
    events: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if PREFIX in line:
            encoded = line.split(PREFIX, 1)[1].strip()
            try:
                event = json.loads(encoded)
                if not isinstance(event, dict):
                    raise ValueError("event is not an object")
                event["_line"] = number
                events.append(event)
            except Exception as exc:
                errors.append(f"{role}:{number}: malformed range event: {exc}")
        if "Iteration(" in line:
            match = ITERATION_RE.search(line)
            if not match:
                errors.append(f"{role}:{number}: malformed iteration line")
                continue
            rank_match = DP_RE.search(line)
            iterations.append(
                {
                    "line": number,
                    "rank": int(rank_match.group("rank")) if rank_match else None,
                    "context_requests": int(match.group("context_requests")),
                    "context_tokens": int(match.group("context_tokens")),
                    "generation_requests": int(match.group("generation_requests")),
                    "generation_tokens": int(match.group("generation_tokens")),
                    "dummy": bool(match.group("dummy")),
                }
            )
    return events, iterations, text


def validate_range_event(event: dict[str, Any], role: str, layers: int, errors: list[str]) -> None:
    line = event["_line"]
    fields = set(event) - {"_line"}
    if fields != RANGE_FIELDS:
        errors.append(f"{role}:{line}: range fields mismatch: missing={sorted(RANGE_FIELDS-fields)} extra={sorted(fields-RANGE_FIELDS)}")
        return
    allowed_directions = {"save", "load"} if role == "prefill" else {"load"}
    if event["direction"] not in allowed_directions:
        errors.append(
            f"{role}:{line}: expected direction in {sorted(allowed_directions)}, "
            f"got {event['direction']!r}"
        )
    if not is_int(event["layer_id"]) or not 0 <= event["layer_id"] < layers:
        errors.append(f"{role}:{line}: invalid layer_id={event['layer_id']!r}")
    count = event["key_count"]
    if not is_int(count) or count <= 0:
        errors.append(f"{role}:{line}: invalid key_count={count!r}")
        return
    vectors = [event[name] for name in ("requested_bytes", "sizes", "object_offsets", "results")]
    if any(not isinstance(vector, list) or len(vector) != count for vector in vectors):
        errors.append(f"{role}:{line}: all vector lengths must equal key_count={count}")
        return
    requested, sizes, offsets, results = vectors
    for index in range(count):
        if not isinstance(sizes[index], list) or not isinstance(offsets[index], list) or not sizes[index] or len(sizes[index]) != len(offsets[index]):
            errors.append(f"{role}:{line}: invalid fragment shape at key {index}")
            continue
        if not all(is_int(value) and value >= 0 for value in sizes[index] + offsets[index]):
            errors.append(f"{role}:{line}: fragment sizes/offsets must be non-negative integers at key {index}")
            continue
        if not is_int(requested[index]) or requested[index] != sum(sizes[index]):
            errors.append(f"{role}:{line}: requested byte mismatch at key {index}")
        if not is_int(results[index]) or results[index] < 0:
            errors.append(f"{role}:{line}: invalid negative/non-integer result at key {index}")
        elif results[index] != requested[index]:
            errors.append(f"{role}:{line}: result byte mismatch at key {index}")


def validate_events(events: list[dict[str, Any]], role: str, layers: int, errors: list[str]) -> dict[str, Any]:
    ranges, commits, whole = [], [], []
    for event in events:
        kind = event.get("event")
        if kind == "range":
            validate_range_event(event, role, layers, errors)
            ranges.append(event)
        elif kind == "commit":
            commits.append(event)
        elif kind == "whole_key":
            whole.append(event)
        else:
            errors.append(f"{role}:{event['_line']}: unknown event={kind!r}")
    actual_layers = {event.get("layer_id") for event in ranges if is_int(event.get("layer_id"))}
    direction_layers = {
        direction: {
            event.get("layer_id")
            for event in ranges
            if event.get("direction") == direction and is_int(event.get("layer_id"))
        }
        for direction in ("save", "load")
    }
    required_directions = ("save", "load") if role == "prefill" else ("load",)
    for direction in required_directions:
        if direction_layers[direction] != set(range(layers)):
            errors.append(
                f"{role}: {direction} layer set mismatch: "
                f"expected={list(range(layers))} "
                f"actual={sorted(direction_layers[direction])}"
            )
    if whole:
        errors.append(f"{role}: whole-key event count must be zero, got {len(whole)}")
    for event in whole:
        if set(event) - {"_line"} != WHOLE_KEY_FIELDS or event.get("direction") not in {"put", "get"}:
            errors.append(f"{role}:{event['_line']}: malformed whole-key event")
    if role == "decode" and commits:
        errors.append(f"decode: commit event count must be zero, got {len(commits)}")
    committed_key_count = 0
    if role == "prefill":
        if not commits:
            errors.append("prefill: successful final commit is missing")
        for event in commits:
            if set(event) - {"_line"} != COMMIT_FIELDS:
                errors.append(f"prefill:{event['_line']}: commit fields mismatch")
                continue
            count, results = event.get("key_count"), event.get("results")
            if event.get("layer_id") != layers - 1:
                errors.append(f"prefill:{event['_line']}: commit is not on final layer")
            if not is_int(count) or count <= 0 or not isinstance(results, list) or len(results) != count or not all(is_int(value) and value == 0 for value in results):
                errors.append(f"prefill:{event['_line']}: commit result is not successful")
            else:
                committed_key_count += count
            preceding = [item for item in ranges if item["_line"] < event["_line"]]
            if (
                not preceding
                or preceding[-1].get("direction") != "save"
                or preceding[-1].get("layer_id") != layers - 1
            ):
                errors.append(f"prefill:{event['_line']}: commit does not immediately follow a final-layer save")
    return {"event_count": len(events), "range_event_count": len(ranges), "range_layers": sorted(actual_layers), "save_layers": sorted(direction_layers["save"]), "load_layers": sorted(direction_layers["load"]), "commit_event_count": len(commits), "committed_key_count": committed_key_count, "whole_key_event_count": len(whole)}


def real_context(iterations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in iterations if not item["dummy"] and item["context_requests"] > 0]


def validate_iteration_budget(items: list[dict[str, Any]], maximum: int, role: str, errors: list[str]) -> None:
    if not items:
        errors.append(f"{role}: non-dummy context iteration evidence is missing")
    for item in items:
        if item["context_tokens"] > maximum:
            errors.append(f"{role}:{item['line']}: context tokens {item['context_tokens']} exceed {maximum}")
        if item["rank"] is None:
            errors.append(f"{role}:{item['line']}: context iteration lacks EngineCore_DP rank")


def output(path: Path, mode: str, checks: dict[str, Any], errors: list[str]) -> int:
    summary = {"schema_version": 1, "mode": mode, "status": "failed" if errors else "passed", "validated": not errors, "checks": checks, "errors": errors}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 1 if errors else 0


def topology(args: argparse.Namespace) -> int:
    errors: list[str] = []
    prefill_log = read(args.prefill_log, "prefill log", errors)
    decode_log = read(args.decode_log, "decode log", errors)
    prefill_yaml = read(args.prefill_pod_yaml, "prefill Pod YAML", errors)
    decode_yaml = read(args.decode_pod_yaml, "decode Pod YAML", errors)
    prefill_ps = read(args.prefill_ps, "prefill ps", errors)
    decode_ps = read(args.decode_ps, "decode ps", errors)
    prefill_npu = read(args.prefill_npu_info, "prefill npu info", errors)
    decode_npu = read(args.decode_npu_info, "decode npu info", errors)
    npu_process_re = re.compile(
        r"(?m)^\|\s*(?P<device>\d+)\s+\d+\s+\|\s+\d+\s+\|\s+(?P<name>\S+)",
        re.I,
    )
    prefill_devices = {match.group("device") for match in npu_process_re.finditer(prefill_npu)}
    decode_devices = {match.group("device") for match in npu_process_re.finditer(decode_npu)}
    required = {
        "prefill DP=2": any(token in prefill_log for token in ("data_parallel_size=2", "data-parallel-size 2", "data_parallel_size': 2")),
        "prefill TP=2": any(token in prefill_log for token in ("tensor_parallel_size=2", "tensor-parallel-size 2", "tensor_parallel_size': 2")),
        "decode DP=1": any(token in decode_log for token in ("data_parallel_size=1", "data-parallel-size 1", "data_parallel_size': 1")),
        "decode TP=2": any(token in decode_log for token in ("tensor_parallel_size=2", "tensor-parallel-size 2", "tensor_parallel_size': 2")),
        "prefill allocation=4": len(re.findall(r"huawei\.com/Ascend910:\s*[\"']?4", prefill_yaml)) >= 2,
        "decode allocation=2": len(re.findall(r"huawei\.com/Ascend910:\s*[\"']?2", decode_yaml)) >= 2,
        "prefill DP0 process": "DP0" in prefill_ps,
        "prefill DP1 process": "DP1" in prefill_ps,
        "prefill active devices>=4": len(prefill_devices) >= 4,
        "decode active devices>=2": len(decode_devices) >= 2,
    }
    errors.extend(f"topology check failed: {name}" for name, passed in required.items() if not passed)
    return output(args.output, "topology", required, errors)


def pinned(args: argparse.Namespace) -> int:
    errors: list[str] = []
    prefill_events, prefill_iterations, prefill_text = parse_log(args.prefill_log_window, "prefill", errors)
    decode_events, _, decode_text = parse_log(args.decode_log_window, "decode", errors)
    context = real_context(prefill_iterations)
    validate_iteration_budget(context, args.max_context_tokens, "prefill", errors)
    ranks = {item["rank"] for item in context}
    if ranks != {args.expected_prefill_dp_rank}:
        errors.append(f"prefill: active DP ranks expected [{args.expected_prefill_dp_rank}], got {sorted(rank for rank in ranks if rank is not None)}")
    if len(context) < args.min_context_iterations:
        errors.append(f"prefill: expected at least {args.min_context_iterations} context iterations, got {len(context)}")
    context_sum = sum(item["context_tokens"] for item in context)
    if context_sum != args.expected_prompt_tokens:
        errors.append(f"prefill: context token sum expected {args.expected_prompt_tokens}, got {context_sum}")
    blocks = args.expected_hit_tokens // 128
    if f"hit_blocks=0/{blocks}" not in prefill_text:
        errors.append(f"prefill: cold lookup evidence hit_blocks=0/{blocks} is missing")
    if f"kvpool hit tokens: {args.expected_hit_tokens}" not in decode_text:
        errors.append(f"decode: expected hit-token evidence {args.expected_hit_tokens} is missing")
    checks = {
        "expected_prefill_dp_rank": args.expected_prefill_dp_rank,
        "active_prefill_dp_ranks": sorted(rank for rank in ranks if rank is not None),
        "context_iteration_count": len(context),
        "context_token_sum": context_sum,
        "max_context_tokens_seen": max((item["context_tokens"] for item in context), default=0),
        "prefill_ranges": validate_events(prefill_events, "prefill", args.num_layers, errors),
        "decode_ranges": validate_events(decode_events, "decode", args.num_layers, errors),
    }
    if checks["prefill_ranges"]["committed_key_count"] != blocks:
        errors.append(
            f"prefill: committed key count expected {blocks}, got "
            f"{checks['prefill_ranges']['committed_key_count']}"
        )
    return output(args.output, "pinned", checks, errors)


def aggregate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    prefill_events, prefill_iterations, _ = parse_log(args.prefill_log_window, "prefill", errors)
    decode_events, _, _ = parse_log(args.decode_log_window, "decode", errors)
    context = real_context(prefill_iterations)
    validate_iteration_budget(context, args.max_context_tokens, "prefill", errors)
    ranks = {item["rank"] for item in context if item["rank"] is not None}
    required = {int(item) for item in args.required_prefill_dp_ranks.split(",") if item != ""}
    if not required.issubset(ranks):
        errors.append(f"prefill: required DP ranks {sorted(required)}, observed {sorted(ranks)}")
    checks = {
        "required_prefill_dp_ranks": sorted(required),
        "active_prefill_dp_ranks": sorted(ranks),
        "context_iteration_count": len(context),
        "max_context_tokens_seen": max((item["context_tokens"] for item in context), default=0),
        "prefill_ranges": validate_events(prefill_events, "prefill", args.num_layers, errors),
        "decode_ranges": validate_events(decode_events, "decode", args.num_layers, errors),
    }
    return output(args.output, "aggregate", checks, errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    top = sub.add_parser("topology")
    for name in ("prefill_log", "decode_log", "prefill_pod_yaml", "decode_pod_yaml", "prefill_ps", "decode_ps", "prefill_npu_info", "decode_npu_info"):
        top.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    top.add_argument("--output", type=Path, required=True)
    pin = sub.add_parser("pinned")
    pin.add_argument("--prefill-log-window", type=Path, required=True)
    pin.add_argument("--decode-log-window", type=Path, required=True)
    pin.add_argument("--expected-prefill-dp-rank", type=int, required=True)
    pin.add_argument("--expected-prompt-tokens", type=int, required=True)
    pin.add_argument("--expected-hit-tokens", type=int, required=True)
    pin.add_argument("--min-context-iterations", type=int, required=True)
    pin.add_argument("--max-context-tokens", type=int, default=1024)
    pin.add_argument("--num-layers", type=int, default=27)
    pin.add_argument("--output", type=Path, required=True)
    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument("--prefill-log-window", type=Path, required=True)
    aggregate_parser.add_argument("--decode-log-window", type=Path, required=True)
    aggregate_parser.add_argument("--required-prefill-dp-ranks", required=True)
    aggregate_parser.add_argument("--max-context-tokens", type=int, default=1024)
    aggregate_parser.add_argument("--num-layers", type=int, default=27)
    aggregate_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return {"topology": topology, "pinned": pinned, "aggregate": aggregate}[args.mode](args)


if __name__ == "__main__":
    sys.exit(main())
