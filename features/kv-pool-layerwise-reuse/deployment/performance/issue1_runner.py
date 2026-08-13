from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from performance import handoff, image, issue1_diagnostics, report, runner, runtime
from performance.contract import TOPOLOGIES, WorkloadPoint
from performance.issue1_contract import (
    CLIENT_FIXTURE_SEED,
    INPUT_TOKENS,
    PREFERRED_TEST2_CONCURRENCY,
    SEED_BLOCKS,
    SEED_TOKENS,
    SHARED_SEED_REQUESTS,
    TEST1_POINTS,
    WARMUP_REQUESTS,
    Issue1Point,
    build_issue1_run_contract,
    expected_admission_contexts,
    point_id,
    test2_points,
)

REQUIRED_AUTHORIZATION = (
    "private Issue #1",
    "input=32000",
    "external hit=28800",
    "output=128",
    "concurrency=8",
    "125 formal requests",
    "output=1",
    "concurrency=40",
    "100 formal requests",
    "max_num_partial_prefills=8",
    "max_num_partial_prefills=40",
    "KVPOOL_PERF_METRICS",
    "VLLM_ASCEND_KVPOOL_RANGE_DEBUG",
    "one-wave short diagnostic",
    "conditional LAYERWISE c40 diagnostic control",
)
PERF_METRICS_FLUSH_SECONDS = 2 * runtime.KVPOOL_PERF_METRICS_INTERVAL_SECONDS


def _workload(point: Issue1Point, *, output_tokens: int | None = None) -> WorkloadPoint:
    return WorkloadPoint(
        point.topology,
        point.input_tokens,
        point.output_tokens if output_tokens is None else output_tokens,
        point.variant,
        point.concurrency,
    )


def _all_points() -> tuple[Issue1Point, ...]:
    return (*TEST1_POINTS, *test2_points(PREFERRED_TEST2_CONCURRENCY))


def _diagnostic_points(
    test: str,
    formal_points: tuple[Issue1Point, ...],
) -> tuple[Issue1Point, ...]:
    if test == "test1":
        return formal_points
    if test == "test2":
        bulk, reuse3 = formal_points
        return bulk, replace(reuse3, variant="layerwise"), reuse3
    raise ValueError(f"unsupported diagnostic test: {test}")


def validate_authorization(state: handoff.HandoffState) -> list[str]:
    scope = "\n".join(state.authorized_scope)
    return [
        f"Issue #1 authorization is missing {value}"
        for value in REQUIRED_AUTHORIZATION
        if value not in scope
    ]


def _generate_fixture_command(
    point: Issue1Point,
    environment: runner.RunEnvironment,
) -> runner.Command:
    return runner.Command(
        (
            "kubectl",
            "exec",
            "-n",
            environment.namespace,
            environment.client_pod,
            "-c",
            "aisbench",
            "--",
            "chroot",
            "/performance-workspace/rootfs",
            "env",
            "TORCH_DEVICE_BACKEND_AUTOLOAD=0",
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONPATH=/client-tools/tooling",
            "/client-tools/venv/bin/python",
            "-m",
            "performance.fixtures",
            "generate",
            "--tokenizer",
            "/client-tools/tokenizer",
            "--output",
            "/client-tools/fixtures",
            "--input-tokens",
            str(point.input_tokens),
            "--seed-tokens",
            str(SEED_TOKENS),
            "--concurrency",
            str(point.concurrency),
            "--warmup-count",
            str(WARMUP_REQUESTS),
            "--formal-count",
            str(point.formal_requests),
            "--seed-request-count",
            str(SHARED_SEED_REQUESTS),
            "--admission-count",
            str(point.concurrency),
            "--shared-prefix",
            "--seed",
            str(CLIENT_FIXTURE_SEED),
        ),
        description=f"generate-issue1-c{point.concurrency}-fixtures",
    )


