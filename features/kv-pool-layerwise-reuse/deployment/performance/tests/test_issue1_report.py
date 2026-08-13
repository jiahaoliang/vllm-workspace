from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from performance import issue1_diagnostics, issue1_report
from performance.issue1_contract import (
    PREFERRED_TEST2_CONCURRENCY,
    TEST1_POINTS,
    point_id,
)
from performance.issue1_contract import (
    test2_points as issue1_test2_points,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _checksums(root: Path) -> None:
    paths = sorted(
        path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def _write_complete_fixture(root: Path, concurrency: int, formal_count: int) -> None:
    fixture = root / "fixtures" / f"tokens-32000-c{concurrency}"
    seed_id = f"c{concurrency}-seed"
    formal_ids = [f"c{concurrency}-formal-{index}" for index in range(formal_count)]
    _write_json(
        fixture / "manifest.json",
        {
            "formal_tokens": 32000,
            "seed_tokens": 28800,
            "expected_hit_rate": 0.9,
            "prefix_mode": "shared",
            "concurrency": concurrency,
            "warmup_ids": [f"warmup-{index}" for index in range(8)],
            "seed_ids": [seed_id],
            "admission_ids": [f"admission-{index}" for index in range(concurrency)],
            "formal_ids": [formal_ids],
            "seed_formal_pairs": [
                {
                    "seed_request_id": seed_id,
                    "seed_token_ids_sha256": "same",
                    "formal_prefix_token_ids_sha256": "same",
                }
                for _ in formal_ids
            ],
        },
    )
    for name in (
        "metadata.jsonl",
        "SHA256SUMS",
        "warmup.jsonl",
        "seed.jsonl",
        "admission.jsonl",
        "formal-1.jsonl",
    ):
        path = fixture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")


def _write_server_evidence(
    raw: Path,
    contexts: int,
    *,
    require_capacity_waiting: bool,
    include_range_debug: bool = False,
    critical_wait_ms: float = 1.0,
) -> dict[str, object]:
    metric_payload = {
        "schema_version": 2,
        "events": {
            "critical.wait_for_layer_load|layer=2": {
                "count": 1,
                "bytes": 0,
                "sum_ms": critical_wait_ms,
                "exclusive_sum_ms": critical_wait_ms,
                "p50_ms": critical_wait_ms,
                "p95_ms": critical_wait_ms,
                "max_ms": critical_wait_ms,
                "sample_count": 1,
            }
        },
    }
    metric_line = "KVPOOL_PERF_METRICS " + json.dumps(metric_payload)
    te_line = (
        "[Metrics] Transfer Engine Stats (over last 1s): "
        "Throughput: 10.00 MB/s | Latency Distribution (count=1): "
        "0-10us 100%"
    )
    iteration = (
        f"Iteration(1): {contexts} context requests, {contexts * 768} context "
        "tokens, 0 generation requests, 0 generation tokens, iteration "
        "elapsed time: 10 ms"
    )
    range_line = (
        '[KVPOOL_RANGE_DEBUG] {"event":"range","direction":"load",'
        '"layer_id":2,"key_count":1,"requested_bytes":[128],"results":[0]}'
    )
    prefill_lines = [iteration, metric_line, te_line]
    decode_lines = [metric_line, te_line]
    if include_range_debug:
        prefill_lines.append(range_line)
        decode_lines.append(range_line)
    logs = {
        "prefill": "\n".join(prefill_lines) + "\n",
        "decode": "\n".join(decode_lines) + "\n",
    }
    capacity_waiting = 1 if require_capacity_waiting else 0
    prometheus = (
        "TIMESTAMP 2026-08-13T00:00:00Z\n"
        f'vllm:num_requests_running{{engine="0"}} {contexts}\n'
        f'vllm:num_requests_waiting_by_reason{{engine="0",reason="capacity"}} '
        f"{capacity_waiting}\n"
        'vllm:num_requests_waiting_by_reason{engine="0",reason="deferred"} 0\n'
        'vllm:num_preemptions_total{engine="0"} 0\n'
    )
    decode_prometheus = (
        "TIMESTAMP 2026-08-13T00:00:00Z\n"
        'vllm:num_requests_running{engine="0"} 2\n'
        'vllm:num_requests_waiting_by_reason{engine="0",reason="capacity"} 0\n'
        'vllm:num_requests_waiting_by_reason{engine="0",reason="deferred"} 0\n'
        'vllm:num_preemptions_total{engine="0"} 0\n'
    )
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "prefill-delta.log").write_text(logs["prefill"], encoding="utf-8")
    (raw / "decode-delta.log").write_text(logs["decode"], encoding="utf-8")
    (raw / "prefill-prometheus-timeseries.metrics").write_text(
        prometheus,
        encoding="utf-8",
    )
    (raw / "decode-prometheus-timeseries.metrics").write_text(
        decode_prometheus,
        encoding="utf-8",
    )
    attempt = {
        "kvpool_events_by_role": {
            role: issue1_diagnostics.parse_kvpool_metrics(text)
            for role, text in logs.items()
        },
        "kvpool_metric_metadata_by_role": {
            role: issue1_diagnostics.parse_kvpool_metric_metadata(text)
            for role, text in logs.items()
        },
        "te_metrics_by_role": {
            role: issue1_diagnostics.parse_te_metrics(text)
            for role, text in logs.items()
        },
    }
    return {
        "admission": issue1_diagnostics.validate_admission(
            logs["prefill"],
            prometheus,
            expected_contexts=contexts,
            require_capacity_waiting=require_capacity_waiting,
        ),
        "observability": issue1_diagnostics.validate_observability(attempt),
        "decode_prometheus": issue1_diagnostics.parse_prometheus_timeseries(
            decode_prometheus
        ),
        "kvpool_events_by_role": attempt["kvpool_events_by_role"],
        "kvpool_metric_metadata_by_role": attempt[
            "kvpool_metric_metadata_by_role"
        ],
        "te_metrics_by_role": attempt["te_metrics_by_role"],
        "range_debug_by_role": {
            role: issue1_diagnostics.parse_range_debug_metrics(text)
            for role, text in logs.items()
        },
        "kvpool_events": issue1_diagnostics.parse_kvpool_metrics(
            logs["prefill"] + "\n" + logs["decode"]
        ),
        "te_metrics": issue1_diagnostics.parse_te_metrics(
            logs["prefill"] + "\n" + logs["decode"]
        ),
    }


def _write_details_and_fingerprint(
    raw: Path,
    request_count: int,
) -> dict[str, object]:
    details_relative = Path("aisbench-output/details.jsonl")
    details = raw / details_relative
    details.parent.mkdir(parents=True, exist_ok=True)
    predictions = {
        data_id: f"prediction-{data_id}" for data_id in range(request_count)
    }
    details.write_text(
        "".join(
            json.dumps(
                {
                    "data_id": data_id,
                    "success": True,
                    "prediction": prediction,
                }
            )
            + "\n"
            for data_id, prediction in predictions.items()
        ),
        encoding="utf-8",
    )
    rows = {
        str(data_id): hashlib.sha256(prediction.encode("utf-8")).hexdigest()
        for data_id, prediction in predictions.items()
    }
    digest = hashlib.sha256(
        "\n".join(f"{data_id}:{rows[str(data_id)]}" for data_id in predictions).encode(
            "ascii"
        )
    ).hexdigest()
    return {
        "valid": True,
        "errors": [],
        "request_count": request_count,
        "data_ids": list(predictions),
        "prediction_sha256_by_data_id": rows,
        "digest": digest,
        "raw_details": str(details_relative),
    }


def _write_complete_evidence(root: Path) -> None:
    points = (*TEST1_POINTS, *issue1_test2_points(PREFERRED_TEST2_CONCURRENCY))
    for name in ("handoff.json", "source-identity.json", "client-identity.json"):
        _write_json(root / name, {})
    _write_json(
        root / "run-contract.json",
        {
            "expected_points": [point_id(point) for point in points],
            "input_tokens": 32000,
            "seed_tokens": 28800,
            "seed_request_count": 1,
            "server_seed": 1024,
            "client_fixture_seed": 1023,
            "test1_long_prefill_token_threshold": 4096,
            "test2_long_prefill_token_threshold": 768,
            "max_num_partial_prefills": {"test1": 8, "test2": 40},
            "max_long_partial_prefills": {"test1": 8, "test2": 40},
            "test2_concurrency": 40,
            "bulk_request_capacity": 39,
            "reuse3_request_capacity": 40,
        },
    )
    _write_complete_fixture(root, 8, 125)
    _write_complete_fixture(root, 40, 100)

    point_results: dict[str, dict[str, object]] = {}
    for index, point in enumerate(points, 1):
        selected = point_id(point)
        point_root = root / "points" / selected
        _write_json(point_root / "identity.json", {"point_id": selected})
        for phase, count in (("warmup", 1), ("seed", 2)):
            for attempt in range(1, count + 1):
                (point_root / phase / f"attempt-{attempt}" / "raw").mkdir(
                    parents=True, exist_ok=True
                )
        expected_contexts = (
            2 if point.test == "test2" and point.variant == "bulk" else point.concurrency
        )
        require_capacity_waiting = (
            point.test == "test2" and point.variant == "bulk"
        )
        canary_raw = point_root / "admission" / "attempt-1" / "raw"
        canary_server = _write_server_evidence(
            canary_raw,
            expected_contexts,
            require_capacity_waiting=require_capacity_waiting,
        )
        _write_json(
            canary_raw / "admission-validation.json",
            canary_server["admission"],
        )
        _write_json(
            canary_raw / "observability-validation.json",
            canary_server["observability"],
        )
        formal_raw = point_root / "formal-1" / "attempt-1" / "raw"
        formal_server = _write_server_evidence(
            formal_raw,
            expected_contexts,
            require_capacity_waiting=require_capacity_waiting,
        )
        metrics = {
            "Request Throughput": 1.0 + index / 10,
            "Input Token Throughput": 32000.0,
            "Output Token Throughput": 128.0,
            "TTFT P95": 10.0,
            "E2EL P95": 20.0,
            "TPOT P95": 1.0,
            "ITL P95": 1.0,
        }
        output_fingerprint = _write_details_and_fingerprint(
            formal_raw,
            point.formal_requests,
        )
        _write_json(
            formal_raw / "summary.json",
            {
                "valid": True,
                "request_count": point.formal_requests,
                "success_count": point.formal_requests,
                "metrics": metrics,
                "raw_details": output_fingerprint.pop("raw_details"),
            },
        )
        _write_json(
            formal_raw / "hit-validation.json",
            {
                "valid": True,
                "request_count": point.formal_requests,
                "expected_hit_tokens": 28800,
                "min_hit_tokens": 28800,
                "max_hit_tokens": 28800,
                "local_hit_tokens": 0,
            },
        )
        admission = formal_server["admission"]
        _write_json(formal_raw / "admission-validation.json", admission)
        _write_json(formal_raw / "output-fingerprint.json", output_fingerprint)
        result = {
            "point_id": selected,
            "request_count": point.formal_requests,
            "request_throughput": metrics["Request Throughput"],
            "metrics": metrics,
            "admission": admission,
            "admission_canary": canary_server["admission"],
            "observability_canary": canary_server["observability"],
            "decode_prometheus": formal_server["decode_prometheus"],
            "kvpool_events": formal_server["kvpool_events"],
            "kvpool_events_by_role": formal_server["kvpool_events_by_role"],
            "kvpool_metric_metadata_by_role": formal_server[
                "kvpool_metric_metadata_by_role"
            ],
            "te_metrics": formal_server["te_metrics"],
            "te_metrics_by_role": formal_server["te_metrics_by_role"],
            "output_fingerprint": output_fingerprint,
        }
        point_results[selected] = result
        _write_json(point_root / "diagnostic-summary.json", result)

    test1_fingerprint = _load_json_fingerprint(
        root / "points" / point_id(TEST1_POINTS[0]) / "diagnostic-summary.json"
    )
    test2_fingerprint = _load_json_fingerprint(
        root
        / "points"
        / point_id(issue1_test2_points(PREFERRED_TEST2_CONCURRENCY)[0])
        / "diagnostic-summary.json"
    )
    test1_bulk = point_results[point_id(TEST1_POINTS[0])]
    test1_layerwise = point_results[point_id(TEST1_POINTS[1])]
    test2_bulk_point, test2_reuse_point = issue1_test2_points(
        PREFERRED_TEST2_CONCURRENCY
    )
    test2_bulk = point_results[point_id(test2_bulk_point)]
    test2_reuse = point_results[point_id(test2_reuse_point)]
    _write_json(
        root / "diagnosis.json",
        {
            "test1": issue1_diagnostics.classify_slowdown(
                test1_bulk,
                test1_layerwise,
                alternative_name="layerwise",
            ),
            "test2": issue1_diagnostics.classify_slowdown(
                test2_bulk,
                test2_reuse,
                alternative_name="reuse3",
            ),
            "reuse3_capacity_advantage": (
                issue1_diagnostics.validate_reuse_capacity_advantage(
                    test2_bulk,
                    test2_reuse,
                )
            ),
            "output_consistency": {
                "test1": _matching_consistency(test1_fingerprint),
                "test2": _matching_consistency(test2_fingerprint),
            },
            "short_diagnostics": {},
        },
    )
    _write_json(
        root / "restoration.json",
        {"completed": True, "mooncake_empty": True, "engines_stopped": True},
    )
    _checksums(root)


def _load_json_fingerprint(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))["output_fingerprint"]
    assert isinstance(value, dict)
    return value


