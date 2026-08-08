from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from performance import handoff, image, report, runtime
from performance.contract import (
    INPUT_TOKENS,
    PointResult,
    TOPOLOGIES,
    WorkloadPoint,
    adaptive_stop,
    build_matrix,
    sample_counts,
)


WORKSPACE_ROOT = Path(os.environ.get("VLLM_WORKSPACE_ROOT", Path.cwd())).resolve()


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    mutates_server: bool = False
    sends_inference: bool = False
    description: str = ""


@dataclass(frozen=True)
class RunEnvironment:
    namespace: str = "liangjiahao"
    client_pod: str = "layerwise-performance-aisbench"
    prefill_resource: str = "deployment/prefill-engine-deployment"
    decode_resource: str = "deployment/decode-engine-deployment"
    master_resource: str = "deployment/mooncake-master-deployment"
    restore_manifest: Path | None = None
    image_digest: str = ""


class Runner(Protocol):
    def run(self, command: Command) -> str: ...


class SubprocessCommandRunner:
    def __init__(self, evidence_root: Path) -> None:
        self.evidence_root = evidence_root
        command_root = evidence_root / "commands"
        existing = [
            int(path.name.split("-", 1)[0])
            for path in command_root.glob("[0-9][0-9][0-9][0-9]-*")
            if path.name.split("-", 1)[0].isdigit()
        ]
        self.command_index = max(existing, default=0)

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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _clean_kubernetes_resource(value: dict[str, object]) -> dict[str, object]:
    cleaned = deepcopy(value)
    cleaned.pop("status", None)
    metadata = cleaned.get("metadata")
    if isinstance(metadata, dict):
        for key in (
            "annotations",
            "creationTimestamp",
            "generation",
            "managedFields",
            "resourceVersion",
            "selfLink",
            "uid",
        ):
            if key == "annotations":
                annotations = metadata.get(key)
                if isinstance(annotations, dict):
                    annotations.pop("deployment.kubernetes.io/revision", None)
                    annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
                    if not annotations:
                        metadata.pop(key, None)
                continue
            metadata.pop(key, None)
    return cleaned


def _available_test_npus(nodes: dict[str, object], pods: dict[str, object]) -> int:
    node_items = nodes.get("items", [])
    if not isinstance(node_items, list):
        raise ValueError("node inventory items are malformed")
    matching = [
        node
        for node in node_items
        if isinstance(node, dict)
        and isinstance(node.get("metadata"), dict)
        and node["metadata"].get("name") == "n1"
    ]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one n1 node, got {len(matching)}")
    allocatable = matching[0].get("status", {}).get("allocatable", {})
    if not isinstance(allocatable, dict):
        raise ValueError("n1 allocatable capacity is malformed")
    physical = int(allocatable.get("huawei.com/Ascend910", 0))
    pod_items = pods.get("items", [])
    if not isinstance(pod_items, list):
        raise ValueError("pod inventory items are malformed")
    used = 0
    for pod in pod_items:
        if not isinstance(pod, dict):
            continue
        metadata = pod.get("metadata", {})
        spec = pod.get("spec", {})
        status = pod.get("status", {})
        if not all(isinstance(value, dict) for value in (metadata, spec, status)):
            continue
        if spec.get("nodeName") != "n1" or status.get("phase") in {
            "Succeeded",
            "Failed",
        }:
            continue
        labels = metadata.get("labels", {})
        if isinstance(labels, dict) and labels.get("app") in {"prefill", "decode"}:
            continue
        containers = spec.get("containers", [])
        if not isinstance(containers, list):
            continue
        for container in containers:
            if not isinstance(container, dict):
                continue
            resources = container.get("resources", {})
            requests = resources.get("requests", {}) if isinstance(resources, dict) else {}
            if isinstance(requests, dict):
                used += int(requests.get("huawei.com/Ascend910", 0))
    return physical - used


class _ImageRunner:
    def __init__(self, command_runner: Runner) -> None:
        self.command_runner = command_runner

    def run(self, argv: tuple[str, ...]) -> str:
        return self.command_runner.run(Command(argv, description="image-" + argv[3]))


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
        f"tar --exclude='*/__pycache__' --exclude='*.pyc' "
        f"-C {str(Path(__file__).resolve().parent.parent)!r} -cf - performance | "
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
                "set -eu; root=/performance-workspace/rootfs; "
                "target=$root/root/.cache/modelscope/vllm-ascend/"
                "DeepSeek-V2-Lite-W8A8; mkdir -p \"$(dirname \"$target\")\"; "
                "if test -L \"$target\"; then "
                "test \"$(readlink \"$target\")\" = /client-tools/tokenizer; "
                "else test ! -e \"$target\"; ln -s /client-tools/tokenizer \"$target\"; fi",
            ),
            description="link-tokenizer-model-path",
        ),
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


