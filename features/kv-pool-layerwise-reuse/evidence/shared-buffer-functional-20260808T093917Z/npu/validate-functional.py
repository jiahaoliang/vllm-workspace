#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path


ROOT = Path(os.environ.get("FUNCTIONAL_ROOT", Path(__file__).resolve().parent))
PREFIX = "[KVPOOL_RANGE_DEBUG]"
EXPECTED_LAYERS = list(range(27))
PRODUCER_CONFIG = (
    '{"kv_connector":"AscendStoreConnector","kv_role":"kv_producer",'
    '"kv_load_failure_policy":"fail","kv_connector_extra_config":{'
    '"backend":"mooncake","use_layerwise":true,'
    '"layerwise_num_shared_buffers":3,"layerwise_prefetch_layers":1,'
    '"lookup_rpc_port":0}}'
)
BOTH_CONFIG = PRODUCER_CONFIG.replace('"kv_producer"', '"kv_both"')


def metric(path: Path, name: str) -> float:
    match = re.search(
        rf"^{re.escape(name)} ([0-9.eE+-]+)$",
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"missing metric {name} in {path}")
    return float(match.group(1))


def response_signature(path: Path) -> dict[str, object]:
    response = json.loads(path.read_text(encoding="utf-8"))
    choice = response["choices"][0]
    usage = response["usage"]
    assert choice["finish_reason"] == "length"
    assert usage["prompt_tokens"] == 525
    assert usage["completion_tokens"] == 16
    assert usage["total_tokens"] == 541
    return {
        "text": choice["text"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
    }


def events(log: str) -> list[dict[str, object]]:
    return [
        json.loads(line.split(PREFIX, 1)[1].strip())
        for line in log.splitlines()
        if PREFIX in line
    ]


def validate_ranges(
    log: str,
    direction: str,
    expected_key_counts: set[int],
) -> dict[str, object]:
    matching = [
        event
        for event in events(log)
        if event.get("event") == "range" and event.get("direction") == direction
    ]
    layers = sorted({int(event["layer_id"]) for event in matching})
    assert layers == EXPECTED_LAYERS, (direction, layers)
    key_counts = Counter(int(event["key_count"]) for event in matching)
    assert set(key_counts) == expected_key_counts, (direction, key_counts)
    for event in matching:
        key_count = int(event["key_count"])
        assert key_count == len(event["requested_bytes"])
        assert key_count == len(event["sizes"])
        assert key_count == len(event["object_offsets"])
        assert key_count == len(event["results"])
        assert all(
            requested == sum(sizes) == result
            for requested, sizes, result in zip(
                event["requested_bytes"], event["sizes"], event["results"]
            )
        )
    return {
        "event_count": len(matching),
        "key_count_distribution": dict(sorted(key_counts.items())),
        "layers": layers,
    }


def validate_commits(log: str, expected_key_counts: set[int]) -> dict[str, object]:
    matching = [event for event in events(log) if event.get("event") == "commit"]
    key_counts = Counter(int(event["key_count"]) for event in matching)
    assert set(key_counts) == expected_key_counts, key_counts
    for event in matching:
        assert int(event["key_count"]) == len(event["results"])
        assert all(result == 0 for result in event["results"]), event
    return {
        "event_count": len(matching),
        "key_count_distribution": dict(sorted(key_counts.items())),
        "all_results_zero": True,
    }


def validate_final_metrics(case_dir: Path) -> None:
    assert {
        name: metric(case_dir / "final.metrics", name)
        for name in (
            "master_key_count",
            "master_allocated_bytes",
            "master_active_clients",
        )
    } == {
        "master_key_count": 0.0,
        "master_allocated_bytes": 0.0,
        "master_active_clients": 0.0,
    }


def main() -> int:
    baseline_dir = ROOT / "baseline"
    producer_dir = ROOT / "producer-reuse"
    both_dir = ROOT / "both-reuse"
    baseline = response_signature(baseline_dir / "response-1.json")
    producer = response_signature(producer_dir / "response-1.json")
    both_cold = response_signature(both_dir / "response-1.json")
    both_warm = response_signature(both_dir / "response-2.json")
    assert producer == baseline
    assert both_cold == baseline
    assert both_warm == baseline

    expected_startup = (
        "Layerwise KV cache reuse uses 5 slots for 27 layers; "
        "scale logical KV budget by 5.400."
    )
    expected_merge = (
        "Layerwise KV cache reuse merged 27 tensor descriptors into 5 "
        "descriptors across 5 physical slots."
    )
    expected_plan = (
        "GVA layerwise reuse plan: 27 layers, 3 shared slots, "
        "independent layers=[0, 26]."
    )

    summaries: dict[str, object] = {}
    for name, case_dir, config, request_count, expected_master_keys in (
        ("baseline", baseline_dir, None, 1, 4),
        ("producer-reuse", producer_dir, PRODUCER_CONFIG, 1, 20),
        ("both-reuse", both_dir, BOTH_CONFIG, 2, 36),
    ):
        log = (case_dir / "vllm-prefill.log").read_text(encoding="utf-8")
        assert log.count('POST /v1/completions HTTP/1.1" 200 OK') == request_count
        for forbidden in (
            "Traceback (most recent call last)",
            "TimeoutError",
            "save wait timed out",
            "load wait timed out",
            "did not drain after abort",
        ):
            assert forbidden not in log, (name, forbidden)
        all_events = events(log)
        assert not [event for event in all_events if event.get("event") == "whole_key"]
        if config is None:
            assert expected_startup not in log
            assert expected_merge not in log
            assert expected_plan not in log
        else:
            assert expected_startup in log
            assert expected_merge in log
            assert expected_plan in log
            cmdline = (case_dir / "cmdline.txt").read_text(encoding="utf-8")
            assert cmdline.splitlines().count(config) == 1

        post = {
            key: metric(case_dir / "post-request.metrics", key)
            for key in (
                "master_key_count",
                "master_allocated_bytes",
                "master_active_clients",
            )
        }
        assert post["master_key_count"] == expected_master_keys
        assert post["master_allocated_bytes"] > 0
        assert post["master_active_clients"] == 1
        validate_final_metrics(case_dir)
        if config is None:
            save = validate_ranges(log, "save", {4})
            assert not [
                event
                for event in all_events
                if event.get("event") == "range"
                and event.get("direction") == "load"
            ]
            commit = validate_commits(log, {4})
            load = None
        else:
            save = validate_ranges(log, "save", {1, 5})
            load = validate_ranges(
                log,
                "load",
                {5} if name == "producer-reuse" else {4, 5},
            )
            commit = validate_commits(log, {1, 5})
        summaries[name] = {
            "requests": request_count,
            "post_metrics": post,
            "save": save,
            "load": load,
            "commit": commit,
            "whole_key_calls": 0,
        }

    both_log = (both_dir / "vllm-prefill.log").read_text(encoding="utf-8")
    assert "kvpool hit tokens: 512, need to load: 512" in both_log

    result = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "run_id": os.environ.get("FUNCTIONAL_RUN_ID", "20260808T090506Z"),
        "roles": ["kv_producer", "kv_both"],
        "num_layers": 27,
        "shared_buffers": 3,
        "physical_slots": 5,
        "memory_factor": 5.4,
        "response_equality": True,
        "final_master_empty_each_case": True,
        "cases": summaries,
        "errors": [],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
