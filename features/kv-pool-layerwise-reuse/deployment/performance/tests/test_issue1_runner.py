from __future__ import annotations

from pathlib import Path

import pytest
from performance import handoff, issue1_runner, runner
from performance.issue1_contract import TEST1_POINTS
from performance.issue1_contract import test2_points as issue1_test2_points


def _state(scope: str) -> handoff.HandoffState:
    return handoff.HandoffState(
        path=Path("handoff.md"),
        digest="digest",
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=17,
        placeholders_remaining=False,
        authorized_scope=tuple(scope.splitlines()),
        gates={},
        evidence_fields={},
        source_rows={},
        image_fields={},
        contains_pending=False,
    )


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[runner.Command] = []

    def run(self, command: runner.Command) -> str:
        self.calls.append(command)
        return ""


def test_current_generation16_scope_cannot_authorize_issue1() -> None:
    state = _state("backend=mooncake\nconcurrency=8")

    errors = issue1_runner.validate_authorization(state)

    assert errors
    assert any("input=32000" in error for error in errors)
    assert any("concurrency=40" in error for error in errors)


def test_current_generation16_run_fails_before_any_command(tmp_path: Path) -> None:
    command_runner = RecordingRunner()
    state = _state("backend=mooncake\nconcurrency=8")

    with pytest.raises(handoff.HandoffError, match="handoff is not ready"):
        issue1_runner.run(
            command_runner,
            state,
            tmp_path / "run",
            npu_node="m1",
        )

    assert command_runner.calls == []


def test_exact_issue1_scope_is_authorized() -> None:
    state = _state("\n".join(issue1_runner.REQUIRED_AUTHORIZATION))

    assert issue1_runner.validate_authorization(state) == []


def test_fixture_commands_freeze_shared_prefix_and_counts() -> None:
    test1 = issue1_runner._generate_fixture_command(
        TEST1_POINTS[0], runner.RunEnvironment()
    )
    test2 = issue1_runner._generate_fixture_command(
        issue1_test2_points(40)[0], runner.RunEnvironment()
    )

    assert "--shared-prefix" in test1.argv
    assert test1.argv[test1.argv.index("--seed-request-count") + 1] == "1"
    assert test1.argv[test1.argv.index("--formal-count") + 1] == "125"
    assert test1.argv[test1.argv.index("--admission-count") + 1] == "8"
    assert test2.argv[test2.argv.index("--formal-count") + 1] == "100"
    assert test2.argv[test2.argv.index("--admission-count") + 1] == "40"


def test_sampler_collects_server_metrics_every_second() -> None:
    command = issue1_runner._sampled_command(("true",), runner.RunEnvironment())
    script = command.argv[2]

    assert "127.0.0.1:8100/metrics" in script
    assert "127.0.0.1:8200/metrics" in script
    assert "prefill-prometheus-timeseries.metrics" in script
    assert "decode-prometheus-timeseries.metrics" in script
    assert "sleep 1" in script
    assert "-n liangjiahao" in script


def test_perf_metrics_phase_boundaries_flush_two_intervals() -> None:
    before = issue1_runner._perf_metrics_flush_command("before")
    after = issue1_runner._perf_metrics_flush_command("after")

    assert issue1_runner.PERF_METRICS_FLUSH_SECONDS == 2
    assert before.argv == ("sleep", "2")
    assert before.description == "flush-perf-metrics-before"
    assert after.description == "flush-perf-metrics-after"


def test_issue1_seed_phases_clear_mooncake_but_measured_phases_do_not() -> None:
    point = issue1_runner._workload(TEST1_POINTS[0])
    environment = runner.RunEnvironment()

    lifecycle_by_phase = {
        phase: [
            command.description
            for command in runner._attempt_commands(
                point,
                phase,
                1,
                f"issue1/{phase}/token",
                environment,
                fixture_concurrency=8,
            )
        ]
        for phase in ("warmup", "seed", "admission", "formal-1")
    }

    assert "remove-all-keys" in lifecycle_by_phase["warmup"]
    assert "remove-all-keys" in lifecycle_by_phase["seed"]
    assert "remove-all-keys" not in lifecycle_by_phase["admission"]
    assert "remove-all-keys" not in lifecycle_by_phase["formal-1"]


def test_workload_conversion_preserves_four_point_contract() -> None:
    points = issue1_runner._all_points()

    assert [issue1_runner._workload(point).output_tokens for point in points] == [
        128,
        128,
        1,
        1,
    ]
    assert [point.variant for point in points] == [
        "bulk",
        "layerwise",
        "bulk",
        "reuse3",
    ]


def test_test2_short_diagnostic_adds_layerwise_control_only() -> None:
    formal = issue1_test2_points(40)

    diagnostic = issue1_runner._diagnostic_points("test2", formal)

    assert [point.variant for point in formal] == ["bulk", "reuse3"]
    assert [point.variant for point in diagnostic] == [
        "bulk",
        "layerwise",
        "reuse3",
    ]
    assert all(point.formal_requests == 100 for point in diagnostic)
    assert [
        issue1_runner._expected_contexts(point, 39 * 32000)
        for point in diagnostic
    ] == [2, 2, 40]
    assert [
        issue1_runner._requires_capacity_waiting(point) for point in diagnostic
    ] == [True, True, False]


def test_short_diagnostic_runs_exactly_one_wave_after_warmup_and_seed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    phases: list[tuple[str, int, bool]] = []

    def fake_attempt(
        command_runner: object,
        issue_point: object,
        attempt_point: object,
        phase: str,
        request_count: int,
        point_root: Path,
        environment: object,
        *,
        capture_server_evidence: bool,
    ) -> dict[str, object]:
        phases.append((phase, request_count, capture_server_evidence))
        return {
            "phase": phase,
            "attempt": str(point_root / phase / "attempt-1"),
        }

    expected_result = {"request_count": 8, "request_throughput": 1.0}
    monkeypatch.setattr(issue1_runner, "_attempt", fake_attempt)
    monkeypatch.setattr(
        issue1_runner,
        "_measured_result",
        lambda *args, **kwargs: expected_result,
    )
    monkeypatch.setattr(
        issue1_runner.issue1_diagnostics,
        "validate_observability",
        lambda attempt: {"valid": True, "errors": []},
    )

    result = issue1_runner.execute_short_diagnostic(
        RecordingRunner(),
        TEST1_POINTS[0],
        tmp_path,
        runner.RunEnvironment(),
        bulk_capacity_tokens=64000,
    )

    assert result is expected_result
    assert phases == [
        ("warmup", 8, False),
        ("seed", 1, False),
        ("admission", 8, True),
    ]
    assert not (tmp_path / "short-diagnostics/test1/bulk/formal-1").exists()
