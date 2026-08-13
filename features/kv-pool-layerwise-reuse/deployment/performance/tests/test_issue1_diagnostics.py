from __future__ import annotations

import json
from pathlib import Path

from performance import issue1_diagnostics


def test_parses_capacity_and_iteration_details() -> None:
    text = """
GPU KV cache size: 3,414,784 tokens
Iteration(17): 8 context requests, 25600 context tokens, 0 generation requests, 0 generation tokens, iteration elapsed time: 31.25 ms
"""

    assert issue1_diagnostics.parse_kv_capacity_tokens(text) == 3414784
    assert issue1_diagnostics.parse_iteration_details(text) == (
        {
            "iteration": 17,
            "context_requests": 8,
            "context_tokens": 25600,
            "generation_requests": 0,
            "generation_tokens": 0,
            "elapsed_ms": 31.25,
        },
    )


def test_admission_requires_iteration_and_prometheus_multiple_contexts() -> None:
    log = (
        "Iteration(1): 8 context requests, 25600 context tokens, "
        "0 generation requests, 0 generation tokens, iteration elapsed time: 30 ms\n"
    )
    metrics = """
TIMESTAMP 2026-08-13T00:00:00Z
vllm:num_requests_running{engine="0"} 8
vllm:num_requests_waiting{engine="0"} 0
vllm:num_requests_waiting_by_reason{engine="0",reason="capacity"} 0
TIMESTAMP 2026-08-13T00:00:01Z
vllm:num_requests_running{engine="0"} 6
vllm:num_requests_waiting_by_reason{engine="0",reason="capacity"} 2
"""

    result = issue1_diagnostics.validate_admission(
        log, metrics, expected_contexts=8
    )

    assert result["valid"] is True
    assert result["max_context_requests"] == 8
    assert result["prometheus"]["max_running"] == 8
    assert result["prometheus"]["mean_active_running"] == 7
    assert result["prometheus"]["capacity_waiting_sample_sum"] == 2
    assert result["prometheus"]["capacity_waiting_positive_samples"] == 1


def test_admission_rejects_historical_one_running_seven_waiting_shape() -> None:
    log = (
        "Iteration(1): 1 context requests, 1024 context tokens, "
        "0 generation requests, 0 generation tokens, iteration elapsed time: 300 ms\n"
    )
    metrics = """
TIMESTAMP 2026-08-13T00:00:00Z
vllm:num_requests_running{engine="0"} 1
vllm:num_requests_waiting{engine="0"} 7
vllm:num_requests_waiting_by_reason{engine="0",reason="capacity"} 7
"""

    result = issue1_diagnostics.validate_admission(
        log, metrics, expected_contexts=8
    )

    assert result["valid"] is False
    assert result["max_context_requests"] == 1
    assert len(result["errors"]) == 2


def test_kvpool_and_te_metrics_are_aggregated() -> None:
    payload = {
        "schema_version": 2,
        "events": {
            "critical.wait_for_layer_load|layer=2": {
                "count": 2,
                "bytes": 128,
                "sum_ms": 7.5,
                "exclusive_sum_ms": 6.0,
                "p50_ms": 2.0,
                "p95_ms": 5.0,
                "max_ms": 5.0,
                "sample_count": 2,
            }
        }
    }
    text = "prefix KVPOOL_PERF_METRICS " + json.dumps(payload)

    events = issue1_diagnostics.parse_kvpool_metrics(text + "\n" + text)
    metadata = issue1_diagnostics.parse_kvpool_metric_metadata(text + "\n" + text)
    te = issue1_diagnostics.parse_te_metrics(
        "[Metrics] Transfer Engine Stats (over last 1s): Throughput: 12.50 MB/s "
        "| Latency Distribution (count=4): 0-10us 100%"
    )

    assert events["critical.wait_for_layer_load|layer=2"] == {
        "count": 4,
        "bytes": 256,
        "sum_ms": 15.0,
        "exclusive_sum_ms": 12.0,
        "max_ms": 5.0,
        "max_p50_ms": 2.0,
        "max_p95_ms": 5.0,
        "sample_count": 4,
    }
    assert metadata == {
        "intervals": 2,
        "schema_versions": [2],
        "events": 2,
        "missing_exclusive_events": 0,
        "malformed_lines": 0,
    }
    assert te == {
        "intervals": 1,
        "metric_lines": 1,
        "throughput_intervals": 1,
        "latency_intervals": 1,
        "mean_throughput_mb_s": 12.5,
        "max_throughput_mb_s": 12.5,
        "task_count": 4,
    }


