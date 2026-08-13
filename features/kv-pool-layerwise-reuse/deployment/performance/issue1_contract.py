from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

BLOCK_SIZE = 128
INPUT_TOKENS = 32000
SEED_TOKENS = 28800
FORMAL_BLOCKS = INPUT_TOKENS // BLOCK_SIZE
SEED_BLOCKS = SEED_TOKENS // BLOCK_SIZE
EXPECTED_HIT_RATE = SEED_TOKENS / INPUT_TOKENS
PREFERRED_TEST2_CONCURRENCY = 40
WARMUP_REQUESTS = 8
SHARED_SEED_REQUESTS = 1
TEST1_FORMAL_REQUESTS = 125
TEST2_FORMAL_REQUESTS = 100
SERVER_SEED = 1024
CLIENT_FIXTURE_SEED = 1023

RUNTIME_CONSTANTS = MappingProxyType(
    {
        "block_size": BLOCK_SIZE,
        "max_model_len": 32768,
        "max_num_batched_tokens": 32768,
        "gpu_memory_utilization": 0.95,
        "enable_chunked_prefill": True,
        "enable_prefix_caching": False,
        "async_scheduling": True,
        "server_seed": SERVER_SEED,
        "client_fixture_seed": CLIENT_FIXTURE_SEED,
        "request_rate": 0,
        "prefix_mode": "shared",
    }
)


@dataclass(frozen=True)
class Issue1Point:
    test: str
    topology: str
    input_tokens: int
    output_tokens: int
    variant: str
    concurrency: int
    formal_requests: int


@dataclass(frozen=True)
class CapacitySelection:
    concurrency: int
    bulk_request_capacity: int
    reuse3_request_capacity: int
    reason: str


TEST1_POINTS = (
    Issue1Point("test1", "dp1", INPUT_TOKENS, 128, "bulk", 8, TEST1_FORMAL_REQUESTS),
    Issue1Point(
        "test1", "dp1", INPUT_TOKENS, 128, "layerwise", 8, TEST1_FORMAL_REQUESTS
    ),
)


def test2_points(concurrency: int) -> tuple[Issue1Point, ...]:
    if concurrency <= 0:
        raise ValueError("test2 concurrency must be positive")
    return (
        Issue1Point(
            "test2",
            "dp1",
            INPUT_TOKENS,
            1,
            "bulk",
            concurrency,
            TEST2_FORMAL_REQUESTS,
        ),
        Issue1Point(
            "test2",
            "dp1",
            INPUT_TOKENS,
            1,
            "reuse3",
            concurrency,
            TEST2_FORMAL_REQUESTS,
        ),
    )


def point_id(point: Issue1Point) -> str:
    return (
        f"{point.test}-{point.topology}-{point.input_tokens}-{point.variant}"
        f"-o{point.output_tokens}-c{point.concurrency}"
    )


def long_prefill_token_threshold(concurrency: int) -> int:
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")
    budget = int(RUNTIME_CONSTANTS["max_num_batched_tokens"])
    threshold = (budget // concurrency // BLOCK_SIZE) * BLOCK_SIZE
    if threshold < BLOCK_SIZE:
        raise ValueError(
            f"concurrency {concurrency} cannot receive one {BLOCK_SIZE}-token chunk "
            f"within budget {budget}"
        )
    return threshold


def expected_admission_contexts(
    point: Issue1Point,
    *,
    bulk_request_capacity: int | None = None,
) -> int:
    if point.test == "test1":
        return point.concurrency
    if point.variant == "reuse3":
        return point.concurrency
    if bulk_request_capacity is None:
        raise ValueError("Test 2 BULK admission requires startup capacity")
    # BULK is intentionally over capacity. Its admission canary only proves
    # the old single-context scheduler behavior is gone; capacity pressure is
    # checked via waiting_by_reason and sustained running samples.
    return 2


def select_test2_concurrency(
    bulk_capacity_tokens: int,
    reuse3_capacity_tokens: int,
) -> CapacitySelection:
    if bulk_capacity_tokens <= 0 or reuse3_capacity_tokens <= 0:
        raise ValueError("capacity tokens must be positive")

    bulk_capacity = bulk_capacity_tokens // INPUT_TOKENS
    reuse3_capacity = reuse3_capacity_tokens // INPUT_TOKENS
    if (
        PREFERRED_TEST2_CONCURRENCY > bulk_capacity
        and PREFERRED_TEST2_CONCURRENCY <= reuse3_capacity
    ):
        return CapacitySelection(
            PREFERRED_TEST2_CONCURRENCY,
            bulk_capacity,
            reuse3_capacity,
            "preferred_c40_crosses_bulk_and_fits_reuse3",
        )

    raise ValueError(
        "reviewed c40 is not above BULK capacity and within REUSE3 capacity; "
        "freeze a new handoff before selecting another concurrency"
    )


def build_issue1_run_contract(
    *,
    image_digest: str,
    bulk_capacity_tokens: int,
    reuse3_capacity_tokens: int,
    npu_node: str,
) -> dict[str, object]:
    selection = select_test2_concurrency(
        bulk_capacity_tokens,
        reuse3_capacity_tokens,
    )
    points = (*TEST1_POINTS, *test2_points(selection.concurrency))
    return {
        "schema_version": 1,
        "npu_node": npu_node,
        "image_digest": image_digest,
        "expected_points": [point_id(point) for point in points],
        "formal_request_counts": {
            "test1": TEST1_FORMAL_REQUESTS,
            "test2": TEST2_FORMAL_REQUESTS,
        },
        "warmup_request_count": WARMUP_REQUESTS,
        "seed_request_count": SHARED_SEED_REQUESTS,
        "input_tokens": INPUT_TOKENS,
        "seed_tokens": SEED_TOKENS,
        "formal_blocks": FORMAL_BLOCKS,
        "seed_blocks": SEED_BLOCKS,
        "expected_hit_tokens": SEED_TOKENS,
        "expected_hit_rate": EXPECTED_HIT_RATE,
        "local_prefix_caching": False,
        "request_rate": 0,
        "server_seed": SERVER_SEED,
        "client_fixture_seed": CLIENT_FIXTURE_SEED,
        "test2_concurrency": selection.concurrency,
        "test2_concurrency_reason": selection.reason,
        "bulk_request_capacity": selection.bulk_request_capacity,
        "reuse3_request_capacity": selection.reuse3_request_capacity,
        "test2_long_prefill_token_threshold": long_prefill_token_threshold(
            selection.concurrency
        ),
        "test1_long_prefill_token_threshold": long_prefill_token_threshold(8),
        "max_num_partial_prefills": {
            "test1": 8,
            "test2": selection.concurrency,
        },
        "max_long_partial_prefills": {
            "test1": 8,
            "test2": selection.concurrency,
        },
        "expected_admission_contexts": {
            point_id(point): expected_admission_contexts(
                point,
                bulk_request_capacity=selection.bulk_request_capacity,
            )
            for point in points
        },
        "requires_multiple_server_contexts": True,
        "requires_capacity_waiting_for_bulk_test2": True,
        "requires_reuse3_running_gt_bulk": True,
        "raw_characterization_only": True,
    }
