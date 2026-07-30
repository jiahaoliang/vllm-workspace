from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER_PATH = Path(__file__).resolve().parents[1] / "check-validation-report.py"
SPEC = importlib.util.spec_from_file_location("check_validation_report", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


def valid_report() -> str:
    return """# Validation Report

## Status And Scope

Status: passed. Correctness is limited to the frozen source and image identity.

## Original Validation

[Original report](original.md)

## Identity

| Field | Value |
| --- | --- |
| Evidence commit | `0123456789abcdef0123456789abcdef01234567` |
| Script SHA256 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |

## Gate Results

| Gate | Expected | Actual | Exit code | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| G0 | exact identity | exact identity | 0 | PASSED | [summary](evidence/summary.json) |

## Changes From Original Validation

| Original | Current | Reason | Correctness impact | Commit/evidence |
| --- | --- | --- | --- | --- |
| old image | pinned image | rebased source | identity is exact | [summary](evidence/summary.json) |

## Script Provenance

Original and current script revisions and SHA256 values were compared above.

## Live Reproduction Runbook

Inputs are assigned literally in the commands below.

```bash
REPORT_NAMESPACE=liangjiahao
kubectl get pods -n "${REPORT_NAMESPACE}"
```

Expected output: the named validation Pods are Running. State change: none. Final state: retained.

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/test/SHA256SUMS
jq -e '.status == "passed"' features/kv-pool-layerwise-reuse/evidence/test/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/test/summary.json
```

## Attempts And Failures

The final attempt passed; no earlier attempt was made.

## Limitations And Final State

The claim does not extend beyond the frozen identities. Workloads are retained with engines stopped.
"""


def create_fixture(tmp_path: Path) -> tuple[Path, set[str]]:
    report = tmp_path / "report.md"
    (tmp_path / "original.md").write_text("# Original\n")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "summary.json").write_text('{"status":"passed"}\n')
    report.write_text(valid_report())
    tracked = {"report.md", "original.md", "evidence/summary.json"}
    return report, tracked


class ValidationReportCheckerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.report, self.tracked = create_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_valid_report_passes_contract(self):
        self.assertEqual(checker.validate_report(self.report, self.root, self.tracked), [])

    def test_missing_section_and_untracked_link_fail_closed(self):
        self.report.write_text(valid_report().replace("## Script Provenance\n", "").replace("evidence/summary.json", "evidence/missing.json"))
        errors = checker.validate_report(self.report, self.root, self.tracked)
        self.assertTrue(any("Script Provenance" in error for error in errors))
        self.assertTrue(any("not tracked" in error for error in errors))

    def test_namespace_placeholder_absolute_path_and_secret_are_rejected(self):
        self.report.write_text(
            valid_report().replace(
                'kubectl get pods -n "${REPORT_NAMESPACE}"',
                "kubectl get pods\n# TODO\ncurl /tmp/private-evidence\nexport API_KEY=secret-value",
            )
        )
        errors = checker.validate_report(self.report, self.root, self.tracked)
        self.assertTrue(any("namespace" in error for error in errors))
        self.assertTrue(any("placeholder" in error for error in errors))
        self.assertTrue(any("absolute evidence path" in error for error in errors))
        self.assertTrue(any("credential" in error for error in errors))

    def test_cli_returns_nonzero_for_invalid_report(self):
        self.report.write_text("# incomplete\n")
        result = subprocess.run(
            [sys.executable, str(CHECKER_PATH), str(self.report), "--repo-root", str(self.root)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Status And Scope", result.stdout)


if __name__ == "__main__":
    unittest.main()