def test_te_parser_accepts_latency_only_metric_line() -> None:
    result = issue1_diagnostics.parse_te_metrics(
        "[Metrics] Transfer Engine Stats (over last 1s): "
        "| Latency Distribution (count=3): 0-10us 100%"
    )

    assert result == {
        "intervals": 1,
        "metric_lines": 1,
        "throughput_intervals": 0,
        "latency_intervals": 1,
        "mean_throughput_mb_s": 0.0,
        "max_throughput_mb_s": 0.0,
        "task_count": 3,
    }


def test_observability_rejects_missing_role_metrics_before_formal() -> None:
    result = issue1_diagnostics.validate_observability(
        {
            "kvpool_events_by_role": {
                "prefill": {"mooncake.get": {"count": 1}},
                "decode": {},
            },
            "kvpool_metric_metadata_by_role": {
                "prefill": {
                    "intervals": 1,
                    "schema_versions": [2],
                    "events": 1,
                    "missing_exclusive_events": 0,
                    "malformed_lines": 0,
                },
                "decode": {
                    "intervals": 0,
                    "schema_versions": [],
                    "events": 0,
                    "missing_exclusive_events": 0,
                    "malformed_lines": 0,
                },
            },
            "te_metrics_by_role": {
                "prefill": {"metric_lines": 1},
                "decode": {"metric_lines": 0},
            },
        }
    )

    assert result["valid"] is False
    assert result["errors"] == [
        "Decode emitted no KVPool performance events",
        "Decode KVPool metric schema v2 evidence is invalid",
        "Decode emitted no Transfer Engine metrics",
    ]


def test_observability_rejects_old_metric_schema() -> None:
    result = issue1_diagnostics.validate_observability(
        {
            "kvpool_events_by_role": {
                "prefill": {"critical.wait": {"count": 1}},
                "decode": {"critical.wait": {"count": 1}},
            },
            "kvpool_metric_metadata_by_role": {
                role: {
                    "intervals": 1,
                    "schema_versions": [1],
                    "events": 1,
                    "missing_exclusive_events": 1,
                    "malformed_lines": 0,
                }
                for role in ("prefill", "decode")
            },
            "te_metrics_by_role": {
                "prefill": {"metric_lines": 1},
                "decode": {"metric_lines": 1},
            },
        }
    )

    assert result["valid"] is False
    assert result["errors"] == [
        "Prefill KVPool metric schema v2 evidence is invalid",
        "Decode KVPool metric schema v2 evidence is invalid",
    ]


def test_range_debug_events_are_structured_and_failures_are_counted() -> None:
    text = "\n".join(
        (
            'INFO [KVPOOL_RANGE_DEBUG] {"event":"range","direction":"load",'
            '"layer_id":2,"key_count":2,"requested_bytes":[64,128],'
            '"results":[64,-1]}',
            'INFO [KVPOOL_RANGE_DEBUG] {"event":"commit","layer_id":2,'
            '"key_count":2,"results":[0,0]}',
            "INFO [KVPOOL_RANGE_DEBUG] not-json",
        )
    )

    result = issue1_diagnostics.parse_range_debug_metrics(text)

    assert result == {
        "total_events": 2,
        "malformed_events": 1,
        "range_events": 1,
        "commit_events": 1,
        "whole_key_events": 0,
        "requested_bytes": 192,
        "key_count": 4,
        "failed_results": 1,
        "directions": {"load": 1},
        "layers": {"2": 2},
    }


