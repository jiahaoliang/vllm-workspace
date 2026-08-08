from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from performance import handoff
from performance.contract import WorkloadPoint, sample_counts


WORKSPACE_ROOT = Path(os.environ.get("VLLM_WORKSPACE_ROOT", Path.cwd())).resolve()


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    mutates_server: bool = False
    sends_inference: bool = False
    description: str = ""


class Runner(Protocol):
    def run(self, command: Command) -> str: ...


class SubprocessCommandRunner:
    def __init__(self, evidence_root: Path) -> None:
        self.evidence_root = evidence_root
        self.command_index = 0

    def run(self, command: Command) -> str:
        self.command_index += 1
        command_id = f"{self.command_index:04d}-{command.description or 'command'}"
        command_root = self.evidence_root / "commands" / command_id
        command_root.mkdir(parents=True, exist_ok=False)
        (command_root / "argv.json").write_text(
            json.dumps(command.argv, indent=2) + "\n", encoding="utf-8"
        )
        result = subprocess.run(command.argv, check=False, capture_output=True, text=True)
        (command_root / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (command_root / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (command_root / "result.json").write_text(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "mutates_server": command.mutates_server,
                    "sends_inference": command.sends_inference,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if result.returncode:
            raise RuntimeError(
                f"command failed ({result.returncode}): {' '.join(command.argv)}"
            )
        return result.stdout


def _append(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def prepare(command_runner: Runner, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _append(
        output_dir / "steps.jsonl",
        {"phase": "prepare", "status": "started", "server_authorized": False},
    )
    manifest = Path(__file__).with_name("00-aisbench-client.yaml")
    bootstrap = r'''
set -euo pipefail
root=/performance-workspace
src=${root}/src/benchmark
venv=${root}/venv
mkdir -p "${root}/provenance" "${root}/src"
python3 --version | tee "${root}/provenance/python-version.txt"
python3 -m pip install --disable-pip-version-check --no-cache-dir \
  --target "${root}/uv-bootstrap" uv==0.12.3 \
  2>&1 | tee "${root}/provenance/uv-install.log"
uv=${root}/uv-bootstrap/bin/uv
"${uv}" --version | tee "${root}/provenance/uv-version.txt"
"${uv}" venv --python /usr/local/python3.12.13/bin/python3 "${venv}"
if [[ ! -d ${src}/.git ]]; then
  git clone https://github.com/AISBench/benchmark.git "${src}"
fi
git -C "${src}" fetch origin 3fd27b4a5fd022fcb5484fb084307f49955491ba
git -C "${src}" checkout --detach 3fd27b4a5fd022fcb5484fb084307f49955491ba
test "$(git -C "${src}" rev-parse HEAD)" = \
  3fd27b4a5fd022fcb5484fb084307f49955491ba
"${uv}" pip install --python "${venv}/bin/python" \
  -e "${src}" -r "${src}/requirements/api.txt" \
  2>&1 | tee "${root}/provenance/aisbench-install.log"
"${venv}/bin/python" -c \
  'import ais_bench.benchmark as b; print(b.__version__)' \
  | tee "${root}/provenance/aisbench-version.txt"
"${venv}/bin/python" -c \
  'from ais_bench.benchmark.models import VLLMCustomAPI; from ais_bench.benchmark.datasets import CustomDataset; from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer; print("imports: OK")' \
  | tee "${root}/provenance/import-smoke.txt"
"${uv}" pip freeze --python "${venv}/bin/python" \
  >"${root}/provenance/requirements.freeze.txt"
git -C "${src}" rev-parse HEAD >"${root}/provenance/aisbench-commit.txt"
'''.strip()
    commands = (
        Command(("kubectl", "config", "current-context"), description="kube-context"),
        Command(
            ("kubectl", "get", "node", "m1", "-o", "json"),
            description="m1-inventory",
        ),
        Command(
            ("kubectl", "apply", "-n", "liangjiahao", "-f", str(manifest)),
            description="apply-client",
        ),
        Command(
            (
                "kubectl",
                "wait",
                "-n",
                "liangjiahao",
                "--for=condition=Ready",
                "pod/layerwise-performance-aisbench",
                "--timeout=300s",
            ),
            description="wait-client",
        ),
        Command(
            (
                "kubectl",
                "get",
                "pod",
                "-n",
                "liangjiahao",
                "layerwise-performance-aisbench",
                "-o",
                "json",
            ),
            description="client-identity",
        ),
        Command(
            (
                "kubectl",
                "exec",
                "-n",
                "liangjiahao",
                "layerwise-performance-aisbench",
                "-c",
                "aisbench",
                "--",
                "bash",
                "-lc",
                bootstrap,
            ),
            description="bootstrap-client",
        ),
    )
    try:
        for command in commands:
            output = command_runner.run(command)
            _append(
                output_dir / "steps.jsonl",
                {"phase": "prepare", "status": "completed", "step": command.description},
            )
            if command.description == "client-identity":
                (output_dir / "client-pod.json").write_text(output, encoding="utf-8")
    except Exception as error:
        _append(
            output_dir / "steps.jsonl",
            {
                "phase": "prepare",
                "status": "failed",
                "error": type(error).__name__,
                "message": str(error),
            },
        )
        raise
    _append(
        output_dir / "steps.jsonl",
        {"phase": "prepare", "status": "completed", "server_authorized": False},
    )


def run(
    command_runner: Runner,
    state: handoff.HandoffState,
    output_dir: Path,
    topology: str,
) -> None:
    del command_runner, output_dir, topology
    errors = handoff.validate_readiness(state)
    if errors:
        raise handoff.HandoffError("handoff is not ready: " + "; ".join(errors))
    errors = handoff.validate_handoff(state, WORKSPACE_ROOT)
    if errors:
        raise handoff.HandoffError("handoff validation failed: " + "; ".join(errors))


def _point_id(point: WorkloadPoint) -> str:
    return (
        f"{point.topology}-{point.input_tokens}-{point.variant}"
        f"-o{point.output_tokens}-c{point.concurrency}"
    )


def _new_attempt(root: Path, phase: str) -> Path:
    phase_root = root / phase
    phase_root.mkdir(parents=True, exist_ok=True)
    existing = [
        int(path.name.removeprefix("attempt-"))
        for path in phase_root.glob("attempt-[0-9]*")
        if path.name.removeprefix("attempt-").isdigit()
    ]
    attempt = phase_root / f"attempt-{max(existing, default=0) + 1}"
    (attempt / "raw").mkdir(parents=True, exist_ok=False)
    return attempt


def _invoke(command_runner: Runner, command: Command, attempt: Path) -> str:
    _append(
        attempt / "state.jsonl",
        {
            "status": "running",
            "description": command.description,
            "argv": command.argv,
        },
    )
    output = command_runner.run(command)
    _append(
        attempt / "state.jsonl",
        {"status": "completed", "description": command.description},
    )
    return output


def execute_point(
    command_runner: Runner,
    point: WorkloadPoint,
    output_dir: Path,
) -> None:
    point_root = output_dir / "points" / _point_id(point)
    warmup_count, formal_count, repetitions = sample_counts(point.concurrency)
    phases = [("warmup", warmup_count)] + [
        (f"formal-{index}", formal_count) for index in range(1, repetitions + 1)
    ]
    current_attempt = point_root
    try:
        for phase, request_count in phases:
            current_attempt = _new_attempt(point_root, phase)
            _invoke(
                command_runner,
                Command(
                    ("benchmark", "reset-master"),
                    mutates_server=True,
                    description="reset-master",
                ),
                current_attempt,
            )
            _invoke(
                command_runner,
                Command(
                    (
                        "benchmark",
                        "aisbench",
                        "--point",
                        _point_id(point),
                        "--phase",
                        phase,
                        "--request-count",
                        str(request_count),
                    ),
                    sends_inference=True,
                    description="aisbench",
                ),
                current_attempt,
            )
    except Exception as error:
        _append(
            current_attempt / "state.jsonl",
            {"status": "failed", "error": type(error).__name__, "message": str(error)},
        )
        command_runner.run(
            Command(("benchmark", "capture-failure"), description="capture-failure")
        )
        command_runner.run(
            Command(
                ("benchmark", "restore-pre-run-state"),
                mutates_server=True,
                description="restore-pre-run-state",
            )
        )
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--output", type=Path, required=True)
    wait_parser = subparsers.add_parser("wait")
    wait_parser.add_argument("--output", type=Path, required=True)
    wait_parser.add_argument("--poll-seconds", type=float, default=10.0)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--topology", choices=("dp1", "dp2"), required=True)
    run_parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handoff_path = (
        WORKSPACE_ROOT
        / "features/kv-pool-layerwise-reuse/performance-validation-handoff.md"
    )
    if args.command == "wait":
        handoff.wait_for_ready(
            handoff_path,
            WORKSPACE_ROOT,
            args.poll_seconds,
            args.output / "observations.jsonl",
        )
        return 0
    command_runner = SubprocessCommandRunner(args.output)
    if args.command == "prepare":
        prepare(command_runner, args.output)
        return 0
    state = handoff.parse_handoff(handoff_path)
    run(command_runner, state, args.output, topology=args.topology)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
