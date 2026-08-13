from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from performance import issue1_diagnostics
from performance.issue1_contract import (
    PREFERRED_TEST2_CONCURRENCY,
    TEST1_POINTS,
    point_id,
    test2_points,
)


def _load_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {description}: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} is not a JSON object: {path}")
    return value


def validate_checksums(root: Path) -> list[str]:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        return ["missing root SHA256SUMS"]
    errors: list[str] = []
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), 1
    ):
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64 or not relative:
            errors.append(f"malformed SHA256SUMS line {line_number}")
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(f"SHA256SUMS path escapes evidence root: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        if actual != digest:
            errors.append(f"SHA256SUMS replay failed: {relative}")
    return errors


def _single_attempt(point_root: Path, phase: str) -> Path | None:
    attempts = list((point_root / phase).glob("attempt-*"))
    return attempts[0] if len(attempts) == 1 else None


def _recompute_output_fingerprint(
    raw: Path,
    summary: dict[str, Any],
    expected_count: int,
    description: str,
) -> tuple[dict[str, object], list[str]]:
    relative = summary.get("raw_details")
    if not isinstance(relative, str) or not relative:
        return {}, [f"missing raw AISBench details path: {description}"]
    details = (raw / relative).resolve()
    if not details.is_relative_to(raw.resolve()):
        return {}, [f"raw AISBench details path escapes attempt: {description}"]
    fingerprint = issue1_diagnostics.fingerprint_predictions(
        details,
        expected_count,
    )
    if fingerprint.get("valid") is not True:
        return fingerprint, [f"invalid raw output details: {description}"]
    return fingerprint, []


def _compare_fingerprint(
    actual: object,
    recomputed: dict[str, object],
    description: str,
) -> list[str]:
    if not isinstance(actual, dict) or actual != recomputed:
        return [f"raw output fingerprint drift: {description}"]
    return []


def _recompute_server_evidence(
    raw: Path,
    *,
    expected_contexts: int,
    require_capacity_waiting: bool,
    description: str,
) -> tuple[dict[str, object], list[str]]:
    paths = {
        "prefill_log": raw / "prefill-delta.log",
        "decode_log": raw / "decode-delta.log",
        "prefill_prometheus": raw / "prefill-prometheus-timeseries.metrics",
        "decode_prometheus": raw / "decode-prometheus-timeseries.metrics",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return {}, [
            f"missing raw server evidence for {description}: {', '.join(missing)}"
        ]
    texts = {
        name: path.read_text(encoding="utf-8") for name, path in paths.items()
    }
    logs = {
        "prefill": texts["prefill_log"],
        "decode": texts["decode_log"],
    }
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
            texts["prefill_prometheus"],
            expected_contexts=expected_contexts,
            require_capacity_waiting=require_capacity_waiting,
        ),
        "observability": issue1_diagnostics.validate_observability(attempt),
        "decode_prometheus": issue1_diagnostics.parse_prometheus_timeseries(
            texts["decode_prometheus"]
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
    }, []


def _compare_server_field(
    actual: object,
    recomputed: dict[str, object],
    field: str,
    description: str,
) -> list[str]:
    canonical_actual = json.loads(json.dumps(actual, sort_keys=True))
    canonical_recomputed = json.loads(
        json.dumps(recomputed.get(field), sort_keys=True)
    )
    if canonical_actual != canonical_recomputed:
        return [f"raw server evidence drift for {description}: {field}"]
    return []


def _validate_fixture(root: Path, concurrency: int, formal_count: int) -> list[str]:
    fixture = root / "fixtures" / f"tokens-32000-c{concurrency}"
    errors: list[str] = []
    required = (
        "manifest.json",
        "metadata.jsonl",
        "SHA256SUMS",
        "warmup.jsonl",
        "seed.jsonl",
        "admission.jsonl",
        "formal-1.jsonl",
    )
    for name in required:
        if not (fixture / name).is_file():
            errors.append(f"missing c{concurrency} fixture artifact: {name}")
    if errors:
        return errors
    manifest = _load_object(fixture / "manifest.json", "fixture manifest")
    checks = {
        "formal_tokens": 32000,
        "seed_tokens": 28800,
        "expected_hit_rate": 0.9,
        "prefix_mode": "shared",
        "concurrency": concurrency,
    }
    for key, expected in checks.items():
        if manifest.get(key) != expected:
            errors.append(
                f"c{concurrency} fixture {key} mismatch: "
                f"{manifest.get(key)!r} != {expected!r}"
            )
    expected_counts = {
        "warmup_ids": 8,
        "seed_ids": 1,
        "admission_ids": concurrency,
    }
    for key, expected in expected_counts.items():
        values = manifest.get(key)
        if not isinstance(values, list) or len(values) != expected:
            errors.append(f"c{concurrency} fixture {key} count must be {expected}")
    formal_ids = manifest.get("formal_ids")
    if (
        not isinstance(formal_ids, list)
        or len(formal_ids) != 1
        or not isinstance(formal_ids[0], list)
        or len(formal_ids[0]) != formal_count
    ):
        errors.append(
            f"c{concurrency} fixture formal request count must be {formal_count}"
        )
    pairs = manifest.get("seed_formal_pairs")
    if not isinstance(pairs, list) or len(pairs) != formal_count:
        errors.append(f"c{concurrency} fixture prefix proofs must be {formal_count}")
    else:
        seed_ids = manifest.get("seed_ids")
        seed_id = seed_ids[0] if isinstance(seed_ids, list) and seed_ids else None
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                errors.append(f"c{concurrency} fixture pair {index} is malformed")
                continue
            if pair.get("seed_request_id") != seed_id:
                errors.append(f"c{concurrency} fixture pair {index} seed ID drift")
            if pair.get("seed_token_ids_sha256") != pair.get(
                "formal_prefix_token_ids_sha256"
            ):
                errors.append(f"c{concurrency} fixture pair {index} prefix mismatch")
    return errors


def _validate_short_diagnostic_evidence(
    root: Path,
    test: str,
    alternative: str,
    result: dict[str, Any],
    short_diagnostics: object,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("source") != "short_diagnostic":
        return [], {}
    errors: list[str] = []
    if not isinstance(short_diagnostics, dict):
        return [f"missing executed short diagnostic: {test}"], {}
    execution = short_diagnostics.get(test)
    if not isinstance(execution, dict):
        errors.append(f"missing executed short diagnostic: {test}")
    elif execution.get("final") != result:
        errors.append(f"short diagnostic final classification drift: {test}")

    variants = (
        ("bulk", alternative)
        if test == "test1"
        else ("bulk", "layerwise", "reuse3")
    )
    recomputed_by_variant: dict[str, dict[str, object]] = {}
    recomputed_points: dict[str, dict[str, Any]] = {}
    for variant in variants:
        point_root = root / "short-diagnostics" / test / variant
        identity_path = point_root / "identity.json"
        summary_path = point_root / "diagnostic-summary.json"
        if not identity_path.is_file() or not summary_path.is_file():
            errors.append(f"missing {test} {variant} short diagnostic summary")
            continue
        identity = _load_object(identity_path, "short diagnostic identity")
        expected_concurrency = 8 if test == "test1" else 40
        if (
            identity.get("test") != test
            or identity.get("variant") != variant
            or identity.get("request_count") != expected_concurrency
            or identity.get("range_debug") is not True
        ):
            errors.append(f"invalid {test} {variant} short diagnostic identity")
        expected_phases = (("warmup", 1), ("seed", 1), ("admission", 1))
        for phase, expected_attempts in expected_phases:
            attempts = list((point_root / phase).glob("attempt-*"))
            if len(attempts) != expected_attempts:
                errors.append(
                    f"{test} {variant} short diagnostic {phase} attempts must be "
                    f"{expected_attempts}: {len(attempts)}"
                )
        if (point_root / "formal-1").exists():
            errors.append(f"{test} {variant} short diagnostic repeated formal traffic")
        summary = _load_object(summary_path, "short diagnostic summary")
        if (
            summary.get("request_count") != expected_concurrency
            or not isinstance(summary.get("request_throughput"), (int, float))
        ):
            errors.append(f"invalid {test} {variant} short diagnostic result")
        by_role = summary.get("range_debug_by_role")
        if not isinstance(by_role, dict) or set(by_role) != {"prefill", "decode"}:
            errors.append(f"missing {test} {variant} role range-debug evidence")
        else:
            for role in ("prefill", "decode"):
                metrics = by_role.get(role)
                if (
                    not isinstance(metrics, dict)
                    or int(metrics.get("total_events", 0)) <= 0
                    or int(metrics.get("malformed_events", 0)) != 0
                    or int(metrics.get("failed_results", 0)) != 0
                ):
                    errors.append(
                        f"invalid {test} {variant} {role} range-debug evidence"
                    )
        kvpool_metadata_by_role = summary.get("kvpool_metric_metadata_by_role")
        if (
            not isinstance(kvpool_metadata_by_role, dict)
            or set(kvpool_metadata_by_role) != {"prefill", "decode"}
        ):
            errors.append(
                f"missing {test} {variant} KVPool metric schema metadata"
            )
        else:
            for role, metadata in kvpool_metadata_by_role.items():
                if (
                    not isinstance(metadata, dict)
                    or int(metadata.get("intervals", 0)) <= 0
                    or metadata.get("schema_versions") != [2]
                    or int(metadata.get("events", 0)) <= 0
                    or int(metadata.get("missing_exclusive_events", 0)) != 0
                    or int(metadata.get("malformed_lines", 0)) != 0
                ):
                    errors.append(
                        f"invalid {test} {variant} {role} KVPool metric schema metadata"
                    )
        admission = _single_attempt(point_root, "admission")
        if admission is not None:
            for name in (
                "summary.json",
                "hit-validation.json",
                "admission-validation.json",
                "observability-validation.json",
            ):
                if not (admission / "raw" / name).is_file():
                    errors.append(
                        f"missing {test} {variant} short diagnostic {name}"
                    )
            raw = admission / "raw"
            aisbench_summary_path = raw / "summary.json"
            archived_path = raw / "output-fingerprint.json"
            expected_contexts = (
                2 if test == "test2" and variant != "reuse3" else expected_concurrency
            )
            require_capacity_waiting = test == "test2" and variant != "reuse3"
            server_recomputed, server_errors = _recompute_server_evidence(
                raw,
                expected_contexts=expected_contexts,
                require_capacity_waiting=require_capacity_waiting,
                description=f"{test} {variant} short diagnostic",
            )
            errors.extend(server_errors)
            execution_points = (
                execution.get("points") if isinstance(execution, dict) else None
            )
            execution_point = (
                execution_points.get(variant)
                if isinstance(execution_points, dict)
                else None
            )
            if server_recomputed:
                for field in (
                    "admission",
                    "decode_prometheus",
                    "kvpool_events",
                    "kvpool_events_by_role",
                    "kvpool_metric_metadata_by_role",
                    "te_metrics",
                    "te_metrics_by_role",
                    "range_debug_by_role",
                ):
                    errors.extend(
                        _compare_server_field(
                            summary.get(field),
                            server_recomputed,
                            field,
                            f"{test} {variant} short diagnostic summary",
                        )
                    )
                    if isinstance(execution_point, dict):
                        errors.extend(
                            _compare_server_field(
                                execution_point.get(field),
                                server_recomputed,
                                field,
                                f"{test} {variant} short diagnostic diagnosis",
                            )
                        )
                if aisbench_summary_path.is_file():
                    raw_summary = _load_object(
                        aisbench_summary_path,
                        "short diagnostic AISBench summary",
                    )
                    raw_metrics = raw_summary.get("metrics")
                    if isinstance(raw_metrics, dict) and isinstance(
                        raw_metrics.get("Request Throughput"), (int, float)
                    ):
                        recomputed_points[variant] = {
                            "request_count": expected_concurrency,
                            "request_throughput": raw_metrics[
                                "Request Throughput"
                            ],
                            "metrics": raw_metrics,
                            "admission": server_recomputed["admission"],
                            "decode_prometheus": server_recomputed[
                                "decode_prometheus"
                            ],
                            "kvpool_events": server_recomputed[
                                "kvpool_events"
                            ],
                            "kvpool_events_by_role": server_recomputed[
                                "kvpool_events_by_role"
                            ],
                            "te_metrics": server_recomputed["te_metrics"],
                            "te_metrics_by_role": server_recomputed[
                                "te_metrics_by_role"
                            ],
                            "range_debug_by_role": server_recomputed[
                                "range_debug_by_role"
                            ],
                        }
                observability = _load_object(
                    raw / "observability-validation.json",
                    "short diagnostic observability validation",
                )
                errors.extend(
                    _compare_server_field(
                        observability,
                        server_recomputed,
                        "observability",
                        f"{test} {variant} short diagnostic archive",
                    )
                )
                archived_admission = _load_object(
                    raw / "admission-validation.json",
                    "short diagnostic admission validation",
                )
                errors.extend(
                    _compare_server_field(
                        archived_admission,
                        server_recomputed,
                        "admission",
                        f"{test} {variant} short diagnostic archive",
                    )
                )
            if not archived_path.is_file():
                errors.append(
                    f"missing {test} {variant} short diagnostic output fingerprint"
                )
            if aisbench_summary_path.is_file():
                aisbench_summary = _load_object(
                    aisbench_summary_path,
                    "short diagnostic AISBench summary",
                )
                recomputed, fingerprint_errors = _recompute_output_fingerprint(
                    raw,
                    aisbench_summary,
                    expected_concurrency,
                    f"{test} {variant} short diagnostic",
                )
                errors.extend(fingerprint_errors)
                if recomputed.get("valid") is True:
                    recomputed_by_variant[variant] = recomputed
                    if archived_path.is_file():
                        archived = _load_object(
                            archived_path,
                            "short diagnostic output fingerprint",
                        )
                        errors.extend(
                            _compare_fingerprint(
                                archived,
                                recomputed,
                                f"{test} {variant} short diagnostic archive",
                            )
                        )
                    errors.extend(
                        _compare_fingerprint(
                            summary.get("output_fingerprint"),
                            recomputed,
                            f"{test} {variant} short diagnostic summary",
                        )
                    )
                    execution_fingerprint = (
                        execution_point.get("output_fingerprint")
                        if isinstance(execution_point, dict)
                        else None
                    )
                    errors.extend(
                        _compare_fingerprint(
                            execution_fingerprint,
                            recomputed,
                            f"{test} {variant} short diagnostic diagnosis",
                        )
                    )
    if set(recomputed_by_variant) == set(variants):
        if test == "test1":
            recomputed_consistency: dict[str, object] = (
                issue1_diagnostics.validate_output_consistency(
                    {"output_fingerprint": recomputed_by_variant["bulk"]},
                    {"output_fingerprint": recomputed_by_variant[alternative]},
                )
            )
            valid_consistency = recomputed_consistency.get("valid") is True
        else:
            recomputed_consistency = {
                "bulk_layerwise": issue1_diagnostics.validate_output_consistency(
                    {"output_fingerprint": recomputed_by_variant["bulk"]},
                    {"output_fingerprint": recomputed_by_variant["layerwise"]},
                ),
                "bulk_reuse3": issue1_diagnostics.validate_output_consistency(
                    {"output_fingerprint": recomputed_by_variant["bulk"]},
                    {"output_fingerprint": recomputed_by_variant["reuse3"]},
                ),
                "layerwise_reuse3": issue1_diagnostics.validate_output_consistency(
                    {"output_fingerprint": recomputed_by_variant["layerwise"]},
                    {"output_fingerprint": recomputed_by_variant["reuse3"]},
                ),
            }
            valid_consistency = all(
                isinstance(value, dict) and value.get("valid") is True
                for value in recomputed_consistency.values()
            )
        if not valid_consistency:
            errors.append(f"recomputed short diagnostic output mismatch: {test}")
        if not isinstance(execution, dict) or execution.get(
            "output_consistency"
        ) != recomputed_consistency:
            errors.append(f"short diagnostic output consistency drift: {test}")
    for variant, fingerprint in recomputed_by_variant.items():
        if variant in recomputed_points:
            recomputed_points[variant]["output_fingerprint"] = fingerprint
    return errors, recomputed_points


def validate_evidence(root: Path) -> list[str]:
    errors = validate_checksums(root)
    for name in (
        "handoff.json",
        "source-identity.json",
        "client-identity.json",
        "run-contract.json",
        "restoration.json",
        "diagnosis.json",
    ):
        if not (root / name).is_file():
            errors.append(f"missing root evidence: {name}")
    if errors:
        return errors

    points = (*TEST1_POINTS, *test2_points(PREFERRED_TEST2_CONCURRENCY))
    expected_points = [point_id(point) for point in points]
    contract = _load_object(root / "run-contract.json", "run contract")
    if contract.get("expected_points") != expected_points:
        errors.append("run contract does not contain the exact four Issue #1 points")
    if contract.get("input_tokens") != 32000:
        errors.append("run contract input_tokens must be 32000")
    if contract.get("seed_tokens") != 28800:
        errors.append("run contract seed_tokens must be 28800")
    if contract.get("seed_request_count") != 1:
        errors.append("run contract seed_request_count must be 1")
    if contract.get("server_seed") != 1024:
        errors.append("server seed must be 1024")
    if contract.get("client_fixture_seed") != 1023:
        errors.append("client fixture seed must be 1023")
    if contract.get("test1_long_prefill_token_threshold") != 4096:
        errors.append("Test 1 long Prefill threshold must be 4096")
    if contract.get("test2_long_prefill_token_threshold") != 768:
        errors.append("Test 2 long Prefill threshold must be 768")
    if contract.get("max_num_partial_prefills") != {"test1": 8, "test2": 40}:
        errors.append("max_num_partial_prefills contract drift")
    if contract.get("max_long_partial_prefills") != {"test1": 8, "test2": 40}:
        errors.append("max_long_partial_prefills contract drift")
    if contract.get("test2_concurrency") != 40:
        errors.append("Test 2 concurrency must be the reviewed c40")
    bulk_capacity = contract.get("bulk_request_capacity")
    reuse_capacity = contract.get("reuse3_request_capacity")
    if (
        not isinstance(bulk_capacity, int)
        or not isinstance(reuse_capacity, int)
        or not (bulk_capacity < 40 <= reuse_capacity)
    ):
        errors.append("c40 must cross BULK capacity and fit REUSE3 capacity")

    errors.extend(_validate_fixture(root, 8, 125))
    errors.extend(_validate_fixture(root, 40, 100))
    recomputed_formal: dict[str, dict[str, object]] = {}
    recomputed_results: dict[str, dict[str, Any]] = {}
    for point in points:
        selected = point_id(point)
        point_root = root / "points" / selected
        if not (point_root / "identity.json").is_file():
            errors.append(f"missing point identity: {selected}")
        expected_phases = (
            ("warmup", 1),
            ("seed", 2),
            ("admission", 1),
            ("formal-1", 1),
        )
        for phase, expected_attempts in expected_phases:
            attempts = list((point_root / phase).glob("attempt-*"))
            if len(attempts) != expected_attempts:
                errors.append(
                    f"{selected} {phase} attempts must be {expected_attempts}: "
                    f"{len(attempts)}"
                )
        diagnostic_path = point_root / "diagnostic-summary.json"
        if not diagnostic_path.is_file():
            errors.append(f"missing diagnostic summary: {selected}")
            continue
        diagnostic = _load_object(diagnostic_path, "point diagnostic summary")
        if diagnostic.get("point_id") != selected:
            errors.append(f"diagnostic point ID mismatch: {selected}")
        admission = diagnostic.get("admission")
        canary = diagnostic.get("admission_canary")
        observability = diagnostic.get("observability_canary")
        if not isinstance(admission, dict) or admission.get("valid") is not True:
            errors.append(f"invalid formal admission evidence: {selected}")
        if not isinstance(canary, dict) or canary.get("valid") is not True:
            errors.append(f"invalid admission canary: {selected}")
        if (
            not isinstance(observability, dict)
            or observability.get("valid") is not True
        ):
            errors.append(f"invalid observability canary: {selected}")
        expected_contexts = (
            2 if point.test == "test2" and point.variant == "bulk" else point.concurrency
        )
        require_capacity_waiting = (
            point.test == "test2" and point.variant == "bulk"
        )
        admission_attempt = _single_attempt(point_root, "admission")
        if admission_attempt is not None:
            admission_recomputed, admission_errors = _recompute_server_evidence(
                admission_attempt / "raw",
                expected_contexts=expected_contexts,
                require_capacity_waiting=require_capacity_waiting,
                description=f"{selected} admission canary",
            )
            errors.extend(admission_errors)
            if admission_recomputed:
                errors.extend(
                    _compare_server_field(
                        canary,
                        admission_recomputed,
                        "admission",
                        f"{selected} admission canary",
                    )
                )
                errors.extend(
                    _compare_server_field(
                        observability,
                        admission_recomputed,
                        "observability",
                        f"{selected} observability canary",
                    )
                )
        kvpool_events = diagnostic.get("kvpool_events")
        if not isinstance(kvpool_events, dict) or not kvpool_events:
            errors.append(f"missing KVPool timing events: {selected}")
        kvpool_by_role = diagnostic.get("kvpool_events_by_role")
        if (
            not isinstance(kvpool_by_role, dict)
            or set(kvpool_by_role) != {"prefill", "decode"}
            or not all(isinstance(value, dict) for value in kvpool_by_role.values())
        ):
            errors.append(f"missing role-specific KVPool timings: {selected}")
        kvpool_metadata_by_role = diagnostic.get(
            "kvpool_metric_metadata_by_role"
        )
        if (
            not isinstance(kvpool_metadata_by_role, dict)
            or set(kvpool_metadata_by_role) != {"prefill", "decode"}
        ):
            errors.append(f"missing KVPool metric schema metadata: {selected}")
        else:
            for role, metadata in kvpool_metadata_by_role.items():
                if (
                    not isinstance(metadata, dict)
                    or int(metadata.get("intervals", 0)) <= 0
                    or metadata.get("schema_versions") != [2]
                    or int(metadata.get("events", 0)) <= 0
                    or int(metadata.get("missing_exclusive_events", 0)) != 0
                    or int(metadata.get("malformed_lines", 0)) != 0
                ):
                    errors.append(
                        f"invalid {role} KVPool metric schema metadata: {selected}"
                    )
        te_metrics = diagnostic.get("te_metrics")
        if (
            not isinstance(te_metrics, dict)
            or int(te_metrics.get("intervals", 0)) <= 0
        ):
            errors.append(f"missing Transfer Engine metrics: {selected}")
        te_by_role = diagnostic.get("te_metrics_by_role")
        if (
            not isinstance(te_by_role, dict)
            or set(te_by_role) != {"prefill", "decode"}
            or not all(isinstance(value, dict) for value in te_by_role.values())
        ):
            errors.append(f"missing role-specific Transfer Engine metrics: {selected}")
        if not isinstance(diagnostic.get("decode_prometheus"), dict):
            errors.append(f"missing Decode scheduler metrics: {selected}")
        output_fingerprint = diagnostic.get("output_fingerprint")
        if (
            not isinstance(output_fingerprint, dict)
            or output_fingerprint.get("valid") is not True
            or output_fingerprint.get("request_count") != point.formal_requests
            or not isinstance(output_fingerprint.get("digest"), str)
            or len(output_fingerprint.get("digest", "")) != 64
        ):
            errors.append(f"invalid output correctness fingerprint: {selected}")
        formal = _single_attempt(point_root, "formal-1")
        if formal is None:
            continue
        summary_path = formal / "raw" / "summary.json"
        hit_path = formal / "raw" / "hit-validation.json"
        admission_path = formal / "raw" / "admission-validation.json"
        output_path = formal / "raw" / "output-fingerprint.json"
        for path, description in (
            (summary_path, "formal summary"),
            (hit_path, "hit validation"),
            (admission_path, "formal admission validation"),
            (output_path, "formal output fingerprint"),
        ):
            if not path.is_file():
                errors.append(f"missing {description}: {selected}")
        if summary_path.is_file():
            summary = _load_object(summary_path, "formal summary")
            if (
                summary.get("valid") is not True
                or summary.get("request_count") != point.formal_requests
                or summary.get("success_count") != point.formal_requests
            ):
                errors.append(f"invalid formal summary: {selected}")
            metrics = summary.get("metrics")
            required_metrics = {
                "Request Throughput",
                "Input Token Throughput",
                "TTFT P95",
                "E2EL P95",
            }
            if point.output_tokens == 128:
                required_metrics.update(
                    {"Output Token Throughput", "TPOT P95", "ITL P95"}
                )
            if not isinstance(metrics, dict) or not required_metrics.issubset(metrics):
                errors.append(f"incomplete formal performance metrics: {selected}")
            recomputed, fingerprint_errors = _recompute_output_fingerprint(
                formal / "raw",
                summary,
                point.formal_requests,
                selected,
            )
            errors.extend(fingerprint_errors)
            if recomputed.get("valid") is True:
                recomputed_formal[selected] = recomputed
                if output_path.is_file():
                    archived = _load_object(
                        output_path,
                        "formal output fingerprint",
                    )
                    errors.extend(
                        _compare_fingerprint(
                            archived,
                            recomputed,
                            f"{selected} archive",
                        )
                    )
                errors.extend(
                    _compare_fingerprint(
                        diagnostic.get("output_fingerprint"),
                        recomputed,
                        f"{selected} diagnostic summary",
                    )
                )
            server_recomputed, server_errors = _recompute_server_evidence(
                formal / "raw",
                expected_contexts=expected_contexts,
                require_capacity_waiting=require_capacity_waiting,
                description=f"{selected} formal",
            )
            errors.extend(server_errors)
            if server_recomputed:
                for field in (
                    "admission",
                    "decode_prometheus",
                    "kvpool_events",
                    "kvpool_events_by_role",
                    "kvpool_metric_metadata_by_role",
                    "te_metrics",
                    "te_metrics_by_role",
                ):
                    errors.extend(
                        _compare_server_field(
                            diagnostic.get(field),
                            server_recomputed,
                            field,
                            f"{selected} formal",
                        )
                    )
                if admission_path.is_file():
                    archived_admission = _load_object(
                        admission_path,
                        "formal admission validation",
                    )
                    errors.extend(
                        _compare_server_field(
                            archived_admission,
                            server_recomputed,
                            "admission",
                            f"{selected} formal archive",
                        )
                    )
                if isinstance(metrics, dict):
                    recomputed_results[selected] = {
                        "point_id": selected,
                        "request_count": point.formal_requests,
                        "request_throughput": metrics["Request Throughput"],
                        "metrics": metrics,
                        "admission": server_recomputed["admission"],
                        "decode_prometheus": server_recomputed[
                            "decode_prometheus"
                        ],
                        "kvpool_events": server_recomputed["kvpool_events"],
                        "kvpool_events_by_role": server_recomputed[
                            "kvpool_events_by_role"
                        ],
                        "te_metrics": server_recomputed["te_metrics"],
                        "te_metrics_by_role": server_recomputed[
                            "te_metrics_by_role"
                        ],
                    }
        if hit_path.is_file():
            hit = _load_object(hit_path, "hit validation")
            if (
                hit.get("valid") is not True
                or hit.get("request_count") != point.formal_requests
                or hit.get("expected_hit_tokens") != 28800
                or hit.get("min_hit_tokens") != 28800
                or hit.get("max_hit_tokens") != 28800
                or hit.get("local_hit_tokens") != 0
            ):
                errors.append(f"invalid exact-hit evidence: {selected}")

    diagnosis = _load_object(root / "diagnosis.json", "diagnosis")
    output_consistency = diagnosis.get("output_consistency")
    if not isinstance(output_consistency, dict):
        errors.append("missing cross-variant output consistency evidence")
    else:
        for test in ("test1", "test2"):
            value = output_consistency.get(test)
            if not isinstance(value, dict) or value.get("valid") is not True:
                errors.append(f"cross-variant output mismatch or missing evidence: {test}")
    comparison_points = {
        "test1": TEST1_POINTS,
        "test2": test2_points(PREFERRED_TEST2_CONCURRENCY),
    }
    for test, comparison in comparison_points.items():
        bulk_id, alternative_id = (point_id(point) for point in comparison)
        if bulk_id not in recomputed_formal or alternative_id not in recomputed_formal:
            continue
        recomputed_consistency = issue1_diagnostics.validate_output_consistency(
            {"output_fingerprint": recomputed_formal[bulk_id]},
            {"output_fingerprint": recomputed_formal[alternative_id]},
        )
        if recomputed_consistency.get("valid") is not True:
            errors.append(f"recomputed cross-variant output mismatch: {test}")
        if (
            not isinstance(output_consistency, dict)
            or output_consistency.get(test) != recomputed_consistency
        ):
            errors.append(f"cross-variant output consistency drift: {test}")
    short_diagnostics = diagnosis.get("short_diagnostics", {})
    for test, comparison in comparison_points.items():
        bulk_id, alternative_id = (point_id(point) for point in comparison)
        if bulk_id not in recomputed_results or alternative_id not in recomputed_results:
            continue
        recomputed_classification = issue1_diagnostics.classify_slowdown(
            recomputed_results[bulk_id],
            recomputed_results[alternative_id],
            alternative_name="layerwise" if test == "test1" else "reuse3",
        )
        if not isinstance(short_diagnostics, dict) or test not in short_diagnostics:
            if diagnosis.get(test) != recomputed_classification:
                errors.append(f"formal slowdown classification drift: {test}")
    for test in ("test1", "test2"):
        result = diagnosis.get(test)
        if not isinstance(result, dict):
            errors.append(f"missing slowdown classification: {test}")
            continue
        if result.get("slower") is True and result.get("cause") in {None, "", "none"}:
            errors.append(f"slower result lacks a cause: {test}")
        if result.get("slower") is True and not isinstance(
            result.get("evidence"), dict
        ):
            errors.append(f"slower result lacks causal evidence: {test}")
        if result.get("slower") is True and result.get("resolved") is not True:
            errors.append(f"slower result remains unresolved: {test}")
        short_errors, short_points = _validate_short_diagnostic_evidence(
            root,
            test,
            "layerwise" if test == "test1" else "reuse3",
            result,
            short_diagnostics,
        )
        errors.extend(short_errors)
        if short_points:
            comparison = comparison_points[test]
            bulk_id, alternative_id = (point_id(point) for point in comparison)
            if (
                bulk_id in recomputed_results
                and alternative_id in recomputed_results
            ):
                formal_classification = issue1_diagnostics.classify_slowdown(
                    recomputed_results[bulk_id],
                    recomputed_results[alternative_id],
                    alternative_name=(
                        "layerwise" if test == "test1" else "reuse3"
                    ),
                )
                if test == "test1" and set(short_points) == {
                    "bulk",
                    "layerwise",
                }:
                    recomputed_final = (
                        issue1_diagnostics.resolve_with_short_diagnostic(
                            formal_classification,
                            short_points["bulk"],
                            short_points["layerwise"],
                            alternative_name="layerwise",
                        )
                    )
                elif test == "test2" and set(short_points) == {
                    "bulk",
                    "layerwise",
                    "reuse3",
                }:
                    recomputed_final = (
                        issue1_diagnostics.resolve_reuse3_with_layerwise_control(
                            formal_classification,
                            short_points["bulk"],
                            short_points["layerwise"],
                            short_points["reuse3"],
                        )
                    )
                else:
                    recomputed_final = None
                if recomputed_final is not None and recomputed_final != result:
                    errors.append(f"short diagnostic final classification drift: {test}")
    advantage = diagnosis.get("reuse3_capacity_advantage")
    if not isinstance(advantage, dict):
        errors.append("missing REUSE3 server-side capacity diagnosis")
    elif advantage.get("valid") is not True:
        errors.append("REUSE3 HBM capacity was not converted into sustained concurrency")
    test2_bulk_id, test2_reuse_id = (
        point_id(point) for point in test2_points(PREFERRED_TEST2_CONCURRENCY)
    )
    if (
        test2_bulk_id in recomputed_results
        and test2_reuse_id in recomputed_results
    ):
        recomputed_advantage = issue1_diagnostics.validate_reuse_capacity_advantage(
            recomputed_results[test2_bulk_id],
            recomputed_results[test2_reuse_id],
        )
        if advantage != recomputed_advantage:
            errors.append("REUSE3 capacity diagnosis drift")
    restoration = _load_object(root / "restoration.json", "restoration")
    if (
        restoration.get("completed") is not True
        or restoration.get("mooncake_empty") is not True
        or restoration.get("engines_stopped") is not True
    ):
        errors.append("serving environment restoration is incomplete")
    return errors


def render_report(root: Path) -> str:
    errors = validate_evidence(root)
    if errors:
        raise ValueError("invalid Issue #1 evidence: " + "; ".join(errors))
    points = (*TEST1_POINTS, *test2_points(PREFERRED_TEST2_CONCURRENCY))
    diagnostics = {
        point_id(point): _load_object(
            root / "points" / point_id(point) / "diagnostic-summary.json",
            "point diagnostic summary",
        )
        for point in points
    }
    diagnosis = _load_object(root / "diagnosis.json", "diagnosis")
    capacity_advantage = diagnosis["reuse3_capacity_advantage"]
    lines = [
        "# Mooncake Private Issue #1 Performance Diagnosis",
        "",
        "All four formal points passed identity, exact shared-prefix hit, "
        "server admission, request correctness, timing, and restoration gates.",
        "REUSE3 sustained server-side capacity advantage: "
        f"{str(capacity_advantage['valid']).lower()}.",
        "Cross-variant output consistency: true for Test 1 and Test 2.",
        "",
        "## Results",
        "",
        "| Test | Variant | Requests | Req/s | Input tok/s | Output tok/s | TTFT P95 ms | E2EL P95 ms | TPOT P95 ms | ITL P95 ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in points:
        selected = diagnostics[point_id(point)]
        metrics = selected["metrics"]
        lines.append(
            f"| {point.test} | {point.variant.upper()} | {point.formal_requests} | "
            f"{float(metrics['Request Throughput']):.6f} | "
            f"{float(metrics['Input Token Throughput']):.3f} | "
            f"{float(metrics.get('Output Token Throughput', 0)):.3f} | "
            f"{float(metrics['TTFT P95']):.3f} | "
            f"{float(metrics['E2EL P95']):.3f} | "
            f"{float(metrics.get('TPOT P95', 0)):.3f} | "
            f"{float(metrics.get('ITL P95', 0)):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Server Concurrency",
            "",
            "| Test | Variant | Peak Contexts | Mean Active Running | Capacity Waiting Sum | Preemptions | Context ms / 1K tokens |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for point in points:
        selected = diagnostics[point_id(point)]
        admission = selected["admission"]
        prometheus = admission["prometheus"]
        lines.append(
            f"| {point.test} | {point.variant.upper()} | "
            f"{int(admission['max_context_requests'])} | "
            f"{float(prometheus['mean_active_running']):.3f} | "
            f"{float(prometheus['capacity_waiting_sample_sum']):.3f} | "
            f"{float(prometheus['preemption_delta']):.3f} | "
            f"{float(admission['context_ms_per_1k_tokens']):.6f} |"
    )
    if diagnosis.get("short_diagnostics"):
        lines.extend(
            [
                "",
                "## Short Diagnostics",
                "",
                "Only one concurrency wave per variant was used for causal "
                "attribution; formal throughput points were not repeated.",
                "",
                "```json",
                json.dumps(diagnosis["short_diagnostics"], indent=2, sort_keys=True),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Diagnosis",
            "",
            "| Comparison | Throughput Ratio | Slower | Resolved | Cause |",
            "| --- | ---: | --- | --- | --- |",
            f"| LAYERWISE / BULK | {float(diagnosis['test1']['throughput_ratio']):.6f} | "
            f"{str(diagnosis['test1']['slower']).lower()} | "
            f"{str(diagnosis['test1']['resolved']).lower()} | {diagnosis['test1']['cause']} |",
            f"| REUSE3 / BULK | {float(diagnosis['test2']['throughput_ratio']):.6f} | "
            f"{str(diagnosis['test2']['slower']).lower()} | "
            f"{str(diagnosis['test2']['resolved']).lower()} | {diagnosis['test2']['cause']} |",
            "",
            "### REUSE3 Capacity",
            "",
            "```json",
            json.dumps(capacity_advantage, indent=2, sort_keys=True),
            "```",
        ]
    )
    for test, comparison in (("test1", "LAYERWISE / BULK"), ("test2", "REUSE3 / BULK")):
        result = diagnosis[test]
        lines.extend(
            [
                "",
                f"### {comparison} Evidence",
                "",
                "```json",
                json.dumps(
                    {
                        "cause": result["cause"],
                        "resolved": result["resolved"],
                        "evidence": result.get("evidence", {}),
                        "timing_breakdown": result.get("timing_breakdown", {}),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Transfer Engine",
            "",
            "| Test | Variant | Role | Mean MB/s | Max MB/s | Tasks |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for point in points:
        selected = diagnostics[point_id(point)]
        for role in ("prefill", "decode"):
            metrics = selected["te_metrics_by_role"][role]
            lines.append(
                f"| {point.test} | {point.variant.upper()} | {role} | "
                f"{float(metrics['mean_throughput_mb_s']):.3f} | "
                f"{float(metrics['max_throughput_mb_s']):.3f} | "
                f"{int(metrics['task_count'])} |"
            )
    lines.extend(
        [
            "",
            "The ratios are one-run characterization. They are not statistical "
            "significance or product performance thresholds. KVPool timing sums "
            "are aggregated rank-time for same-topology A/B attribution, not "
            "end-to-end wall-time decomposition.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    text = render_report(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
