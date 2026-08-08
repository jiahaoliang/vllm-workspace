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


def test_capacity_inventory_covers_all_namespaces(tmp_path: Path) -> None:
    class InventoryRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description.startswith("capture-"):
                return "{}"
            return ""

    fake = InventoryRunner()

    runner._capture_pre_run_state(fake, tmp_path)

    inventory = next(
        call for call in fake.calls if call.description == "capture-pod-inventory"
    )
    assert "--all-namespaces" in inventory.argv
    assert "-n" not in inventory.argv


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


def test_run_resumes_incomplete_existing_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = replace(
        waiting_state(tmp_path),
        digest="ready-digest",
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=1,
        placeholders_remaining=False,
        contains_pending=False,
    )
    (tmp_path / "run-contract.json").write_text(
        json.dumps(
            {
                "topologies": ["dp1"],
                "image_digest": "sha256:image",
                "expected_points": ["dp1-4096-bulk-o1-c1"],
                "formal_repetitions": 3,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "handoff.json").write_text(
        json.dumps({"sha256": state.digest}), encoding="utf-8"
    )
    runner._write_checksums(tmp_path)

    monkeypatch.setattr(runner.handoff, "validate_readiness", lambda selected: [])
    monkeypatch.setattr(
        runner.handoff, "validate_handoff", lambda selected, workspace: []
    )
    monkeypatch.setattr(runner, "_sync_client_tooling", lambda *args: None)
    monkeypatch.setattr(runner, "_capture_identity", lambda *args: None)

    def capture_pre_run_state(command_runner: object, output_dir: Path) -> None:
        del command_runner
        (output_dir / "cluster").mkdir(exist_ok=True)
        (output_dir / "cluster" / "nodes.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "metadata": {"name": "n1"},
                            "status": {
                                "allocatable": {"huawei.com/Ascend910": "8"}
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (output_dir / "cluster" / "pods.json").write_text(
            json.dumps({"items": []}), encoding="utf-8"
        )

    monkeypatch.setattr(runner, "_capture_pre_run_state", capture_pre_run_state)
    monkeypatch.setattr(runner, "build_matrix", lambda topology: ())
    monkeypatch.setattr(
        runner.image,
        "resolve_server_image",
        lambda *args: runner.image.ImageIdentity(
            reference="image",
            digest="sha256:image",
            platform="linux/arm64",
            base_reference="base",
            base_digest="sha256:base",
            patched_file="/source.py",
            patched_file_sha256="source",
            source_labels={},
            mode="ready-image",
        ),
    )
    monkeypatch.setattr(runner, "_restore_pre_run_state", lambda *args: [])

    runner.run(FakeCommandRunner(), state, tmp_path, topology="dp1", resume=True)

    contract = json.loads((tmp_path / "run-contract.json").read_text(encoding="utf-8"))
    assert contract["topologies"] == ["dp1"]
    assert contract["expected_points"] == []


def test_run_resume_rejects_checksum_drift_before_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = replace(
        waiting_state(tmp_path),
        digest="ready-digest",
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=1,
        placeholders_remaining=False,
        contains_pending=False,
    )
    (tmp_path / "run-contract.json").write_text(
        json.dumps(
            {
                "topologies": ["dp1"],
                "image_digest": "sha256:image",
                "expected_points": [],
                "formal_repetitions": 3,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "handoff.json").write_text(
        json.dumps({"sha256": state.digest}), encoding="utf-8"
    )
    artifact = tmp_path / "prior-artifact.json"
    artifact.write_text("{}\n", encoding="utf-8")
    runner._write_checksums(tmp_path)
    artifact.write_text('{"changed": true}\n', encoding="utf-8")
    monkeypatch.setattr(runner.handoff, "validate_readiness", lambda selected: [])
    monkeypatch.setattr(
        runner.handoff, "validate_handoff", lambda selected, workspace: []
    )
    fake = FakeCommandRunner()

    with pytest.raises(RuntimeError, match="resume checksum validation failed"):
        runner.run(fake, state, tmp_path, topology="dp1", resume=True)

    assert fake.calls == []


def test_point_failure_defers_restore_to_top_level_runner(tmp_path: Path) -> None:
    fake = FakeCommandRunner(fail_step="aisbench")
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 1)

    with pytest.raises(RuntimeError, match="failed at aisbench"):
        runner.execute_point(fake, point, tmp_path)

    descriptions = [call.description for call in fake.calls]
    assert descriptions[-1] == "capture-failure"
    assert "restore-pre-run-state" not in descriptions


def test_master_empty_probe_retries_service_startup() -> None:
    script = runner._master_empty_script()

    assert "for attempt in range(60)" in script
    assert "time.sleep(1)" in script


def test_sync_client_tooling_prepares_chroot_shared_memory(tmp_path: Path) -> None:
    class ClientRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description == "verify-client-rootfs-marker":
                return (
                    "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b\n"
                )
            if command.description == "verify-client-tokenizer-link":
                return "/client-tools/tokenizer\n"
            return ""

    fake = ClientRunner()

    runner._sync_client_tooling(fake, tmp_path)

    shared_memory = next(
        call for call in fake.calls if call.description == "prepare-client-shared-memory"
    )
    assert "/performance-workspace/rootfs/dev/shm" in shared_memory.argv
    assert "1777" in shared_memory.argv
    procfs = next(
        call for call in fake.calls if call.description == "prepare-client-procfs"
    )
    assert "/performance-workspace/rootfs/proc" in procfs.argv
    assert "/proc/meminfo" in procfs.argv


def test_three_formal_repetitions_have_distinct_raw_directories(
    tmp_path: Path,
) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 4)

    runner.execute_point(fake, point, tmp_path)

    descriptions = [call.description for call in fake.calls]
    assert descriptions.count("remove-all-keys") == 4
    assert "reset-master" not in descriptions
    assert len(list(tmp_path.glob("points/**/formal-*/attempt-*/raw"))) == 3


def test_execute_point_reuses_valid_prior_phases(tmp_path: Path) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 1)
    point_root = tmp_path / "points" / "dp1-4096-bulk-o1-c1"
    summary = {
        "valid": True,
        "image_digest": "sha256:image",
        "errors": [],
        "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
    }
    for phase in ("warmup", "formal-1", "formal-2", "formal-3"):
        raw = point_root / phase / "attempt-1" / "raw"
        raw.mkdir(parents=True)
        (raw / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    summaries = runner.execute_point(
        fake,
        point,
        tmp_path,
        runner.RunEnvironment(image_digest="sha256:image"),
    )

    assert len(summaries) == 3
    assert fake.calls == []
    assert not list(point_root.glob("*/attempt-2"))


def test_execute_point_resumes_after_prior_stable_duration_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 4)
    point_root = tmp_path / "points" / "dp1-4096-bulk-o1-c4"
    for attempt, request_count in ((1, 8), (2, 16)):
        raw = point_root / "warmup" / f"attempt-{attempt}" / "raw"
        raw.mkdir(parents=True)
        (raw / "summary.json").write_text(
            json.dumps(
                {
                    "valid": False,
                    "image_digest": "sha256:image",
                    "request_count": request_count,
                    "errors": ["stable benchmark duration is insufficient"],
                    "metrics": {},
                }
            ),
            encoding="utf-8",
        )
    request_counts: list[int] = []

    def summarize(
        raw: Path,
        selected: WorkloadPoint,
        request_count: int,
        image_digest: str,
    ) -> dict[str, object]:
        del raw, selected
        request_counts.append(request_count)
        return {
            "valid": True,
            "image_digest": image_digest,
            "errors": [],
            "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
        }

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", summarize)

    runner.execute_point(
        fake,
        point,
        tmp_path,
        runner.RunEnvironment(image_digest="sha256:image"),
    )

    assert request_counts == [32, 32, 32, 32]
    assert (point_root / "warmup" / "attempt-3").is_dir()


def test_insufficient_stable_duration_doubles_until_formal_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 1)
    request_counts: list[int] = []

    def summarize(
        raw: Path,
        selected: WorkloadPoint,
        request_count: int,
        image_digest: str,
    ) -> dict[str, object]:
        del raw, selected, image_digest
        request_counts.append(request_count)
        if len(request_counts) <= 2:
            return {
                "valid": False,
                "errors": ["stable benchmark duration is insufficient"],
                "metrics": {},
            }
        return {
            "valid": True,
            "errors": [],
            "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
        }

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", summarize)

    runner.execute_point(
        fake,
        point,
        tmp_path,
        runner.RunEnvironment(image_digest="sha256:image"),
    )

    assert request_counts == [8, 16, 32, 32, 32, 32]
    assert (
        tmp_path / "points" / "dp1-4096-bulk-o1-c1" / "warmup" / "attempt-3"
    ).is_dir()


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
    assert "-m" in aisbench.argv
    assert "perf" in aisbench.argv
    assert "--num-warmups" in aisbench.argv
    assert "0" in aisbench.argv
    assert "--pressure" not in aisbench.argv


def test_variant_rollout_resets_master_after_all_old_pods_are_deleted(
    tmp_path: Path,
) -> None:
    class PodRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description == "capture-old-prefill-pods":
                return "pod/prefill-old\n"
            if command.description == "capture-old-decode-pods":
                return "pod/decode-old\n"
            return ""

    fake = PodRunner()
    paths = tuple(tmp_path / f"resource-{index}.json" for index in range(3))
    point = WorkloadPoint("dp1", 4096, 1, "bulk", 1)

    runner._apply_variant_block(
        fake,
        paths,
        point,
        runner.RunEnvironment(),
        tmp_path,
    )

    descriptions = [call.description for call in fake.calls]
    reset = descriptions.index("reset-master")
    assert descriptions.index("wait-old-prefill-deleted") < reset
    assert descriptions.index("wait-old-decode-deleted") < reset
    assert reset < descriptions.index("start-prefill")
    assert reset < descriptions.index("start-decode")
    assert descriptions[reset : reset + 3] == [
        "reset-master",
        "wait-master",
        "assert-master-empty",
    ]


def test_variant_canary_checks_live_master_before_inference(tmp_path: Path) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 4096, 1, "layerwise", 1)

    runner._run_variant_canary(
        fake,
        point,
        runner.RunEnvironment(),
        tmp_path,
    )

    assert [call.description for call in fake.calls] == [
        "assert-master-empty",
        "assert-engine-reconnect",
        "correctness-canary",
    ]
    assert fake.calls[-1].sends_inference


def test_variant_canary_captures_diagnostics_before_restore(tmp_path: Path) -> None:
    fake = FakeCommandRunner(fail_step="correctness-canary")
    point = WorkloadPoint("dp1", 4096, 1, "layerwise", 1)

    with pytest.raises(RuntimeError, match="failed at correctness-canary"):
        runner._run_variant_canary(
            fake,
            point,
            runner.RunEnvironment(),
            tmp_path,
        )

    descriptions = [call.description for call in fake.calls]
    canary_index = descriptions.index("correctness-canary")
    assert descriptions[canary_index + 1 :] == [
        "mooncake-metrics",
        "prefill-log",
        "decode-log",
        "prefill-npu",
        "decode-npu",
        "engine-pods",
    ]
    raw = next(tmp_path.glob("canary-failures/**/attempt-1/raw"))
    assert (raw / "vllm-prefill.log").is_file()
    assert (raw / "vllm-decode.log").is_file()
    assert (raw / "mooncake.metrics").is_file()


def test_attempt_cleanup_removes_keys_without_restarting_master() -> None:
    point = WorkloadPoint("dp1", 4096, 1, "layerwise", 1)

    commands = runner._attempt_commands(
        point,
        "warmup",
        8,
        "remote-attempt",
        runner.RunEnvironment(),
    )

    descriptions = [command.description for command in commands]
    assert descriptions[:3] == [
        "remove-all-keys",
        "assert-master-empty",
        "assert-engine-reconnect",
    ]
    assert "reset-master" not in descriptions
    assert "wait-master" not in descriptions
    remove_all = commands[0]
    assert remove_all.mutates_server
    assert "api/v1/remove_all?force=true" in " ".join(remove_all.argv)


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