def _run_and_save(
    command_runner: Runner, command: Command, destination: Path
) -> str:
    output = command_runner.run(command)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8")
    return output


def _sync_client_tooling(command_runner: Runner, output_dir: Path) -> None:
    package = Path(__file__).resolve().parent
    files = sorted(
        path
        for path in package.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )
    _write_json(
        output_dir / "tooling-identity.json",
        {
            "files": {
                str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in files
            }
        },
    )
    deployment_root = package.parent
    script = (
        "set -euo pipefail; "
        "tar --exclude='*/__pycache__' --exclude='*.pyc' "
        f"-C {str(deployment_root)!r} -cf - performance | "
        "kubectl exec -i -n liangjiahao layerwise-performance-aisbench "
        "-c aisbench -- tar -C "
        "/performance-workspace/rootfs/client-tools/tooling -xf -"
    )
    command_runner.run(
        Command(("bash", "-c", script), description="sync-formal-tooling")
    )
    marker = command_runner.run(
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
                "cat",
                "/performance-workspace/rootfs/.performance-image-config-digest",
            ),
            description="verify-client-rootfs-marker",
        )
    ).strip()
    expected = "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
    if marker != expected:
        raise RuntimeError(f"client rootfs config digest mismatch: {marker}")
    link = command_runner.run(
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
                "readlink",
                "/performance-workspace/rootfs/root/.cache/modelscope/"
                "vllm-ascend/DeepSeek-V2-Lite-W8A8",
            ),
            description="verify-client-tokenizer-link",
        )
    ).strip()
    if link != "/client-tools/tokenizer":
        raise RuntimeError(f"client tokenizer link mismatch: {link}")


def _capture_pre_run_state(
    command_runner: Runner, output_dir: Path
) -> runtime.RuntimeInputs:
    pre_run = output_dir / "pre-run-state"
    resources = {
        "prefill-deployment": (
            "deployment",
            "prefill-engine-deployment",
        ),
        "decode-deployment": (
            "deployment",
            "decode-engine-deployment",
        ),
        "runtime-configmap": ("configmap", "layerwise-runtime-config"),
    }
    values: dict[str, dict[str, object]] = {}
    for name, (kind, resource_name) in resources.items():
        raw = _run_and_save(
            command_runner,
            Command(
                (
                    "kubectl",
                    "get",
                    "-n",
                    "liangjiahao",
                    kind,
                    resource_name,
                    "-o",
                    "json",
                ),
                description=f"capture-{name}",
            ),
            pre_run / f"{name}.raw.json",
        )
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"captured resource is not an object: {name}")
        cleaned = _clean_kubernetes_resource(parsed)
        values[name] = cleaned
        _write_json(pre_run / f"{name}.json", cleaned)
    _run_and_save(
        command_runner,
        Command(
            (
                "kubectl",
                "get",
                "nodes",
                "-o",
                "json",
            ),
            description="capture-node-inventory",
        ),
        output_dir / "cluster" / "nodes.json",
    )
    _run_and_save(
        command_runner,
        Command(
            (
                "kubectl",
                "get",
                "pods",
                "-n",
                "liangjiahao",
                "-o",
                "json",
            ),
            description="capture-pod-inventory",
        ),
        output_dir / "cluster" / "pods.json",
    )
    for role, resource_name in (
        ("prefill", "deployment/prefill-engine-deployment"),
        ("decode", "deployment/decode-engine-deployment"),
    ):
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    "liangjiahao",
                    resource_name,
                    "-c",
                    f"{role}-engine",
                    "--",
                    "sh",
                    "-c",
                    f"test ! -e /tmp/vllm-{role}.pid",
                ),
                description=f"assert-pre-run-{role}-stopped",
            )
        )
    return runtime.RuntimeInputs(
        prefill_deployment=values["prefill-deployment"],
        decode_deployment=values["decode-deployment"],
        runtime_configmap=values["runtime-configmap"],
    )


