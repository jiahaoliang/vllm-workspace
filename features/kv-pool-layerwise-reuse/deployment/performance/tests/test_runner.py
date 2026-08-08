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

    bootstrap = next(call for call in fake.calls if call.description == "bootstrap-client")
    bootstrap_text = " ".join(bootstrap.argv)
    assert "/usr/local/python3.12.13/bin/python3.12" in bootstrap_text
    assert "--index-url https://pypi.org/simple" in bootstrap_text
    assert "venv --system-site-packages" in bootstrap_text
    assert "--no-deps -e" in bootstrap_text
    assert "requirements/runtime.txt" in bootstrap_text
    assert "requirements/api.txt" in bootstrap_text
    assert "TORCH_DEVICE_BACKEND_AUTOLOAD=0" in bootstrap_text
    assert any(call.description == "configure-chroot-dns" for call in fake.calls)
    devices = next(
        call for call in fake.calls if call.description == "configure-chroot-devices"
    )
    devices_text = " ".join(devices.argv)
    assert "dev/null" in devices_text
    assert "dev/urandom" in devices_text
    tokenizer_link = next(
        call for call in fake.calls if call.description == "link-tokenizer-model-path"
    )
    assert "/client-tools/tokenizer" in " ".join(tokenizer_link.argv)


def test_run_checks_handoff_before_any_command(tmp_path: Path) -> None:
    fake = FakeCommandRunner()

    with pytest.raises(handoff.HandoffError, match="not ready"):
        runner.run(fake, waiting_state(tmp_path), tmp_path, topology="dp1")

    assert fake.calls == []


def test_checksum_manifest_excludes_itself(tmp_path: Path) -> None:
    (tmp_path / "artifact.txt").write_text("value\n", encoding="utf-8")

    runner._write_checksums(tmp_path)

    lines = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert lines[0].endswith("  artifact.txt")


def test_subprocess_runner_resumes_command_numbering(tmp_path: Path) -> None:
    (tmp_path / "commands" / "0007-prior").mkdir(parents=True)

    command_runner = runner.SubprocessCommandRunner(tmp_path)

    assert command_runner.command_index == 7


def test_physical_capacity_ignores_vnpu_and_replaced_engines() -> None:
    nodes = {
        "items": [
            {
                "metadata": {"name": "n1"},
                "status": {
                    "allocatable": {
                        "huawei.com/Ascend910": "8",
                        "huawei.com/vnpu-number": "64",
                    }
                },
            }
        ]
    }
    pods = {
        "items": [
            {
                "metadata": {"labels": {"app": "prefill"}},
                "spec": {
                    "nodeName": "n1",
                    "containers": [
                        {
                            "resources": {
                                "requests": {"huawei.com/Ascend910": "4"}
                            }
                        }
                    ],
                },
                "status": {"phase": "Running"},
            },
            {
                "metadata": {"labels": {"app": "other"}},
                "spec": {
                    "nodeName": "n1",
                    "containers": [
                        {
                            "resources": {
                                "requests": {
                                    "huawei.com/Ascend910": "1",
                                    "huawei.com/vnpu-number": "63",
                                }
                            }
                        }
                    ],
                },
                "status": {"phase": "Running"},
            },
        ]
    }

    assert runner._available_test_npus(nodes, pods) == 7


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


def test_point_lifecycle_uses_real_namespaced_aisbench_commands(tmp_path: Path) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp2", 16384, 1, "reuse3", 32)

    runner.execute_point(fake, point, tmp_path)

    assert all(
        call.argv[0] == "kubectl"
        or (call.argv[0] == "bash" and call.description == "aisbench")
        for call in fake.calls
    )
    assert all("liangjiahao" in " ".join(call.argv) for call in fake.calls)
    assert not any("benchmark" in call.argv for call in fake.calls)
    aisbench = next(call for call in fake.calls if call.description == "aisbench")
    assert "chroot" in aisbench.argv
    assert "/performance-workspace/rootfs" in aisbench.argv
    assert "prefill-npu-timeseries.log" in aisbench.argv[2]
    assert "mooncake-timeseries.metrics" in aisbench.argv[2]
    config = next(
        call for call in fake.calls if call.description == "render-aisbench-config"
    )
    assert "performance.fixtures" in config.argv
    assert "--request-count" in config.argv


def test_aisbench_manifest_is_cpu_only_on_m1() -> None:
    path = Path(__file__).resolve().parents[1] / "00-aisbench-client.yaml"
    pod = json.loads(path.read_text(encoding="utf-8"))
    container = pod["spec"]["containers"][0]
    resources = container["resources"]

    assert pod["metadata"]["namespace"] == "liangjiahao"
    assert pod["metadata"]["name"] == "layerwise-performance-aisbench"
    assert pod["spec"]["nodeName"] == "m1"
    assert container["image"] == "docker.io/library/vllm-ascend:latest"
    assert pod["metadata"]["annotations"]["performance.vllm.ai/source-image"].endswith(
        "45b2e785-df3f74ed-20260807T100722Z"
    )
    assert pod["metadata"]["annotations"]["performance.vllm.ai/repo-digest"] == (
        "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
    )
    assert pod["metadata"]["annotations"]["performance.vllm.ai/config-digest"] == (
        "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
    )
    assert (
        pod["metadata"]["annotations"]["performance.vllm.ai/execution-mode"]
        == "exact-rootfs-chroot"
    )
    assert resources == {
        "requests": {"cpu": "4", "memory": "16Gi"},
        "limits": {"cpu": "8", "memory": "32Gi"},
    }
    assert "huawei.com/Ascend910" not in json.dumps(resources)
    assert "huawei.com/vnpu-number" not in json.dumps(resources)
