from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from performance import handoff, image, runner, runtime
from performance.contract import FORMAL_REQUEST_COUNT, SEED_TOKENS, WorkloadPoint


class FakeCommandRunner:
    def __init__(self, fail_step: str | None = None) -> None:
        self.calls: list[runner.Command] = []
        self.fail_step = fail_step

    def run(self, command: runner.Command) -> str:
        self.calls.append(command)
        if command.description == self.fail_step:
            raise RuntimeError(f"failed at {self.fail_step}")
        if command.description == "inspect-client-image":
            return json.dumps(
                [
                    {
                        "Id": "sha256:config",
                        "RepoDigests": ["candidate@sha256:manifest"],
                        "Architecture": "arm64",
                        "Os": "linux",
                    }
                ]
            )
        if command.description == "prefill-log-offset":
            return "0\n"
        if command.description == "formal-prefill-hit-log":
            return "".join(
                f"Reqid: request-{index}, Total tokens 16384, "
                f"kvpool hit tokens: {SEED_TOKENS}, need to load: {SEED_TOKENS}\n"
                for index in range(FORMAL_REQUEST_COUNT)
            )
        return ""


def tokenizer_source(tmp_path: Path) -> Path:
    source = tmp_path / "tokenizer"
    source.mkdir()
    for name in runner.TOKENIZER_FILES:
        (source / name).write_text(name, encoding="utf-8")
    return source


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

    runner.prepare(
        fake,
        tmp_path,
        "candidate",
        "sha256:manifest",
        "sha256:config",
        tokenizer_source(tmp_path),
    )

    assert not any(call.mutates_server or call.sends_inference for call in fake.calls)
    command_text = "\n".join(" ".join(call.argv) for call in fake.calls)
    assert "vllm-proxy-service" not in command_text
    for call in fake.calls:
        if call.description in {
            "apply-client",
            "wait-client",
            "client-identity",
            "bootstrap-client",
        }:
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
    devices = next(call for call in fake.calls if call.description == "configure-chroot-devices")
    devices_text = " ".join(devices.argv)
    assert "dev/null" in devices_text
    assert "dev/urandom" in devices_text
    tokenizer_link = next(call for call in fake.calls if call.description == "link-tokenizer-model-path")
    assert "/client-tools/tokenizer" in " ".join(tokenizer_link.argv)
    fixture_generator = next(call for call in fake.calls if call.description == "generate-fixtures")
    assert (
        fixture_generator.argv[fixture_generator.argv.index("--concurrency") + 1] == "8"
    )
    assert fake.calls[0].description == "inspect-client-image"
    rootfs = next(
        call for call in fake.calls if call.description == "sync-exact-client-rootfs"
    )
    assert "mkdir -p /performance-workspace/rootfs" in " ".join(rootfs.argv)
    tokenizer = next(
        call for call in fake.calls if call.description == "copy-tokenizer"
    )
    tokenizer_text = " ".join(tokenizer.argv)
    assert "prefill-engine-deployment" not in tokenizer_text
    assert str((tmp_path / "tokenizer").resolve()) in tokenizer_text
    manifest = json.loads((tmp_path / "client-pod-manifest.json").read_text())
    assert manifest["spec"]["containers"][0]["image"] == "candidate"


def test_prepare_rejects_candidate_identity_before_cluster_commands(
    tmp_path: Path,
) -> None:
    fake = FakeCommandRunner()

    with pytest.raises(ValueError, match="manifest digest mismatch"):
        runner.prepare(
            fake,
            tmp_path,
            "candidate",
            "sha256:wrong",
            "sha256:config",
            tokenizer_source(tmp_path),
        )

    assert [call.description for call in fake.calls] == ["inspect-client-image"]


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


def test_subprocess_runner_references_owned_stdout_artifact(tmp_path: Path) -> None:
    command_runner = runner.SubprocessCommandRunner(tmp_path)

    output = command_runner.run(
        runner.Command(
            ("sh", "-c", "printf payload"),
            description="capture",
            stdout_artifact="artifacts/output.txt",
        )
    )

    command_dir = next((tmp_path / "commands").iterdir())
    result = json.loads((command_dir / "result.json").read_text())
    assert output == "payload"
    assert result["stdout_artifact"] == "artifacts/output.txt"
    assert not (command_dir / "stdout.txt").exists()


