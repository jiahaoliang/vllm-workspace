from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


FEATURE_DIR = Path(__file__).resolve().parents[2]
DEPLOYMENT_DIR = FEATURE_DIR / "deployment"
ROOT = FEATURE_DIR.parents[1]
IDENTITY = json.loads((DEPLOYMENT_DIR / "validation-identity.json").read_text())


def read(relative: str) -> str:
    return (FEATURE_DIR / relative).read_text(encoding="utf-8")


class ValidationIdentityTest(unittest.TestCase):
    def test_workspace_lock_and_dockerfile_match_frozen_source_identity(self):
        lock = json.loads((ROOT / "workspace.lock.json").read_text(encoding="utf-8-sig"))
        dockerfile = read("Dockerfile.a2")
        self.assertIn(f'FROM {IDENTITY["base_image"]}', dockerfile)
        arg_names = {"vllm": "VLLM_COMMIT", "vllm_ascend": "VLLM_ASCEND_COMMIT", "mooncake": "MOONCAKE_COMMIT"}
        lock_names = {"vllm": "vllm", "vllm_ascend": "vllm-ascend", "mooncake": "Mooncake"}
        for component, commit in IDENTITY["commits"].items():
            self.assertEqual(lock["repos"][lock_names[component]]["commit"], commit)
            self.assertIn(f'ARG {arg_names[component]}="{commit}"', dockerfile)

    def test_all_feature_manifests_use_the_pinned_image_and_vllm_version(self):
        manifests = [
            "deployment/30-mooncake-master.yaml",
            "deployment/40-prefill-engine.yaml",
            "deployment/50-decode-engine.yaml",
            "deployment/60-vllm-ascend-ut-pod.yaml",
            "deployment/stress/40-prefill-engine.yaml",
            "deployment/stress/50-decode-engine.yaml",
        ]
        for manifest in manifests:
            self.assertIn(f'image: {IDENTITY["image"]}', read(manifest), manifest)
        for manifest in [path for path in manifests if "master" not in path]:
            self.assertRegex(
                read(manifest),
                rf'VLLM_VERSION(?:, value:|\n\s+value:) "{re.escape(IDENTITY["vllm_version"])}"',
                manifest,
            )

    def test_runners_and_runtime_checkers_match_identity_and_new_session_api(self):
        runner_paths = [
            "deployment/run-smoke-test.sh",
            "deployment/run-stress-test.sh",
            "deployment/run-vllm-ascend-ut.sh",
            "deployment/sync-vllm-ascend-python.sh",
        ]
        for path in runner_paths:
            text = read(path)
            self.assertIn(IDENTITY["image"], text, path)
            self.assertIn(IDENTITY["commits"]["vllm_ascend"], text, path)
        checked_paths = [
            "deployment/10-runtime-config.yaml",
            "deployment/stress/10-runtime-config.yaml",
            "deployment/range-api-smoke.py",
            "deployment/lease-expiry-test.py",
            "deployment/tests/test_range_api_smoke.py",
            "deployment/tests/test_lease_expiry.py",
        ]
        combined = "\n".join(read(path) for path in checked_paths)
        for api in IDENTITY["session_apis"]:
            self.assertIn(api, combined)
        for old_api in ("batch_put_start", "batch_put_end", "batch_put_revoke", "batch_get_start", "batch_get_end"):
            self.assertIsNone(re.search(rf"\b{old_api}\b", combined), old_api)

    def test_stress_summary_embeds_exact_source_identity(self):
        runner = read("deployment/run-stress-test.sh")
        for commit in IDENTITY["commits"].values():
            self.assertIn(commit, runner)


if __name__ == "__main__":
    unittest.main()
