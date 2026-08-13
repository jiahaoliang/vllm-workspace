from __future__ import annotations

import pytest
from performance import issue1_contract


def test_test1_matrix_is_exactly_bulk_and_layerwise_o128() -> None:
    assert issue1_contract.TEST1_POINTS == (
        issue1_contract.Issue1Point(
            "test1", "dp1", 32000, 128, "bulk", 8, 125
        ),
        issue1_contract.Issue1Point(
            "test1", "dp1", 32000, 128, "layerwise", 8, 125
        ),
    )


def test_test2_matrix_is_one_bulk_reuse3_c40_point() -> None:
    assert issue1_contract.test2_points(40) == (
        issue1_contract.Issue1Point(
            "test2", "dp1", 32000, 1, "bulk", 40, 100
        ),
        issue1_contract.Issue1Point(
            "test2", "dp1", 32000, 1, "reuse3", 40, 100
        ),
    )


def test_prefix_and_scheduler_contract_matches_private_issue() -> None:
    assert issue1_contract.BLOCK_SIZE == 128
    assert issue1_contract.INPUT_TOKENS == 32000
    assert issue1_contract.SEED_TOKENS == 28800
    assert issue1_contract.FORMAL_BLOCKS == 250
    assert issue1_contract.SEED_BLOCKS == 225
    assert issue1_contract.EXPECTED_HIT_RATE == 0.9
    assert issue1_contract.RUNTIME_CONSTANTS == {
        "block_size": 128,
        "max_model_len": 32768,
        "max_num_batched_tokens": 32768,
        "gpu_memory_utilization": 0.95,
        "enable_chunked_prefill": True,
        "enable_prefix_caching": False,
        "async_scheduling": True,
        "server_seed": 1024,
        "client_fixture_seed": 1023,
        "request_rate": 0,
        "prefix_mode": "shared",
    }
    assert issue1_contract.long_prefill_token_threshold(40) == 768
    assert 40 * issue1_contract.long_prefill_token_threshold(40) <= 32768


def test_capacity_selection_prefers_c40_when_it_crosses_bulk_only() -> None:
    selection = issue1_contract.select_test2_concurrency(
        bulk_capacity_tokens=632320,
        reuse3_capacity_tokens=3414784,
    )

    assert selection.concurrency == 40
    assert selection.bulk_request_capacity == 19
    assert selection.reuse3_request_capacity == 106
    assert selection.reason == "preferred_c40_crosses_bulk_and_fits_reuse3"


def test_capacity_selection_never_substitutes_an_unreviewed_concurrency() -> None:
    with pytest.raises(ValueError, match="reviewed c40"):
        issue1_contract.select_test2_concurrency(
            bulk_capacity_tokens=41 * 32000,
            reuse3_capacity_tokens=80 * 32000,
        )


def test_capacity_selection_rejects_no_reuse3_headroom() -> None:
    with pytest.raises(ValueError, match="reviewed c40"):
        issue1_contract.select_test2_concurrency(
            bulk_capacity_tokens=41 * 32000,
            reuse3_capacity_tokens=47 * 32000,
        )


def test_run_contract_records_exact_points_and_validity_gates() -> None:
    contract = issue1_contract.build_issue1_run_contract(
        image_digest="sha256:image",
        bulk_capacity_tokens=632320,
        reuse3_capacity_tokens=3414784,
        npu_node="m1",
    )

    assert contract["expected_points"] == [
        "test1-dp1-32000-bulk-o128-c8",
        "test1-dp1-32000-layerwise-o128-c8",
        "test2-dp1-32000-bulk-o1-c40",
        "test2-dp1-32000-reuse3-o1-c40",
    ]
    assert contract["formal_request_counts"] == {"test1": 125, "test2": 100}
    assert contract["warmup_request_count"] == 8
    assert contract["seed_request_count"] == 1
    assert contract["server_seed"] == 1024
    assert contract["client_fixture_seed"] == 1023
    assert contract["seed_tokens"] == 28800
    assert contract["expected_hit_rate"] == 0.9
    assert contract["test2_concurrency"] == 40
    assert contract["test2_long_prefill_token_threshold"] == 768
    assert contract["test1_long_prefill_token_threshold"] == 4096
    assert contract["max_num_partial_prefills"] == {"test1": 8, "test2": 40}
    assert contract["max_long_partial_prefills"] == {"test1": 8, "test2": 40}
    assert contract["expected_admission_contexts"] == {
        "test1-dp1-32000-bulk-o128-c8": 8,
        "test1-dp1-32000-layerwise-o128-c8": 8,
        "test2-dp1-32000-bulk-o1-c40": 2,
        "test2-dp1-32000-reuse3-o1-c40": 40,
    }
    assert contract["requires_multiple_server_contexts"] is True
    assert contract["requires_capacity_waiting_for_bulk_test2"] is True
    assert contract["requires_reuse3_running_gt_bulk"] is True
