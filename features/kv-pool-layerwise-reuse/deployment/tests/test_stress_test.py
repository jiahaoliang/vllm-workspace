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
    assert fixture["generated_tokens"] == 24
    boundary = fixture["cached_boundary_tokens"]
    prompts = [request["prompt"] for request in requests]
    assert all(request["return_token_ids"] is True for request in requests)
    assert all(request["max_tokens"] == 24 for request in requests)
    assert len({tuple(prompt[boundary:]) for prompt in prompts}) == 1
    for block in range(shared):
        assert len({tuple(prompt[block * 128 : (block + 1) * 128]) for prompt in prompts}) == 1
    for block in range(shared, shared + unique):
        assert len({tuple(prompt[block * 128 : (block + 1) * 128]) for prompt in prompts}) == cases
    for index, marker in enumerate(fixture["markers"]):
        marker_tokens = CharacterTokenizer().encode(marker)
        assert stress.contains_subsequence(prompts[index][:boundary], marker_tokens)
        assert not stress.contains_subsequence(prompts[index][boundary:], marker_tokens)
        expected_text = f" {marker}"
        assert fixture["expected_marker_texts"][index] == expected_text
        assert fixture["expected_marker_token_ids"][index] == CharacterTokenizer().encode(
            expected_text
        )
        assert len(fixture["expected_marker_token_ids"][index]) != 7


def test_seeds_and_request_ids_are_deterministic():
    _, first = stress.build_fixtures(CharacterTokenizer(), stress.SCENARIOS["s2"])
    _, second = stress.build_fixtures(CharacterTokenizer(), stress.SCENARIOS["s2"])
    assert first == second
    assert first["seeds"] == list(range(2026072500, 2026072516))
    assert first["request_ids"]["proxy"][15] == "stress-s2-proxy-15"


def body(text=" S1_CASE_00", prompt_tokens=10, token_ids=None):
    if token_ids is None:
        token_ids = list(range(24))
    return {
        "choices": [
            {
                "text": text,
                "token_ids": token_ids,
                "finish_reason": "length",
                "stop_reason": None,
            }
        ],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 24},
    }


def test_exact_and_normalized_comparison_are_distinct():
    left = stress.response_signature(body(" S1_CASE_00  value"))
    right = stress.response_signature(body(" S1_CASE_00 value"))
    assert left != right
    assert stress.normalized_text(left["text"]) == stress.normalized_text(right["text"])


def test_foreign_marker_is_rejected():
    passed, foreign = stress.isolation("S1_CASE_00 S1_CASE_01", "S1_CASE_00", ["S1_CASE_00", "S1_CASE_01"])
    assert not passed
    assert foreign == ["S1_CASE_01"]


def completion_checks(signature, marker_token_ids=None):
    marker_token_ids = marker_token_ids or [901, 902, 903]
    return stress.validate_completion_signature(
        signature,
        expected_marker_text=" S1_CASE_00",
        expected_marker_token_ids=marker_token_ids,
        own_marker="S1_CASE_00",
        markers=["S1_CASE_00", "S1_CASE_01"],
        expected_prompt_tokens=10,
    )


def test_marker_prefix_validation_uses_dynamic_token_count():
    marker_token_ids = [901, 902, 903]
    signature = stress.response_signature(
        body(token_ids=marker_token_ids + list(range(21)))
    )
    checks, errors = completion_checks(signature, marker_token_ids)
    assert errors == []
    assert checks["validated"] is True
    assert checks["expected_marker_token_count"] == 3
    assert checks["marker_token_prefix_match"] is True