def prepare(
    command_runner: runner.Runner,
    output_dir: Path,
    image_reference: str,
    manifest_digest: str,
    config_digest: str,
    tokenizer_source: Path,
) -> None:
    runner.prepare(
        command_runner,
        output_dir,
        image_reference,
        manifest_digest,
        config_digest,
        tokenizer_source,
    )
    environment = runner.RunEnvironment()
    points = (TEST1_POINTS[0], test2_points(PREFERRED_TEST2_CONCURRENCY)[0])
    for point in points:
        command_runner.run(_generate_fixture_command(point, environment))
        runner._archive_fixture(
            command_runner,
            output_dir,
            point.input_tokens,
            point.concurrency,
            include_admission=True,
        )
    runner._write_json(
        output_dir / "issue1-preparation-contract.json",
        {
            "input_tokens": INPUT_TOKENS,
            "seed_tokens": SEED_TOKENS,
            "prefix_mode": "shared",
            "fixtures": [
                {
                    "concurrency": point.concurrency,
                    "formal_requests": point.formal_requests,
                    "warmup_requests": WARMUP_REQUESTS,
                    "seed_requests": SHARED_SEED_REQUESTS,
                    "admission_requests": point.concurrency,
                }
                for point in points
            ],
        },
    )
    runner._write_checksums(output_dir)


def _role_log_offset_command(
    role: str,
    environment: runner.RunEnvironment,
) -> runner.Command:
    return runner.Command(
        (
            "kubectl",
            "exec",
            "-n",
            environment.namespace,
            getattr(environment, f"{role}_resource"),
            "-c",
            f"{role}-engine",
            "--",
            "sh",
            "-c",
            f"wc -c < /tmp/vllm-{role}.log",
        ),
        description=f"{role}-log-offset",
    )


def _role_log_delta_command(
    role: str,
    environment: runner.RunEnvironment,
    offset: int,
) -> runner.Command:
    return runner.Command(
        (
            "kubectl",
            "exec",
            "-n",
            environment.namespace,
            getattr(environment, f"{role}_resource"),
            "-c",
            f"{role}-engine",
            "--",
            "tail",
            "-c",
            f"+{offset + 1}",
            f"/tmp/vllm-{role}.log",
        ),
        description=f"{role}-log-delta",
    )


def _perf_metrics_flush_command(boundary: str) -> runner.Command:
    return runner.Command(
        ("sleep", str(PERF_METRICS_FLUSH_SECONDS)),
        description=f"flush-perf-metrics-{boundary}",
    )


def _sampled_command(
    aisbench_argv: tuple[str, ...],
    environment: runner.RunEnvironment,
) -> runner.Command:
    namespace = environment.namespace
    script = f'''set -euo pipefail
raw=$1
shift
mkdir -p "${{raw}}"
sample_npu() {{
  role=$1
  resource=$2
  while true; do
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
    kubectl exec -n {namespace} "${{resource}}" -c "${{role}}-engine" -- npu-smi info || true
    sleep 10
  done
}}
sample_prefill_metrics() {{
  while true; do
    echo "TIMESTAMP $(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
    kubectl exec -n {namespace} {environment.prefill_resource} -c prefill-engine -- \
      python3 -c 'from urllib.request import urlopen; print(urlopen("http://127.0.0.1:8100/metrics", timeout=5).read().decode(), end="")' || true
    sleep 1
  done
}}
sample_decode_metrics() {{
  while true; do
    echo "TIMESTAMP $(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
    kubectl exec -n {namespace} {environment.decode_resource} -c decode-engine -- \
      python3 -c 'from urllib.request import urlopen; print(urlopen("http://127.0.0.1:8200/metrics", timeout=5).read().decode(), end="")' || true
    sleep 1
  done
}}
sample_master() {{
  while true; do
    echo "TIMESTAMP $(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
    kubectl exec -n {namespace} {environment.client_pod} -c aisbench -- \
      chroot /performance-workspace/rootfs /client-tools/venv/bin/python -c \
      'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics", timeout=5).read().decode(), end="")' || true
    sleep 10
  done
}}
sample_npu prefill {environment.prefill_resource} >"${{raw}}/prefill-npu-timeseries.log" 2>&1 & p1=$!
sample_npu decode {environment.decode_resource} >"${{raw}}/decode-npu-timeseries.log" 2>&1 & p2=$!
sample_prefill_metrics >"${{raw}}/prefill-prometheus-timeseries.metrics" 2>&1 & p3=$!
sample_decode_metrics >"${{raw}}/decode-prometheus-timeseries.metrics" 2>&1 & p4=$!
sample_master >"${{raw}}/mooncake-timeseries.metrics" 2>&1 & p5=$!
cleanup() {{
  kill "${{p1}}" "${{p2}}" "${{p3}}" "${{p4}}" "${{p5}}" 2>/dev/null || true
  wait "${{p1}}" "${{p2}}" "${{p3}}" "${{p4}}" "${{p5}}" 2>/dev/null || true
}}
trap cleanup EXIT INT TERM
"$@"
'''
    return runner.Command(
        ("bash", "-c", script, "bash", "__LOCAL_RAW__", *aisbench_argv),
        sends_inference=True,
        description="aisbench",
    )


