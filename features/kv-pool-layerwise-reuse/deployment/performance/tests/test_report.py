from __future__ import annotations

import json
import shutil
import hashlib
from pathlib import Path

import pytest

from performance import report
from performance.contract import WorkloadPoint


POINT = "dp1-4096-bulk-o1-c1"


def refresh_checksums(root: Path) -> None:
    artifacts = sorted(
        path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n"
            for path in artifacts
        )
    )


@pytest.fixture
def valid_tree(tmp_path: Path) -> Path:
    (tmp_path / "points" / POINT / "warmup" / "attempt-1" / "raw").mkdir(
        parents=True
    )
    for repetition in range(1, 4):
        raw = (
            tmp_path
            / "points"
            / POINT
            / f"formal-{repetition}"
            / "attempt-1"
            / "raw"
        )
        raw.mkdir(parents=True)
        (raw / "summary.json").write_text(
            json.dumps(
                {
                    "valid": True,
                    "image_digest": "sha256:image",
                    "metrics": {
                        "Input Token Throughput": 100.0 + repetition,
                        "Request Throughput": 2.0,
                        "TTFT P95": 10.0,
                        "E2EL P95": 11.0,
                        "Achieved Concurrency": 1.0,
                    },
                }
            )
        )
    (tmp_path / "points" / POINT / "identity.json").write_text(
        json.dumps({"image_digest": "sha256:image", "variant": "bulk"})
    )
    (tmp_path / "run-contract.json").write_text(
        json.dumps(
            {
                "image_digest": "sha256:image",
                "expected_points": [POINT],
                "formal_repetitions": 3,
            }
        )
    )
    for name in (
        "handoff.json",
        "source-identity.json",
        "client-identity.json",
        "restoration.json",
    ):
        (tmp_path / name).write_text("{}\n")
    refresh_checksums(tmp_path)
    return tmp_path


def test_missing_formal_repetition_is_rejected(valid_tree: Path) -> None:
    shutil.rmtree(valid_tree / "points" / POINT / "formal-2")

    errors = report.validate_evidence(valid_tree)

    assert any("formal repetition 2" in error for error in errors)


def test_image_drift_is_rejected(valid_tree: Path) -> None:
    identity_path = valid_tree / "points" / POINT / "identity.json"
    identity = json.loads(identity_path.read_text())
    identity["image_digest"] = "sha256:other"
    identity_path.write_text(json.dumps(identity))

    errors = report.validate_evidence(valid_tree)

    assert any("image digest drift" in error for error in errors)


def test_checksum_corruption_is_rejected(valid_tree: Path) -> None:
    (valid_tree / "client-identity.json").write_text('{"changed": true}\n')

    errors = report.validate_evidence(valid_tree)

    assert "SHA256SUMS replay failed: client-identity.json" in errors


def test_raw_report_keeps_repetitions_and_direct_ratios(valid_tree: Path) -> None:
    point_root = valid_tree / "points" / POINT
    point_ids = [POINT]
    for variant, multiplier in (("layerwise", 1.2), ("reuse3", 1.5)):
        point_id = f"dp1-4096-{variant}-o1-c1"
        target = valid_tree / "points" / point_id
        shutil.copytree(point_root, target)
        (target / "identity.json").write_text(
            json.dumps({"image_digest": "sha256:image", "variant": variant})
        )
        for summary_path in target.glob("formal-*/attempt-*/raw/summary.json"):
            summary = json.loads(summary_path.read_text())
            summary["metrics"]["Input Token Throughput"] *= multiplier
            summary_path.write_text(json.dumps(summary))
        point_ids.append(point_id)
    contract = json.loads((valid_tree / "run-contract.json").read_text())
    contract["expected_points"] = point_ids
    (valid_tree / "run-contract.json").write_text(json.dumps(contract))
    refresh_checksums(valid_tree)

    text = report.render_report(valid_tree)

    assert text.count("| dp1 | 4096 | 1 | BULK |") == 3
    assert text.count("| dp1 | 4096 | 1 | LAYERWISE |") == 3
    assert text.count("| dp1 | 4096 | 1 | REUSE3 |") == 3
    assert "LAYERWISE / BULK" in text
    assert "REUSE3 / LAYERWISE" in text
    assert "REUSE3 / BULK" in text
    assert "p-value" not in text
    assert "confidence interval" not in text
    assert "Performance PASS" not in text


def test_aisbench_raw_summary_requires_exact_tokens_and_stable_duration(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    performance = raw / "aisbench-output" / "performances" / "service"
    performance.mkdir(parents=True)
    (performance / "bulk.json").write_text(
        json.dumps(
            {
                "Input Token Throughput": {"stable": "4096 token/s"},
                "Request Throughput": {"stable": "2 req/s"},
                "Concurrency": {"stable": 4},
                "Output Token Throughput": {"stable": "2 token/s"},
                "Benchmark Duration": {"stable": "4000 ms"},
                "Failed Requests": {"stable": 0},
                "Success Requests": {"stable": 2},
            }
        ),
        encoding="utf-8",
    )
    (performance / "bulk.csv").write_text(
        "Performance Parameters,Stage,Average,Max,P95,N\n"
        "E2EL,stable,1.0 ms,1000 ms,900 ms,2\n"
        "TTFT,stable,1.0 ms,900 ms,800 ms,2\n",
        encoding="utf-8",
    )
    (performance / "bulk_details.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "success": True,
                    "input_tokens": 4096,
                    "output_tokens": 1,
                }
            )
            + "\n"
            for _ in range(2)
        ),
        encoding="utf-8",
    )

    summary = report.summarize_aisbench_attempt(
        raw,
        WorkloadPoint("dp1", 4096, 1, "bulk", 4),
        request_count=2,
        image_digest="sha256:image",
    )

    assert summary["valid"] is True
    metrics = summary["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["E2EL P95"] == 900
    assert metrics["Input Token Throughput"] == 4096