def test_sampler_uses_ten_second_interval() -> None:
    command = runner._sampled_aisbench_command(("true",), runner.RunEnvironment())
    sleep_lines = [line.strip() for line in command.argv[2].splitlines() if line.strip().startswith("sleep ")]

    assert sleep_lines == ["sleep 10"] * 4
    assert "'from urllib.request import urlopen; ''print(urlopen(" in command.argv[2]


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
                    "containers": [{"resources": {"requests": {"huawei.com/Ascend910": "4"}}}],
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


def test_physical_capacity_accepts_explicit_node_name() -> None:
    nodes = {
        "items": [
            {
                "metadata": {"name": "custom-node"},
                "status": {
                    "allocatable": {"huawei.com/Ascend910": "4"},
                },
            }
        ]
    }
    pods = {
        "items": [
            {
                "metadata": {"labels": {"app": "other"}},
                "spec": {
                    "nodeName": "custom-node",
                    "containers": [
                        {
                            "resources": {
                                "requests": {"huawei.com/Ascend910": "1"}
                            }
                        }
                    ],
                },
                "status": {"phase": "Running"},
            }
        ]
    }

    assert runner._available_test_npus(nodes, pods, "custom-node") == 3


def test_capacity_inventory_covers_all_namespaces(tmp_path: Path) -> None:
    class InventoryRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description.startswith("capture-"):
                return "{}"
            return ""

    fake = InventoryRunner()

    runner._capture_pre_run_state(fake, tmp_path)

    inventory = next(call for call in fake.calls if call.description == "capture-pod-inventory")
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


def test_rapid_run_rejects_resume_before_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = replace(
        waiting_state(tmp_path),
        digest="ready-digest",
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=1,
        placeholders_remaining=False,
        contains_pending=False,
    )
    monkeypatch.setattr(runner.handoff, "validate_readiness", lambda selected: [])
    monkeypatch.setattr(runner.handoff, "validate_handoff", lambda selected, workspace: [])
    fake = FakeCommandRunner()

    with pytest.raises(ValueError, match="rapid run does not support resume"):
        runner.run(fake, state, tmp_path, topology="dp1", resume=True)

    assert fake.calls == []


def test_rapid_run_groups_exact_points_into_three_variant_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = replace(
        waiting_state(tmp_path),
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=5,
        placeholders_remaining=False,
        image_fields={"Derived config digest": "sha256:candidate"},
        contains_pending=False,
    )
    events: list[str] = []
    executed: list[str] = []
    monkeypatch.setattr(runner.handoff, "validate_readiness", lambda selected: [])
    monkeypatch.setattr(runner.handoff, "validate_handoff", lambda selected, workspace: [])
    monkeypatch.setattr(
        runner,
        "_sync_client_tooling",
        lambda command_runner, output, config_digest: events.append(
            f"sync:{config_digest}"
        ),
    )
    monkeypatch.setattr(
        runner,
        "_archive_shared_fixtures",
        lambda command_runner, output: events.append("fixtures"),
    )
    monkeypatch.setattr(runner, "_capture_identity", lambda *args: None)

    def capture_pre_run(command_runner: object, output: Path) -> runtime.RuntimeInputs:
        del command_runner
        cluster = output / "cluster"
        cluster.mkdir(parents=True)
        (cluster / "nodes.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "metadata": {"name": "m1"},
                            "status": {"allocatable": {"huawei.com/Ascend910": "8"}},
                        }
                    ]
                }
            )
        )
        (cluster / "pods.json").write_text('{"items": []}')
        return runtime.RuntimeInputs({}, {}, {})

    monkeypatch.setattr(runner, "_capture_pre_run_state", capture_pre_run)
    monkeypatch.setattr(
        runner.image,
        "resolve_server_image",
        lambda *args: image.ImageIdentity(
            "image:rapid",
            "sha256:image",
            "linux/arm64",
            "image:base",
            "sha256:base",
            "/file.py",
            "a" * 64,
            {},
            "ready-image",
        ),
    )

    def write_rendered(
        inputs: runtime.RuntimeInputs,
        point: WorkloadPoint,
        reference: str,
        output: Path,
        node_name: str = "n1",
    ) -> tuple[runtime.RenderedResources, tuple[Path, Path, Path]]:
        del inputs, reference, output
        events.append(f"render:{point.variant}:{node_name}")
        resources = runtime.RenderedResources({}, {}, {"metadata": {"name": f"rapid-{point.variant}"}}, 2, 2)
        return resources, (Path("prefill"), Path("decode"), Path("config"))

    monkeypatch.setattr(runner, "_write_rendered_block", write_rendered)
    monkeypatch.setattr(runner.runtime, "validate_unique_difference", lambda values: [])
    monkeypatch.setattr(
        runner,
        "_apply_variant_block",
        lambda command_runner, paths, point, environment, output: events.append(f"start:{point.variant}"),
    )
    monkeypatch.setattr(runner, "_run_variant_canary", lambda *args: None)
    monkeypatch.setattr(
        runner,
        "execute_point",
        lambda command_runner, point, output, environment: executed.append(runner._point_id(point)),
    )
    monkeypatch.setattr(
        runner,
        "_capture_variant_diagnostics",
        lambda command_runner, variant, environment, output: events.append(f"logs:{variant}"),
    )
    stop_count = 0

    def stop(*args: object) -> list[str]:
        nonlocal stop_count
        stop_count += 1
        return []

    monkeypatch.setattr(runner, "_stop_engines", stop)
    monkeypatch.setattr(runner, "_restore_pre_run_state", lambda *args: [])
    monkeypatch.setattr(runner, "_write_checksums", lambda output: None)

    runner.run(
        FakeCommandRunner(),
        state,
        tmp_path / "run",
        topology="dp1",
        npu_node="m1",
    )

    assert events == [
        "sync:sha256:candidate",
        "fixtures",
        "render:bulk:m1",
        "render:layerwise:m1",
        "render:reuse3:m1",
        "start:bulk",
        "logs:bulk",
        "start:layerwise",
        "logs:layerwise",
        "start:reuse3",
        "logs:reuse3",
    ]
    assert executed == [
        "dp1-16384-bulk-o1-c8",
        "dp1-16384-layerwise-o1-c8",
        "dp1-16384-reuse3-o1-c8",
    ]
    assert stop_count == 3
    run_contract = json.loads((tmp_path / "run" / "run-contract.json").read_text())
    assert run_contract["npu_node"] == "m1"