def _matching_consistency(fingerprint: dict[str, object]) -> dict[str, object]:
    rows = fingerprint["prediction_sha256_by_data_id"]
    assert isinstance(rows, dict)
    return {
        "valid": True,
        "errors": [],
        "request_count": len(rows),
        "mismatched_data_ids": [],
        "bulk_digest": fingerprint["digest"],
        "alternative_digest": fingerprint["digest"],
    }


def _write_complete_short_diagnostic(root: Path, test: str) -> None:
    alternative = "layerwise" if test == "test1" else "reuse3"
    request_count = 8 if test == "test1" else 40
    point_results: dict[str, object] = {}
    variants = (
        ("bulk", alternative)
        if test == "test1"
        else ("bulk", "layerwise", "reuse3")
    )
    formal_points = (
        TEST1_POINTS
        if test == "test1"
        else issue1_test2_points(PREFERRED_TEST2_CONCURRENCY)
    )
    formal_bulk_path = root / "points" / point_id(formal_points[0])
    formal_alternative_path = root / "points" / point_id(formal_points[1])
    formal_bulk = json.loads(
        (formal_bulk_path / "diagnostic-summary.json").read_text(encoding="utf-8")
    )
    formal_alternative = json.loads(
        (formal_alternative_path / "diagnostic-summary.json").read_text(
            encoding="utf-8"
        )
    )
    slower_throughput = float(formal_bulk["request_throughput"]) * 0.8
    formal_alternative["request_throughput"] = slower_throughput
    formal_alternative["metrics"]["Request Throughput"] = slower_throughput
    _write_json(
        formal_alternative_path / "diagnostic-summary.json",
        formal_alternative,
    )
    formal_summary_path = (
        formal_alternative_path / "formal-1/attempt-1/raw/summary.json"
    )
    formal_summary = json.loads(formal_summary_path.read_text(encoding="utf-8"))
    formal_summary["metrics"]["Request Throughput"] = slower_throughput
    _write_json(formal_summary_path, formal_summary)
    formal_classification = issue1_diagnostics.classify_slowdown(
        formal_bulk,
        formal_alternative,
        alternative_name=alternative,
    )
    short_throughputs = (
        {"bulk": 1.0, "layerwise": 0.8}
        if test == "test1"
        else {"bulk": 1.0, "layerwise": 0.8, "reuse3": 0.7}
    )
    critical_waits = (
        {"bulk": 1.0, "layerwise": 12_001.0}
        if test == "test1"
        else {"bulk": 1.0, "layerwise": 12_001.0, "reuse3": 22_001.0}
    )
    for variant in variants:
        point_root = root / "short-diagnostics" / test / variant
        _write_json(
            point_root / "identity.json",
            {
                "test": test,
                "variant": variant,
                "request_count": request_count,
                "range_debug": True,
            },
        )
        for phase in ("warmup", "seed"):
            (point_root / phase / "attempt-1" / "raw").mkdir(
                parents=True,
                exist_ok=True,
            )
        raw = point_root / "admission" / "attempt-1" / "raw"
        expected_contexts = (
            2 if test == "test2" and variant != "reuse3" else request_count
        )
        server = _write_server_evidence(
            raw,
            expected_contexts,
            require_capacity_waiting=(test == "test2" and variant != "reuse3"),
            include_range_debug=True,
            critical_wait_ms=critical_waits[variant],
        )
        output_fingerprint = _write_details_and_fingerprint(raw, request_count)
        _write_json(
            raw / "summary.json",
            {
                "valid": True,
                "request_count": request_count,
                "success_count": request_count,
                "metrics": {"Request Throughput": short_throughputs[variant]},
                "raw_details": output_fingerprint.pop("raw_details"),
            },
        )
        _write_json(raw / "hit-validation.json", {"valid": True})
        _write_json(raw / "admission-validation.json", server["admission"])
        _write_json(
            raw / "observability-validation.json",
            server["observability"],
        )
        _write_json(raw / "output-fingerprint.json", output_fingerprint)
        result = {
            "request_count": request_count,
            "request_throughput": short_throughputs[variant],
            "admission": server["admission"],
            "observability_canary": server["observability"],
            "decode_prometheus": server["decode_prometheus"],
            "range_debug_by_role": server["range_debug_by_role"],
            "kvpool_events": server["kvpool_events"],
            "kvpool_events_by_role": server["kvpool_events_by_role"],
            "kvpool_metric_metadata_by_role": server[
                "kvpool_metric_metadata_by_role"
            ],
            "te_metrics": server["te_metrics"],
            "te_metrics_by_role": server["te_metrics_by_role"],
            "output_fingerprint": output_fingerprint,
        }
        _write_json(point_root / "diagnostic-summary.json", result)
        point_results[variant] = result

    bulk = point_results["bulk"]
    assert isinstance(bulk, dict)
    fingerprint = bulk["output_fingerprint"]
    assert isinstance(fingerprint, dict)
    diagnosis_path = root / "diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    if test == "test1":
        final = issue1_diagnostics.resolve_with_short_diagnostic(
            formal_classification,
            point_results["bulk"],
            point_results["layerwise"],
            alternative_name="layerwise",
        )
    else:
        final = issue1_diagnostics.resolve_reuse3_with_layerwise_control(
            formal_classification,
            point_results["bulk"],
            point_results["layerwise"],
            point_results["reuse3"],
        )
    diagnosis[test] = final
    if test == "test1":
        output_consistency: dict[str, object] = _matching_consistency(fingerprint)
    else:
        output_consistency = {
            "bulk_layerwise": _matching_consistency(fingerprint),
            "bulk_reuse3": _matching_consistency(fingerprint),
            "layerwise_reuse3": _matching_consistency(fingerprint),
        }
    diagnosis["short_diagnostics"][test] = {
        "spec": {},
        "preliminary": formal_classification,
        "points": point_results,
        "output_consistency": output_consistency,
        "final": final,
    }
    _write_json(diagnosis_path, diagnosis)


