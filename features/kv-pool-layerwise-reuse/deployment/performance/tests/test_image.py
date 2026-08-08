from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

from performance import handoff, image


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> str:
        self.commands.append(command)
        if "inspect" in command:
            return json.dumps(
                [
                    {
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RepoDigests": ["derived@sha256:abc"],
                        "Config": {
                            "Labels": {
                                "vllm.source": "vllm-sha",
                                "vllm-ascend.source": "ascend-sha",
                                "mooncake.source": "mooncake-sha",
                            }
                        },
                    }
                ]
            )
        if "run" in command:
            return json.dumps(
                {
                    "path": "/usr/local/lib/python3.12/site-packages/vllm_ascend/x.py",
                    "sha256": "file-sha",
                }
            )
        raise AssertionError(command)


def ready_state(tmp_path: Path) -> handoff.HandoffState:
    return handoff.HandoffState(
        path=tmp_path / "handoff.md",
        digest="handoff-sha",
        status="READY_FOR_PERFORMANCE_VALIDATION",
        ready=True,
        generation=1,
        placeholders_remaining=False,
        authorized_scope=(),
        gates={},
        evidence_fields={},
        source_rows={},
        image_fields={
            "Base image reference": "base",
            "Base manifest digest": "sha256:base",
            "Patched file path": "/usr/local/lib/python3.12/site-packages/vllm_ascend/x.py",
            "Patched file SHA256": "file-sha",
            "Patched source commit": "ascend-sha",
            "Derived image reference": "derived",
            "Platform": "linux/arm64",
            "Derived manifest digest": "sha256:abc",
            "vLLM source label": "vllm-sha",
            "vLLM-Ascend source label": "ascend-sha",
            "Mooncake source label": "mooncake-sha",
            "Derived-image/run ID": "functional-run",
        },
        contains_pending=False,
    )


def test_ready_image_avoids_materialization(tmp_path: Path) -> None:
    runner = FakeRunner()

    identity = image.resolve_server_image(ready_state(tmp_path), runner, tmp_path)

    assert identity.reference == "derived"
    assert identity.digest == "sha256:abc"
    command_text = [" ".join(command) for command in runner.commands]
    assert not any(
        forbidden in text
        for text in command_text
        for forbidden in ("buildctl", "docker build", "nerdctl build", " create ", " cp ", " commit ")
    )


def test_patch_mode_requires_hash_before_mutation(tmp_path: Path) -> None:
    state = ready_state(tmp_path)
    fields = dict(state.image_fields)
    fields.update(
        {
            "Image delivery mode": "patch",
            "Patch source path": str(tmp_path / "patched.py"),
            "Patched file SHA256": "",
        }
    )
    runner = FakeRunner()

    try:
        image.resolve_server_image(replace(state, image_fields=fields), runner, tmp_path)
    except image.ImageContractError as error:
        assert "Patched file SHA256" in str(error)
    else:
        raise AssertionError("missing patch hash was accepted")
    assert runner.commands == []


def test_patch_failure_removes_temporary_container(tmp_path: Path) -> None:
    patch = tmp_path / "patched.py"
    patch.write_text("value = 1\n", encoding="utf-8")
    state = ready_state(tmp_path)
    fields = dict(state.image_fields)
    fields.update(
        {
            "Image delivery mode": "patch",
            "Patch source path": str(patch),
            "Patched file SHA256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        }
    )

    class FailingPatchRunner(FakeRunner):
        def run(self, command: tuple[str, ...]) -> str:
            self.commands.append(command)
            if "cp" in command:
                raise RuntimeError("copy failed")
            return ""

    runner = FailingPatchRunner()
    try:
        image.resolve_server_image(replace(state, image_fields=fields), runner, tmp_path)
    except RuntimeError as error:
        assert str(error) == "copy failed"
    else:
        raise AssertionError("copy failure was ignored")

    assert "rm" in runner.commands[-1]
    assert "layerwise-performance-patch-g1" in runner.commands[-1]