def _capture_identity(
    command_runner: Runner,
    state: handoff.HandoffState,
    output_dir: Path,
) -> None:
    _write_json(
        output_dir / "handoff.json",
        {
            "path": str(state.path),
            "sha256": state.digest,
            "generation": state.generation,
            "status": state.status,
            "ready": state.ready,
            "source_rows": state.source_rows,
            "image_fields": state.image_fields,
            "evidence_fields": state.evidence_fields,
        },
    )
    source_identity: dict[str, object] = {"handoff": state.source_rows}
    for name, repository in (
        ("control repo", WORKSPACE_ROOT),
        ("repos/vllm", WORKSPACE_ROOT / "repos/vllm"),
        ("repos/vllm-ascend", WORKSPACE_ROOT / "repos/vllm-ascend"),
        ("repos/Mooncake", WORKSPACE_ROOT / "repos/Mooncake"),
    ):
        commit = command_runner.run(
            Command(
                ("git", "-C", str(repository), "rev-parse", "HEAD"),
                description=f"source-{name.replace('/', '-')}",
            )
        ).strip()
        dirty = command_runner.run(
            Command(
                ("git", "-C", str(repository), "status", "--porcelain"),
                description=f"dirty-{name.replace('/', '-')}",
            )
        )
        source_identity[name] = {"commit": commit, "dirty": dirty.splitlines()}
    _write_json(output_dir / "source-identity.json", source_identity)
    client = _run_and_save(
        command_runner,
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
            description="capture-client-identity",
        ),
        output_dir / "client-identity.json",
    )
    if not isinstance(json.loads(client), dict):
        raise RuntimeError("client identity is not a JSON object")


def _write_rendered_block(
    inputs: runtime.RuntimeInputs,
    point: WorkloadPoint,
    image_reference: str,
    output_dir: Path,
) -> tuple[runtime.RenderedResources, tuple[Path, Path, Path]]:
    rendered = runtime.render_resources(inputs, point, image_reference)
    block = output_dir / "rendered" / point.topology / str(point.input_tokens) / point.variant
    paths = (
        block / "runtime-configmap.json",
        block / "prefill-deployment.json",
        block / "decode-deployment.json",
    )
    _write_json(paths[0], _clean_kubernetes_resource(rendered.runtime_configmap))
    _write_json(paths[1], _clean_kubernetes_resource(rendered.prefill_deployment))
    _write_json(paths[2], _clean_kubernetes_resource(rendered.decode_deployment))
    return rendered, paths


def _apply_variant_block(
    command_runner: Runner,
    paths: tuple[Path, Path, Path],
    point: WorkloadPoint,
    environment: RunEnvironment,
    output_dir: Path,
) -> None:
    for path, description in zip(
        paths,
        ("apply-runtime-config", "apply-prefill", "apply-decode"),
        strict=True,
    ):
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "apply",
                    "-n",
                    environment.namespace,
                    "-f",
                    str(path),
                ),
                mutates_server=True,
                description=description,
            )
        )
    for role in ("prefill", "decode"):
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "wait",
                    "-n",
                    environment.namespace,
                    "--for=jsonpath={.status.phase}=Running",
                    "pod",
                    "-l",
                    f"app={role}",
                    "--timeout=600s",
                ),
                description=f"wait-{role}-running",
            )
        )
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    environment.namespace,
                    getattr(environment, f"{role}_resource"),
                    "-c",
                    f"{role}-engine",
                    "--",
                    f"/opt/vllm-layerwise/start-{role}.sh",
                ),
                mutates_server=True,
                description=f"start-{role}",
            )
        )
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "wait",
                    "-n",
                    environment.namespace,
                    "--for=condition=Ready",
                    "pod",
                    "-l",
                    f"app={role}",
                    "--timeout=1800s",
                ),
                description=f"wait-{role}-ready",
            )
        )
        _run_and_save(
            command_runner,
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    environment.namespace,
                    getattr(environment, f"{role}_resource"),
                    "-c",
                    f"{role}-engine",
                    "--",
                    "python3",
                    "/opt/vllm-layerwise/check-runtime.py",
                    "--role",
                    role,
                ),
                description=f"check-runtime-{role}",
            ),
            output_dir
            / "runtime-checks"
            / f"{point.topology}-{point.input_tokens}-{point.variant}-{role}.json",
        )


