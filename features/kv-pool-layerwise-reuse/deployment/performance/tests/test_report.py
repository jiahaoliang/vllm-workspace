from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from performance import report
from performance.contract import WorkloadPoint, build_run_contract

POINTS = (
    "dp1-16384-bulk-o1-c8",
    "dp1-16384-layerwise-o1-c8",
    "dp1-16384-reuse3-o1-c8",
)
POINT = POINTS[0]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_checksums(root: Path) -> None:
    root_manifest = root / "SHA256SUMS"
    artifacts = sorted(
        path for path in root.rglob("*") if path.is_file() and path != root_manifest
    )
    root_manifest.write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n" for path in artifacts)
    )


def write_valid_fixture(root: Path) -> dict[str, str]:
    fixture_root = root / "fixtures" / "tokens-16384-c8"
    fixture_root.mkdir(parents=True)
    phase_rows: dict[str, list[dict[str, object]]] = {
        "warmup": [
            {"question": f"warmup-{index}", "answer": "", "request_id": f"warmup-{index}"}
            for index in range(8)
        ],
        "seed": [
            {"question": f"seed-{index}", "answer": "", "request_id": f"seed-{index}"}
            for index in range(64)
        ],
        "formal-1": [
            {"question": f"formal-{index}", "answer": "", "request_id": f"formal-{index}"}
            for index in range(64)
        ],
    }
    for phase, rows in phase_rows.items():
        (fixture_root / f"{phase}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    metadata: list[dict[str, object]] = []
    pairs: list[dict[str, str]] = []
    for phase, rows in phase_rows.items():
        for index, row in enumerate(rows):
            if phase == "seed":
                token_ids = [index] * 13312
            elif phase == "formal-1":
                token_ids = [index] * 13312 + [1000 + index] * 3072
            else:
                token_ids = [2000 + index] * 16384
            metadata.append(
                {
                    "request_id": row["request_id"],
                    "partition": phase,
                    "token_count": len(token_ids),
                    "token_ids": token_ids,
                    "prompt_sha256": hashlib.sha256(
                        str(row["question"]).encode("utf-8")
                    ).hexdigest(),
                }
            )
    metadata_path = fixture_root / "metadata.jsonl"
    metadata_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in metadata),
        encoding="utf-8",
    )
    for index in range(64):
        seed_tokens = [index] * 13312
        formal_tokens = seed_tokens + [1000 + index] * 3072
        seed_digest = hashlib.sha256(
            json.dumps(seed_tokens, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        formal_digest = hashlib.sha256(
            json.dumps(formal_tokens, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        pairs.append(
            {
                "seed_request_id": f"seed-{index}",
                "formal_request_id": f"formal-{index}",
                "seed_token_ids_sha256": seed_digest,
                "formal_prefix_token_ids_sha256": seed_digest,
                "formal_token_ids_sha256": formal_digest,
            }
        )
    artifacts = {
        name: digest(fixture_root / name)
        for name in ("warmup.jsonl", "seed.jsonl", "formal-1.jsonl", "metadata.jsonl")
    }
    manifest_path = fixture_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "formal_tokens": 16384,
                "seed_tokens": 13312,
                "expected_hit_rate": 0.8125,
                "warmup_ids": [f"warmup-{index}" for index in range(8)],
                "seed_ids": [f"seed-{index}" for index in range(64)],
                "formal_ids": [[f"formal-{index}" for index in range(64)]],
                "seed_formal_pairs": pairs,
                "artifact_checksums": artifacts,
            }
        ),
        encoding="utf-8",
    )
    inner_names = (*artifacts, "manifest.json")
    (fixture_root / "SHA256SUMS").write_text(
        "".join(f"{digest(fixture_root / name)}  {name}\n" for name in sorted(inner_names)),
        encoding="utf-8",
    )
    return {phase: digest(fixture_root / f"{phase}.jsonl") for phase in phase_rows}


@pytest.fixture
def valid_tree(tmp_path: Path) -> Path:
    fixture_digests = write_valid_fixture(tmp_path)
    for index, point in enumerate(POINTS, start=1):
        variant = point.split("-")[2]
        for phase in ("warmup", "seed", "formal-1"):
            raw = tmp_path / "points" / point / phase / "attempt-1" / "raw"
            raw.mkdir(parents=True)
            (raw / "fixture-reference.json").write_text(
                json.dumps(
                    {
                        "path": f"fixtures/tokens-16384-c8/{phase}.jsonl",
                        "sha256": fixture_digests[phase],
                    }
                )
            )
        seed_raw = tmp_path / "points" / point / "seed" / "attempt-1" / "raw"
        (seed_raw / "summary.json").write_text(
            json.dumps(
                {
                    "valid": True,
                    "image_digest": "sha256:image",
                    "request_count": 64,
                    "stage_request_count": 64,
                    "measurement_stage": "total",
                    "single_wave": False,
                    "concurrency_waves": 8,
                    "success_count": 64,
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
                        "output_tokens": 1,
                    }
                )
                + "\n"
                for request_index in range(64)
            ),
            encoding="utf-8",
        )
        (raw / "summary.json").write_text(
            json.dumps(
                {
                    "valid": True,
                    "image_digest": "sha256:image",
                    "request_count": 64,
                    "stage_request_count": 64,
                    "measurement_stage": "total",
                    "single_wave": False,
                    "concurrency_waves": 8,
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
        (raw / "hit-validation.json").write_text(
            json.dumps(
                {
                    "valid": True,
                    "request_count": 64,
                    "expected_request_count": 64,
                    "expected_total_tokens": 16384,
                    "expected_hit_tokens": 13312,
                    "expected_hit_rate": 0.8125,
                    "min_hit_tokens": 13312,
                    "max_hit_tokens": 13312,
                    "hit_rate": 0.8125,
                    "expected_need_to_load_tokens": 13312,
                    "min_need_to_load_tokens": 13312,
                    "max_need_to_load_tokens": 13312,
                    "local_hit_tokens": 0,
                }
            )
        )
        (tmp_path / "points" / point / "identity.json").write_text(
            json.dumps({"image_digest": "sha256:image", "variant": variant})
        )
    (tmp_path / "run-contract.json").write_text(json.dumps(build_run_contract("sha256:image")))
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


def test_exact_high_hit_evidence_is_accepted(valid_tree: Path) -> None:
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


def test_fixture_checksum_manifest_is_covered_by_root_manifest(
    valid_tree: Path,
) -> None:
    manifest = valid_tree / "fixtures" / "tokens-16384-c8" / "SHA256SUMS"
    manifest.write_text(manifest.read_text() + "0" * 64 + "  extra\n")

    errors = report.validate_evidence(valid_tree)

    assert any(
        "SHA256SUMS replay failed: fixtures/tokens-16384-c8/SHA256SUMS"
        in error
        for error in errors
    )


def test_raw_report_keeps_three_high_hit_rows_and_ratios(valid_tree: Path) -> None:
    text = report.render_report(valid_tree)

    assert text.count("| dp1 | 16384 | 1 | BULK |") == 1
    assert text.count("| dp1 | 16384 | 1 | LAYERWISE |") == 1
    assert text.count("| dp1 | 16384 | 1 | REUSE3 |") == 1
    assert text.count("| LAYERWISE / BULK | dp1 | 16384 | 1 |") > 0
    assert text.count("| REUSE3 / LAYERWISE | dp1 | 16384 | 1 |") > 0
    assert text.count("| REUSE3 / BULK | dp1 | 16384 | 1 |") > 0
    assert "Single formal attempt with eight concurrency waves; not a statistically significant result." in text
    assert "81.25%" in text
    assert "p-value" not in text
    assert "confidence interval" not in text
    assert "Performance PASS" not in text


def test_raw_report_keeps_all_192_per_request_rows(valid_tree: Path) -> None:
    text = report.render_report(valid_tree)

    assert "## Per-Request Results" in text
    for point in POINTS:
        assert text.count(f"| {point} | 1 |") == 64
        for request_index in range(64):
            assert f"{point}-request-{request_index}" in text


def test_missing_seed_attempt_is_rejected(valid_tree: Path) -> None:
    shutil.rmtree(valid_tree / "points" / POINT / "seed")

    errors = report.validate_evidence(valid_tree)

    assert any("seed" in error for error in errors)


def test_invalid_formal_hit_evidence_is_rejected(valid_tree: Path) -> None:
    hit_path = (
        valid_tree
        / "points"
        / POINT
        / "formal-1"
        / "attempt-1"
        / "raw"
        / "hit-validation.json"
    )
    hit = json.loads(hit_path.read_text())
    hit["valid"] = False
    hit["min_hit_tokens"] = 0
    hit_path.write_text(json.dumps(hit))

    errors = report.validate_evidence(valid_tree)

    assert any("hit evidence" in error for error in errors)


def test_local_hbm_hit_evidence_is_rejected(valid_tree: Path) -> None:
    hit_path = (
        valid_tree
        / "points"
        / POINT
        / "formal-1"
        / "attempt-1"
        / "raw"
        / "hit-validation.json"
    )
    hit = json.loads(hit_path.read_text())
    hit["min_need_to_load_tokens"] = 13184
    hit["local_hit_tokens"] = 128
    hit_path.write_text(json.dumps(hit))

    errors = report.validate_evidence(valid_tree)

    assert any("invalid formal hit evidence" in error for error in errors)


def test_seed_formal_token_prefix_drift_is_rejected(valid_tree: Path) -> None:
    metadata_path = valid_tree / "fixtures" / "tokens-16384-c8" / "metadata.jsonl"
    rows = [json.loads(line) for line in metadata_path.read_text().splitlines()]
    formal = next(row for row in rows if row["request_id"] == "formal-0")
    formal["token_ids"][0] = 9999
    metadata_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    )

    errors = report.validate_evidence(valid_tree)

    assert any("token prefix mismatch" in error for error in errors)


def test_aisbench_raw_summary_uses_all_formal_requests(tmp_path: Path) -> None:
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
                "Total Requests": {"total": 64},
                "Failed Requests": {"total": 0},
                "Success Requests": {"total": 64},
            }
        ),
        encoding="utf-8",
    )
    (performance / "bulk.csv").write_text(
        "Performance Parameters,Stage,Average,Max,Median,P95,N\n"
        "E2EL,total,1.0 ms,1000 ms,850 ms,900 ms,64\n"
        "TTFT,total,1.0 ms,900 ms,800 ms,850 ms,64\n",
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
            for _ in range(64)
        ),
        encoding="utf-8",
    )

    summary = report.summarize_aisbench_attempt(
        raw,
        WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        request_count=64,
        image_digest="sha256:image",
    )

    assert summary["valid"] is True
    assert summary["measurement_stage"] == "total"
    assert summary["single_wave"] is False
    assert summary["concurrency_waves"] == 8
    assert summary["request_count"] == 64
    assert summary["success_count"] == 64
    metrics = summary["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["TTFT Median"] == 800
    assert metrics["TTFT Max"] == 900
    assert metrics["E2EL P95"] == 900
    assert metrics["Input Token Throughput"] == 4096