def _attempt(
    command_runner: runner.Runner,
    issue_point: Issue1Point,
    attempt_point: WorkloadPoint,
    phase: str,
    request_count: int,
    point_root: Path,
    environment: runner.RunEnvironment,
    *,
    capture_server_evidence: bool,
) -> dict[str, Any]:
    attempt = runner._new_attempt(point_root, phase)
    offsets: dict[str, int] = {}
    if capture_server_evidence:
        runner._invoke(
            command_runner,
            _perf_metrics_flush_command("before"),
            attempt,
        )
        for role in ("prefill", "decode"):
            raw_offset = runner._capture(
                command_runner,
                _role_log_offset_command(role, environment),
                attempt,
                f"{role}-log-offset.txt",
            )
            try:
                offsets[role] = int(raw_offset.strip())
            except ValueError as error:
                raise RuntimeError(f"invalid {role} log offset: {raw_offset!r}") from error

    token = hashlib.sha256(str(attempt.resolve()).encode()).hexdigest()[:16]
    remote = f"issue1/{point_id(issue_point)}/{phase}/{token}"
    commands = runner._attempt_commands(
        attempt_point,
        phase,
        request_count,
        remote,
        environment,
        fixture_concurrency=issue_point.concurrency,
        sampled_command=_sampled_command,
    )
    for command in commands:
        if command.description in {"aisbench", "archive-aisbench"}:
            command = replace(
                command,
                argv=tuple(
                    str(attempt / "raw") if value == "__LOCAL_RAW__" else value
                    for value in command.argv
                ),
            )
        runner._invoke(command_runner, command, attempt)
    if capture_server_evidence:
        runner._invoke(
            command_runner,
            _perf_metrics_flush_command("after"),
            attempt,
        )
    runner._replace_attempt_fixture(
        attempt / "raw",
        issue_point.input_tokens,
        phase,
        issue_point.concurrency,
    )

    result: dict[str, Any] = {"attempt": str(attempt)}
    if phase == "seed":
        seeded = runner._client_python(
            environment, runner._master_key_count_script(SEED_BLOCKS)
        )
        runner._capture(
            command_runner,
            runner.Command(seeded.argv, description="assert-shared-seed"),
            attempt,
            "seeded-mooncake.metrics",
        )

    if capture_server_evidence:
        logs: dict[str, str] = {}
        for role in ("prefill", "decode"):
            logs[role] = runner._capture(
                command_runner,
                _role_log_delta_command(role, environment, offsets[role]),
                attempt,
                f"{role}-delta.log",
            )
        hit_validation = runner.validate_prefill_hits(
            logs["prefill"],
            expected_request_count=request_count,
            expected_total_tokens=INPUT_TOKENS,
            expected_hit_tokens=SEED_TOKENS,
        )
        runner._write_json(attempt / "raw" / "hit-validation.json", hit_validation)
        if hit_validation["valid"] is not True:
            raise RuntimeError(
                "invalid Issue #1 hit evidence: "
                + "; ".join(str(value) for value in hit_validation["errors"])
            )
        prometheus_path = attempt / "raw" / "prefill-prometheus-timeseries.metrics"
        prometheus_text = (
            prometheus_path.read_text(encoding="utf-8")
            if prometheus_path.is_file()
            else ""
        )
        result["logs"] = logs
        result["prometheus_text"] = prometheus_text
        decode_prometheus_path = (
            attempt / "raw" / "decode-prometheus-timeseries.metrics"
        )
        decode_prometheus_text = (
            decode_prometheus_path.read_text(encoding="utf-8")
            if decode_prometheus_path.is_file()
            else ""
        )
        result["decode_prometheus"] = (
            issue1_diagnostics.parse_prometheus_timeseries(
                decode_prometheus_text
            )
        )
        result["kvpool_events_by_role"] = {
            role: issue1_diagnostics.parse_kvpool_metrics(text)
            for role, text in logs.items()
        }
        result["kvpool_metric_metadata_by_role"] = {
            role: issue1_diagnostics.parse_kvpool_metric_metadata(text)
            for role, text in logs.items()
        }
        result["te_metrics_by_role"] = {
            role: issue1_diagnostics.parse_te_metrics(text)
            for role, text in logs.items()
        }
        result["range_debug_by_role"] = {
            role: issue1_diagnostics.parse_range_debug_metrics(text)
            for role, text in logs.items()
        }
        result["kvpool_events"] = issue1_diagnostics.parse_kvpool_metrics(
            logs["prefill"] + "\n" + logs["decode"]
        )
        result["te_metrics"] = issue1_diagnostics.parse_te_metrics(
            logs["prefill"] + "\n" + logs["decode"]
        )

    if environment.image_digest:
        summary_point = (
            replace(attempt_point, input_tokens=SEED_TOKENS)
            if phase == "seed"
            else attempt_point
        )
        summary = report.summarize_aisbench_attempt(
            attempt / "raw",
            summary_point,
            request_count,
            environment.image_digest,
        )
        runner._write_json(attempt / "raw" / "summary.json", summary)
        if summary.get("valid") is not True:
            raise RuntimeError(
                "invalid AISBench attempt: "
                + "; ".join(str(value) for value in summary.get("errors", []))
            )
        result["summary"] = summary
    return result


