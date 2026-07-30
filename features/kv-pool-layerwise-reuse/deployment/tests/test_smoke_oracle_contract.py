from __future__ import annotations

import unittest
from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / "10-runtime-config.yaml"


class SmokeOracleContractTest(unittest.TestCase):
    def test_hard_gates_do_not_depend_on_full_continuation_equality(self):
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn('"return_token_ids": True', text)
        self.assertIn('case["validated"] = case["hard_gate_checks"]["validated"]', text)
        self.assertNotIn("deterministic_or_replayed", text)

    def test_marker_token_usage_and_finish_reason_are_hard_gates(self):
        text = CONFIG.read_text(encoding="utf-8")
        for token in (
            "marker_token_prefix_match",
            "text_marker_prefix_match",
            "generated_token_count_match",
            "prompt_tokens_match",
            "completion_tokens_match",
            "finish_reason_match",
            "foreign_markers",
        ):
            self.assertIn(token, text)

    def test_full_equality_and_serial_replay_remain_diagnostics(self):
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn('"exact_match": exact_match', text)
        self.assertIn('case["serial_replay_match"]', text)
        self.assertIn("hard_gates_passed_with_generation_variation", text)


if __name__ == "__main__":
    unittest.main()
