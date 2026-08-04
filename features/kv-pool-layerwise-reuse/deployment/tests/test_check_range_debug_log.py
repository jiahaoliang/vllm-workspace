from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "check-range-debug-log.py"
SPEC = importlib.util.spec_from_file_location("check_range_debug_log", PATH)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


def range_event(result):
    return {
        "event": "range",
        "direction": "save",
        "layer_id": 0,
        "key_count": 1,
        "requested_bytes": [8],
        "sizes": [[3, 5]],
        "object_offsets": [[0, 3]],
        "results": [result],
        "_line": 1,
    }


@pytest.mark.parametrize("result", [0, 7, 8])
def test_validate_range_accepts_any_nonnegative_result(result):
    errors = []
    checker.validate_range(range_event(result), "prefill", 1, errors)
    assert errors == []


@pytest.mark.parametrize("result", [-1, True, 1.5])
def test_validate_range_rejects_negative_or_noninteger_result(result):
    errors = []
    checker.validate_range(range_event(result), "prefill", 1, errors)
    assert any("negative or invalid result" in error for error in errors)