def _measured_result(
    point: Issue1Point,
    attempt: dict[str, Any],
    *,
    expected_contexts: int,
    require_capacity_waiting: bool,
) -> dict[str, Any]:
    admission = issue1_diagnostics.validate_admission(
        attempt["logs"]["prefill"],
        attempt["prometheus_text"],
        expected_contexts=expected_contexts,
        require_capacity_waiting=require_capacity_waiting,
    )
    runner._write_json(
        Path(attempt["attempt"]) / "raw" / "admission-validation.json",
        admission,
    )
    if admission["valid"] is not True:
        raise RuntimeError(
            "measured traffic did not preserve server admission: "
            + "; ".join(str(value) for value in admission["errors"])
        )
    metrics = attempt["summary"]["metrics"]
    required_metrics = {
        "Request Throughput",
        "Input Token Throughput",
        "TTFT P95",
        "E2EL P95",
    }
    if point.output_tokens == 128:
        required_metrics.update({"Output Token Throughput", "TPOT P95", "ITL P95"})
    missing_metrics = sorted(required_metrics - metrics.keys())
    if missing_metrics:
        raise RuntimeError(
            "measured AISBench metrics are incomplete: " + ", ".join(missing_metrics)
        )
    details_path = (
        Path(attempt["attempt"])
        / "raw"
        / str(attempt["summary"].get("raw_details", ""))
    )
    output_fingerprint = issue1_diagnostics.fingerprint_predictions(
        details_path,
        int(attempt["summary"]["request_count"]),
    )
    runner._write_json(
        Path(attempt["attempt"]) / "raw" / "output-fingerprint.json",
        output_fingerprint,
    )
    if output_fingerprint["valid"] is not True:
        raise RuntimeError(
            "invalid output correctness evidence: "
            + "; ".join(str(value) for value in output_fingerprint["errors"])
        )
    return {
        "point_id": point_id(point),
        "request_count": int(attempt["summary"]["request_count"]),
        "request_throughput": metrics["Request Throughput"],
        "metrics": metrics,
        "admission": admission,
        "decode_prometheus": attempt["decode_prometheus"],
        "kvpool_events": attempt["kvpool_events"],
        "kvpool_events_by_role": attempt["kvpool_events_by_role"],
        "kvpool_metric_metadata_by_role": attempt[
            "kvpool_metric_metadata_by_role"
        ],
        "te_metrics": attempt["te_metrics"],
        "te_metrics_by_role": attempt["te_metrics_by_role"],
        "range_debug_by_role": attempt["range_debug_by_role"],
        "output_fingerprint": output_fingerprint,
    }


def _expected_contexts(
    point: Issue1Point,
    bulk_capacity_tokens: int,
) -> int:
    if point.test == "test2" and point.variant != "reuse3":
        # The scheduler may admit all 40 initial chunks before incremental KV
        # allocation reaches the startup-capacity boundary. Require multiple
        # contexts for both no-reuse variants; capacity pressure itself is
        # proven independently by waiting_by_reason and sustained-running
        # metrics.
        return 2
    return expected_admission_contexts(
        point,
        bulk_request_capacity=bulk_capacity_tokens // INPUT_TOKENS,
    )


