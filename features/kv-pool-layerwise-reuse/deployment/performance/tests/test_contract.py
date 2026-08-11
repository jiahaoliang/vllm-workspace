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


def test_rapid_matrix_is_exactly_five_points() -> None:
    assert tuple(contract.TOPOLOGIES) == ("dp1",)
    assert contract.TOPOLOGIES["dp1"].concurrency == (8,)
    assert contract.INPUT_TOKENS == (16384,)
    assert contract.VARIANT_ORDER == ("bulk", "layerwise", "reuse3")
    assert contract.build_matrix() == (
        contract.WorkloadPoint("dp1", 16384, 128, "bulk", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        contract.WorkloadPoint("dp1", 16384, 128, "layerwise", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
    )
    assert contract.build_matrix("dp1") == contract.build_matrix()
    with pytest.raises(ValueError, match="unsupported topology"):
        contract.build_matrix("dp2")


def test_request_counts_are_frozen() -> None:
    assert contract.sample_counts(8) == (8, 64, 1)
    with pytest.raises(ValueError, match="concurrency must be 8"):
        contract.sample_counts(1)


def test_rapid_run_contract_is_self_describing() -> None:
    assert contract.build_run_contract("sha256:image") == {
        "topologies": ["dp1"],
        "npu_node": "n1",
        "image_digest": "sha256:image",
        "expected_points": [
            "dp1-16384-bulk-o128-c8",
            "dp1-16384-bulk-o1-c8",
            "dp1-16384-layerwise-o128-c8",
            "dp1-16384-layerwise-o1-c8",
            "dp1-16384-reuse3-o1-c8",
        ],
        "formal_repetitions": 1,
        "warmup_request_count": 8,
        "formal_request_count": 64,
        "formal_concurrency_waves": 8,
        "calculator": "total",
        "single_wave": False,
        "raw_characterization_only": True,
    }

    assert (
        contract.build_run_contract("sha256:image", npu_node="m1")["npu_node"] == "m1"
    )


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