def _canary_command(point: WorkloadPoint, environment: RunEnvironment) -> Command:
    script = '''import json, sys
from pathlib import Path
from urllib.request import Request, urlopen
input_tokens, output_tokens = map(int, sys.argv[1:])
fixture = Path(f"/client-tools/fixtures/tokens-{input_tokens}-c64/warmup.jsonl")
prompt = json.loads(fixture.read_text(encoding="utf-8").splitlines()[0])["question"]
payload = json.dumps({
    "model": "vllm-ascend/DeepSeek-V2-Lite-W8A8",
    "prompt": prompt,
    "max_tokens": output_tokens,
    "temperature": 0,
    "ignore_eos": True,
    "stream": False,
}).encode()
request = Request(
    "http://vllm-proxy-service:8000/v1/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
)
with urlopen(request, timeout=1800) as response:
    assert response.status == 200, response.status
    body = json.loads(response.read())
usage = body["usage"]
assert usage["prompt_tokens"] == input_tokens, usage
assert usage["completion_tokens"] == output_tokens, usage
assert len(body["choices"]) == 1, body
print(json.dumps(body, sort_keys=True))
'''
    base = _client_python(environment, script)
    return Command(
        (*base.argv, str(point.input_tokens), str(point.output_tokens)),
        sends_inference=True,
        description="correctness-canary",
    )


def _stop_engines(command_runner: Runner, environment: RunEnvironment) -> list[str]:
    errors: list[str] = []
    for role in ("prefill", "decode"):
        try:
            command_runner.run(
                Command(
                    (
                        "kubectl",
                        "exec",
                        "-n",
                        environment.namespace,
                        getattr(environment, f"{role}_resource"),
                        "-c",
                        f"{role}-engine",
                        "--",
                        "/opt/vllm-layerwise/stop-engine.sh",
                        role,
                    ),
                    mutates_server=True,
                    description=f"stop-{role}",
                )
            )
        except Exception as error:
            errors.append(f"stop {role}: {error}")
    return errors


def _restore_pre_run_state(
    command_runner: Runner,
    output_dir: Path,
    environment: RunEnvironment,
    configmaps: set[str],
) -> list[str]:
    errors = _stop_engines(command_runner, environment)
    for name in ("runtime-configmap", "prefill-deployment", "decode-deployment"):
        path = output_dir / "pre-run-state" / f"{name}.json"
        try:
            command_runner.run(
                Command(
                    (
                        "kubectl",
                        "apply",
                        "-n",
                        environment.namespace,
                        "-f",
                        str(path),
                    ),
                    mutates_server=True,
                    description=f"restore-{name}",
                )
            )
        except Exception as error:
            errors.append(f"restore {name}: {error}")
    for name in sorted(configmaps):
        try:
            command_runner.run(
                Command(
                    (
                        "kubectl",
                        "delete",
                        "configmap",
                        "-n",
                        environment.namespace,
                        name,
                        "--ignore-not-found=true",
                    ),
                    mutates_server=True,
                    description="delete-performance-configmap",
                )
            )
        except Exception as error:
            errors.append(f"delete ConfigMap {name}: {error}")
    try:
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "rollout",
                    "restart",
                    "-n",
                    environment.namespace,
                    environment.master_resource,
                ),
                mutates_server=True,
                description="final-reset-master",
            )
        )
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "rollout",
                    "status",
                    "-n",
                    environment.namespace,
                    environment.master_resource,
                    "--timeout=300s",
                ),
                description="wait-final-master",
            )
        )
        empty = _client_python(environment, _master_empty_script())
        _run_and_save(
            command_runner,
            Command(empty.argv, description="prove-final-master-empty"),
            output_dir / "final-mooncake-empty.metrics",
        )
    except Exception as error:
        errors.append(f"final Mooncake cleanup: {error}")
    _write_json(
        output_dir / "restoration.json",
        {
            "completed": not errors,
            "errors": errors,
            "engines_stopped": True,
            "mooncake_empty": not errors,
        },
    )
    return errors


