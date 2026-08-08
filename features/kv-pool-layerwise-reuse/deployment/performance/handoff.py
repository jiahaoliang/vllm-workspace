from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HandoffError(ValueError):
    """Raised when the handoff document cannot be parsed."""


@dataclass(frozen=True)
class HandoffState:
    path: Path
    digest: str
    status: str
    ready: bool
    generation: int
    placeholders_remaining: bool
    authorized_scope: tuple[str, ...]
    gates: dict[str, str]
    evidence_fields: dict[str, str]
    source_rows: dict[str, dict[str, str]]
    image_fields: dict[str, str]
    contains_pending: bool


REQUIRED_SCOPE = (
    "backend=mooncake",
    "use_layerwise=true",
    "layerwise_num_shared_buffers=3",
    "kv_producer",
    "no-reuse pure-consumer Decode companion",
    "liangjiahao",
)

REQUIRED_COMPONENTS = (
    "control repo",
    "repos/vllm",
    "repos/vllm-ascend",
    "repos/Mooncake",
)
HANDOFF_TRANSITION_PATH = (
    "features/kv-pool-layerwise-reuse/performance-validation-handoff.md"
)
REQUIRED_GATES = (
    "Focused CPU/mock UT",
    "Complete AscendStore CPU/mock UT",
    "Ruff",
    "Python compilation",
    "git diff --check",
    "kv_producer Mooncake/NPU correctness",
    "kv_both Mooncake/NPU correctness",
    "Physical-slot/memory-factor proof",
    "Reuse-mate save-gate timeout/corruption check",
    "Final Mooncake resource cleanup",
)
REQUIRED_IMAGE_FIELDS = (
    "Base image reference",
    "Base manifest digest",
    "Patched file path",
    "Patched file SHA256",
    "Patched source commit",
    "Derived image reference",
    "Platform",
    "Derived manifest digest",
    "vLLM source label",
    "vLLM-Ascend source label",
    "Mooncake source label",
    "Derived-image/run ID",
)
REQUIRED_EVIDENCE_FIELDS = (
    "Evidence root",
    "Root SHA256SUMS path",
    "Root SHA256SUMS digest",
    "Functional validation report",
    "Validation config snapshot",
)


def _scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    try:
        return int(normalized)
    except ValueError:
        return normalized