def test_output_fingerprint_is_stable_without_retaining_predictions(
    tmp_path: Path,
) -> None:
    details = tmp_path / "details.jsonl"
    details.write_text(
        "\n".join(
            (
                json.dumps({"data_id": 2, "success": True, "prediction": "second"}),
                json.dumps({"data_id": 1, "success": True, "prediction": "first"}),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    result = issue1_diagnostics.fingerprint_predictions(details, 2)

    assert result["valid"] is True
    assert result["request_count"] == 2
    assert result["data_ids"] == [1, 2]
    assert len(result["prediction_sha256_by_data_id"]["1"]) == 64
    assert len(result["prediction_sha256_by_data_id"]["2"]) == 64
    assert "first" not in json.dumps(result)
    assert "second" not in json.dumps(result)


def test_output_consistency_requires_every_request_to_match() -> None:
    bulk = {
        "output_fingerprint": {
            "valid": True,
            "request_count": 2,
            "digest": "bulk",
            "prediction_sha256_by_data_id": {"1": "same", "2": "bulk-only"},
        }
    }
    alternative = {
        "output_fingerprint": {
            "valid": True,
            "request_count": 2,
            "digest": "alternative",
            "prediction_sha256_by_data_id": {"1": "same", "2": "changed"},
        }
    }

    result = issue1_diagnostics.validate_output_consistency(bulk, alternative)

    assert result["valid"] is False
    assert result["mismatched_data_ids"] == [2]
    assert result["bulk_digest"] == "bulk"
    assert result["alternative_digest"] == "alternative"


def test_slowdown_classifier_attributes_reuse_gate_wait() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 3,
                "max_waiting_capacity": 22,
                "max_waiting_deferred": 0,
            },
        },
        "kvpool_events": {},
    }
    reuse = {
        "request_throughput": 0.8,
        "request_count": 1,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 39,
                "preemption_delta": 0,
                "max_waiting_capacity": 0,
                "max_waiting_deferred": 0,
            },
        },
        "kvpool_events": {
            "critical.wait_for_layer_load|layer=4": {"sum_ms": 200.0},
            "reuse3.wait_for_save_layer|layer=4": {"sum_ms": 900.0},
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, reuse, alternative_name="reuse3"
    )

    assert result["slower"] is True
    assert result["cause"] == "layer_or_reuse_gate_wait"
    assert result["resolved"] is True
    assert result["evidence"] == {
        "role": "combined",
        "timing_category": "reuse_gate_ms",
        "delta_ms": 900.0,
        "observed_wall_gap_ms": 250.0,
        "aggregated_rank_time_explained_fraction": 3.6,
        "critical_path_delta_ms": 200.0,
        "critical_path_explained_fraction": 0.8,
    }
    assert result["timing_breakdown"]["dominant_positive_delta"] == (
        "reuse_gate_ms"
    )


def test_slowdown_classifier_rejects_background_timing_without_critical_wait() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events_by_role": {"prefill": {}, "decode": {}},
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 1,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events_by_role": {
            "prefill": {},
            "decode": {
                "mooncake.batch_copy_get|layer=4": {"sum_ms": 500.0}
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False
    candidate = result["evidence"]["candidate_timing"]
    assert candidate["timing_category"] == "mooncake_api_ms"
    assert candidate["critical_path_delta_ms"] == 0.0


def test_slowdown_classifier_attributes_background_timing_with_critical_wait() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events_by_role": {"prefill": {}, "decode": {}},
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 1,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events_by_role": {
            "prefill": {},
            "decode": {
                "critical.wait_for_layer_load|layer=4": {"sum_ms": 200.0},
                "mooncake.batch_copy_get|layer=4": {"sum_ms": 500.0},
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "decode_mooncake_transfer_or_session_overhead"
    assert result["evidence"]["timing_category"] == "mooncake_api_ms"
    assert result["evidence"]["critical_path_delta_ms"] == 200.0
    assert result["evidence"]["critical_path_explained_fraction"] == 0.8


def test_slowdown_classifier_does_not_double_count_nested_slot_reload() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events": {},
    }
    reuse3 = {
        "request_throughput": 0.8,
        "request_count": 1,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events": {
            "critical.wait_for_layer_load|layer=4": {
                "count": 1,
                "sum_ms": 200.0,
                "exclusive_sum_ms": 200.0,
            },
            "reuse3.slot_reload|layer=4": {
                "count": 1,
                "sum_ms": 900.0,
                "exclusive_sum_ms": 50.0,
            },
            "layerwise.batch_copy_get|layer=4": {
                "count": 1,
                "sum_ms": 850.0,
                "exclusive_sum_ms": 50.0,
            },
            "mooncake.batch_copy_get": {
                "count": 1,
                "sum_ms": 800.0,
                "exclusive_sum_ms": 800.0,
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, reuse3, alternative_name="reuse3"
    )

    assert result["cause"] == "mooncake_transfer_or_session_overhead"
    assert result["evidence"]["timing_category"] == "mooncake_api_ms"
    assert result["evidence"]["delta_ms"] == 800.0
    assert result["evidence"]["critical_path_delta_ms"] == 200.0
    timing = result["timing_breakdown"]["by_role"]["combined"]
    assert timing["alternative_ms"]["reuse_slot_orchestration_ms"] == 50.0
    assert timing["alternative_counts"]["reuse_slot_reload"] == 1


def test_slowdown_classifier_rejects_immaterial_timing_delta() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events": {},
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 100,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "kvpool_events": {
            "critical.wait_for_layer_load|layer=2": {"sum_ms": 10.0}
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False
    candidate = result["evidence"]["candidate_timing"]
    assert candidate["timing_category"] == "critical_wait_ms"
    assert candidate["observed_wall_gap_ms"] == 25000.0
    assert candidate["aggregated_rank_time_explained_fraction"] == 0.0004


def test_unconverted_reuse_capacity_does_not_masquerade_as_slowdown_cause() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 0,
                "max_waiting_capacity": 22,
                "max_waiting_deferred": 0,
            },
        },
    }
    reuse3 = {
        "request_throughput": 0.8,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 0,
                "max_waiting_capacity": 22,
                "max_waiting_deferred": 0,
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, reuse3, alternative_name="reuse3"
    )

    assert result["slower"] is True
    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False
    capacity = result["evidence"]["reuse3_capacity_conversion"]
    assert capacity["valid"] is False