def test_three_points_expand_to_exactly_nine_aisbench_attempts() -> None:
    phases: list[str] = []

    for point in runner.build_matrix("dp1"):
        warmup_count, formal_count, repetitions = runner.sample_counts(
            point.concurrency
        )
        assert repetitions == 1
        for phase, count in (
            ("warmup", warmup_count),
            ("seed", formal_count),
            ("formal-1", formal_count),
        ):
            commands = runner._attempt_commands(
                point,
                phase,
                count,
                f"{runner._point_id(point)}/{phase}/token",
                runner.RunEnvironment(),
            )
            assert sum(command.sends_inference for command in commands) == 1
            assert [command.description for command in commands].count("aisbench") == 1
            config = next(
                command
                for command in commands
                if command.description == "render-aisbench-config"
            )
            assert "--phase" in config.argv
            assert "--fixture-manifest" in config.argv
            phases.append(f"{runner._point_id(point)}:{phase}")

    assert phases == [
        "dp1-16384-bulk-o1-c8:warmup",
        "dp1-16384-bulk-o1-c8:seed",
        "dp1-16384-bulk-o1-c8:formal-1",
        "dp1-16384-layerwise-o1-c8:warmup",
        "dp1-16384-layerwise-o1-c8:seed",
        "dp1-16384-layerwise-o1-c8:formal-1",
        "dp1-16384-reuse3-o1-c8:warmup",
        "dp1-16384-reuse3-o1-c8:seed",
        "dp1-16384-reuse3-o1-c8:formal-1",
    ]


def test_run_cli_accepts_explicit_npu_node() -> None:
    args = runner._parser().parse_args(
        ["run", "--output", "/tmp/run", "--topology", "dp1", "--npu-node", "m1"]
    )

    assert args.npu_node == "m1"


def test_point_failure_defers_restore_to_top_level_runner(tmp_path: Path) -> None:
    fake = FakeCommandRunner(fail_step="aisbench")
    point = WorkloadPoint("dp1", 16384, 1, "bulk", 8)

    with pytest.raises(RuntimeError, match="failed at aisbench"):
        runner.execute_point(fake, point, tmp_path)

    descriptions = [call.description for call in fake.calls]
    assert descriptions[-1] == "capture-failure"
    assert "restore-pre-run-state" not in descriptions