def run(
    command_runner: Runner,
    state: handoff.HandoffState,
    output_dir: Path,
    topology: str,
    resume: bool = False,
) -> None:
    errors = handoff.validate_readiness(state)
    if errors:
        raise handoff.HandoffError("handoff is not ready: " + "; ".join(errors))
    errors = handoff.validate_handoff(state, WORKSPACE_ROOT)
    if errors:
        raise handoff.HandoffError("handoff validation failed: " + "; ".join(errors))
    if output_dir.exists() and any(output_dir.iterdir()) and not resume:
        raise FileExistsError(f"run output is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_contract: dict[str, object] = {}
    prior_topologies: list[str] = []
    if resume:
        contract_path = output_dir / "run-contract.json"
        handoff_path = output_dir / "handoff.json"
        if not contract_path.is_file() or not handoff_path.is_file():
            raise FileNotFoundError("resume requires run-contract.json and handoff.json")
        existing_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        archived_handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        if archived_handoff.get("sha256") != state.digest:
            raise handoff.HandoffError("handoff changed since the original topology run")
        topologies = existing_contract.get("topologies", [])
        if not isinstance(topologies, list) or topology in topologies:
            raise ValueError(f"topology is already present or malformed: {topology}")
        prior_topologies = [str(value) for value in topologies]
    _sync_client_tooling(command_runner, output_dir)
    _capture_identity(command_runner, state, output_dir)
    inputs = _capture_pre_run_state(command_runner, output_dir)
    nodes = json.loads((output_dir / "cluster" / "nodes.json").read_text())
    pods = json.loads((output_dir / "cluster" / "pods.json").read_text())
    available_npus = _available_test_npus(nodes, pods)
    required_npus = TOPOLOGIES[topology].prefill_npus + TOPOLOGIES[topology].decode_npus
    _write_json(
        output_dir / "cluster" / f"{topology}-capacity.json",
        {
            "node": "n1",
            "resource": "huawei.com/Ascend910",
            "available_after_replacing_current_engines": available_npus,
            "required": required_npus,
            "vnpu_number_ignored": True,
        },
    )
    if available_npus < required_npus:
        raise RuntimeError(
            f"insufficient physical Ascend910 capacity: {available_npus} < {required_npus}"
        )
    image_identity = image.resolve_server_image(
        state, _ImageRunner(command_runner), output_dir / "image"
    )
    if existing_contract and existing_contract.get("image_digest") != image_identity.digest:
        raise image.ImageContractError("server image changed since the original topology run")
    points = build_matrix(topology)
    prior_points = existing_contract.get("expected_points", [])
    provisional_points = (
        [str(value) for value in prior_points]
        if isinstance(prior_points, list)
        else []
    )
    provisional_points.extend(_point_id(point) for point in points)
    _write_json(
        output_dir / "run-contract.json",
        {
            "topologies": [*prior_topologies, topology],
            "image_digest": image_identity.digest,
            "expected_points": provisional_points,
            "formal_repetitions": 3,
            "raw_characterization_only": True,
        },
    )
    environment = RunEnvironment(
        restore_manifest=output_dir / "pre-run-state",
        image_digest=image_identity.digest,
    )
    performance_configmaps: set[str] = set()
    existing_points = existing_contract.get("expected_points", [])
    existing_stops = existing_contract.get("adaptive_stops", [])
    executed_points: list[str] = (
        list(existing_points) if isinstance(existing_points, list) else []
    )
    stop_decisions: list[dict[str, object]] = (
        list(existing_stops) if isinstance(existing_stops, list) else []
    )
    run_error: BaseException | None = None
    try:
        for input_tokens in INPUT_TOKENS:
            ordered_variants = tuple(
                dict.fromkeys(
                    point.variant
                    for point in points
                    if point.input_tokens == input_tokens
                )
            )
            rendered_variants: dict[str, runtime.RenderedResources] = {}
            rendered_paths: dict[str, tuple[Path, Path, Path]] = {}
            for variant in ordered_variants:
                representative = next(
                    point
                    for point in points
                    if point.input_tokens == input_tokens and point.variant == variant
                )
                rendered, paths = _write_rendered_block(
                    inputs,
                    representative,
                    image_identity.reference,
                    output_dir,
                )
                rendered_variants[variant] = rendered
                rendered_paths[variant] = paths
                performance_configmaps.add(
                    str(rendered.runtime_configmap["metadata"]["name"])
                )
            drift = runtime.validate_unique_difference(rendered_variants)
            if drift:
                raise RuntimeError("runtime variant drift: " + "; ".join(drift))
            for variant in ordered_variants:
                block_points = tuple(
                    point
                    for point in points
                    if point.input_tokens == input_tokens
                    and point.variant == variant
                )
                representative = block_points[0]
                _apply_variant_block(
                    command_runner,
                    rendered_paths[variant],
                    representative,
                    environment,
                    output_dir,
                )
                _run_and_save(
                    command_runner,
                    _canary_command(representative, environment),
                    output_dir
                    / "canaries"
                    / f"{topology}-{input_tokens}-{variant}.json",
                )
                for output_tokens in dict.fromkeys(
                    point.output_tokens for point in block_points
                ):
                    history: list[PointResult] = []
                    for point in (
                        selected
                        for selected in block_points
                        if selected.output_tokens == output_tokens
                    ):
                        point_root = output_dir / "points" / _point_id(point)
                        _write_json(
                            point_root / "identity.json",
                            {
                                "image_digest": image_identity.digest,
                                "variant": point.variant,
                                "topology": point.topology,
                                "input_tokens": point.input_tokens,
                                "output_tokens": point.output_tokens,
                                "concurrency": point.concurrency,
                            },
                        )
                        summaries = execute_point(
                            command_runner, point, output_dir, environment
                        )
                        executed_points.append(_point_id(point))
                        last = summaries[-1]
                        raw_metrics = last.get("metrics", {})
                        if not isinstance(raw_metrics, dict):
                            raise RuntimeError("formal summary metrics are malformed")
                        history.append(
                            PointResult(
                                float(raw_metrics["Request Throughput"]),
                                float(raw_metrics["E2EL P95"]),
                            )
                        )
                        decision = adaptive_stop(tuple(history), hard_failure=False)
                        if decision.stop:
                            stop_decisions.append(
                                {
                                    "topology": topology,
                                    "input_tokens": input_tokens,
                                    "output_tokens": output_tokens,
                                    "variant": variant,
                                    "after_concurrency": point.concurrency,
                                    "reason": decision.reason,
                                }
                            )
                            break
                stop_errors = _stop_engines(command_runner, environment)
                if stop_errors:
                    raise RuntimeError("; ".join(stop_errors))
    except BaseException as error:
        run_error = error
    restoration_errors = _restore_pre_run_state(
        command_runner, output_dir, environment, performance_configmaps
    )
    if run_error is None:
        _write_json(
            output_dir / "run-contract.json",
            {
                "topologies": [*prior_topologies, topology],
                "image_digest": image_identity.digest,
                "expected_points": executed_points,
                "formal_repetitions": 3,
                "raw_characterization_only": True,
                "adaptive_stops": stop_decisions,
            },
        )
    _write_checksums(output_dir)
    if run_error is not None:
        raise run_error
    if restoration_errors:
        raise RuntimeError("restoration failed: " + "; ".join(restoration_errors))


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


def _capture(
    command_runner: Runner, command: Command, attempt: Path, filename: str
) -> str:
    output = _invoke(command_runner, command, attempt)
    (attempt / "raw" / filename).write_text(output, encoding="utf-8")
    return output


def _master_empty_script() -> str:
    return '''from urllib.request import urlopen
text = urlopen("http://mooncake-master-service:9003/metrics", timeout=10).read().decode()
values = {}
for line in text.splitlines():
    fields = line.split()
    if len(fields) == 2:
        try:
            values[fields[0]] = float(fields[1])
        except ValueError:
            pass
assert values.get("master_key_count") == 0, values
assert values.get("master_allocated_bytes") == 0, values
print(text, end="")
'''


def _http_ok_script() -> str:
    return '''from urllib.request import urlopen
for url in (
    "http://vllm-proxy-service:8000/health",
    "http://vllm-proxy-service:8000/listEndPoints",
):
    with urlopen(url, timeout=30) as response:
        assert response.status == 200, (url, response.status)
        print(url, response.read().decode())
'''


def _client_python(environment: RunEnvironment, script: str) -> Command:
    return Command(
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
            "/client-tools/venv/bin/python",
            "-c",
            script,
        )
    )