def _front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise HandoffError("handoff must start with YAML front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise HandoffError("handoff front matter is not terminated") from error

    values: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip():
            raise HandoffError(f"invalid front matter line: {line!r}")
        name = key.strip()
        if name in values:
            raise HandoffError(f"duplicate front matter field: {name}")
        values[name] = _scalar(value)
    return values


def parse_handoff(path: Path) -> HandoffState:
    content = path.read_bytes()
    text = content.decode("utf-8")
    values = _front_matter(text)
    required = {
        "status": str,
        "ready": bool,
        "generation": int,
        "placeholders_remaining": bool,
    }
    for name, expected_type in required.items():
        value = values.get(name)
        if type(value) is not expected_type:
            raise HandoffError(
                f"front matter field {name!r} must be {expected_type.__name__}"
            )
    return HandoffState(
        path=path,
        digest=hashlib.sha256(content).hexdigest(),
        status=values["status"],
        ready=values["ready"],
        generation=values["generation"],
        placeholders_remaining=values["placeholders_remaining"],
        authorized_scope=_section_lines(text, "Authorized Performance Scope"),
        gates=_functional_gates(text),
        evidence_fields=_field_table(text, "Evidence Identity"),
        source_rows=_source_rows(text),
        image_fields=_field_table(text, "Image Identity"),
        contains_pending="PENDING" in text,
    )


def _section_lines(text: str, heading: str) -> tuple[str, ...]:
    lines = text.splitlines()
    marker = f"## {heading}"
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return ()
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            section.append(line.strip())
    return tuple(section)


def _table(text: str, heading: str) -> list[dict[str, str]]:
    lines = _section_lines(text, heading)
    table_lines = [line for line in lines if line.startswith("|")]
    if not table_lines:
        return []
    rows = [
        [cell.strip().replace("`", "") for cell in line.strip("|").split("|")]
        for line in table_lines
    ]
    headers = rows[0]
    if len(headers) != len(set(headers)):
        raise HandoffError(f"duplicate table header in {heading}")
    values: list[dict[str, str]] = []
    for row in rows[2:]:
        if len(row) != len(headers):
            raise HandoffError(f"malformed table row in {heading}")
        values.append(dict(zip(headers, row)))
    return values


def _functional_gates(text: str) -> dict[str, str]:
    gates: dict[str, str] = {}
    for row in _table(text, "Functional Acceptance"):
        gate = row.get("Gate", "")
        required = row.get("Required result", "")
        actual = row.get("Actual result", "")
        if not gate:
            raise HandoffError("Functional Acceptance row is missing Gate")
        if gate in gates:
            raise HandoffError(f"duplicate functional gate: {gate}")
        if required == "PASS":
            gates[gate] = actual
    return gates


def _field_table(text: str, heading: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in _table(text, heading):
        field = row.get("Field", "")
        value = row.get("Value", "")
        if not field:
            raise HandoffError(f"{heading} row is missing Field")
        if field in fields:
            raise HandoffError(f"duplicate field in {heading}: {field}")
        fields[field] = value
    return fields


def _source_rows(text: str) -> dict[str, dict[str, str]]:
    source_rows: dict[str, dict[str, str]] = {}
    for row in _table(text, "Source Identity"):
        component = row.get("Component", "")
        if not component:
            raise HandoffError("Source Identity row is missing Component")
        if component in source_rows:
            raise HandoffError(f"duplicate Source Identity component: {component}")
        source_rows[component] = row
    return source_rows


def _workspace_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else workspace / path).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        raise HandoffError(f"handoff path escapes workspace: {value}")
    return resolved


def _validate_evidence(state: HandoffState, workspace: Path) -> list[str]:
    if not state.evidence_fields:
        return []
    manifest_value = state.evidence_fields.get("Root SHA256SUMS path", "")
    expected_digest = state.evidence_fields.get("Root SHA256SUMS digest", "")
    if not manifest_value or not expected_digest:
        return ["Evidence Identity is missing SHA256SUMS path or digest"]
    try:
        manifest = _workspace_path(workspace, manifest_value)
        content = manifest.read_bytes()
    except (OSError, HandoffError) as error:
        return [f"SHA256SUMS is unavailable: {error}"]
    if hashlib.sha256(content).hexdigest() != expected_digest:
        return ["Root SHA256SUMS digest does not match"]
    errors: list[str] = []
    for line_number, line in enumerate(content.decode("utf-8").splitlines(), 1):
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name:
            errors.append(f"malformed SHA256SUMS line {line_number}")
            continue
        try:
            artifact = _workspace_path(manifest.parent, name.lstrip("*"))
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        except (OSError, HandoffError):
            actual = ""
        if actual != digest:
            errors.append(f"SHA256SUMS replay failed: {name}")
    return errors


def _validate_sources(state: HandoffState, workspace: Path) -> list[str]:
    errors: list[str] = []
    for component in REQUIRED_COMPONENTS:
        row = state.source_rows.get(component)
        if not row:
            continue
        expected = row.get("Commit", "")
        repository = workspace if component == "control repo" else workspace / component
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        actual = result.stdout.strip() if result.returncode == 0 else "unavailable"
        control_transition_error = None
        if component == "control repo" and actual != expected:
            revision = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "rev-list",
                    "--parents",
                    "-n",
                    "1",
                    "HEAD",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            revision_parts = revision.stdout.strip().split()
            is_direct_child = (
                revision.returncode == 0
                and len(revision_parts) == 2
                and revision_parts[1] == expected
            )
            if is_direct_child:
                changed = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repository),
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        "HEAD",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                changed_paths = tuple(changed.stdout.splitlines())
                if changed.returncode != 0 or changed_paths != (
                    HANDOFF_TRANSITION_PATH,
                ):
                    control_transition_error = (
                        "control repo transition is not handoff-only: "
                        + ", ".join(changed_paths)
                    )
                else:
                    actual = expected
        if control_transition_error:
            errors.append(control_transition_error)
        elif actual != expected:
            errors.append(
                f"source HEAD mismatch: {component}: expected {expected}, got {actual}"
            )
        remote_equality = row.get("Remote equality", "")
        if expected and expected not in remote_equality:
            errors.append(f"remote equality does not freeze source commit: {component}")
    return errors