def test_failed_run_finalization_preserves_serving_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    restored = False

    def restore(*_: object) -> list[str]:
        nonlocal restored
        restored = True
        return []

    monkeypatch.setattr(runner, "_restore_pre_run_state", restore)

    errors = runner._finalize_run(
        FakeCommandRunner(),
        tmp_path,
        runner.RunEnvironment(),
        {"performance-config"},
        {"expected_points": []},
        RuntimeError("startup failed"),
    )

    assert errors == []
    assert restored is False
    restoration = json.loads((tmp_path / "restoration.json").read_text())
    assert restoration["failed_environment_preserved"] is True
    assert restoration["completed"] is False
    assert not (tmp_path / "run-contract.json").exists()
    assert (tmp_path / "SHA256SUMS").is_file()


def test_master_empty_probe_retries_service_startup() -> None:
    script = runner._master_empty_script()

    assert "for attempt in range(60)" in script
    assert "time.sleep(1)" in script


def test_sync_client_tooling_prepares_chroot_shared_memory(tmp_path: Path) -> None:
    class ClientRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description == "verify-client-rootfs-marker":
                return "sha256:candidate\n"
            if command.description == "verify-client-tokenizer-link":
                return "/client-tools/tokenizer\n"
            return ""

    fake = ClientRunner()

    runner._sync_client_tooling(fake, tmp_path, "sha256:candidate")

    shared_memory = next(call for call in fake.calls if call.description == "prepare-client-shared-memory")
    assert "/performance-workspace/rootfs/dev/shm" in shared_memory.argv
    assert "1777" in shared_memory.argv
    procfs = next(call for call in fake.calls if call.description == "prepare-client-procfs")
    assert "/performance-workspace/rootfs/proc" in procfs.argv
    assert "/proc/meminfo" in procfs.argv


def test_archive_shared_fixtures_copies_high_hit_evidence(tmp_path: Path) -> None:
    fake = FakeCommandRunner()

    runner._archive_shared_fixtures(fake, tmp_path)

    assert [call.description for call in fake.calls] == [
        "archive-fixture-manifest",
        "archive-fixture-metadata",
        "archive-fixture-SHA256SUMS",
        "archive-fixture-warmup",
        "archive-fixture-seed",
        "archive-fixture-formal-1",
    ]
    assert [Path(call.argv[-1]).name for call in fake.calls] == [
        "manifest.json",
        "metadata.jsonl",
        "SHA256SUMS",
        "warmup.jsonl",
        "seed.jsonl",
        "formal-1.jsonl",
    ]
    assert all("-n" in call.argv and "liangjiahao" in call.argv for call in fake.calls)


def test_execute_point_runs_warmup_seed_and_one_formal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 16384, 1, "bulk", 8)

    def summarize(
        raw: Path,
        selected: WorkloadPoint,
        request_count: int,
        image_digest: str,
    ) -> dict[str, object]:
        del raw, selected, request_count
        return {
            "valid": True,
            "image_digest": image_digest,
            "errors": [],
            "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
        }

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", summarize)

    summaries = runner.execute_point(
        fake,
        point,
        tmp_path,
        runner.RunEnvironment(image_digest="sha256:image"),
    )

    descriptions = [call.description for call in fake.calls]
    assert len(summaries) == 1
    assert descriptions.count("remove-all-keys") == 2
    assert descriptions.count("mooncake-metrics") == 3
    assert descriptions.index("remove-all-keys", descriptions.index("aisbench") + 1) < descriptions.index(
        "aisbench", descriptions.index("aisbench") + 1
    )
    formal_index = len(descriptions) - 1 - descriptions[::-1].index("aisbench")
    seed_index = descriptions.index("aisbench", descriptions.index("aisbench") + 1)
    assert "remove-all-keys" not in descriptions[seed_index + 1 : formal_index]
    assert descriptions.count("prefill-log-offset") == 1
    assert descriptions.count("formal-prefill-hit-log") == 1
    assert "prefill-log" not in descriptions
    assert "decode-log" not in descriptions
    assert "reset-master" not in descriptions
    assert len(list(tmp_path.glob("points/**/warmup/attempt-1/raw"))) == 1
    assert len(list(tmp_path.glob("points/**/seed/attempt-1/raw"))) == 1
    assert len(list(tmp_path.glob("points/**/formal-1/attempt-1/raw"))) == 1
    assert not list(tmp_path.glob("points/**/formal-2"))


