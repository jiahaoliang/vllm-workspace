from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from performance.handoff import HandoffError, HandoffState, validate_readiness


class ImageContractError(HandoffError):
    """Raised when the handed-off image does not replay exactly."""


class CommandRunner(Protocol):
    def run(self, command: tuple[str, ...]) -> str: ...


@dataclass(frozen=True)
class ImageIdentity:
    reference: str
    digest: str
    platform: str
    base_reference: str
    base_digest: str
    patched_file: str
    patched_file_sha256: str
    source_labels: dict[str, str]
    mode: str


LABEL_FIELDS = {
    "org.opencontainers.image.vllm.commit": "vLLM source label",
    "org.opencontainers.image.vllm-ascend.commit": "vLLM-Ascend source label",
    "org.opencontainers.image.mooncake.commit": "Mooncake source label",
}


def _inspect(reference: str, runner: CommandRunner) -> dict[str, object]:
    raw = runner.run(
        ("nerdctl", "--namespace", "k8s.io", "image", "inspect", reference)
    )
    parsed = json.loads(raw)
    if (
        not isinstance(parsed, list)
        or len(parsed) != 1
        or not isinstance(parsed[0], dict)
    ):
        raise ImageContractError("nerdctl image inspect did not return one image")
    return parsed[0]


def verify_import(
    reference: str,
    patched_file: str,
    expected_sha256: str,
    runner: CommandRunner,
) -> dict[str, str]:
    script = (
        "import hashlib,json; from pathlib import Path; "
        f"p=Path({patched_file!r}).resolve(); "
        "print(json.dumps({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
    )
    raw = runner.run(
        (
            "nerdctl",
            "--namespace",
            "k8s.io",
            "run",
            "--rm",
            "--entrypoint",
            "python3",
            reference,
            "-c",
            script,
        )
    )
    result = json.loads(raw)
    if result.get("path") != patched_file or result.get("sha256") != expected_sha256:
        raise ImageContractError("patched import path or SHA256 does not match handoff")
    return {"path": result["path"], "sha256": result["sha256"]}


def resolve_server_image(
    state: HandoffState,
    runner: CommandRunner,
    output_dir: Path,
) -> ImageIdentity:
    readiness_errors = validate_readiness(state)
    if readiness_errors:
        raise ImageContractError("handoff is not ready: " + "; ".join(readiness_errors))
    fields = state.image_fields
    if fields.get("Image delivery mode") == "patch":
        patch_sha = fields.get("Patched file SHA256", "")
        if not patch_sha:
            raise ImageContractError("patch mode requires Patched file SHA256")
        patch_source = fields.get("Patch source path", "")
        if not patch_source:
            raise ImageContractError("patch mode requires Patch source path")
        source_path = Path(patch_source)
        if not source_path.is_file():
            raise ImageContractError(f"patch source is unavailable: {source_path}")
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != patch_sha:
            raise ImageContractError("patch source does not match Patched file SHA256")
        name = f"layerwise-performance-patch-g{state.generation}"
        base = fields.get("Base image reference", "")
        derived = fields.get("Derived image reference", "")
        target = fields.get("Patched file path", "")
        if not all((base, derived, target)):
            raise ImageContractError("patch mode image fields are incomplete")
        try:
            runner.run(
                (
                    "nerdctl",
                    "--namespace",
                    "k8s.io",
                    "create",
                    "--name",
                    name,
                    base,
                )
            )
            runner.run(
                (
                    "nerdctl",
                    "--namespace",
                    "k8s.io",
                    "cp",
                    str(source_path),
                    f"{name}:{target}",
                )
            )
            runner.run(
                (
                    "nerdctl",
                    "--namespace",
                    "k8s.io",
                    "commit",
                    name,
                    derived,
                )
            )
        finally:
            runner.run(
                (
                    "nerdctl",
                    "--namespace",
                    "k8s.io",
                    "rm",
                    "-f",
                    name,
                )
            )
    reference = fields.get("Derived image reference", "")
    digest = fields.get("Derived manifest digest", "")
    if not reference or not digest:
        raise ImageContractError(
            "ready-image mode requires derived reference and digest"
        )
    inspected = _inspect(reference, runner)
    platform = f"{inspected.get('Os', '')}/{inspected.get('Architecture', '')}"
    if platform != fields.get("Platform") or platform != "linux/arm64":
        raise ImageContractError(f"server image platform mismatch: {platform}")
    repo_digests = inspected.get("RepoDigests", [])
    if not isinstance(repo_digests, list) or not any(
        str(value).endswith(f"@{digest}") for value in repo_digests
    ):
        raise ImageContractError("derived manifest digest does not match image inspect")
    config = inspected.get("Config", {})
    labels = config.get("Labels", {}) if isinstance(config, dict) else {}
    if not isinstance(labels, dict):
        raise ImageContractError("image source labels are unavailable")
    expected_labels = {
        key: fields.get(field, "") for key, field in LABEL_FIELDS.items()
    }
    if any(labels.get(key) != value for key, value in expected_labels.items()):
        raise ImageContractError("image source labels do not match handoff")
    patched_file = fields.get("Patched file path", "")
    patched_sha = fields.get("Patched file SHA256", "")
    verify_import(reference, patched_file, patched_sha, runner)
    identity = ImageIdentity(
        reference=reference,
        digest=digest,
        platform=platform,
        base_reference=fields.get("Base image reference", ""),
        base_digest=fields.get("Base manifest digest", ""),
        patched_file=patched_file,
        patched_file_sha256=patched_sha,
        source_labels=expected_labels,
        mode="patch" if fields.get("Image delivery mode") == "patch" else "ready-image",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "image-resolution.json").write_text(
        json.dumps(asdict(identity), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return identity
