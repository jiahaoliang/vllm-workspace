from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "check-stress-log.py"
SPEC = importlib.util.spec_from_file_location("check_stress_log", PATH)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


def range_event(role, layer, *, result=None):
    requested = 8
    return {
        "event": "range",
        "direction": "save" if role == "prefill" else "load",
        "layer_id": layer,
        "key_count": 1,
        "requested_bytes": [requested],
        "sizes": [[3, 5]],
        "object_offsets": [[layer * 8, layer * 8 + 3]],
        "results": [requested if result is None else result],
    }


def ranged_lines(role, layers=3, commit=True):
    lines = [f"x {checker.PREFIX} {json.dumps(range_event(role, layer))}" for layer in range(layers)]
    if role == "prefill" and commit:
        lines.append(f"x {checker.PREFIX} " + json.dumps({"event": "commit", "layer_id": layers - 1, "key_count": 1, "results": [0]}))
    return lines


def iteration(rank, tokens, dummy=False):
    suffix = " (dummy)" if dummy else ""
    return f"INFO EngineCore_DP{rank} Iteration(1): 1 context requests, {tokens} context tokens, 0 generation requests, 0 generation tokens, iteration elapsed time: 1.0 ms{suffix}"


def write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pinned_args(tmp_path, prefill_lines, decode_lines, *, rank=0, prompt=16, minimum=2, maximum=1024, hit=256, layers=3):
    prefill = tmp_path / "prefill.log"
    decode = tmp_path / "decode.log"
    result = tmp_path / "result.json"
    write(prefill, prefill_lines)
    write(decode, decode_lines)
    return Namespace(prefill_log_window=prefill, decode_log_window=decode, expected_prefill_dp_rank=rank, expected_prompt_tokens=prompt, expected_hit_tokens=hit, min_context_iterations=minimum, max_context_tokens=maximum, num_layers=layers, output=result)


@pytest.mark.parametrize("rank", [0, 1])
def test_valid_pinned_dp_rank(tmp_path, rank):
    prefill = [iteration(rank, 8), iteration(rank, 8), "hit_blocks=0/2", *ranged_lines("prefill")]
    decode = ["kvpool hit tokens: 256", *ranged_lines("decode")]
    args = pinned_args(tmp_path, prefill, decode, rank=rank)
    assert checker.pinned(args) == 0
    assert json.loads(args.output.read_text())["validated"] is True


@pytest.mark.parametrize(
    ("extra", "message"),
    [([iteration(1, 0)], "active DP ranks"), ([iteration(0, 8)], "context token sum"), ([iteration(0, 2048)], "exceed")],
)
def test_pinned_iteration_failures(tmp_path, extra, message):
    prefill = [iteration(0, 8), iteration(0, 8), *extra, "hit_blocks=0/2", *ranged_lines("prefill")]
    decode = ["kvpool hit tokens: 256", *ranged_lines("decode")]
    args = pinned_args(tmp_path, prefill, decode)
    assert checker.pinned(args) == 1
    assert message in " ".join(json.loads(args.output.read_text())["errors"])


def test_pinned_too_few_iterations(tmp_path):
    args = pinned_args(tmp_path, [iteration(0, 16), "hit_blocks=0/2", *ranged_lines("prefill")], ["kvpool hit tokens: 256", *ranged_lines("decode")])
    assert checker.pinned(args) == 1
    assert "at least 2" in " ".join(json.loads(args.output.read_text())["errors"])


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda lines: lines.pop(1), "layer set mismatch"),
        (lambda lines: lines.__setitem__(0, f"x {checker.PREFIX} not-json"), "malformed range event"),
        (lambda lines: lines.__setitem__(0, f"x {checker.PREFIX} {json.dumps(range_event('prefill', 0, result=7))}"), "result byte mismatch"),
        (lambda lines: lines.__setitem__(0, f"x {checker.PREFIX} {json.dumps(range_event('prefill', 0, result=-1))}"), "negative"),
        (lambda lines: lines.insert(0, f"x {checker.PREFIX} " + json.dumps({"event": "commit", "layer_id": 2, "key_count": 1, "results": [0]})), "does not immediately follow"),
        (lambda lines: lines.append(f"x {checker.PREFIX} " + json.dumps({"event": "whole_key", "direction": "put", "key_count": 1})), "whole-key"),
    ],
)
def test_range_failures(tmp_path, mutator, message):
    ranges = ranged_lines("prefill")
    mutator(ranges)
    args = pinned_args(tmp_path, [iteration(0, 8), iteration(0, 8), "hit_blocks=0/2", *ranges], ["kvpool hit tokens: 256", *ranged_lines("decode")])
    assert checker.pinned(args) == 1
    assert message in " ".join(json.loads(args.output.read_text())["errors"])


