from __future__ import annotations

import sys
import hashlib
import json
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from performance import handoff  # noqa: E402


READY_SCOPE = """## Authorized Performance Scope

- `backend=mooncake` and `use_layerwise=true`;
- `layerwise_num_shared_buffers=3`;
- `kv_producer`;
- no-reuse pure-consumer Decode companion;
- namespace `liangjiahao`.
"""


def test_waiting_handoff_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: WAITING_FOR_FUNCTIONAL_VALIDATION
ready: false
placeholders_remaining: true
generation: 0
updated_at: 2026-08-08T11:47:33+08:00
---

# Handoff
""",
        encoding="utf-8",
    )

    state = handoff.parse_handoff(path)

    assert handoff.validate_readiness(state) == [
        "status is not READY_FOR_PERFORMANCE_VALIDATION",
        "ready is not true",
        "generation must be greater than zero",
        "placeholders_remaining is not false",
    ]


def test_ready_handoff_requires_decode_companion_authorization(
    tmp_path: Path,
) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T12:00:00+08:00
---

# Handoff

## Authorized Performance Scope

- `backend=mooncake` and `use_layerwise=true`;
- `layerwise_num_shared_buffers=3`;
- `kv_producer` and `kv_both` roles;
- namespace `liangjiahao`.
""",
        encoding="utf-8",
    )

    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)

    assert any("no-reuse pure-consumer Decode companion" in error for error in errors)


def test_ready_handoff_rejects_non_pass_required_gate(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T12:00:00+08:00
---

# Handoff

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | FAIL | evidence/ut.txt |

"""
        + READY_SCOPE,
        encoding="utf-8",
    )

    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)

    assert "required functional gate is not PASS: Focused CPU/mock UT" in errors


def test_bad_evidence_checksum_is_rejected(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence" / "functional"
    evidence.mkdir(parents=True)
    identity = evidence / "identity.json"
    identity.write_text('{"generation": 1}\n', encoding="utf-8")
    identity_digest = hashlib.sha256(identity.read_bytes()).hexdigest()
    manifest = evidence / "SHA256SUMS"
    manifest.write_text(f"{identity_digest}  identity.json\n", encoding="utf-8")
    manifest_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T12:00:00+08:00
---

# Handoff

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | evidence/functional |
| Root `SHA256SUMS` path | evidence/functional/SHA256SUMS |
| Root `SHA256SUMS` digest | """
        + manifest_digest
        + """ |

"""
        + READY_SCOPE,
        encoding="utf-8",
    )
    identity.write_text("changed\n", encoding="utf-8")

    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)

    assert any("SHA256SUMS replay failed" in error for error in errors)


def test_ready_handoff_requires_all_identity_tables(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T12:00:00+08:00
---

# Handoff

"""
        + READY_SCOPE,
        encoding="utf-8",
    )

    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)

    assert "Source Identity table is incomplete" in errors
    assert "Image Identity table is incomplete" in errors
    assert "Functional Acceptance table is incomplete" in errors
    assert "Evidence Identity table is incomplete" in errors


def test_check_cli_writes_one_json_result(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(
        """---
schema_version: 1
status: WAITING_FOR_FUNCTIONAL_VALIDATION
ready: false
placeholders_remaining: true
generation: 0
updated_at: 2026-08-08T11:47:33+08:00
---
""",
        encoding="utf-8",
    )

    exit_code = handoff.main(
        ["check", "--handoff", str(path), "--workspace", str(tmp_path)]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    result = json.loads(captured.out)

    assert exit_code == 1
    assert result["generation"] == 0
    assert result["status"] == "WAITING_FOR_FUNCTIONAL_VALIDATION"
    assert result["valid"] is False


def test_source_commit_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    rows = "\n".join(
        f"| {component} | branch | {'a' * 40} | origin/main={'a' * 40} |"
        for component in handoff.REQUIRED_COMPONENTS
    )
    path.write_text(
        """---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T12:00:00+08:00
---

# Handoff

## Source Identity

| Component | Branch / role | Commit | Remote equality |
| --- | --- | --- | --- |
"""
        + rows
        + "\n\n"
        + READY_SCOPE,
        encoding="utf-8",
    )

    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)

    assert any("source HEAD mismatch: control repo" in error for error in errors)