def _sampled_aisbench_command(
    aisbench_argv: tuple[str, ...], environment: RunEnvironment
) -> Command:
    namespace = environment.namespace
    script = f'''set -euo pipefail
raw=$1
shift
mkdir -p "${{raw}}"
sample_prefill() {{
  while true; do
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
    kubectl exec -n {namespace} {environment.prefill_resource} \
      -c prefill-engine -- npu-smi info || true
    sleep 1
  done
}}
sample_decode() {{
  while true; do
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
    kubectl exec -n {namespace} {environment.decode_resource} \
      -c decode-engine -- npu-smi info || true
    sleep 1
  done
}}
sample_master() {{
  while true; do
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
    kubectl exec -n {namespace} {environment.client_pod} -c aisbench -- \
      chroot /performance-workspace/rootfs \
      /client-tools/venv/bin/python -c \
      'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics",timeout=5).read().decode(),end="")' \
      || true
    sleep 1
  done
}}
sample_client() {{
  while true; do
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
    kubectl top pod -n {namespace} {environment.client_pod} || true
    kubectl exec -n {namespace} {environment.client_pod} -c aisbench -- \
      sh -c 'cat /proc/net/dev; ss -s 2>/dev/null || true' || true
    sleep 1
  done
}}
sample_prefill >"${{raw}}/prefill-npu-timeseries.log" 2>&1 & p1=$!
sample_decode >"${{raw}}/decode-npu-timeseries.log" 2>&1 & p2=$!
sample_master >"${{raw}}/mooncake-timeseries.metrics" 2>&1 & p3=$!
sample_client >"${{raw}}/client-timeseries.log" 2>&1 & p4=$!
cleanup() {{
  kill "${{p1}}" "${{p2}}" "${{p3}}" "${{p4}}" 2>/dev/null || true
  wait "${{p1}}" "${{p2}}" "${{p3}}" "${{p4}}" 2>/dev/null || true
}}
trap cleanup EXIT INT TERM
"$@"
'''
    return Command(
        ("bash", "-c", script, "bash", "__LOCAL_RAW__", *aisbench_argv),
        sends_inference=True,
        description="aisbench",
    )