def test_invalid_formal_attempt_is_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 16384, 1, "bulk", 8)
    request_counts: list[int] = []

    def summarize(
        raw: Path,
        selected: WorkloadPoint,
        request_count: int,
        image_digest: str,
    ) -> dict[str, object]:
        del raw, selected
        request_counts.append(request_count)
        if len(request_counts) < 3:
            return {
                "valid": True,
                "image_digest": image_digest,
                "errors": [],
                "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
            }
        return {
            "valid": False,
            "image_digest": image_digest,
            "errors": ["bad response"],
            "metrics": {},
        }

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", summarize)

    with pytest.raises(RuntimeError, match="bad response"):
        runner.execute_point(
            fake,
            point,
            tmp_path,
            runner.RunEnvironment(image_digest="sha256:image"),
        )

    assert request_counts == [8, 64, 64]
    assert not list(tmp_path.glob("points/**/attempt-2"))


def test_execute_point_replaces_dataset_copies_with_fixture_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ArchiveRunner(FakeCommandRunner):
        def run(self, command: runner.Command) -> str:
            self.calls.append(command)
            if command.description == "archive-aisbench":
                raw = Path(command.argv[-1])
                raw.mkdir(parents=True, exist_ok=True)
                (raw / "dataset.jsonl").write_text("fixture\n", encoding="utf-8")
            if command.description == "prefill-log-offset":
                return "0\n"
            if command.description == "formal-prefill-hit-log":
                return "".join(
                    f"Reqid: request-{index}, Total tokens 16384, "
                    "kvpool hit tokens: 13312, need to load: 13312\n"
                    for index in range(64)
                )
            return ""

    def summarize(
        raw: Path,
        selected: WorkloadPoint,
        request_count: int,
        image_digest: str,
    ) -> dict[str, object]:
        del raw, selected, request_count
        return {
            "valid": True,
            "image_digest": image_digest,
            "errors": [],
            "metrics": {"Request Throughput": 1.0, "E2EL P95": 1.0},
        }

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", summarize)
    runner.execute_point(
        ArchiveRunner(),
        WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        tmp_path,
        runner.RunEnvironment(image_digest="sha256:image"),
    )

    raw_dirs = list(tmp_path.glob("points/**/attempt-1/raw"))
    assert len(raw_dirs) == 3
    for raw in raw_dirs:
        assert not (raw / "dataset.jsonl").exists()
        reference = json.loads((raw / "fixture-reference.json").read_text())
        assert reference["path"].startswith("fixtures/tokens-16384-c8/")
        assert len(reference["sha256"]) == 64


def test_point_lifecycle_uses_real_namespaced_aisbench_commands(tmp_path: Path) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 16384, 1, "reuse3", 8)

    runner.execute_point(fake, point, tmp_path)

    assert all(
        call.argv[0] == "kubectl" or (call.argv[0] == "bash" and call.description == "aisbench") for call in fake.calls
    )
    assert all("liangjiahao" in " ".join(call.argv) for call in fake.calls)
    assert not any("benchmark" in call.argv for call in fake.calls)
    aisbench = next(call for call in fake.calls if call.description == "aisbench")
    assert "chroot" in aisbench.argv
    assert "/performance-workspace/rootfs" in aisbench.argv
    assert "prefill-npu-timeseries.log" in aisbench.argv[2]
    assert "mooncake-timeseries.metrics" in aisbench.argv[2]
    config = next(call for call in fake.calls if call.description == "render-aisbench-config")
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
    canary_text = " ".join(fake.calls[-1].argv)
    assert "tokens-{input_tokens}-c8/warmup.jsonl" in canary_text
    assert "tokens-{input_tokens}-c64" not in canary_text


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


def test_variant_diagnostics_capture_complete_logs_once(tmp_path: Path) -> None:
    fake = FakeCommandRunner()

    runner._capture_variant_diagnostics(
        fake,
        "bulk",
        runner.RunEnvironment(),
        tmp_path,
    )

    descriptions = [call.description for call in fake.calls]
    assert descriptions.count("prefill-log") == 1
    assert descriptions.count("decode-log") == 1
    assert descriptions == ["prefill-log", "decode-log"]
    assert (tmp_path / "variants" / "bulk" / "raw" / "vllm-prefill.log").is_file()
    assert (tmp_path / "variants" / "bulk" / "raw" / "vllm-decode.log").is_file()


