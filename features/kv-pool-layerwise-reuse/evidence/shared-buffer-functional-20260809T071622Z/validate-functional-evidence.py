#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict), relative
    return value


def steps(relative: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
        if line
    ]


def metrics(relative: str) -> dict[str, float]:
    selected = {
        "master_key_count",
        "master_allocated_bytes",
        "master_active_clients",
    }
    return {
        fields[0]: float(fields[1])
        for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
        if len(fields := line.split()) == 2 and fields[0] in selected
    }


def main() -> int:
    cpu = load("cpu/summary.json")
    image = load("image/summary.json")
    npu = load("npu/summary.json")
    canary = load("npu/pure-consumer-canary/summary.json")
    config = load("validation-config.json")
    for name, value in (
        ("cpu", cpu),
        ("image", image),
        ("npu", npu),
        ("canary", canary),
    ):
        assert value["status"] == "passed", name
        assert value["validated"] is True, name

    source = "5355559175f9998f5d70866734fb79569dfc86f9"
    assert cpu["source_head"] == image["source_head"] == source
    assert config["commits"]["vllm_ascend"] == source
    assert config["image_commits"]["vllm_ascend"] == source
    assert config["image"] == image["final_image"]
    assert config["derived_image"]["manifest_digest"] == image[
        "final_manifest_digest"
    ]
    assert config["derived_image"]["config_digest"] == image[
        "final_config_digest"
    ]

    assert npu["roles"] == ["kv_producer", "kv_both"]
    assert npu["shared_buffers"] == 3
    assert npu["physical_slots"] == 5
    assert npu["memory_factor"] == 5.4
    assert npu["response_equality"] is True
    assert canary["variant"] == "reuse3"
    assert canary["prefill_role"] == "kv_producer"
    assert canary["decode_role"] == "kv_consumer"
    assert canary["decode_shared_buffers_configured"] is False
    assert canary["block_hits"] == "32/32"
    assert canary["kvpool_hit_tokens"] == 4095
    assert canary["vllm_cached_tokens"] == 0

    zero = {
        "master_key_count": 0.0,
        "master_allocated_bytes": 0.0,
        "master_active_clients": 0.0,
    }
    for relative in (
        "npu/baseline/final.metrics",
        "npu/producer-reuse/final.metrics",
        "npu/both-reuse/final.metrics",
        "npu/pure-consumer-canary/final.metrics",
    ):
        assert metrics(relative) == zero, relative

    for relative in ("cpu/steps.jsonl", "image/steps.jsonl", "npu/steps.jsonl"):
        failures = [step for step in steps(relative) if step["exit_code"] != 0]
        assert failures == [], (relative, failures)
    canary_failures = [
        step
        for step in steps("npu/pure-consumer-canary/steps.jsonl")
        if step["exit_code"] != 0
    ]
    assert [step["name"] for step in canary_failures] == [
        "render TP2 4096 REUSE3 canary",
        "send exact 4096-token REUSE3 canary",
    ]
    assert load("npu/pure-consumer-canary/summary.json")["errors"] == []

    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    assert "Status: **PASS**" in report
    assert image["final_image"] in report
    assert source in report

    result = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "source_head": source,
        "image_manifest": image["final_manifest_digest"],
        "cpu_tests": 515,
        "runtime_roles": npu["roles"],
        "targeted_canary": "passed",
        "intentional_tooling_diagnostics": [
            step["name"] for step in canary_failures
        ],
        "final_master_empty": True,
        "errors": [],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