def _attempt_commands(
    point: WorkloadPoint,
    phase: str,
    request_count: int,
    remote_attempt: str,
    environment: RunEnvironment,
) -> tuple[Command, ...]:
    namespace = environment.namespace
    rootfs = "/performance-workspace/rootfs"
    chroot_attempt = f"/client-tools/runs/{remote_attempt}"
    host_attempt = f"{rootfs}{chroot_attempt}"
    fixture = (
        f"{rootfs}/client-tools/fixtures/tokens-{point.input_tokens}-c64/"
        f"{phase}.jsonl"
    )
    prepare_script = (
        "set -eu; test ! -e \"$1\"; mkdir -p \"$1\"; "
        "cp \"$2\" \"$1/dataset.jsonl\""
    )
    config_argv = (
        "kubectl",
        "exec",
        "-n",
        namespace,
        environment.client_pod,
        "-c",
        "aisbench",
        "--",
        "chroot",
        rootfs,
        "env",
        "TORCH_DEVICE_BACKEND_AUTOLOAD=0",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH=/client-tools/tooling",
        "/client-tools/venv/bin/python",
        "-m",
        "performance.fixtures",
        "config",
        "--topology",
        point.topology,
        "--input-tokens",
        str(point.input_tokens),
        "--output-tokens",
        str(point.output_tokens),
        "--variant",
        point.variant,
        "--concurrency",
        str(point.concurrency),
        "--dataset",
        f"{chroot_attempt}/dataset.jsonl",
        "--request-count",
        str(request_count),
        "--output",
        f"{chroot_attempt}/config.py",
    )
    aisbench_argv = (
        "kubectl",
        "exec",
        "-n",
        namespace,
        environment.client_pod,
        "-c",
        "aisbench",
        "--",
        "chroot",
        rootfs,
        "env",
        "TORCH_DEVICE_BACKEND_AUTOLOAD=0",
        "PYTHONDONTWRITEBYTECODE=1",
        "/client-tools/venv/bin/ais_bench",
        f"{chroot_attempt}/config.py",
    )
    master_empty = _client_python(environment, _master_empty_script())
    reconnect = _client_python(environment, _http_ok_script())
    return (
        Command(
            (
                "kubectl",
                "rollout",
                "restart",
                "-n",
                namespace,
                environment.master_resource,
            ),
            mutates_server=True,
            description="reset-master",
        ),
        Command(
            (
                "kubectl",
                "rollout",
                "status",
                "-n",
                namespace,
                environment.master_resource,
                "--timeout=300s",
            ),
            description="wait-master",
        ),
        Command(master_empty.argv, description="assert-master-empty"),
        Command(reconnect.argv, description="assert-engine-reconnect"),
        Command(
            (
                "kubectl",
                "exec",
                "-n",
                namespace,
                environment.client_pod,
                "-c",
                "aisbench",
                "--",
                "sh",
                "-c",
                prepare_script,
                "sh",
                host_attempt,
                fixture,
            ),
            description="prepare-aisbench-attempt",
        ),
        Command(config_argv, description="render-aisbench-config"),
        _sampled_aisbench_command(aisbench_argv, environment),
        Command(
            (
                "kubectl",
                "cp",
                "-n",
                namespace,
                "-c",
                "aisbench",
                f"{environment.client_pod}:{host_attempt}/.",
                "__LOCAL_RAW__",
            ),
            description="archive-aisbench",
        ),
    )


