from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from performance import report
from performance.contract import WorkloadPoint, build_run_contract

POINTS = (
    "dp1-16384-bulk-o128-c8",
    "dp1-16384-bulk-o1-c8",
    "dp1-16384-layerwise-o128-c8",
    "dp1-16384-layerwise-o1-c8",
    "dp1-16384-reuse3-o1-c8",
)
POINT = POINTS[0]


def refresh_checksums(root: Path) -> None:
    artifacts = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (root / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n" for path in artifacts)
    )


@pytest.fixture
def valid_tree(tmp_path: Path) -> Path:
    for index, point in enumerate(POINTS, start=1):
        variant = point.split("-")[2]
        for phase in ("warmup", "formal-1"):
            raw = tmp_path / "points" / point / phase / "attempt-1" / "raw"
            raw.mkdir(parents=True)
            (raw / "fixture-reference.json").write_text(
                json.dumps(
                    {
                        "path": f"fixtures/tokens-16384-c64/{phase}.jsonl",
                        "sha256": hashlib.sha256(b"fixture\n").hexdigest(),
                    }
                )
            )
        raw = tmp_path / "points" / point / "formal-1" / "attempt-1" / "raw"
        (raw / "details.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "data_id": request_index,
                        "uuid": f"{point}-request-{request_index}",
                        "success": True,
                        "input_tokens": 16384,
                        "output_tokens": 128 if "-o128-" in point else 1,
                    }
                )
                + "\n"
                for request_index in range(8)
            ),
            encoding="utf-8",
        )
        (raw / "summary.json").write_text(
            json.dumps(
                {
                    "valid": True,
                    "image_digest": "sha256:image",
                    "request_count": 8,
                    "stage_request_count": 8,
                    "measurement_stage": "total",
                    "single_wave": True,
                    "raw_details": "details.jsonl",
                    "metrics": {
                        "Input Token Throughput": 100.0 * index,
                        "Request Throughput": 2.0,
                        "TTFT P95": 10.0,
                        "E2EL P95": 11.0,
                        "Achieved Concurrency": 8.0,
                    },
                }
            )
        )
        (tmp_path / "points" / point / "identity.json").write_text(
            json.dumps({"image_digest": "sha256:image", "variant": variant})
        )
    (tmp_path / "run-contract.json").write_text(json.dumps(build_run_contract("sha256:image")))
    fixture_root = tmp_path / "fixtures" / "tokens-16384-c64"
    fixture_root.mkdir(parents=True)
    for name in ("manifest.json", "warmup.jsonl", "formal-1.jsonl"):
        (fixture_root / name).write_text("fixture\n")
    for variant in ("bulk", "layerwise", "reuse3"):
        raw = tmp_path / "variants" / variant / "raw"
        raw.mkdir(parents=True)
        (raw / "vllm-prefill.log").write_text("prefill\n")
        (raw / "vllm-decode.log").write_text("decode\n")
    for name in (
        "handoff.json",
        "source-identity.json",
        "client-identity.json",
        "restoration.json",
    ):
        (tmp_path / name).write_text("{}\n")
    refresh_checksums(tmp_path)
    return tmp_path


def test_exact_rapid_evidence_is_accepted(valid_tree: Path) -> None:
    assert report.validate_evidence(valid_tree) == []


def test_missing_formal_repetition_is_rejected(valid_tree: Path) -> None:
    shutil.rmtree(valid_tree / "points" / POINT / "formal-1")

    errors = report.validate_evidence(valid_tree)

    assert any("formal repetition 1" in error for error in errors)


def test_extra_point_is_rejected(valid_tree: Path) -> None:
    shutil.copytree(valid_tree / "points" / POINT, valid_tree / "points" / "extra")
    refresh_checksums(valid_tree)

    assert "unexpected point directory: extra" in report.validate_evidence(valid_tree)


def test_unexpected_formal_phase_is_rejected(valid_tree: Path) -> None:
    shutil.copytree(
        valid_tree / "points" / POINT / "formal-1",
        valid_tree / "points" / POINT / "formal-2",
    )
    refresh_checksums(valid_tree)

    assert any("unexpected formal phase" in error for error in report.validate_evidence(valid_tree))