def test_slowdown_classifier_compares_deferred_wait_to_bulk() -> None:
    common = {
        "max_context_requests": 8,
        "prometheus": {
            "mean_active_running": 8,
            "preemption_delta": 0,
            "max_waiting_capacity": 0,
            "max_waiting_deferred": 1,
        },
        "context_ms_per_1k_tokens": 1.0,
    }
    bulk = {"request_throughput": 1.0, "admission": common}
    layerwise = {"request_throughput": 0.8, "admission": common}

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False


def test_slowdown_classifier_attributes_increased_deferred_wait() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {
                "max_waiting_deferred": 0,
                "queue_time_sum_delta": 0,
            },
        },
    }
    layerwise = {
        "request_throughput": 0.8,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {
                "max_waiting_deferred": 2,
                "queue_time_sum_delta": 0.2,
            },
        },
        "request_count": 1,
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "kv_transfer_or_scheduler_deferred_wait"
    assert result["resolved"] is True


def test_slowdown_classifier_rejects_nonmaterial_deferred_wait_spike() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {
                "max_waiting_deferred": 0,
                "queue_time_sum_delta": 0,
            },
        },
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 100,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {
                "max_waiting_deferred": 2,
                "queue_time_sum_delta": 0.01,
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False


def test_slowdown_classifier_rejects_small_peak_admission_delta_without_sustained_loss() -> None:
    bulk = {
        "request_throughput": 1.0,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {
                "max_waiting_deferred": 0,
                "mean_active_running": 7,
            },
        },
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 100,
        "admission": {
            "max_context_requests": 7,
            "prometheus": {
                "max_waiting_deferred": 0,
                "mean_active_running": 7,
            },
        },
    }

    result = issue1_diagnostics.classify_slowdown(
        bulk, layerwise, alternative_name="layerwise"
    )

    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["resolved"] is False


def test_reuse_capacity_advantage_accepts_sustained_running_improvement() -> None:
    bulk = {
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 3,
                "max_waiting_capacity": 22,
            },
        }
    }
    reuse3 = {
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 39,
                "preemption_delta": 0,
                "max_waiting_capacity": 0,
            },
        }
    }

    result = issue1_diagnostics.validate_reuse_capacity_advantage(bulk, reuse3)

    assert result["valid"] is True
    assert result["advantages"] == {
        "higher_peak_contexts": False,
        "higher_sustained_running": True,
        "fewer_preemptions": True,
        "less_capacity_waiting": True,
    }


def test_reuse_capacity_advantage_rejects_peak_only_improvement() -> None:
    bulk = {
        "admission": {
            "max_context_requests": 20,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 0,
                "max_waiting_capacity": 22,
            },
        }
    }
    reuse3 = {
        "admission": {
            "max_context_requests": 40,
            "prometheus": {
                "mean_active_running": 18,
                "preemption_delta": 0,
                "max_waiting_capacity": 22,
            },
        }
    }

    result = issue1_diagnostics.validate_reuse_capacity_advantage(bulk, reuse3)

    assert result["valid"] is False
    assert result["advantages"]["higher_peak_contexts"] is True


def test_short_diagnostic_is_one_wave_and_does_not_repeat_formal() -> None:
    spec = issue1_diagnostics.short_diagnostic_spec(
        "test2",
        {
            "slower": True,
            "resolved": False,
            "cause": "unresolved_requires_short_diagnostic",
        },
    )

    assert spec is not None
    assert spec["variants"] == ["bulk", "layerwise", "reuse3"]
    assert spec["request_count_per_variant"] == 40
    assert spec["concurrency"] == 40
    assert spec["formal_rerun_required"] is False
    assert spec["enable_environment"]["VLLM_ASCEND_KVPOOL_RANGE_DEBUG"] == "1"


def test_short_diagnostic_is_not_requested_for_resolved_result() -> None:
    assert (
        issue1_diagnostics.short_diagnostic_spec(
            "test1", {"slower": True, "resolved": True}
        )
        is None
    )