def aggregate_args(tmp_path, ranks=(0, 1)):
    prefill = tmp_path / "aggregate-prefill.log"
    decode = tmp_path / "aggregate-decode.log"
    result = tmp_path / "aggregate.json"
    lines = []
    for rank in ranks:
        lines.extend([iteration(rank, 512), *ranged_lines("prefill")])
    write(prefill, lines)
    write(decode, ranged_lines("decode") + ranged_lines("decode"))
    return Namespace(prefill_log_window=prefill, decode_log_window=decode, required_prefill_dp_ranks="0,1", max_context_tokens=1024, num_layers=3, output=result)


def test_valid_aggregate_allows_repeated_layers(tmp_path):
    args = aggregate_args(tmp_path)
    assert checker.aggregate(args) == 0


def test_aggregate_requires_dp1(tmp_path):
    args = aggregate_args(tmp_path, ranks=(0,))
    assert checker.aggregate(args) == 1
    assert "required DP ranks" in " ".join(json.loads(args.output.read_text())["errors"])


def npu_process_table(devices):
    lines = ["| NPU     Chip              | Process id    | Process name             | Process memory(MB)      |"]
    lines.extend(f"| {device}       0                 | {8000 + device}          | VLLMEngineCor            | 27752                   |" for device in devices)
    return "\n".join(lines)


def test_topology_validates_config_allocations_processes_and_devices(tmp_path):
    paths = {}
    values = {
        "prefill_log": "config: tensor_parallel_size=2, data_parallel_size=2\n",
        "decode_log": "config: tensor_parallel_size=2, data_parallel_size=1\n",
        "prefill_pod_yaml": "requests:\n  huawei.com/Ascend910: '4'\nlimits:\n  huawei.com/Ascend910: '4'\n",
        "decode_pod_yaml": "requests:\n  huawei.com/Ascend910: '2'\nlimits:\n  huawei.com/Ascend910: '2'\n",
        "prefill_ps": "VLLM::EngineCore_DP0\nVLLM::EngineCore_DP1\n",
        "decode_ps": "VLLM::EngineCore_DP0\n",
        "prefill_npu_info": npu_process_table(range(4)),
        "decode_npu_info": npu_process_table(range(2)),
    }
    for name, value in values.items():
        paths[name] = tmp_path / f"{name}.txt"
        paths[name].write_text(value, encoding="utf-8")
    result = tmp_path / "topology.json"
    args = Namespace(**paths, output=result)
    assert checker.topology(args) == 0
    assert json.loads(result.read_text())["validated"] is True


def test_topology_requires_both_request_and_limit(tmp_path):
    paths = {}
    values = {
        "prefill_log": "tensor_parallel_size=2 data_parallel_size=2",
        "decode_log": "tensor_parallel_size=2 data_parallel_size=1",
        "prefill_pod_yaml": "huawei.com/Ascend910: '4'",
        "decode_pod_yaml": "huawei.com/Ascend910: '2'\nhuawei.com/Ascend910: '2'",
        "prefill_ps": "DP0 DP1",
        "decode_ps": "DP0",
        "prefill_npu_info": npu_process_table(range(4)),
        "decode_npu_info": npu_process_table(range(2)),
    }
    for name, value in values.items():
        paths[name] = tmp_path / f"{name}.txt"
        paths[name].write_text(value, encoding="utf-8")
    result = tmp_path / "topology.json"
    assert checker.topology(Namespace(**paths, output=result)) == 1
    assert "prefill allocation=4" in " ".join(json.loads(result.read_text())["errors"])
