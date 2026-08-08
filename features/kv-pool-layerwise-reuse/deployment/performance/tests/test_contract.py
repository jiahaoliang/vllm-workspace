from __future__ import annotations

import pytest

from performance import contract


def test_variant_contract() -> None:
    assert contract.VARIANTS["bulk"].prefill["use_layerwise"] is False
    assert contract.VARIANTS["bulk"].prefill["layerwise_prefetch_layers"] == 3
    assert "layerwise_num_shared_buffers" not in contract.VARIANTS["layerwise"].prefill
    assert contract.VARIANTS["reuse3"].prefill["layerwise_num_shared_buffers"] == 3
    assert "layerwise_num_shared_buffers" not in contract.VARIANTS["reuse3"].decode
    assert contract.outputs_for("bulk") == (1, 128)
    assert contract.outputs_for("reuse3") == (1,)


def test_topology_matrix_and_rotation() -> None:
    assert contract.TOPOLOGIES["dp1"].concurrency == (1, 2, 4, 8, 16, 32)
    assert contract.TOPOLOGIES["dp2"].concurrency == (2, 4, 8, 16, 32, 64)
    assert contract.DP1_ROTATION[4096] == ("bulk", "layerwise", "reuse3")
    assert contract.DP2_ROTATION[4096] == ("reuse3", "layerwise", "bulk")
    matrix = contract.build_matrix()
    assert len(matrix) == 180
    assert {point.input_tokens for point in matrix} == {4096, 16384, 32768}
    assert not any(
        point.variant == "reuse3" and point.output_tokens == 128 for point in matrix
    )


@pytest.mark.parametrize(
    ("concurrency", "warmup", "formal"),
    [(1, 8, 32), (4, 8, 32), (16, 32, 128), (64, 128, 512)],
)
def test_sample_counts(concurrency: int, warmup: int, formal: int) -> None:
    assert contract.sample_counts(concurrency) == (warmup, formal, 3)


def test_adaptive_stop_and_stable_duration() -> None:
    history = (
        contract.PointResult(100.0, 100.0),
        contract.PointResult(104.0, 160.0),
        contract.PointResult(107.0, 250.0),
    )
    assert contract.adaptive_stop(history, hard_failure=False).stop is True
    assert contract.adaptive_stop(history[:2], hard_failure=False).stop is False
    assert contract.adaptive_stop((), hard_failure=True).stop is True
    assert contract.stable_measurement_valid(900.0, 3001.0)
    assert not contract.stable_measurement_valid(1001.0, 3000.0)


def test_runtime_constants_are_frozen() -> None:
    assert contract.RUNTIME_CONSTANTS == {
        "block_size": 128,
        "max_model_len": 65536,
        "max_num_batched_tokens": 1024,
        "max_num_seqs": 64,
        "gpu_memory_utilization": 0.90,
        "tensor_parallel_size": 2,
        "pipeline_parallel_size": 1,
        "prefill_context_parallel_size": 1,
        "decode_context_parallel_size": 1,
        "enable_chunked_prefill": True,
        "layerwise_prefetch_layers": 3,
    }
