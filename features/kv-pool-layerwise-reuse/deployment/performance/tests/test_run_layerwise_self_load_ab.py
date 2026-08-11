from __future__ import annotations

import json
from pathlib import Path

import pytest

from performance import diagnose_layerwise_prefill as diagnose
from performance import run_layerwise_self_load_ab as ab


class FakeRunner:
    def __init__(self, image_id: str) -> None:
        self.image_id = image_id

    def run(self, command: object) -> str:
        del command
        return json.dumps(
            {
                "items": [
                    {
                        "metadata": {"labels": {"app": role}},
                        "spec": {"containers": [{"image": "image:candidate"}]},
                        "status": {
                            "containerStatuses": [{"imageID": self.image_id}]
                        },
                    }
                    for role in ("prefill", "decode")
                ]
            }
        )


def test_deployed_candidate_image_requires_both_matching_config_digests(
    tmp_path: Path,
) -> None:
    ab._assert_deployed_image(
        FakeRunner("sha256:candidate"),
        tmp_path,
        "image:candidate",
        "sha256:candidate",
    )

    observed = json.loads((tmp_path / "deployed-image.json").read_text())
    assert set(observed) == {"prefill", "decode"}


def test_deployed_candidate_image_rejects_stale_image_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="deployed candidate image mismatch"):
        ab._assert_deployed_image(
            FakeRunner("sha256:stale"),
            tmp_path,
            "image:candidate",
            "sha256:candidate",
        )


def test_causal_parser_accepts_source_commit_and_custom_npu_node() -> None:
    args = ab._parser().parse_args(
        [
            "--output",
            "output",
            "--control",
            "control",
            "--image",
            "image:candidate",
            "--image-digest",
            "sha256:manifest",
            "--patch-sha256",
            "a" * 64,
            "--source-commit",
            "57d3c214e642cdbb529400f0742d1a98a8d38708",
            "--npu-node",
            "custom-node",
        ]
    )

    assert args.source_commit == "57d3c214e642cdbb529400f0742d1a98a8d38708"
    assert args.npu_node == "custom-node"


class DirtySourceRunner:
    def run(self, command: object) -> str:
        description = getattr(command, "description")
        if description == "dirty-repos-vllm-ascend":
            return " M vllm_ascend/example.py\n"
        if description.startswith("source-"):
            return "a" * 40 + "\n"
        return ""


def test_source_identity_rejects_dirty_vllm_ascend_checkout(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="repos/vllm-ascend checkout must be clean"):
        ab._capture_source_identity(
            DirtySourceRunner(),
            tmp_path,
            "57d3c214e642cdbb529400f0742d1a98a8d38708",
        )


def _iteration(
    iteration: int,
    elapsed_ms: float,
    context_tokens: int = 1024,
) -> str:
    return (
        f"Iteration({iteration}): 1 context requests, "
        f"{context_tokens} context tokens, "
        "0 generation requests, 0 generation tokens, "
        f"iteration elapsed time: {elapsed_ms} ms\n"
    )


def test_parse_formal_prefill_uses_last_contiguous_iterations(
    tmp_path: Path,
) -> None:
    log = tmp_path / "prefill.log"
    log.write_text(
        _iteration(1, 99.0)
        + "".join(
            _iteration(iteration, float(iteration - 1))
            for iteration in range(2, 6)
        ),
        encoding="utf-8",
    )

    stats = diagnose.parse_formal_prefill(
        log,
        expected_iterations=4,
        context_tokens=1024,
    )

    assert stats.count == 4
    assert (stats.first_iteration, stats.last_iteration) == (2, 5)
    assert stats.mean_ms == pytest.approx(2.5)
    assert stats.median_ms == pytest.approx(2.5)
    assert stats.p95_ms == pytest.approx(4.0)
    assert stats.total_ms == pytest.approx(10.0)


def test_parse_sawtooth_recovers_synthetic_prior_key_slope(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.log"
    baseline = tmp_path / "baseline.log"
    candidate.write_text(
        "".join(
            _iteration(iteration + 1, 7.0 + (iteration % 16) * 8 * 0.25)
            for iteration in range(32)
        ),
        encoding="utf-8",
    )
    baseline.write_text(
        "".join(_iteration(iteration + 1, 2.0) for iteration in range(32)),
        encoding="utf-8",
    )

    stats = diagnose.parse_sawtooth(
        candidate,
        expected_iterations=32,
        context_tokens=1024,
        baseline_path=baseline,
    )

    assert stats.intercept_ms == pytest.approx(5.0)
    assert stats.slope_ms_per_prior_key == pytest.approx(0.25)
    assert stats.r_squared == pytest.approx(1.0)