def validate_readiness(state: HandoffState) -> list[str]:
    errors = []
    if state.status != "READY_FOR_PERFORMANCE_VALIDATION":
        errors.append("status is not READY_FOR_PERFORMANCE_VALIDATION")
    if state.ready is not True:
        errors.append("ready is not true")
    if state.generation <= 0:
        errors.append("generation must be greater than zero")
    if state.placeholders_remaining is not False:
        errors.append("placeholders_remaining is not false")
    return errors


def validate_handoff(state: HandoffState, workspace: Path) -> list[str]:
    errors = validate_readiness(state)
    scope = "\n".join(state.authorized_scope)
    for required in REQUIRED_SCOPE:
        if required not in scope:
            errors.append(f"authorized scope is missing {required}")
    if state.contains_pending:
        errors.append("handoff still contains PENDING placeholders")
    if any(
        component not in state.source_rows
        or not state.source_rows[component].get("Commit")
        or state.source_rows[component].get("Commit") == "PENDING"
        or not state.source_rows[component].get("Remote equality")
        or state.source_rows[component].get("Remote equality") == "PENDING"
        for component in REQUIRED_COMPONENTS
    ):
        errors.append("Source Identity table is incomplete")
    if any(gate not in state.gates for gate in REQUIRED_GATES):
        errors.append("Functional Acceptance table is incomplete")
    if any(
        not state.image_fields.get(field) or state.image_fields.get(field) == "PENDING"
        for field in REQUIRED_IMAGE_FIELDS
    ):
        errors.append("Image Identity table is incomplete")
    if any(
        not state.evidence_fields.get(field)
        or state.evidence_fields.get(field) == "PENDING"
        for field in REQUIRED_EVIDENCE_FIELDS
    ):
        errors.append("Evidence Identity table is incomplete")
    for gate, actual in state.gates.items():
        if actual != "PASS":
            errors.append(f"required functional gate is not PASS: {gate}")
    errors.extend(_validate_sources(state, workspace))
    errors.extend(_validate_evidence(state, workspace))
    return errors


def _result(state: HandoffState, workspace: Path) -> dict[str, Any]:
    stat = state.path.stat()
    errors = validate_handoff(state, workspace)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "path": str(state.path),
        "inode": stat.st_ino,
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "sha256": state.digest,
        "generation": state.generation,
        "status": state.status,
        "ready": state.ready,
        "errors": errors,
        "valid": not errors,
    }


def wait_for_ready(
    path: Path,
    workspace: Path,
    poll_seconds: float,
    observations: Path,
) -> HandoffState:
    observations.parent.mkdir(parents=True, exist_ok=True)
    while True:
        state = parse_handoff(path)
        result = _result(state, workspace)
        with observations.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if result["valid"]:
            return state
        time.sleep(poll_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "wait"):
        command = subparsers.add_parser(name)
        command.add_argument("--handoff", type=Path, required=True)
        command.add_argument("--workspace", type=Path, required=True)
        if name == "wait":
            command.add_argument("--observations", type=Path, required=True)
            command.add_argument("--poll-seconds", type=float, default=10.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "wait":
        state = wait_for_ready(
            args.handoff,
            args.workspace,
            args.poll_seconds,
            args.observations,
        )
        print(json.dumps(_result(state, args.workspace), sort_keys=True))
        return 0
    state = parse_handoff(args.handoff)
    result = _result(state, args.workspace)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
