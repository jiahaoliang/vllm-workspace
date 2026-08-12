from __future__ import annotations

import pytest

from performance import contract


def test_variant_contract() -> None:
    assert contract.VARIANTS["bulk"].prefill["use_layerwise"] is False
    assert contract.VARIANTS["bulk"].prefill["layerwise_prefetch_layers"] == 3
    assert "layerwise_num_shared_buffers" not in contract.VARIANTS["layerwise"].prefill
    assert contract.VARIANTS["reuse3"].prefill["layerwise_num_shared_buffers"] == 3
    assert "layerwise_num_shared_buffers" not in contract.VARIANTS["reuse3"].decode
    assert contract.outputs_for("bulk") == (1,)
    assert contract.outputs_for("layerwise") == (1,)
    assert contract.outputs_for("reuse3") == (1,)


def test_high_hit_matrix_is_exactly_three_points() -> None:
    assert tuple(contract.TOPOLOGIES) == ("dp1",)
    assert contract.TOPOLOGIES["dp1"].concurrency == (8,)
    assert contract.INPUT_TOKENS == (16384,)
    assert contract.VARIANT_ORDER == ("bulk", "layerwise", "reuse3")
    assert contract.build_matrix() == (
        contract.WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
    )
    assert contract.build_matrix("dp1") == contract.build_matrix()
    with pytest.raises(ValueError, match="unsupported topology"):
        contract.build_matrix("dp2")


def test_request_counts_are_frozen() -> None:
    assert contract.sample_counts(8) == (8, 64, 1)
    assert contract.SEED_REQUEST_COUNT == 64
    with pytest.raises(ValueError, match="concurrency must be 8"):
        contract.sample_counts(1)


def test_high_hit_contract_is_self_describing() -> None:
    assert contract.SEED_TOKENS == 13312
    assert contract.SEED_BLOCKS == 104
    assert contract.FORMAL_BLOCKS == 128
    assert contract.EXPECTED_HIT_RATE == 0.8125
    assert contract.build_run_contract("sha256:image") == {
        "topologies": ["dp1"],
        "npu_node": "n1",
        "image_digest": "sha256:image",
        "expected_points": [
            "dp1-16384-bulk-o1-c8",
            "dp1-16384-layerwise-o1-c8",
            "dp1-16384-reuse3-o1-c8",
        ],
        "formal_repetitions": 1,
        "warmup_request_count": 8,
        "seed_request_count": 64,
        "formal_request_count": 64,
        "formal_concurrency_waves": 8,
        "seed_tokens": 13312,
        "seed_blocks": 104,
        "formal_blocks": 128,
        "expected_hit_tokens": 13312,
        "expected_hit_rate": 0.8125,
        "expected_need_to_load_tokens": 13312,
        "local_prefix_caching": False,
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
        "enable_prefix_caching": False,
        "layerwise_prefetch_layers": 3,
    }