def test_attempt_cleanup_removes_keys_without_restarting_master() -> None:
    point = WorkloadPoint("dp1", 16384, 1, "layerwise", 8)

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


def test_formal_commands_preserve_seeded_mooncake() -> None:
    point = WorkloadPoint("dp1", 16384, 1, "layerwise", 8)

    descriptions = [
        command.description
        for command in runner._attempt_commands(
            point,
            "formal-1",
            64,
            "remote-formal",
            runner.RunEnvironment(),
        )
    ]

    assert "remove-all-keys" not in descriptions
    assert "assert-master-empty" not in descriptions
    assert descriptions[0] == "assert-engine-reconnect"


def test_parse_prefill_hit_log_requires_exact_per_request_hits() -> None:
    text = "".join(
        f"Reqid: request-{index}, Total tokens 16384, kvpool hit tokens: 13312, "
        "need to load: 13312\n"
        for index in range(64)
    )

    validation = runner.validate_prefill_hits(text)

    assert validation["valid"] is True
    assert validation["request_count"] == 64
    assert validation["min_hit_tokens"] == 13312
    assert validation["max_hit_tokens"] == 13312
    assert validation["hit_rate"] == 0.8125
    assert validation["min_need_to_load_tokens"] == 13312
    assert validation["max_need_to_load_tokens"] == 13312
    assert validation["local_hit_tokens"] == 0


@pytest.mark.parametrize(
    ("replacement", "error"),
    (
        (("kvpool hit tokens: 13312", "kvpool hit tokens: 0"), "unexpected hit tokens"),
        (("request-63", "request-62"), "duplicate request ID"),
        (("Total tokens 16384", "Total tokens 13312"), "unexpected total tokens"),
    ),
)
def test_parse_prefill_hit_log_rejects_invalid_records(
    replacement: str,
    error: str,
) -> None:
    text = "".join(
        f"Reqid: request-{index}, Total tokens 16384, kvpool hit tokens: 13312, "
        "need to load: 13312\n"
        for index in range(64)
    )
    before, after = replacement

    validation = runner.validate_prefill_hits(text.replace(before, after, 1))

    assert validation["valid"] is False
    assert any(error in message for message in validation["errors"])


def test_parse_prefill_hit_log_rejects_missing_record() -> None:
    text = "".join(
        f"Reqid: request-{index}, Total tokens 16384, kvpool hit tokens: 13312, "
        "need to load: 13312\n"
        for index in range(63)
    )

    validation = runner.validate_prefill_hits(text)

    assert validation["valid"] is False
    assert validation["request_count"] == 63
    assert any("expected 64 hit records" in message for message in validation["errors"])


def test_stop_engines_waits_for_idle_hbm_before_variant_switch() -> None:
    fake = FakeCommandRunner()

    assert runner._stop_engines(fake, runner.RunEnvironment()) == []

    assert [call.description for call in fake.calls] == [
        "stop-prefill",
        "stop-decode",
        "wait-prefill-hbm-idle",
        "wait-decode-hbm-idle",
    ]
    for command in fake.calls[2:]:
        script = command.argv[-1]
        assert "npu-smi info" in script
        assert "max(values) <= 4096" in script
        assert "sleep 1" in script


def test_aisbench_manifest_is_cpu_only_on_m1() -> None:
    path = Path(__file__).resolve().parents[1] / "00-aisbench-client.yaml"
    pod = json.loads(path.read_text(encoding="utf-8"))
    container = pod["spec"]["containers"][0]
    resources = container["resources"]

    assert pod["metadata"]["namespace"] == "liangjiahao"
    assert pod["metadata"]["name"] == "layerwise-performance-aisbench"
    assert pod["spec"]["nodeName"] == "m1"
    assert container["image"] == pod["metadata"]["annotations"][
        "performance.vllm.ai/source-image"
    ]
    assert pod["metadata"]["annotations"]["performance.vllm.ai/source-image"].endswith(
        "57d3c214e-df3f74ed-20260811T145302Z"
    )
    assert pod["metadata"]["annotations"]["performance.vllm.ai/repo-digest"] == (
        "sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3"
    )
    assert pod["metadata"]["annotations"]["performance.vllm.ai/config-digest"] == (
        "sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd"
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
