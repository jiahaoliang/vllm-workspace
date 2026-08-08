from __future__ import annotations

import argparse
import hashlib
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


def _write_checksums(root: Path) -> None:
    paths = sorted(
        path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def prepare(command_runner: Runner, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _append(
        output_dir / "steps.jsonl",
        {"phase": "prepare", "status": "started", "server_authorized": False},
    )
    manifest = Path(__file__).with_name("00-aisbench-client.yaml")
    bootstrap = r'''
set -euo pipefail
root=/client-tools
src=${root}/src/benchmark
venv=${root}/venv
python=/usr/local/python3.12.13/bin/python3.12
export TORCH_DEVICE_BACKEND_AUTOLOAD=0
mkdir -p "${root}/provenance" "${root}/src"
"${python}" --version | tee "${root}/provenance/python-version.txt"
if [[ ! -x ${root}/uv-bootstrap/bin/uv ]]; then
  "${python}" -m pip install --disable-pip-version-check --no-cache-dir \
    --index-url https://pypi.org/simple \
    --target "${root}/uv-bootstrap" uv==0.12.3 \
    2>&1 | tee "${root}/provenance/uv-install.log"
fi
uv=${root}/uv-bootstrap/bin/uv
"${uv}" --version | tee "${root}/provenance/uv-version.txt"
printf '%s\n' \
  'stdlib venv overlay; uv 0.12.3 cannot discover the custom-prefix interpreter' \
  >"${root}/provenance/venv-method.txt"
"${python}" -m venv --system-site-packages "${venv}"
if [[ ! -d ${src}/.git ]]; then
  git clone https://github.com/AISBench/benchmark.git "${src}"
fi
git -C "${src}" fetch origin 3fd27b4a5fd022fcb5484fb084307f49955491ba
git -C "${src}" checkout --detach 3fd27b4a5fd022fcb5484fb084307f49955491ba
test "$(git -C "${src}" rev-parse HEAD)" = \
  3fd27b4a5fd022fcb5484fb084307f49955491ba
"${venv}/bin/python" -m pip install --disable-pip-version-check \
  --no-deps -e "${src}" \
  2>&1 | tee "${root}/provenance/aisbench-install.log"
"${venv}/bin/python" -m pip install --disable-pip-version-check \
  -r "${src}/requirements/runtime.txt" \
  2>&1 | tee "${root}/provenance/runtime-install.log"
"${venv}/bin/python" -m pip install --disable-pip-version-check \
  -r "${src}/requirements/api.txt" \
  2>&1 | tee "${root}/provenance/api-install.log"
"${venv}/bin/python" -c \
  'import ais_bench.benchmark as b; print(b.__version__)' \
  | tee "${root}/provenance/aisbench-version.txt"
"${venv}/bin/python" -c \
  'from ais_bench.benchmark.models import VLLMCustomAPI; from ais_bench.benchmark.datasets import CustomDataset; from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer; print("imports: OK")' \
  | tee "${root}/provenance/import-smoke.txt"
"${venv}/bin/python" -m pip freeze \
  >"${root}/provenance/requirements.freeze.txt"
git -C "${src}" rev-parse HEAD >"${root}/provenance/aisbench-commit.txt"
'''.strip()
    exact_image = (
        "docker.io/library/vllm-ascend:"
        "kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z"
    )
    exact_config_digest = (
        "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
    )
    rootfs_sync = f'''
set -euo pipefail
marker=/performance-workspace/rootfs/.performance-image-config-digest
if kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  test -f "${{marker}}"; then
  actual=$(kubectl exec -n liangjiahao layerwise-performance-aisbench \
    -c aisbench -- cat "${{marker}}")
  test "${{actual}}" = {exact_config_digest!r}
  exit 0
fi
existing=$(kubectl exec -n liangjiahao layerwise-performance-aisbench \
  -c aisbench -- find /performance-workspace/rootfs -mindepth 1 -print -quit)
test -z "${{existing}}"
mount_dir=$(mktemp -d /tmp/layerwise-client-rootfs.XXXXXX)
cleanup_mount() {{
  ctr --namespace k8s.io images unmount "${{mount_dir}}" >/dev/null 2>&1 || true
  rmdir "${{mount_dir}}" >/dev/null 2>&1 || true
}}
trap cleanup_mount EXIT
ctr --namespace k8s.io images mount {exact_image!r} "${{mount_dir}}"
tar --numeric-owner -C "${{mount_dir}}" -cf - . | \
  kubectl exec -i -n liangjiahao layerwise-performance-aisbench \
    -c aisbench -- tar --numeric-owner \
    -C /performance-workspace/rootfs -xf -
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  sh -c 'printf "%s\\n" "$1" >"$2"' sh \
  {exact_config_digest!r} "${{marker}}"
'''.strip()
    tokenizer_copy = r'''
set -euo pipefail
kubectl exec -n liangjiahao deployment/prefill-engine-deployment \
  -c prefill-engine -- tar \
  -C /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 -cf - \
  config.json configuration.json configuration_deepseek.py generation_config.json \
  tokenization_deepseek_fast.py tokenizer.json tokenizer_config.json | \
kubectl exec -i -n liangjiahao layerwise-performance-aisbench \
  -c aisbench -- tar -C /performance-workspace/rootfs/client-tools/tokenizer -xf -
'''.strip()
    tooling_sync = (
        "set -euo pipefail; "
        f"tar -C {str(Path(__file__).resolve().parent.parent)!r} -cf - performance | "
        "kubectl exec -i -n liangjiahao layerwise-performance-aisbench "
        "-c aisbench -- tar -C /performance-workspace/rootfs/client-tools/tooling -xf -"
    )
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
        Command(("bash", "-c", rootfs_sync), description="sync-exact-client-rootfs"),
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
                "mkdir",
                "-p",
                "/performance-workspace/rootfs/client-tools/tokenizer",
                "/performance-workspace/rootfs/client-tools/tooling",
            ),
            description="prepare-client-directories",
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
                "cp",
                "/etc/resolv.conf",
                "/performance-workspace/rootfs/etc/resolv.conf",
            ),
            description="configure-chroot-dns",
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
                "sh",
                "-c",
                "test -c /performance-workspace/rootfs/dev/null || "
                "mknod -m 666 /performance-workspace/rootfs/dev/null c 1 3; "
                "test -c /performance-workspace/rootfs/dev/random || "
                "mknod -m 666 /performance-workspace/rootfs/dev/random c 1 8; "
                "test -c /performance-workspace/rootfs/dev/urandom || "
                "mknod -m 666 /performance-workspace/rootfs/dev/urandom c 1 9",
            ),
            description="configure-chroot-devices",
        ),
        Command(("bash", "-c", tokenizer_copy), description="copy-tokenizer"),
        Command(("bash", "-c", tooling_sync), description="sync-performance-tooling"),
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
                "chroot",
                "/performance-workspace/rootfs",
                "/bin/bash",
                "-c",
                bootstrap,
            ),
            description="bootstrap-client",
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
                "rm",
                "-rf",
                "--",
                "/performance-workspace/rootfs/client-tools/fixtures",
            ),
            description="reset-client-fixtures",
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
                "--concurrency",
                "64",
                "--seed",
                "20260808",
            ),
            description="generate-fixtures",
        ),
        Command(
            (
                "kubectl",
                "cp",
                "-n",
                "liangjiahao",
                "-c",
                "aisbench",
                "layerwise-performance-aisbench:/performance-workspace/rootfs/client-tools/provenance",
                str(output_dir / "client-provenance"),
            ),
            description="archive-client-provenance",
        ),
        Command(
            (
                "kubectl",
                "cp",
                "-n",
                "liangjiahao",
                "-c",
                "aisbench",
                "layerwise-performance-aisbench:/performance-workspace/rootfs/client-tools/fixtures",
                str(output_dir / "fixtures"),
            ),
            description="archive-fixtures",
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
    _write_checksums(output_dir)


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