@pytest.mark.parametrize(
    ("text", "token_ids", "expected_error"),
    [
        (
            " S1_CASE_00 continuation",
            [999, 902, 903] + list(range(21)),
            "do not start with expected marker token_ids",
        ),
        (
            " S1_CASE_00 S1_CASE_01",
            [901, 902, 903] + list(range(21)),
            "contains foreign markers",
        ),
        (
            "noise S1_CASE_00",
            [901, 902, 903] + list(range(21)),
            "does not start with expected marker text",
        ),
    ],
)
def test_wrong_foreign_and_nonprefix_markers_are_rejected(
    text, token_ids, expected_error
):
    signature = stress.response_signature(body(text=text, token_ids=token_ids))
    checks, errors = completion_checks(signature)
    assert checks["validated"] is False
    assert any(expected_error in error for error in errors)


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (lambda signature: signature.update(token_ids=None), "token_ids are missing"),
        (
            lambda signature: signature.update(token_ids=[901, 902, 903] + list(range(20))),
            "generated token count expected 24",
        ),
        (lambda signature: signature.update(prompt_tokens=9), "prompt_tokens expected 10"),
        (
            lambda signature: signature.update(completion_tokens=23),
            "completion_tokens expected 24",
        ),
        (
            lambda signature: signature.update(finish_reason="stop"),
            "finish_reason expected 'length'",
        ),
    ],
)
def test_missing_tokens_short_generation_and_usage_mismatches_are_rejected(
    mutate, expected_error
):
    signature = stress.response_signature(
        body(token_ids=[901, 902, 903] + list(range(21)))
    )
    mutate(signature)
    checks, errors = completion_checks(signature)
    assert checks["validated"] is False
    assert any(expected_error in error for error in errors)


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


def test_finalize_accepts_marker_prefix_with_divergent_continuation(tmp_path):
    output = tmp_path / "scenario"
    output.mkdir()
    markers = [f"S1_CASE_{index:02d}" for index in range(4)]
    marker_token_ids = [[1000 + index, 2000 + index] for index in range(4)]
    fixture = {
        "schema_version": 2,
        "expected_key_count": 508,
        "markers": markers,
        "expected_marker_texts": [f" {marker}" for marker in markers],
        "expected_marker_token_ids": marker_token_ids,
        "generated_tokens": 24,
        "prompt_tokens": [10] * 4,
        "definition": {"case_count": 4},
    }
    actions = {"prepare": {}, "baseline": {}}
    actions.update(
        {
            f"pinned-{index}": {
                "prefill_rank": [0, 1, 0, 1][index],
                "elapsed_seconds": 1.0,
            }
            for index in range(4)
        }
    )
    write_json(output / "fixture.json", fixture)
    write_json(output / "scenario-state.json", {"schema_version": 1, "actions": actions})
    for index, marker in enumerate(markers):
        prefix = marker_token_ids[index]
        baseline_ids = prefix + [3000 + index] * 22
        candidate_ids = (
            prefix + [4000 + index] * 22 if index == 0 else baseline_ids
        )
        baseline_text = f" {marker} baseline continuation"
        candidate_text = (
            f" {marker} cached continuation" if index == 0 else baseline_text
        )
        raw_baseline = {
            "status_code": 200,
            "body": body(baseline_text, token_ids=baseline_ids),
            "error": None,
            "elapsed_seconds": 1.0,
        }
        raw_candidate = {
            "status_code": 200,
            "body": body(candidate_text, token_ids=candidate_ids),
            "error": None,
            "elapsed_seconds": 1.0,
        }
        write_json(output / "baseline" / f"case-{index:02d}.json", raw_baseline)
        write_json(
            output / "pinned" / f"case-{index:02d}-decode.json", raw_candidate
        )

    metrics = tmp_path / "metrics"
    metrics.write_text("master_key_count 508\n", encoding="utf-8")
    log = tmp_path / "log.json"
    write_json(log, {"status": "passed", "validated": True})

    stress.finalize(final_args(output, metrics, [log]))

    summary = json.loads((output / "scenario-summary.json").read_text())
    assert summary["status"] == "passed"
    assert summary["validated"] is True
    assert summary["marker_prefix_match_count"] == 4
    assert summary["isolated_count"] == 4
    assert summary["full_exact_match_count"] == 3
    assert summary["divergent_case_indices"] == [0]
    assert summary["common_prefix_token_count"]["0"] == 2
    assert summary["first_divergence_token_index"]["0"] == 2
    divergent = summary["candidate"]["cases"][0]
    assert divergent["full_exact_match"] is False
    assert divergent["baseline"]["signature"]["token_ids"] == marker_token_ids[0] + [3000] * 22
    assert divergent["candidate"]["signature"]["token_ids"] == marker_token_ids[0] + [4000] * 22
    assert not any("exact" in error for error in summary["errors"])


def test_atomic_json_refuses_raw_overwrite(tmp_path):
    path = tmp_path / "raw.json"
    stress.atomic_json(path, {"first": True}, refuse_existing=True)
    with pytest.raises(stress.ValidationError, match="refusing to overwrite"):
        stress.atomic_json(path, {"second": True}, refuse_existing=True)
    assert json.loads(path.read_text()) == {"first": True}