def test_report_rejects_slower_result_without_cause(tmp_path: Path) -> None:
    for name in (
        "handoff.json",
        "source-identity.json",
        "client-identity.json",
        "run-contract.json",
        "restoration.json",
    ):
        _write_json(tmp_path / name, {})
    _write_json(
        tmp_path / "diagnosis.json",
        {
            "test1": {"slower": True, "cause": "none", "resolved": False},
            "test2": {"slower": False, "cause": "none"},
            "reuse3_capacity_advantage": {"valid": True},
        },
    )
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert "slower result lacks a cause: test1" in errors
    assert "slower result remains unresolved: test1" in errors


def test_report_rejects_unconverted_capacity_separately_from_slowdown_cause(
    tmp_path: Path,
) -> None:
    for name in (
        "handoff.json",
        "source-identity.json",
        "client-identity.json",
        "run-contract.json",
        "restoration.json",
    ):
        _write_json(tmp_path / name, {})
    _write_json(
        tmp_path / "diagnosis.json",
        {
            "test1": {"slower": False, "cause": "none"},
            "test2": {
                "slower": False,
                "cause": "none",
                "resolved": True,
                "evidence": {},
            },
            "reuse3_capacity_advantage": {"valid": False},
        },
    )
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert "missing REUSE3 server-side capacity diagnosis" not in errors
    assert (
        "REUSE3 HBM capacity was not converted into sustained concurrency" in errors
    )


