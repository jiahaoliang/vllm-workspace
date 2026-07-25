from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "stress-test.py"
SPEC = importlib.util.spec_from_file_location("stress_test", PATH)
assert SPEC and SPEC.loader
stress = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stress
SPEC.loader.exec_module(stress)


class CharacterTokenizer:
    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return [ord(character) for character in text]

    def decode(self, tokens, skip_special_tokens=False):
        assert skip_special_tokens is False
        return "".join(chr(token) for token in tokens)


@pytest.mark.parametrize(
    ("name", "cases", "shared", "unique", "keys"),
    [("s1", 4, 0, 127, 508), ("s2", 16, 48, 15, 288), ("s3", 4, 224, 31, 348)],
)
def test_fixture_layout_and_arithmetic(name, cases, shared, unique, keys):
    requests, fixture = stress.build_fixtures(CharacterTokenizer(), stress.SCENARIOS[name])
    assert len(requests) == cases
    assert fixture["expected_key_count"] == keys == shared + cases * unique
    assert fixture["cached_blocks"] == shared + unique
    assert 0 < fixture["tail_tokens"] < 128
    boundary = fixture["cached_boundary_tokens"]
    prompts = [request["prompt"] for request in requests]
    assert len({tuple(prompt[boundary:]) for prompt in prompts}) == 1
    for block in range(shared):
        assert len({tuple(prompt[block * 128 : (block + 1) * 128]) for prompt in prompts}) == 1
    for block in range(shared, shared + unique):
        assert len({tuple(prompt[block * 128 : (block + 1) * 128]) for prompt in prompts}) == cases
    for index, marker in enumerate(fixture["markers"]):
        marker_tokens = CharacterTokenizer().encode(marker)
        assert stress.contains_subsequence(prompts[index][:boundary], marker_tokens)
        assert not stress.contains_subsequence(prompts[index][boundary:], marker_tokens)


def test_seeds_and_request_ids_are_deterministic():
    _, first = stress.build_fixtures(CharacterTokenizer(), stress.SCENARIOS["s2"])
    _, second = stress.build_fixtures(CharacterTokenizer(), stress.SCENARIOS["s2"])
    assert first == second
    assert first["seeds"] == list(range(2026072500, 2026072516))
    assert first["request_ids"]["proxy"][15] == "stress-s2-proxy-15"


def body(text="S1_CASE_00", prompt_tokens=10):
    return {
        "choices": [{"text": text, "finish_reason": "stop", "stop_reason": None}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 1},
    }


def test_exact_and_normalized_comparison_are_distinct():
    left = stress.response_signature(body("S1_CASE_00  value"))
    right = stress.response_signature(body("S1_CASE_00 value"))
    assert left != right
    assert stress.normalized_text(left["text"]) == stress.normalized_text(right["text"])


def test_foreign_marker_is_rejected():
    passed, foreign = stress.isolation("S1_CASE_00 S1_CASE_01", "S1_CASE_00", ["S1_CASE_00", "S1_CASE_01"])
    assert not passed
    assert foreign == ["S1_CASE_01"]


@pytest.mark.parametrize("transfer", [None, {}])
def test_decode_payload_omits_empty_transfer_like_proxy(transfer):
    payload = {"model": "test", "prompt": [1, 2, 3]}
    decoded, attached = stress.decode_payload_with_transfer(payload, transfer)
    assert decoded == payload
    assert "kv_transfer_params" not in decoded
    assert attached is False


def test_decode_payload_attaches_nonempty_transfer_like_proxy():
    payload = {"model": "test", "prompt": [1, 2, 3]}
    transfer = {"remote_block_ids": [1]}
    decoded, attached = stress.decode_payload_with_transfer(payload, transfer)
    assert decoded["kv_transfer_params"] == transfer
    assert attached is True


def test_decode_payload_rejects_non_object_transfer():
    with pytest.raises(stress.ValidationError, match="invalid kv_transfer_params"):
        stress.decode_payload_with_transfer({"prompt": [1]}, ["invalid"])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def final_args(output, metrics, logs):
    return Namespace(scenario="s1", output=output, master_metrics=metrics, log_check_summary=logs, proxy_base_url="unused")


def test_finalize_rejects_missing_actions_and_writes_failed_summary(tmp_path):
    output = tmp_path / "scenario"
    output.mkdir()
    fixture = {
        "expected_key_count": 508,
        "markers": [f"S1_CASE_{i:02d}" for i in range(4)],
        "prompt_tokens": [10] * 4,
        "definition": {"case_count": 4},
    }
    write_json(output / "fixture.json", fixture)
    write_json(output / "scenario-state.json", {"schema_version": 1, "actions": {"prepare": {}, "baseline": {}}})
    metrics = tmp_path / "metrics"
    metrics.write_text("master_key_count 508\n", encoding="utf-8")
    log = tmp_path / "log.json"
    write_json(log, {"status": "passed", "validated": True})
    with pytest.raises(stress.ValidationError, match="missing required action"):
        stress.finalize(final_args(output, metrics, [log]))
    summary = json.loads((output / "scenario-summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["validated"] is False
    assert summary["errors"]


def test_atomic_json_refuses_raw_overwrite(tmp_path):
    path = tmp_path / "raw.json"
    stress.atomic_json(path, {"first": True}, refuse_existing=True)
    with pytest.raises(stress.ValidationError, match="refusing to overwrite"):
        stress.atomic_json(path, {"second": True}, refuse_existing=True)
    assert json.loads(path.read_text()) == {"first": True}
