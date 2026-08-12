#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = "57d3c214e642cdbb529400f0742d1a98a8d38708"
IMAGE = (
    "docker.io/library/vllm-ascend:kv-pool-layerwise-main-"
    "54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z"
)
MANIFEST = "sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3"
CONFIG = "sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd"


def load(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict), relative
    return value


def metric(relative: str, name: str) -> float:
    for line in (ROOT / relative).read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == name:
            return float(fields[1])
    raise AssertionError(f"missing metric {name}: {relative}")


def response_signature(relative: str) -> dict[str, object]:
    response = load(relative)
    choice = response["choices"][0]
    usage = response["usage"]
    return {
        "text": choice["text"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
    }


def replay_checksums() -> None:
    manifest = ROOT / "SHA256SUMS"
    listed: set[str] = set()
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), 1
    ):
        expected, separator, relative = line.partition("  ")
        assert separator and len(expected) == 64 and relative, line_number
        assert relative not in listed, relative
        listed.add(relative)
        artifact = ROOT / relative
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert actual == expected, relative
    actual_files = {
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert listed == actual_files, {
        "missing": sorted(actual_files - listed),
        "unexpected": sorted(listed - actual_files),
    }


def main() -> int:
    cpu = load("cpu/summary.json")
    npu = load("npu/summary.json")
    image = load("image-identity.json")
    config = load("validation-config.json")
    before = load("pre-run-npu-readiness.json")
    after = load("post-cleanup-npu-readiness.json")

    assert cpu["status"] == "passed" and cpu["validated"] is True
    assert cpu["source_head"] == SOURCE
    assert cpu["npu_requested"] is False
    assert cpu["host_path_mounted"] is False
    assert cpu["gates"] == {
        "ascend_store": "516 passed",
        "focused_self_load_regression": "1 passed",
        "mooncake_layer_session": "27 passed",
    }
    assert "91 passed" in (ROOT / "cpu/performance-harness.log").read_text()
    assert "All checks passed!" in (ROOT / "cpu/ruff-source-delta.log").read_text()
    assert "All checks passed!" in (
        ROOT / "cpu/ruff-performance-delta.log"
    ).read_text()

    assert image["status"] == "passed" and image["validated"] is True
    assert image["reference"] == IMAGE
    assert image["manifest_digest"] == MANIFEST
    assert image["config_digest"] == CONFIG
    assert image["embedded_heads"] == {
        "vllm": "54503ecec0f3ac31e5ecfc5f28652e4cc42307b5",
        "vllm_ascend": SOURCE,
        "mooncake": "df3f74ed8ebdb0c935554beea6299a9f11c723e2",
    }
    assert config["commits"]["vllm_ascend"] == SOURCE
    assert config["image"] == IMAGE

    steps = [
        json.loads(line)
        for line in (ROOT / "npu/steps.jsonl").read_text().splitlines()
        if line
    ]
    assert len(steps) == 63
    assert not [step for step in steps if step["exit_code"] != 0]
    signatures = {
        tuple(response_signature(relative).items())
        for relative in (
            "npu/baseline/response-1.json",
            "npu/producer-reuse/response-1.json",
            "npu/both-reuse/response-1.json",
            "npu/both-reuse/response-2.json",
        )
    }
    assert len(signatures) == 1
    signature = dict(next(iter(signatures)))
    assert signature["finish_reason"] == "length"
    assert signature["prompt_tokens"] == 525
    assert signature["completion_tokens"] == 16
    assert signature["total_tokens"] == 541

    assert npu["status"] == "passed" and npu["validated"] is True
    assert npu["run_id"] == "20260812T023541Z"
    assert npu["roles"] == ["kv_producer", "kv_both"]
    assert npu["num_layers"] == 27
    assert npu["shared_buffers"] == 3
    assert npu["physical_slots"] == 5
    assert npu["memory_factor"] == 5.4
    assert npu["response_equality"] is True
    assert npu["final_master_empty_each_case"] is True
    assert npu["errors"] == []
    for case in ("baseline", "producer-reuse", "both-reuse"):
        relative = f"npu/{case}/final.metrics"
        assert metric(relative, "master_key_count") == 0
        assert metric(relative, "master_allocated_bytes") == 0
        assert metric(relative, "master_active_clients") == 0

    for readiness in (before, after):
        assert readiness["status"] == "READY"
        assert readiness["ready"] is True
        assert readiness["node"] == "m1"
        assert readiness["resource"] == "huawei.com/Ascend910"
        assert readiness["allocatable"] == 8
        assert readiness["free"] >= 4
        assert readiness["vnpu_number_ignored"] is True
    assert after["free"] == 8
    assert after["requested_by_non_terminal_pods"] == 0

    replay_checksums()
    result = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "source_head": SOURCE,
        "image_manifest": MANIFEST,
        "cpu_gates": {
            "performance_harness": 91,
            "focused_self_load": 1,
            "mooncake_layer_session": 27,
            "ascend_store": 516,
        },
        "runtime_steps": len(steps),
        "runtime_roles": npu["roles"],
        "response_equality": True,
        "final_master_empty": True,
        "post_cleanup_free_npus": after["free"],
        "errors": [],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