def test_report_requires_checksum_manifest(tmp_path: Path) -> None:
    assert issue1_report.validate_checksums(tmp_path) == ["missing root SHA256SUMS"]


def test_render_report_refuses_incomplete_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid Issue #1 evidence"):
        issue1_report.render_report(tmp_path)


def test_complete_evidence_renders_all_results_and_server_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)

    text = issue1_report.render_report(tmp_path)

    assert "| test1 | BULK | 125 |" in text
    assert "| test1 | LAYERWISE | 125 |" in text
    assert "| test2 | BULK | 100 |" in text
    assert "| test2 | REUSE3 | 100 |" in text
    assert "## Server Concurrency" in text
    assert "## Diagnosis" in text
    assert "## Transfer Engine" in text
    assert "## Short Diagnostics" not in text


def test_report_rejects_short_diagnostic_cause_without_raw_execution(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    diagnosis_path = tmp_path / "diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    diagnosis["test1"] = {
        "slower": True,
        "throughput_ratio": 0.8,
        "cause": "prefill_layer_or_reuse_gate_wait",
        "resolved": True,
        "evidence": {"source": "short_diagnostic"},
    }
    _write_json(diagnosis_path, diagnosis)
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert "missing executed short diagnostic: test1" in errors
    assert "missing test1 bulk short diagnostic summary" in errors
    assert "missing test1 layerwise short diagnostic summary" in errors


