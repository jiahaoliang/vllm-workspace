#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "Status And Scope",
    "Original Validation",
    "Identity",
    "Gate Results",
    "Changes From Original Validation",
    "Script Provenance",
    "Live Reproduction Runbook",
    "Offline Evidence Recheck",
    "Attempts And Failures",
    "Limitations And Final State",
)
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
BASH_RE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
ASSIGNMENT_RE = re.compile(r"(?m)^\s*(?:export\s+|readonly\s+)?([A-Z][A-Z0-9_]*)=(?:[^\n]+)$")
VARIABLE_RE = re.compile(r"\$(?:\{([A-Z][A-Z0-9_]*)[^}]*\}|([A-Z][A-Z0-9_]*))")
CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:API[_-]?KEY|ACCESS[_-]?TOKEN|PASSWORD|SECRET)\s*=\s*(?!\$|<redacted>)[^\s`]+"
)
PLACEHOLDER_RE = re.compile(r"(?i)\b(?:TODO|TBD|PLACEHOLDER|REPLACE_ME)\b")


def _tracked_files(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return set(result.stdout.splitlines())


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)", text
    )
    return match.group(1) if match else ""


def _resolve_namespace(value: str, assignments: dict[str, str]) -> str:
    value = value.strip("'\"")
    variable = re.fullmatch(r"\$\{?([A-Z][A-Z0-9_]*)\}?", value)
    if variable:
        return assignments.get(variable.group(1), value).strip("'\"")
    return value


def _check_kubectl_namespaces(bash: str, errors: list[str]) -> None:
    assignments = {
        name: value.strip()
        for name, value in re.findall(
            r"(?m)^\s*(?:export\s+|readonly\s+)?([A-Z][A-Z0-9_]*)=([^\s#]+)", bash
        )
    }
    logical_lines = bash.replace("\\\n", " ").splitlines()
    for number, raw_line in enumerate(logical_lines, 1):
        line = raw_line.strip()
        if not line.startswith("kubectl "):
            continue
        if re.match(r"kubectl\s+(?:config\b|get\s+(?:node|nodes|namespace|namespaces)\b)", line):
            continue
        namespace_match = re.search(r"(?:^|\s)(?:-n|--namespace(?:=|\s))\s*([^\s]+)", line)
        if namespace_match is None:
            errors.append(f"bash line {number}: kubectl command lacks an explicit namespace")
            continue
        actual = _resolve_namespace(namespace_match.group(1), assignments)
        expected = "default" if "buildkitd" in line else "liangjiahao"
        if actual != expected:
            errors.append(
                f"bash line {number}: kubectl namespace must be {expected}, got {actual}"
            )


def validate_report(
    report_path: Path,
    repo_root: Path,
    tracked_files: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    text = report_path.read_text(encoding="utf-8")
    tracked = _tracked_files(repo_root) if tracked_files is None else tracked_files

    for heading in REQUIRED_SECTIONS:
        if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", text):
            errors.append(f"missing required section: {heading}")

    if PLACEHOLDER_RE.search(text):
        errors.append("report contains a placeholder token")
    if CREDENTIAL_RE.search(text):
        errors.append("report contains a credential-like assignment")
    if re.search(r"(?m)(?:curl|Evidence(?: path)?\s*:)\s+(?:/tmp|/workspace|/root)/", text):
        errors.append("report contains an absolute evidence path")

    report_parent = report_path.parent.resolve()
    root = repo_root.resolve()
    original_links = []
    for raw_target in LINK_RE.findall(text):
        target = raw_target.strip().split("#", 1)[0]
        if not target or re.match(r"(?:https?|mailto):", target):
            continue
        if target.startswith("/"):
            errors.append(f"absolute local link is forbidden: {target}")
            continue
        resolved = (report_parent / target).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"local link escapes the repository: {target}")
            continue
        if relative not in tracked:
            errors.append(f"local link is not tracked: {target}")
        if not resolved.exists():
            errors.append(f"local link does not exist: {target}")
        if target.endswith(".md"):
            original_links.append(target)
    if not original_links or not LINK_RE.search(_section(text, "Original Validation")):
        errors.append("Original Validation must link a tracked Markdown report")

    bash_blocks = BASH_RE.findall(text)
    if not bash_blocks:
        errors.append("Live Reproduction Runbook must contain a Bash command block")
    all_bash = "\n".join(bash_blocks)
    if "BUILDKIT_HOST" in all_bash and "kube-pod://buildkitd?namespace=default" not in all_bash:
        errors.append("BUILDKIT_HOST must name the default namespace explicitly")
    _check_kubectl_namespaces(all_bash, errors)

    assignments = set(ASSIGNMENT_RE.findall(all_bash))
    variables = {left or right for left, right in VARIABLE_RE.findall(all_bash)}
    unexplained = sorted(variables - assignments - {"PATH", "PWD"})
    if unexplained:
        errors.append(f"unexplained Bash variables: {', '.join(unexplained)}")

    required_evidence_tokens = {
        "evidence commit": re.compile(r"(?i)Evidence commit.*[0-9a-f]{40}"),
        "script checksum": re.compile(r"(?i)Script SHA256.*[0-9a-f]{64}"),
        "SHA256SUMS": re.compile(r"SHA256SUMS"),
        "checksum replay": re.compile(r"sha256sum\s+-c"),
        "jq assertion": re.compile(r"jq\s+-e"),
        "Git tracking replay": re.compile(r"git\s+ls-files\s+--error-unmatch"),
    }
    for label, pattern in required_evidence_tokens.items():
        if pattern.search(text) is None:
            errors.append(f"missing {label}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed validation report checker")
    parser.add_argument("report", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_report(args.report.resolve(), args.repo_root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASSED: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
