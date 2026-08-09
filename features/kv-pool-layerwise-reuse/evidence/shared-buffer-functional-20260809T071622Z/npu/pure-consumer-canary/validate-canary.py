#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def metrics(path: Path) -> dict[str, float]:
    selected = {
        "master_key_count",
        "master_allocated_bytes",
        "master_active_clients",
    }
    return {
        fields[0]: float(fields[1])
        for line in path.read_text(encoding="utf-8").splitlines()
        if len(fields := line.split()) == 2 and fields[0] in selected
    }


def debug_events(text: str) -> list[dict[str, object]]:
    prefix = "[KVPOOL_RANGE_DEBUG]"
    return [
        json.loads(line.split(prefix, 1)[1].strip())
        for line in text.splitlines()
        if prefix in line and line.split(prefix, 1)[1].strip().startswith("{")
    ]


def main() -> int:
    response = json.loads(
        (ROOT / "response-retry.json").read_text(encoding="utf-8")
    )
    usage = response["usage"]
    assert usage["prompt_tokens"] == 4096, usage
    assert usage["completion_tokens"] == 1, usage
    assert usage["total_tokens"] == 4097, usage
    assert response["choices"][0]["finish_reason"] == "length", response

    prefill = (ROOT / "vllm-prefill.log").read_text(encoding="utf-8")
    decode = (ROOT / "vllm-decode.log").read_text(encoding="utf-8")
    for forbidden in (
        "KV load failure",
        "Failing 1 request(s)",
        "Traceback (most recent call last)",
        "TimeoutError",
        "load wait timed out",
        "save wait timed out",
    ):
        assert forbidden not in prefill, ("prefill", forbidden)
        assert forbidden not in decode, ("decode", forbidden)

    request_ids = re.findall(r"Reqid: ([^,]+), Total tokens 4096", decode)
    assert len(request_ids) == 1, request_ids
    assert "hit_blocks=32/32" in decode
    assert "kvpool hit tokens: 4095, need to load: 4095" in decode
    assert "vllm_cached=0 kvpool_cached=4095 need_to_allocate=4095" in decode
    assert decode.count('POST /v1/completions HTTP/1.1" 200 OK') == 1
    assert prefill.count('POST /v1/completions HTTP/1.1" 200 OK') == 1

    events = debug_events(prefill)
    saves = [
        event
        for event in events
        if event.get("event") == "range" and event.get("direction") == "save"
    ]
    commits = [event for event in events if event.get("event") == "commit"]
    assert sorted({int(event["layer_id"]) for event in saves}) == list(range(27))
    assert commits and all(
        result == 0 for event in commits for result in event["results"]
    )

    post_metrics = metrics(ROOT / "post-request.metrics")
    assert post_metrics["master_key_count"] == 32
    assert post_metrics["master_allocated_bytes"] > 0
    assert post_metrics["master_active_clients"] == 4
    final_metrics = metrics(ROOT / "final.metrics")
    assert final_metrics == {
        "master_key_count": 0.0,
        "master_allocated_bytes": 0.0,
        "master_active_clients": 0.0,
    }
    for role in ("prefill", "decode"):
        released = (ROOT / f"{role}-npu-released.txt").read_text(encoding="utf-8")
        assert "No running processes found" in released, role

    prefill_runtime = json.loads(
        (ROOT / "prefill-runtime.json").read_text(encoding="utf-8")
    )
    decode_runtime = json.loads(
        (ROOT / "decode-runtime.json").read_text(encoding="utf-8")
    )
    assert prefill_runtime["physical_slots"] == 5
    assert decode_runtime["physical_slots"] == 27

    summary = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "topology": "dp1",
        "variant": "reuse3",
        "prefill_role": "kv_producer",
        "decode_role": "kv_consumer",
        "decode_shared_buffers_configured": False,
        "prompt_tokens": 4096,
        "completion_tokens": 1,
        "block_hits": "32/32",
        "kvpool_hit_tokens": 4095,
        "vllm_cached_tokens": 0,
        "initial_partial_tail_tokens": 127,
        "request_id": request_ids[0],
        "prefill_save_layers": 27,
        "commit_results_zero": True,
        "http_200_prefill_decode": True,
        "kv_load_failure_absent": True,
        "post_metrics": post_metrics,
        "final_metrics": final_metrics,
        "npu_processes_released": True,
        "errors": [],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
