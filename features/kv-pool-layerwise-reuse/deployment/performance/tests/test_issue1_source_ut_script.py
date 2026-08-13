from __future__ import annotations

import re
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "run-issue1-source-ut.sh"


def test_issue1_source_ut_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_issue1_source_ut_script_fails_closed_before_cluster_access() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    first_kubectl = text.index("current_context=$(kubectl config current-context)")

    assert (
        "expected_source_head=8653c6c5e3b554719c8347a0a36fe2109e6a36d9"
        in text
    )
    assert text.index('source_head=$(git -C "${source_repo}" rev-parse HEAD)') < (
        first_kubectl
    )
    assert text.index('source_status=$(git -C "${source_repo}" status') < first_kubectl
    assert "requires a clean vLLM-Ascend checkout" in text
    assert 'source_tree=$(git -C "${source_repo}" rev-parse' in text


def test_issue1_source_ut_script_scopes_every_cluster_command() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    commands = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"^(kubectl|\s+kubectl)\b", line)
    ]

    assert commands
    for command in commands:
        if command == "current_context=$(kubectl config current-context)":
            continue
        assert '-n "${namespace}"' in command, command


def test_issue1_source_ut_script_disables_test_tree_pollution() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "TORCH_DEVICE_BACKEND_AUTOLOAD=0" in text
    assert "PYTHONDONTWRITEBYTECODE=1" in text
    assert "PYTEST_ADDOPTS='-p no:cacheprovider'" in text
    assert "--exclude='*/__pycache__'" in text
    assert "--exclude='*.pyc'" in text