def test_duplicated_attempt_is_rejected(valid_tree: Path) -> None:
    shutil.copytree(
        valid_tree / "points" / POINT / "formal-1" / "attempt-1",
        valid_tree / "points" / POINT / "formal-1" / "attempt-2",
    )
    refresh_checksums(valid_tree)

    assert any("ambiguous formal repetition 1" in error for error in report.validate_evidence(valid_tree))


def test_missing_variant_log_is_rejected(valid_tree: Path) -> None:
    (valid_tree / "variants" / "bulk" / "raw" / "vllm-prefill.log").unlink()
    refresh_checksums(valid_tree)

    assert "missing variant evidence: bulk/vllm-prefill.log" in report.validate_evidence(valid_tree)


def test_missing_fixture_reference_is_rejected(valid_tree: Path) -> None:
    (valid_tree / "points" / POINT / "formal-1" / "attempt-1" / "raw" / "fixture-reference.json").unlink()
    refresh_checksums(valid_tree)

    assert any("missing fixture reference" in error for error in report.validate_evidence(valid_tree))


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


def test_raw_report_keeps_five_rows_and_output_matched_ratios(valid_tree: Path) -> None:
    text = report.render_report(valid_tree)

    assert text.count("| dp1 | 16384 | 128 | BULK |") == 1
    assert text.count("| dp1 | 16384 | 1 | BULK |") == 1
    assert text.count("| dp1 | 16384 | 128 | LAYERWISE |") == 1
    assert text.count("| dp1 | 16384 | 1 | LAYERWISE |") == 1
    assert text.count("| dp1 | 16384 | 1 | REUSE3 |") == 1
    assert text.count("| LAYERWISE / BULK | dp1 | 16384 | 128 |") > 0
    assert text.count("| LAYERWISE / BULK | dp1 | 16384 | 1 |") > 0
    assert text.count("| REUSE3 / LAYERWISE | dp1 | 16384 | 1 |") > 0
    assert text.count("| REUSE3 / BULK | dp1 | 16384 | 1 |") > 0
    assert "Single-wave raw characterization; not a steady-state or statistically significant result." in text
    assert "p-value" not in text
    assert "confidence interval" not in text
    assert "Performance PASS" not in text


def test_raw_report_keeps_all_forty_per_request_rows(valid_tree: Path) -> None:
    text = report.render_report(valid_tree)

    assert "## Per-Request Results" in text
    for point in POINTS:
        assert text.count(f"| {point} | 1 |") == 8
        for request_index in range(8):
            assert f"{point}-request-{request_index}" in text


def test_aisbench_raw_summary_uses_all_single_wave_requests(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    performance = raw / "aisbench-output" / "performances" / "service"
    performance.mkdir(parents=True)
    (performance / "bulk.json").write_text(
        json.dumps(
            {
                "Input Token Throughput": {"total": "4096 token/s"},
                "Request Throughput": {"total": "2 req/s"},
                "Concurrency": {"total": 8},
                "Output Token Throughput": {"total": "2 token/s"},
                "Benchmark Duration": {"total": "4000 ms"},
                "Total Requests": {"total": 8},
                "Failed Requests": {"total": 0},
                "Success Requests": {"total": 8},
            }
        ),
        encoding="utf-8",
    )
    (performance / "bulk.csv").write_text(
        "Performance Parameters,Stage,Average,Max,Median,P95,N\n"
        "E2EL,total,1.0 ms,1000 ms,850 ms,900 ms,8\n"
        "TTFT,total,1.0 ms,900 ms,800 ms,850 ms,8\n",
        encoding="utf-8",
    )
    (performance / "bulk_details.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "success": True,
                    "input_tokens": 16384,
                    "output_tokens": 1,
                }
            )
            + "\n"
            for _ in range(8)
        ),
        encoding="utf-8",
    )

    summary = report.summarize_aisbench_attempt(
        raw,
        WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        request_count=8,
        image_digest="sha256:image",
    )

    assert summary["valid"] is True
    assert summary["measurement_stage"] == "total"
    assert summary["single_wave"] is True
    assert summary["request_count"] == 8
    assert summary["success_count"] == 8
    metrics = summary["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["TTFT Median"] == 800
    assert metrics["TTFT Max"] == 900
    assert metrics["E2EL P95"] == 900
    assert metrics["Input Token Throughput"] == 4096
