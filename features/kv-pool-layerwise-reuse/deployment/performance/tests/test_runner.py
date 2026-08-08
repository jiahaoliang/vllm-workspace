from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from performance import handoff, runner
from performance.contract import WorkloadPoint


class FakeCommandRunner:
    def __init__(self, fail_step: str | None = None) -> None:
        self.calls: list[runner.Command] = []
        self.fail_step = fail_step

    def run(self, command: runner.Command) -> str:
        self.calls.append(command)
        if command.description == self.fail_step:
            raise RuntimeError(f"failed at {self.fail_step}")
        return ""


def waiting_state(tmp_path: Path) -> handoff.HandoffState:
    return handoff.HandoffState(
        path=tmp_path / "handoff.md",
        digest="waiting",
        status="WAITING_FOR_FUNCTIONAL_VALIDATION",
        ready=False,
        generation=0,
        placeholders_remaining=True,
        authorized_scope=(),
        gates={},
        evidence_fields={},
        source_rows={},
        image_fields={},
        contains_pending=True,
    )


def test_prepare_cannot_mutate_server_or_infer(tmp_path: Path) -> None:
    fake = FakeCommandRunner()

    runner.prepare(fake, tmp_path)

    assert not any(call.mutates_server or call.sends_inference for call in fake.calls)
    command_text = "\n".join(" ".join(call.argv) for call in fake.calls)
    assert "vllm-proxy-service" not in command_text
    for call in fake.calls:
        if call.description in {"apply-client", "wait-client", "client-identity", "bootstrap-client"}:
            assert "liangjiahao" in call.argv


def test_run_checks_handoff_before_any_command(tmp_path: Path) -> None:
    fake = FakeCommandRunner()

    with pytest.raises(handoff.HandoffError, match="not ready"):
        runner.run(fake, waiting_state(tmp_path), tmp_path, topology="dp1")

    assert fake.calls == []


def test_run_rejects_incomplete_ready_handoff_before_any_command(
    tmp_path: Path,
) -> None:
    fake = FakeCommandRunner()
    state = replace(
        waiting_state(tmp_path),
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=1,
        placeholders_remaining=False,
        contains_pending=False,
    )

    with pytest.raises(handoff.HandoffError, match="validation failed"):
        runner.run(fake, state, tmp_path, topology="dp1")

    assert fake.calls == []


def test_failure_capture_precedes_restore(tmp_path: Path) -> None:
    fake = FakeCommandRunner(fail_step="aisbench")
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 1)

    with pytest.raises(RuntimeError, match="failed at aisbench"):
        runner.execute_point(fake, point, tmp_path)

    descriptions = [call.description for call in fake.calls]
    assert descriptions.index("capture-failure") < descriptions.index(
        "restore-pre-run-state"
    )


def test_three_formal_repetitions_have_distinct_raw_directories(
    tmp_path: Path,
) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 4)

    runner.execute_point(fake, point, tmp_path)

    descriptions = [call.description for call in fake.calls]
    assert descriptions.count("reset-master") == 4
    assert len(list(tmp_path.glob("points/**/formal-*/attempt-*/raw"))) == 3


def test_aisbench_manifest_is_cpu_only_on_m1() -> None:
    path = Path(__file__).resolve().parents[1] / "00-aisbench-client.yaml"
    pod = json.loads(path.read_text(encoding="utf-8"))
    container = pod["spec"]["containers"][0]
    resources = container["resources"]

    assert pod["metadata"]["namespace"] == "liangjiahao"
    assert pod["metadata"]["name"] == "layerwise-performance-aisbench"
    assert pod["spec"]["nodeName"] == "m1"
    assert container["image"].endswith("45b2e785-df3f74ed-20260807T100722Z")
    assert pod["metadata"]["annotations"]["performance.vllm.ai/source-image"].endswith(
        "45b2e785-df3f74ed-20260807T100722Z"
    )
    assert pod["metadata"]["annotations"]["performance.vllm.ai/repo-digest"] == (
        "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
    )
    assert resources == {
        "requests": {"cpu": "4", "memory": "16Gi"},
        "limits": {"cpu": "8", "memory": "32Gi"},
    }
    assert "huawei.com/Ascend910" not in json.dumps(resources)
    assert "huawei.com/vnpu-number" not in json.dumps(resources)
