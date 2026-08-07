#!/usr/bin/env python3
"""Validate one G4 runtime-audit evidence directory."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


PREFIX = "[KVPOOL_RANGE_DEBUG]"
NUM_LAYERS = 27
KEY_COUNT = 4


def _events(log: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.split(PREFIX, 1)[1].strip())
        for line in log.splitlines()
        if PREFIX in line
    ]


def _metric(path: Path, name: str) -> float:
    match = re.search(
        rf"^{re.escape(name)} ([0-9.eE+-]+)$",
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"missing metric {name} in {path.name}")
    return float(match.group(1))


def validate(root: Path) -> dict[str, Any]:
    summary = json.loads((root / "range-debug-summary.json").read_text())
    expected_layers = list(range(NUM_LAYERS))
    assert summary["status"] == "passed" and summary["errors"] == []
    assert summary["prefill"] == {
        "commit_event_count": 1,
        "event_count": 28,
        "range_event_count": NUM_LAYERS,
        "range_layers": expected_layers,
        "whole_key_event_count": 0,
    }
    assert summary["decode"] == {
        "commit_event_count": 0,
        "event_count": NUM_LAYERS,
        "range_event_count": NUM_LAYERS,
        "range_layers": expected_layers,
        "whole_key_event_count": 0,
    }

    response = json.loads((root / "response.json").read_text())
    assert response["choices"][0]["finish_reason"] == "length"
    assert response["usage"]["prompt_tokens"] == 525
    assert response["usage"]["completion_tokens"] == 16
    assert response["usage"]["total_tokens"] == 541

    role_events: dict[str, list[dict[str, Any]]] = {}
    for role in ("prefill", "decode"):
        log = (root / f"vllm-{role}.log").read_text(encoding="utf-8")
        assert log.count('POST /v1/completions HTTP/1.1" 200 OK') == 1
        assert "Traceback (most recent call last)" not in log
        assert "TypeError" not in log
        events = _events(log)
        role_events[role] = events
        ranges = [event for event in events if event["event"] == "range"]
        assert len(ranges) == NUM_LAYERS
        for event in ranges:
            assert event["key_count"] == KEY_COUNT
            assert len(event["sizes"]) == KEY_COUNT
            assert len(event["requested_bytes"]) == KEY_COUNT
            assert len(event["results"]) == KEY_COUNT
            assert all(
                requested == sum(sizes) == result
                for requested, sizes, result in zip(
                    event["requested_bytes"], event["sizes"], event["results"]
                )
            )

    prefill_events = role_events["prefill"]
    commit_indexes = [
        index for index, event in enumerate(prefill_events) if event["event"] == "commit"
    ]
    assert commit_indexes == [NUM_LAYERS]
    commit = prefill_events[NUM_LAYERS]
    assert commit["layer_id"] == NUM_LAYERS - 1
    assert commit["key_count"] == KEY_COUNT
    assert commit["results"] == [0] * KEY_COUNT

    decode_log = (root / "vllm-decode.log").read_text(encoding="utf-8")
    assert "kvpool hit tokens: 512, need to load: 512" in decode_log

    pre_request = {
        name: _metric(root / "pre-request.metrics", name)
        for name in (
            "master_key_count",
            "master_allocated_bytes",
            "master_active_clients",
        )
    }
    assert pre_request == {
        "master_key_count": 0,
        "master_allocated_bytes": 0,
        "master_active_clients": 2,
    }
    post_request = {
        name: _metric(root / "post-request.metrics", name)
        for name in (
            "master_key_count",
            "master_allocated_bytes",
            "master_active_clients",
            "master_batch_put_start_requests_total",
            "master_batch_put_end_requests_total",
        )
    }
    assert post_request["master_key_count"] == KEY_COUNT
    assert post_request["master_allocated_bytes"] > 0
    assert post_request["master_active_clients"] == 2
    assert post_request["master_batch_put_start_requests_total"] == 1
    assert post_request["master_batch_put_end_requests_total"] == 1

    proxy = json.loads((root / "proxy-endpoints.json").read_text())
    assert proxy["status"] == "ok"
    assert len(proxy["prefill_nodes"]) == 1
    assert len(proxy["decode_nodes"]) == 1

    return {
        "validated": True,
        "num_layers": NUM_LAYERS,
        "key_count": KEY_COUNT,
        "per_key_byte_equality": True,
        "prefill_commits": 1,
        "whole_key_calls": 0,
        "decode_hit_tokens": 512,
        "response_id": response["id"],
        "pre_request_metrics": pre_request,
        "post_request_metrics": post_request,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} EVIDENCE_DIR")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
