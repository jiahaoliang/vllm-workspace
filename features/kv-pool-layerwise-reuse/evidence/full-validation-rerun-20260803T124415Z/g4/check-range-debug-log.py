#!/usr/bin/env python3
"""Fail-closed validation for one clean KVPool range-debug request window."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PREFIX = "[KVPOOL_RANGE_DEBUG]"
RANGE_FIELDS = {
    "event",
    "direction",
    "layer_id",
    "key_count",
    "requested_bytes",
    "sizes",
    "object_offsets",
    "results",
}
COMMIT_FIELDS = {"event", "layer_id", "key_count", "results"}
WHOLE_KEY_FIELDS = {"event", "direction", "key_count"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefill-log", type=Path, required=True)
    parser.add_argument("--decode-log", type=Path, required=True)
    parser.add_argument("--num-layers", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_events(path: Path, role: str, errors: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except Exception as exc:
        errors.append(f"{role}: cannot read log: {exc}")
        return events

    for line_number, line in enumerate(lines, 1):
        if PREFIX not in line:
            continue
        encoded = line.split(PREFIX, 1)[1].strip()
        try:
            event = json.loads(encoded)
        except Exception as exc:
            errors.append(f"{role}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"{role}:{line_number}: event must be a JSON object")
            continue
        event["_line"] = line_number
        events.append(event)
    return events


def validate_range(
    event: dict[str, Any],
    role: str,
    num_layers: int,
    errors: list[str],
) -> None:
    line = event["_line"]
    fields = set(event) - {"_line"}
    if fields != RANGE_FIELDS:
        errors.append(
            f"{role}:{line}: range fields mismatch: "
            f"missing={sorted(RANGE_FIELDS - fields)} extra={sorted(fields - RANGE_FIELDS)}"
        )
        return

    expected_direction = "save" if role == "prefill" else "load"
    if event["direction"] != expected_direction:
        errors.append(
            f"{role}:{line}: expected direction={expected_direction}, "
            f"got {event['direction']!r}"
        )

    layer_id = event["layer_id"]
    if not is_int(layer_id) or not 0 <= layer_id < num_layers:
        errors.append(f"{role}:{line}: invalid layer_id={layer_id!r}")

    key_count = event["key_count"]
    if not is_int(key_count) or key_count <= 0:
        errors.append(f"{role}:{line}: invalid key_count={key_count!r}")
        return

    requested = event["requested_bytes"]
    sizes = event["sizes"]
    offsets = event["object_offsets"]
    results = event["results"]
    vectors = {
        "requested_bytes": requested,
        "sizes": sizes,
        "object_offsets": offsets,
        "results": results,
    }
    for name, vector in vectors.items():
        if not isinstance(vector, list) or len(vector) != key_count:
            errors.append(
                f"{role}:{line}: len({name}) must equal key_count={key_count}"
            )
            return

    for index in range(key_count):
        key_sizes = sizes[index]
        key_offsets = offsets[index]
        if not isinstance(key_sizes, list) or not isinstance(key_offsets, list):
            errors.append(f"{role}:{line}: sizes/offsets[{index}] must be lists")
            continue
        if not key_sizes or len(key_sizes) != len(key_offsets):
            errors.append(
                f"{role}:{line}: fragment shape mismatch for key index {index}"
            )
            continue
        if not all(is_int(value) and value >= 0 for value in key_sizes):
            errors.append(f"{role}:{line}: invalid sizes for key index {index}")
            continue
        if not all(is_int(value) and value >= 0 for value in key_offsets):
            errors.append(
                f"{role}:{line}: invalid object_offsets for key index {index}"
            )
            continue
        if not is_int(requested[index]) or requested[index] != sum(key_sizes):
            errors.append(
                f"{role}:{line}: requested_bytes[{index}] does not equal fragment sum"
            )
        if not is_int(results[index]) or results[index] < 0:
            errors.append(
                f"{role}:{line}: negative or invalid result for key index {index}"
            )
        elif results[index] != requested[index]:
            errors.append(
                f"{role}:{line}: results[{index}] does not equal requested_bytes[{index}]"
            )


def validate_events(
    events: list[dict[str, Any]],
    role: str,
    num_layers: int,
    errors: list[str],
) -> dict[str, Any]:
    range_events: list[dict[str, Any]] = []
    commit_events: list[dict[str, Any]] = []
    whole_key_events: list[dict[str, Any]] = []
    for event in events:
        event_type = event.get("event")
        if event_type == "range":
            validate_range(event, role, num_layers, errors)
            range_events.append(event)
        elif event_type == "commit":
            commit_events.append(event)
        elif event_type == "whole_key":
            whole_key_events.append(event)
        else:
            errors.append(
                f"{role}:{event['_line']}: unknown or missing event={event_type!r}"
            )

    layers = {
        event["layer_id"] for event in range_events if is_int(event.get("layer_id"))
    }
    expected_layers = set(range(num_layers))
    if layers != expected_layers:
        errors.append(
            f"{role}: layer set mismatch: expected={sorted(expected_layers)} "
            f"actual={sorted(layers)}"
        )
    if not range_events:
        errors.append(f"{role}: range event set is empty")

    if whole_key_events:
        errors.append(f"{role}: whole_key event count must be 0")
    for event in whole_key_events:
        fields = set(event) - {"_line"}
        if fields != WHOLE_KEY_FIELDS or event.get("direction") not in {"put", "get"}:
            errors.append(f"{role}:{event['_line']}: invalid whole_key event")

    if role == "decode" and commit_events:
        errors.append("decode: commit event count must be 0")
    if role == "prefill":
        if not commit_events:
            errors.append("prefill: successful final-layer commit event is missing")
        for event in commit_events:
            fields = set(event) - {"_line"}
            if fields != COMMIT_FIELDS:
                errors.append(f"prefill:{event['_line']}: commit fields mismatch")
                continue
            key_count = event["key_count"]
            results = event["results"]
            if event["layer_id"] != num_layers - 1:
                errors.append(f"prefill:{event['_line']}: commit is not on final layer")
            if (
                not is_int(key_count)
                or key_count <= 0
                or not isinstance(results, list)
                or len(results) != key_count
                or not all(is_int(result) and result == 0 for result in results)
            ):
                errors.append(
                    f"prefill:{event['_line']}: commit results are not successful"
                )
        if range_events and commit_events:
            last_save_line = max(event["_line"] for event in range_events)
            last_commit_line = max(event["_line"] for event in commit_events)
            if last_commit_line <= last_save_line:
                errors.append(
                    "prefill: final commit does not follow the last ranged save"
                )

    return {
        "event_count": len(events),
        "range_event_count": len(range_events),
        "range_layers": sorted(layers),
        "commit_event_count": len(commit_events),
        "whole_key_event_count": len(whole_key_events),
    }


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    if args.num_layers <= 0:
        errors.append(f"num_layers must be positive, got {args.num_layers}")

    prefill_events = parse_events(args.prefill_log, "prefill", errors)
    decode_events = parse_events(args.decode_log, "decode", errors)
    prefill_summary = validate_events(
        prefill_events, "prefill", args.num_layers, errors
    )
    decode_summary = validate_events(decode_events, "decode", args.num_layers, errors)
    summary = {
        "schema_version": 1,
        "status": "failed" if errors else "passed",
        "num_layers": args.num_layers,
        "prefill": prefill_summary,
        "decode": decode_summary,
        "errors": errors,
    }
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