def test_report_recomputes_output_consistency_from_raw_details(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    details = (
        tmp_path
        / "points"
        / point_id(TEST1_POINTS[1])
        / "formal-1"
        / "attempt-1"
        / "raw"
        / "aisbench-output"
        / "details.jsonl"
    )
    rows = details.read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["prediction"] = "tampered-layerwise-output"
    rows[0] = json.dumps(first)
    details.write_text("\n".join(rows) + "\n", encoding="utf-8")
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert any("raw output fingerprint drift" in error for error in errors)
    assert any("recomputed cross-variant output mismatch" in error for error in errors)


def test_report_recomputes_short_diagnostic_outputs_from_raw_details(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    _write_complete_short_diagnostic(tmp_path, "test1")
    details = (
        tmp_path
        / "short-diagnostics"
        / "test1"
        / "layerwise"
        / "admission"
        / "attempt-1"
        / "raw"
        / "aisbench-output"
        / "details.jsonl"
    )
    rows = details.read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["prediction"] = "tampered-short-diagnostic-output"
    rows[0] = json.dumps(first)
    details.write_text("\n".join(rows) + "\n", encoding="utf-8")
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert any("short diagnostic archive" in error for error in errors)
    assert "recomputed short diagnostic output mismatch: test1" in errors
    assert "short diagnostic output consistency drift: test1" in errors


def test_report_recomputes_short_diagnostic_range_events_from_raw_logs(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    _write_complete_short_diagnostic(tmp_path, "test1")
    log = (
        tmp_path
        / "short-diagnostics/test1/layerwise/admission/attempt-1/raw"
        / "prefill-delta.log"
    )
    text = log.read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if "[KVPOOL_RANGE_DEBUG]" not in line
    ) + "\n"
    log.write_text(text, encoding="utf-8")
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert any(
        "raw server evidence drift" in error
        and "range_debug_by_role" in error
        for error in errors
    )


def test_report_accepts_complete_test2_three_point_short_diagnostic(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    _write_complete_short_diagnostic(tmp_path, "test2")
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert not any("short diagnostic" in error for error in errors)
    assert (
        tmp_path / "short-diagnostics/test2/layerwise/admission/attempt-1"
    ).is_dir()


def test_report_recomputes_short_diagnostic_final_cause_from_raw_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    _write_complete_short_diagnostic(tmp_path, "test2")
    diagnosis_path = tmp_path / "diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    fabricated = dict(diagnosis["test2"])
    fabricated.update(
        {
            "cause": "scheduler_admission",
            "resolved": True,
            "evidence": {"source": "short_diagnostic", "fabricated": True},
        }
    )
    diagnosis["test2"] = fabricated
    diagnosis["short_diagnostics"]["test2"]["final"] = fabricated
    _write_json(diagnosis_path, diagnosis)
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert "short diagnostic final classification drift: test2" in errors


def test_report_rejects_old_kvpool_metric_schema(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    diagnostic_path = (
        tmp_path
        / "points"
        / point_id(TEST1_POINTS[0])
        / "diagnostic-summary.json"
    )
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    diagnostic["kvpool_metric_metadata_by_role"]["prefill"].update(
        {
            "schema_versions": [1],
            "missing_exclusive_events": 1,
        }
    )
    _write_json(diagnostic_path, diagnostic)
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert any("invalid prefill KVPool metric schema metadata" in error for error in errors)


def test_report_recomputes_server_admission_from_raw_logs(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    point_root = tmp_path / "points" / point_id(TEST1_POINTS[0])
    for phase in ("admission", "formal-1"):
        log = point_root / phase / "attempt-1" / "raw" / "prefill-delta.log"
        text = log.read_text(encoding="utf-8")
        text = text.replace(
            "Iteration(1): 8 context requests, 6144 context tokens",
            "Iteration(1): 1 context requests, 768 context tokens",
        )
        log.write_text(text, encoding="utf-8")
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert any(
        "raw server evidence drift" in error and "admission" in error
        for error in errors
    )


def test_report_recomputes_slowdown_classification_from_raw_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_evidence(tmp_path)
    diagnosis_path = tmp_path / "diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    diagnosis["test1"] = {
        "slower": True,
        "throughput_ratio": 0.5,
        "cause": "scheduler_admission",
        "resolved": True,
        "evidence": {"fabricated": True},
    }
    _write_json(diagnosis_path, diagnosis)
    _checksums(tmp_path)

    errors = issue1_report.validate_evidence(tmp_path)

    assert "formal slowdown classification drift: test1" in errors