def _requires_capacity_waiting(point: Issue1Point) -> bool:
    return point.test == "test2" and point.variant != "reuse3"


def execute_point(
    command_runner: runner.Runner,
    point: Issue1Point,
    output_dir: Path,
    environment: runner.RunEnvironment,
    *,
    bulk_capacity_tokens: int,
) -> dict[str, Any]:
    point_root = output_dir / "points" / point_id(point)
    workload = _workload(point)
    runner._write_json(
        point_root / "identity.json",
        {
            "test": point.test,
            "variant": point.variant,
            "input_tokens": point.input_tokens,
            "output_tokens": point.output_tokens,
            "concurrency": point.concurrency,
            "formal_requests": point.formal_requests,
            "image_digest": environment.image_digest,
        },
    )

    _attempt(
        command_runner,
        point,
        workload,
        "warmup",
        WARMUP_REQUESTS,
        point_root,
        environment,
        capture_server_evidence=False,
    )
    seed_point = replace(workload, output_tokens=1)
    _attempt(
        command_runner,
        point,
        seed_point,
        "seed",
        SHARED_SEED_REQUESTS,
        point_root,
        environment,
        capture_server_evidence=False,
    )
    admission = _attempt(
        command_runner,
        point,
        seed_point,
        "admission",
        point.concurrency,
        point_root,
        environment,
        capture_server_evidence=True,
    )
    expected_contexts = _expected_contexts(point, bulk_capacity_tokens)
    admission_validation = issue1_diagnostics.validate_admission(
        admission["logs"]["prefill"],
        admission["prometheus_text"],
        expected_contexts=expected_contexts,
        require_capacity_waiting=_requires_capacity_waiting(point),
    )
    runner._write_json(
        Path(admission["attempt"]) / "raw" / "admission-validation.json",
        admission_validation,
    )
    if admission_validation["valid"] is not True:
        raise RuntimeError(
            "server admission canary is invalid: "
            + "; ".join(str(value) for value in admission_validation["errors"])
        )
    observability = issue1_diagnostics.validate_observability(admission)
    runner._write_json(
        Path(admission["attempt"]) / "raw" / "observability-validation.json",
        observability,
    )
    if observability["valid"] is not True:
        raise RuntimeError(
            "server observability canary is invalid: "
            + "; ".join(str(value) for value in observability["errors"])
        )

    _attempt(
        command_runner,
        point,
        seed_point,
        "seed",
        SHARED_SEED_REQUESTS,
        point_root,
        environment,
        capture_server_evidence=False,
    )
    formal = _attempt(
        command_runner,
        point,
        workload,
        "formal-1",
        point.formal_requests,
        point_root,
        environment,
        capture_server_evidence=True,
    )
    result = _measured_result(
        point,
        formal,
        expected_contexts=expected_contexts,
        require_capacity_waiting=_requires_capacity_waiting(point),
    )
    result["admission_canary"] = admission_validation
    result["observability_canary"] = observability
    runner._write_json(point_root / "diagnostic-summary.json", result)
    return result


def execute_short_diagnostic(
    command_runner: runner.Runner,
    point: Issue1Point,
    output_dir: Path,
    environment: runner.RunEnvironment,
    *,
    bulk_capacity_tokens: int,
) -> dict[str, Any]:
    point_root = output_dir / "short-diagnostics" / point.test / point.variant
    workload = _workload(point)
    runner._write_json(
        point_root / "identity.json",
        {
            "test": point.test,
            "variant": point.variant,
            "input_tokens": point.input_tokens,
            "output_tokens": point.output_tokens,
            "concurrency": point.concurrency,
            "request_count": point.concurrency,
            "range_debug": True,
            "image_digest": environment.image_digest,
        },
    )
    _attempt(
        command_runner,
        point,
        workload,
        "warmup",
        WARMUP_REQUESTS,
        point_root,
        environment,
        capture_server_evidence=False,
    )
    _attempt(
        command_runner,
        point,
        replace(workload, output_tokens=1),
        "seed",
        SHARED_SEED_REQUESTS,
        point_root,
        environment,
        capture_server_evidence=False,
    )
    measured = _attempt(
        command_runner,
        point,
        workload,
        "admission",
        point.concurrency,
        point_root,
        environment,
        capture_server_evidence=True,
    )
    result = _measured_result(
        point,
        measured,
        expected_contexts=_expected_contexts(point, bulk_capacity_tokens),
        require_capacity_waiting=_requires_capacity_waiting(point),
    )
    observability = issue1_diagnostics.validate_observability(measured)
    runner._write_json(
        Path(measured["attempt"]) / "raw" / "observability-validation.json",
        observability,
    )
    if observability["valid"] is not True:
        raise RuntimeError(
            "short diagnostic observability is invalid: "
            + "; ".join(str(value) for value in observability["errors"])
        )
    result["observability_canary"] = observability
    runner._write_json(point_root / "diagnostic-summary.json", result)
    return result


