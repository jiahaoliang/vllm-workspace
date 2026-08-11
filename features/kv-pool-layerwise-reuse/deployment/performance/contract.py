from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Variant:
    name: str
    prefill: Mapping[str, Any]
    decode: Mapping[str, Any]
    outputs: tuple[int, ...]


@dataclass(frozen=True)
class Topology:
    name: str
    prefill_dp: int
    prefill_npus: int
    decode_dp: int
    decode_npus: int
    concurrency: tuple[int, ...]


@dataclass(frozen=True)
class WorkloadPoint:
    topology: str
    input_tokens: int
    output_tokens: int
    variant: str
    concurrency: int


def _settings(**values: Any) -> Mapping[str, Any]:
    return MappingProxyType(values)


VARIANTS = MappingProxyType(
    {
        "bulk": Variant(
            "bulk",
            _settings(use_layerwise=False, layerwise_prefetch_layers=3),
            _settings(use_layerwise=False, layerwise_prefetch_layers=3),
            (1, 128),
        ),
        "layerwise": Variant(
            "layerwise",
            _settings(use_layerwise=True, layerwise_prefetch_layers=3),
            _settings(use_layerwise=True, layerwise_prefetch_layers=3),
            (1, 128),
        ),
        "reuse3": Variant(
            "reuse3",
            _settings(
                use_layerwise=True,
                layerwise_prefetch_layers=3,
                layerwise_num_shared_buffers=3,
            ),
            _settings(use_layerwise=True, layerwise_prefetch_layers=3),
            (1,),
        ),
    }
)

TOPOLOGIES = MappingProxyType({"dp1": Topology("dp1", 1, 2, 1, 2, (8,))})
INPUT_TOKENS = (16384,)
VARIANT_ORDER = ("bulk", "layerwise", "reuse3")
WARMUP_REQUEST_COUNT = 8
FORMAL_REQUEST_COUNT = 64
FORMAL_REPETITIONS = 1
RUNTIME_CONSTANTS = MappingProxyType(
    {
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
)


def outputs_for(variant: str) -> tuple[int, ...]:
    return VARIANTS[variant].outputs


def build_matrix(topology: str | None = None) -> tuple[WorkloadPoint, ...]:
    if topology not in (None, "dp1"):
        raise ValueError(f"unsupported topology: {topology}")
    return (
        WorkloadPoint("dp1", 16384, 128, "bulk", 8),
        WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        WorkloadPoint("dp1", 16384, 128, "layerwise", 8),
        WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
    )


def point_id(point: WorkloadPoint) -> str:
    return f"{point.topology}-{point.input_tokens}-{point.variant}-o{point.output_tokens}-c{point.concurrency}"


def build_run_contract(image_digest: str, npu_node: str = "n1") -> dict[str, object]:
    return {
        "topologies": ["dp1"],
        "npu_node": npu_node,
        "image_digest": image_digest,
        "expected_points": [point_id(point) for point in build_matrix()],
        "formal_repetitions": FORMAL_REPETITIONS,
        "warmup_request_count": WARMUP_REQUEST_COUNT,
        "formal_request_count": FORMAL_REQUEST_COUNT,
        "formal_concurrency_waves": FORMAL_REQUEST_COUNT // TOPOLOGIES["dp1"].concurrency[0],
        "calculator": "total",
        "single_wave": False,
        "raw_characterization_only": True,
    }


def sample_counts(concurrency: int) -> tuple[int, int, int]:
    if concurrency != 8:
        raise ValueError("concurrency must be 8")
    return WARMUP_REQUEST_COUNT, FORMAL_REQUEST_COUNT, FORMAL_REPETITIONS