def _diagnostic_commands(environment: RunEnvironment) -> tuple[tuple[Command, str], ...]:
    namespace = environment.namespace
    metrics = _client_python(
        environment,
        'from urllib.request import urlopen; print(urlopen('
        '"http://mooncake-master-service:9003/metrics", timeout=10).read().decode(), end="")',
    )
    return (
        (Command(metrics.argv, description="mooncake-metrics"), "mooncake.metrics"),
        (
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    namespace,
                    environment.prefill_resource,
                    "-c",
                    "prefill-engine",
                    "--",
                    "cat",
                    "/tmp/vllm-prefill.log",
                ),
                description="prefill-log",
            ),
            "vllm-prefill.log",
        ),
        (
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    namespace,
                    environment.decode_resource,
                    "-c",
                    "decode-engine",
                    "--",
                    "cat",
                    "/tmp/vllm-decode.log",
                ),
                description="decode-log",
            ),
            "vllm-decode.log",
        ),
        (
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    namespace,
                    environment.prefill_resource,
                    "-c",
                    "prefill-engine",
                    "--",
                    "npu-smi",
                    "info",
                ),
                description="prefill-npu",
            ),
            "prefill-npu.txt",
        ),
        (
            Command(
                (
                    "kubectl",
                    "exec",
                    "-n",
                    namespace,
                    environment.decode_resource,
                    "-c",
                    "decode-engine",
                    "--",
                    "npu-smi",
                    "info",
                ),
                description="decode-npu",
            ),
            "decode-npu.txt",
        ),
        (
            Command(
                (
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    namespace,
                    "-l",
                    "app in (prefill,decode)",
                    "-o",
                    "json",
                ),
                description="engine-pods",
            ),
            "engine-pods.json",
        ),
    )


def execute_point(
    command_runner: Runner,
    point: WorkloadPoint,
    output_dir: Path,
    environment: RunEnvironment = RunEnvironment(),
) -> tuple[dict[str, object], ...]:
    point_root = output_dir / "points" / _point_id(point)
    warmup_count, formal_count, repetitions = sample_counts(point.concurrency)
    phases = [("warmup", warmup_count)] + [
        (f"formal-{index}", formal_count) for index in range(1, repetitions + 1)
    ]
    current_attempt = point_root
    formal_summaries: list[dict[str, object]] = []
    try:
        for phase, request_count in phases:
            current_attempt = _new_attempt(point_root, phase)
            attempt_token = hashlib.sha256(
                str(current_attempt.resolve()).encode("utf-8")
            ).hexdigest()[:16]
            remote_attempt = f"{_point_id(point)}/{phase}/{attempt_token}"
            for command in _attempt_commands(
                point, phase, request_count, remote_attempt, environment
            ):
                if command.description in {"aisbench", "archive-aisbench"}:
                    argv = tuple(
                        str(current_attempt / "raw") if value == "__LOCAL_RAW__" else value
                        for value in command.argv
                    )
                    command = Command(argv, description=command.description)
                _invoke(command_runner, command, current_attempt)
            for command, filename in _diagnostic_commands(environment):
                _capture(command_runner, command, current_attempt, filename)
            if environment.image_digest:
                summary = report.summarize_aisbench_attempt(
                    current_attempt / "raw",
                    point,
                    request_count,
                    environment.image_digest,
                )
                _write_json(current_attempt / "raw" / "summary.json", summary)
                if summary.get("valid") is not True:
                    raise RuntimeError(
                        "invalid AISBench attempt: "
                        + "; ".join(str(error) for error in summary.get("errors", []))
                    )
                if phase.startswith("formal-"):
                    formal_summaries.append(summary)
    except Exception as error:
        _append(
            current_attempt / "state.jsonl",
            {"status": "failed", "error": type(error).__name__, "message": str(error)},
        )
        command_runner.run(
            Command(
                (
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    environment.namespace,
                    "-o",
                    "wide",
                ),
                description="capture-failure",
            )
        )
        restore_argv = (
            "kubectl",
            "apply",
            "-n",
            environment.namespace,
            "-f",
            str(environment.restore_manifest or output_dir / "pre-run-state"),
        )
        command_runner.run(
            Command(
                restore_argv,
                mutates_server=True,
                description="restore-pre-run-state",
            )
        )
        raise
    return tuple(formal_summaries)


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
    run(
        command_runner,
        state,
        args.output,
        topology=args.topology,
        resume=args.resume,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