def test_test2_short_diagnostic_is_skipped_for_direct_scheduler_cause() -> None:
    assert (
        issue1_diagnostics.short_diagnostic_spec(
            "test2",
            {
                "slower": True,
                "resolved": True,
                "cause": "scheduler_admission",
            },
        )
        is None
    )


def test_test2_short_diagnostic_isolates_layerwise_base_cost() -> None:
    formal = {
        "slower": True,
        "throughput_ratio": 0.8,
        "cause": "unresolved_requires_short_diagnostic",
        "resolved": False,
        "evidence": {},
    }
    range_debug = {
        "prefill": {"total_events": 1, "malformed_events": 0},
        "decode": {"total_events": 1, "malformed_events": 0},
    }
    bulk = {
        "request_throughput": 1.0,
        "request_count": 40,
        "admission": {
            "max_context_requests": 40,
            "prometheus": {"mean_active_running": 40},
        },
        "range_debug_by_role": range_debug,
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 40,
        "admission": {
            "max_context_requests": 1,
            "prometheus": {"mean_active_running": 1},
        },
        "range_debug_by_role": range_debug,
    }
    reuse3 = {
        "request_throughput": 0.82,
        "request_count": 40,
        "admission": {
            "max_context_requests": 1,
            "prometheus": {"mean_active_running": 1},
        },
        "range_debug_by_role": range_debug,
    }

    result = issue1_diagnostics.resolve_reuse3_with_layerwise_control(
        formal,
        bulk,
        layerwise,
        reuse3,
    )

    assert result["resolved"] is True
    assert result["cause"] == "layerwise_base_scheduler_admission"
    legs = result["evidence"]["differential_legs"]
    assert legs["layerwise_over_bulk"]["slower"] is True
    assert legs["reuse3_over_layerwise"]["slower"] is False


def test_short_diagnostic_resolves_formal_slowdown_with_complete_replay() -> None:
    formal = {
        "slower": True,
        "throughput_ratio": 0.8,
        "cause": "unresolved_requires_short_diagnostic",
        "resolved": False,
        "evidence": {"candidate_timing": {"timing_category": "none"}},
    }
    common_admission = {
        "max_context_requests": 8,
        "prometheus": {"max_waiting_deferred": 0},
    }
    bulk = {
        "request_throughput": 1.0,
        "request_count": 8,
        "admission": common_admission,
        "range_debug_by_role": {
            "prefill": {"total_events": 1, "malformed_events": 0},
            "decode": {"total_events": 1, "malformed_events": 0},
        },
        "kvpool_events_by_role": {"prefill": {}, "decode": {}},
    }
    layerwise = {
        "request_throughput": 0.8,
        "request_count": 8,
        "admission": common_admission,
        "range_debug_by_role": {
            "prefill": {"total_events": 27, "malformed_events": 0},
            "decode": {"total_events": 27, "malformed_events": 0},
        },
        "kvpool_events_by_role": {
            "prefill": {
                "critical.wait_for_layer_load|layer=2": {"sum_ms": 2500.0},
                "layerwise.attention_done_gate|layer=2": {"sum_ms": 3000.0},
            },
            "decode": {},
        },
    }

    result = issue1_diagnostics.resolve_with_short_diagnostic(
        formal,
        bulk,
        layerwise,
        alternative_name="layerwise",
    )

    assert result["resolved"] is True
    assert result["cause"] == "prefill_layer_or_reuse_gate_wait"
    assert result["throughput_ratio"] == 0.8
    assert result["evidence"]["source"] == "short_diagnostic"
    assert result["evidence"]["diagnostic_throughput_ratio"] == 0.8


def test_short_diagnostic_does_not_resolve_without_complete_range_evidence() -> None:
    formal = {
        "slower": True,
        "throughput_ratio": 0.8,
        "cause": "unresolved_requires_short_diagnostic",
        "resolved": False,
        "evidence": {},
    }
    point = {
        "request_throughput": 1.0,
        "request_count": 8,
        "admission": {
            "max_context_requests": 8,
            "prometheus": {"max_waiting_deferred": 0},
        },
        "range_debug_by_role": {
            "prefill": {"total_events": 0, "malformed_events": 0},
            "decode": {"total_events": 0, "malformed_events": 0},
        },
    }

    result = issue1_diagnostics.resolve_with_short_diagnostic(
        formal,
        point,
        point,
        alternative_name="layerwise",
    )

    assert result["resolved"] is False
    assert result["cause"] == "unresolved_requires_short_diagnostic"
    assert result["evidence"]["short_diagnostic_errors"]
