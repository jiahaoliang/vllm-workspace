from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


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


@dataclass(frozen=True)
class PointResult:
    throughput: float
    p95_latency: float


@dataclass(frozen=True)
class StopDecision:
    stop: bool
    reason: str | None = None


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

TOPOLOGIES = MappingProxyType(
    {
        "dp1": Topology("dp1", 1, 2, 1, 2, (1, 2, 4, 8, 16, 32)),
        "dp2": Topology("dp2", 2, 4, 1, 2, (2, 4, 8, 16, 32, 64)),
    }
)
INPUT_TOKENS = (4096, 16384, 32768)
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
DP1_ROTATION = MappingProxyType(
    {
        4096: ("bulk", "layerwise", "reuse3"),
        16384: ("layerwise", "reuse3", "bulk"),
        32768: ("reuse3", "bulk", "layerwise"),
    }
)
DP2_ROTATION = MappingProxyType(
    {length: tuple(reversed(order)) for length, order in DP1_ROTATION.items()}
)


def outputs_for(variant: str) -> tuple[int, ...]:
    return VARIANTS[variant].outputs


def build_matrix(topology: str | None = None) -> tuple[WorkloadPoint, ...]:
    topology_names = (topology,) if topology is not None else tuple(TOPOLOGIES)
    points: list[WorkloadPoint] = []
    for topology_name in topology_names:
        selected = TOPOLOGIES[topology_name]
        rotation = DP1_ROTATION if topology_name == "dp1" else DP2_ROTATION
        for input_tokens in INPUT_TOKENS:
            for variant in rotation[input_tokens]:
                for output_tokens in outputs_for(variant):
                    for concurrency in selected.concurrency:
                        points.append(
                            WorkloadPoint(
                                topology_name,
                                input_tokens,
                                output_tokens,
                                variant,
                                concurrency,
                            )
                        )
    return tuple(points)


def sample_counts(concurrency: int) -> tuple[int, int, int]:
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")
    return max(8, 2 * concurrency), max(32, 8 * concurrency), 3


def stable_measurement_valid(max_e2el_ms: float, duration_ms: float) -> bool:
    return max_e2el_ms >= 0 and max_e2el_ms * 3 < duration_ms


def adaptive_stop(
    history: tuple[PointResult, ...], hard_failure: bool
) -> StopDecision:
    if hard_failure:
        return StopDecision(True, "hard failure")
    if len(history) < 3:
        return StopDecision(False)
    transitions: list[bool] = []
    for previous, current in zip(history[-3:-1], history[-2:]):
        if previous.throughput <= 0 or previous.p95_latency <= 0:
            transitions.append(False)
            continue
        throughput_gain = current.throughput / previous.throughput - 1
        latency_growth = current.p95_latency / previous.p95_latency - 1
        transitions.append(throughput_gain < 0.05 and latency_growth > 0.50)
    if all(transitions):
        return StopDecision(True, "two consecutive soft-saturation transitions")
    return StopDecision(False)