def _startup_capacity(
    command_runner: runner.Runner,
    point: Issue1Point,
    environment: runner.RunEnvironment,
    output_dir: Path,
) -> int:
    text = runner._run_and_save(
        command_runner,
        runner.Command(
            (
                "kubectl",
                "exec",
                "-n",
                environment.namespace,
                environment.prefill_resource,
                "-c",
                "prefill-engine",
                "--",
                "cat",
                "/tmp/vllm-prefill.log",
            ),
            description="capture-startup-prefill-log",
        ),
        output_dir / "startup" / f"{point_id(point)}-prefill.log",
    )
    capacity = issue1_diagnostics.parse_kv_capacity_tokens(text)
    runner._write_json(
        output_dir / "startup" / f"{point_id(point)}-capacity.json",
        {"point_id": point_id(point), "kv_capacity_tokens": capacity},
    )
    return capacity


def run(
    command_runner: runner.Runner,
    state: handoff.HandoffState,
    output_dir: Path,
    *,
    npu_node: str,
) -> None:
    errors = handoff.validate_handoff(state, runner.WORKSPACE_ROOT)
    errors.extend(validate_authorization(state))
    if errors:
        raise handoff.HandoffError("Issue #1 handoff is not ready: " + "; ".join(errors))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"run output is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_config_digest = state.image_fields.get("Derived config digest", "")
    if not expected_config_digest:
        raise handoff.HandoffError("handoff lacks Derived config digest")
    runner._sync_client_tooling(command_runner, output_dir, expected_config_digest)
    runner._archive_fixture(command_runner, output_dir, INPUT_TOKENS, 8, include_admission=True)
    runner._archive_fixture(command_runner, output_dir, INPUT_TOKENS, 40, include_admission=True)
    runner._capture_identity(command_runner, state, output_dir)
    inputs = runner._capture_pre_run_state(command_runner, output_dir)
    nodes = json.loads((output_dir / "cluster" / "nodes.json").read_text())
    pods = json.loads((output_dir / "cluster" / "pods.json").read_text())
    available_npus = runner._available_test_npus(nodes, pods, npu_node)
    required_npus = TOPOLOGIES["dp1"].prefill_npus + TOPOLOGIES["dp1"].decode_npus
    if available_npus < required_npus:
        raise RuntimeError(
            f"insufficient physical Ascend910 capacity: {available_npus} < {required_npus}"
        )
    image_identity = image.resolve_server_image(
        state, runner._ImageRunner(command_runner), output_dir / "image"
    )
    environment = runner.RunEnvironment(
        restore_manifest=output_dir / "pre-run-state",
        image_digest=image_identity.digest,
    )
    points = _all_points()
    runner._write_json(
        output_dir / "planned-run-contract.json",
        {
            "handoff_sha256": state.digest,
            "image_digest": image_identity.digest,
            "npu_node": npu_node,
            "expected_points": [point_id(point) for point in points],
        },
    )

    configmaps: set[str] = set()
    results: dict[str, dict[str, Any]] = {}
    capacities: dict[str, int] = {}
    run_error: BaseException | None = None
    run_contract: dict[str, object] = {
        "expected_points": [point_id(point) for point in points]
    }
    try:
        rendered: dict[str, runtime.RenderedResources] = {}
        paths: dict[str, tuple[Path, Path, Path]] = {}
        for point in points:
            workload = _workload(point)
            profile = runtime.issue1_runtime_profile(point)
            resources, point_paths = runner._write_rendered_block(
                inputs,
                workload,
                image_identity.reference,
                output_dir,
                node_name=npu_node,
                profile=profile,
            )
            rendered[point_id(point)] = resources
            paths[point_id(point)] = point_paths
            configmaps.add(str(resources.runtime_configmap["metadata"]["name"]))
        for comparison in (
            {point.variant: rendered[point_id(point)] for point in points if point.test == "test1"},
            {point.variant: rendered[point_id(point)] for point in points if point.test == "test2"},
        ):
            drift = runtime.validate_unique_difference(comparison)
            if drift:
                raise RuntimeError("runtime comparison drift: " + "; ".join(drift))

        bulk_capacity = 0
        for point in points:
            workload = _workload(point)
            runner._apply_variant_block(
                command_runner,
                paths[point_id(point)],
                workload,
                environment,
                output_dir,
            )
            capacity = _startup_capacity(
                command_runner, point, environment, output_dir
            )
            capacities[point_id(point)] = capacity
            if point.variant == "bulk":
                bulk_capacity = capacity
            if point.test == "test2" and point.variant == "bulk":
                if point.concurrency <= capacity // INPUT_TOKENS:
                    raise RuntimeError("c40 does not cross BULK startup KV capacity")
            if point.variant == "reuse3" and point.concurrency > capacity // INPUT_TOKENS:
                raise RuntimeError("c40 does not fit REUSE3 startup KV capacity")
            results[point_id(point)] = execute_point(
                command_runner,
                point,
                output_dir,
                environment,
                bulk_capacity_tokens=bulk_capacity,
            )
            runner._capture_variant_diagnostics(
                command_runner, point_id(point), environment, output_dir
            )
            stop_errors = runner._stop_engines(command_runner, environment)
            if stop_errors:
                raise RuntimeError("; ".join(stop_errors))

        reuse_capacity = capacities[point_id(points[-1])]
        run_contract = build_issue1_run_contract(
            image_digest=image_identity.digest,
            bulk_capacity_tokens=bulk_capacity,
            reuse3_capacity_tokens=reuse_capacity,
            npu_node=npu_node,
        )
        test1_bulk, test1_layerwise, test2_bulk, test2_reuse = (
            results[point_id(point)] for point in points
        )
        capacity_advantage = issue1_diagnostics.validate_reuse_capacity_advantage(
            test2_bulk, test2_reuse
        )
        output_consistency = {
            "test1": issue1_diagnostics.validate_output_consistency(
                test1_bulk, test1_layerwise
            ),
            "test2": issue1_diagnostics.validate_output_consistency(
                test2_bulk, test2_reuse
            ),
        }
        invalid_outputs = [
            test for test, value in output_consistency.items() if value["valid"] is not True
        ]
        if invalid_outputs:
            raise RuntimeError(
                "confirmed output correctness defect in: " + ", ".join(invalid_outputs)
            )
        diagnosis = {
            "test1": issue1_diagnostics.classify_slowdown(
                test1_bulk, test1_layerwise, alternative_name="layerwise"
            ),
            "test2": issue1_diagnostics.classify_slowdown(
                test2_bulk, test2_reuse, alternative_name="reuse3"
            ),
            "capacities": capacities,
            "reuse3_capacity_advantage": capacity_advantage,
            "output_consistency": output_consistency,
        }
        short_diagnostics: dict[str, object] = {}
        points_by_test = {
            "test1": points[:2],
            "test2": points[2:],
        }
        alternative_by_test = {"test1": "layerwise", "test2": "reuse3"}
        for test in ("test1", "test2"):
            spec = issue1_diagnostics.short_diagnostic_spec(test, diagnosis[test])
            if spec is None:
                continue
            diagnostic_points = _diagnostic_points(test, points_by_test[test])
            diagnostic_rendered: dict[str, runtime.RenderedResources] = {}
            diagnostic_paths: dict[str, tuple[Path, Path, Path]] = {}
            for point in diagnostic_points:
                profile = runtime.issue1_runtime_profile(point, diagnostic=True)
                resources, point_paths = runner._write_rendered_block(
                    inputs,
                    _workload(point),
                    image_identity.reference,
                    output_dir,
                    node_name=npu_node,
                    profile=profile,
                )
                diagnostic_rendered[point.variant] = resources
                diagnostic_paths[point.variant] = point_paths
                configmaps.add(str(resources.runtime_configmap["metadata"]["name"]))
            drift = runtime.validate_unique_difference(diagnostic_rendered)
            if drift:
                raise RuntimeError(
                    "short diagnostic runtime comparison drift: "
                    + "; ".join(drift)
                )

            diagnostic_results: dict[str, dict[str, Any]] = {}
            for point in diagnostic_points:
                runner._apply_variant_block(
                    command_runner,
                    diagnostic_paths[point.variant],
                    _workload(point),
                    environment,
                    output_dir,
                )
                diagnostic_results[point.variant] = execute_short_diagnostic(
                    command_runner,
                    point,
                    output_dir,
                    environment,
                    bulk_capacity_tokens=bulk_capacity,
                )
                runner._capture_variant_diagnostics(
                    command_runner,
                    f"short-{point_id(point)}",
                    environment,
                    output_dir,
                )
                stop_errors = runner._stop_engines(command_runner, environment)
                if stop_errors:
                    raise RuntimeError("; ".join(stop_errors))

            alternative = alternative_by_test[test]
            if test == "test1":
                diagnostic_output_consistency: dict[str, object] = (
                    issue1_diagnostics.validate_output_consistency(
                        diagnostic_results["bulk"],
                        diagnostic_results[alternative],
                    )
                )
                invalid_diagnostic_outputs = (
                    diagnostic_output_consistency["valid"] is not True
                )
            else:
                diagnostic_output_consistency = {
                    "bulk_layerwise": issue1_diagnostics.validate_output_consistency(
                        diagnostic_results["bulk"],
                        diagnostic_results["layerwise"],
                    ),
                    "bulk_reuse3": issue1_diagnostics.validate_output_consistency(
                        diagnostic_results["bulk"],
                        diagnostic_results["reuse3"],
                    ),
                    "layerwise_reuse3": issue1_diagnostics.validate_output_consistency(
                        diagnostic_results["layerwise"],
                        diagnostic_results["reuse3"],
                    ),
                }
                invalid_diagnostic_outputs = any(
                    not isinstance(value, dict) or value.get("valid") is not True
                    for value in diagnostic_output_consistency.values()
                )
            if invalid_diagnostic_outputs:
                raise RuntimeError(
                    f"confirmed output correctness defect in {test} short diagnostic"
                )
            preliminary = diagnosis[test]
            if test == "test2":
                diagnosis[test] = (
                    issue1_diagnostics.resolve_reuse3_with_layerwise_control(
                        preliminary,
                        diagnostic_results["bulk"],
                        diagnostic_results["layerwise"],
                        diagnostic_results["reuse3"],
                    )
                )
            else:
                diagnosis[test] = issue1_diagnostics.resolve_with_short_diagnostic(
                    preliminary,
                    diagnostic_results["bulk"],
                    diagnostic_results[alternative],
                    alternative_name=alternative,
                )
            short_diagnostics[test] = {
                "spec": spec,
                "preliminary": preliminary,
                "points": diagnostic_results,
                "output_consistency": diagnostic_output_consistency,
                "final": diagnosis[test],
            }
        diagnosis["short_diagnostics"] = short_diagnostics
        runner._write_json(output_dir / "diagnosis.json", diagnosis)
    except BaseException as error:
        run_error = error

    restoration_errors = runner._finalize_run(
        command_runner,
        output_dir,
        environment,
        configmaps,
        run_contract,
        run_error,
    )
    if run_error is not None:
        raise run_error
    if restoration_errors:
        raise RuntimeError("restoration failed: " + "; ".join(restoration_errors))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--image", required=True)
    prepare_parser.add_argument("--manifest-digest", required=True)
    prepare_parser.add_argument("--config-digest", required=True)
    prepare_parser.add_argument(
        "--tokenizer-source",
        type=Path,
        default=Path(
            "/home/llm_cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8"
        ),
    )
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--npu-node", default="m1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command_runner = runner.SubprocessCommandRunner(args.output)
    if args.command == "prepare":
        prepare(
            command_runner,
            args.output,
            args.image,
            args.manifest_digest,
            args.config_digest,
            args.tokenizer_source,
        )
        return 0
    state = handoff.parse_handoff(
        runner.WORKSPACE_ROOT
        / "features/kv-pool-layerwise-reuse/performance-validation-handoff.md"
    )
    run(command_runner, state, args.output, npu_node=args.npu_node)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
