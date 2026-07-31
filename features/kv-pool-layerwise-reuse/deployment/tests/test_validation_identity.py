from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


FEATURE_DIR = Path(__file__).resolve().parents[2]
DEPLOYMENT_DIR = FEATURE_DIR / "deployment"
ROOT = FEATURE_DIR.parents[1]
IDENTITY = json.loads((DEPLOYMENT_DIR / "validation-identity.json").read_text())


def read(relative: str) -> str:
    return (FEATURE_DIR / relative).read_text(encoding="utf-8")


class ValidationIdentityTest(unittest.TestCase):
    def test_main_verified_vllm_lane_does_not_force_release_compatibility(self):
        self.assertEqual(IDENTITY["vllm_lane"], "main-verified")
        self.assertIsNone(IDENTITY["vllm_version_override"])
        self.assertEqual(IDENTITY["vllm_coordinator_keyword"], "max_in_flight_tokens")

        manifests = (
            "deployment/40-prefill-engine.yaml",
            "deployment/50-decode-engine.yaml",
            "deployment/60-vllm-ascend-ut-pod.yaml",
            "deployment/stress/40-prefill-engine.yaml",
            "deployment/stress/50-decode-engine.yaml",
        )
        for manifest in manifests:
            self.assertNotIn("VLLM_VERSION", read(manifest), manifest)

        for config in (
            "deployment/10-runtime-config.yaml",
            "deployment/stress/10-runtime-config.yaml",
        ):
            text = read(config)
            self.assertIn('assert not vllm_version_is("0.25.1")', text, config)
            self.assertIn("inspect.signature(get_kv_cache_coordinator)", text, config)
            self.assertIn(IDENTITY["vllm_coordinator_keyword"], text, config)

    def test_workspace_lock_and_dockerfile_match_frozen_source_identity(self):
        lock = json.loads(
            (ROOT / "workspace.lock.json").read_text(encoding="utf-8-sig")
        )
        dockerfile = read("Dockerfile.a2")
        self.assertIn(f"FROM {IDENTITY['base_image']}", dockerfile)
        self.assertIn(
            f'ARG VLLM_COMPATIBILITY_LANE="{IDENTITY["vllm_lane"]}"',
            dockerfile,
        )
        self.assertIn(
            'org.opencontainers.image.vllm.compatibility-lane="${VLLM_COMPATIBILITY_LANE}"',
            dockerfile,
        )
        arg_names = {
            "vllm": "VLLM_COMMIT",
            "vllm_ascend": "VLLM_ASCEND_COMMIT",
            "mooncake": "MOONCAKE_COMMIT",
        }
        lock_names = {
            "vllm": "vllm",
            "vllm_ascend": "vllm-ascend",
            "mooncake": "Mooncake",
        }
        for component, commit in IDENTITY["commits"].items():
            self.assertEqual(lock["repos"][lock_names[component]]["commit"], commit)
            self.assertIn(f'ARG {arg_names[component]}="{commit}"', dockerfile)

    def test_all_feature_manifests_use_the_pinned_image_and_lane(self):
        manifests = [
            "deployment/30-mooncake-master.yaml",
            "deployment/40-prefill-engine.yaml",
            "deployment/50-decode-engine.yaml",
            "deployment/60-vllm-ascend-ut-pod.yaml",
            "deployment/stress/40-prefill-engine.yaml",
            "deployment/stress/50-decode-engine.yaml",
        ]
        for manifest in manifests:
            self.assertIn(f"image: {IDENTITY['image']}", read(manifest), manifest)

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
        for old_api in (
            "batch_put_start",
            "batch_put_end",
            "batch_put_revoke",
            "batch_get_start",
            "batch_get_end",
        ):
            self.assertIsNone(re.search(rf"\b{old_api}\b", combined), old_api)

        for path in (
            "deployment/10-runtime-config.yaml",
            "deployment/stress/10-runtime-config.yaml",
        ):
            text = read(path)
            self.assertIn('assert not vllm_version_is("0.25.1")', text, path)
            self.assertIn("inspect.signature(get_kv_cache_coordinator)", text, path)
            self.assertIn(IDENTITY["vllm_coordinator_keyword"], text, path)
            self.assertIn(f"compatibility lane: {IDENTITY['vllm_lane']}", text, path)

    def test_run_identity_records_model_runtime_and_cluster_contract(self):
        self.assertRegex(IDENTITY["run_id"], r"^\d{8}T\d{6}Z$")
        self.assertEqual(IDENTITY["attempt"], 1)
        self.assertEqual(IDENTITY["tooling_base"]["branch"], "kv-pool-layerwise-reuse")
        self.assertRegex(IDENTITY["tooling_base"]["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(IDENTITY["model"]["num_layers"], 27)
        self.assertGreaterEqual(
            IDENTITY["model"]["max_position_embeddings"],
            IDENTITY["runtime"]["stress_max_model_len"],
        )
        self.assertEqual(IDENTITY["runtime"]["block_size"], 128)
        self.assertEqual(IDENTITY["runtime"]["lease_expired_code"], -707)
        self.assertEqual(
            IDENTITY["kubernetes"]["context"], "bke-cluster-admin@bke-cluster"
        )
        self.assertEqual(IDENTITY["kubernetes"]["node"], "n1")
        self.assertEqual(
            IDENTITY["kubernetes"]["builder_platform"], IDENTITY["platform"]
        )

    def test_dockerfile_pip_health_gate_is_fail_closed(self):
        dockerfile = read("Dockerfile.a2")
        self.assertIn("python3 -m pip check", dockerfile)
        self.assertIn("unexpected_pip_check", dockerfile)
        self.assertIn("if [[ -s ${unexpected_pip_check} ]]", dockerfile)
        self.assertIn("exit 1", dockerfile)
        for expected_known_issue in (
            "ms-service-profiler 26\\.0\\.0",
            "prometheus-fastapi-instrumentator 8\\.1\\.0",
            "opencv-python-headless 5\\.0\\.0\\.93",
            "vllm 0\\.1\\.dev1\\+g54503ecec\\.empty has requirement fastapi",
            "te 0\\.4\\.0 is not supported on this platform",
        ):
            self.assertIn(expected_known_issue, dockerfile)

        pattern_match = re.search(r"grep -E -v '([^']+)'", dockerfile)
        self.assertIsNotNone(pattern_match)
        pattern = pattern_match.group(1)
        known_issues = (
            "ms-service-profiler 26.0.0 requires matplotlib, which is not installed.",
            "ms-service-profiler 26.0.0 requires msguard, which is not installed.",
            "ms-service-profiler 26.0.0 requires openpyxl, which is not installed.",
            "te 0.4.0 requires ml-dtypes, which is not installed.",
            "te 0.4.0 requires tornado, which is not installed.",
            "mindstudio-kpp 0.0.0.dev0 requires plotly, which is not installed.",
            "ms-service-profiler 26.0.0 has requirement opentelemetry-exporter-otlp-proto-grpc==1.33.1, but you have opentelemetry-exporter-otlp-proto-grpc 1.44.0.",
            "ms-service-profiler 26.0.0 has requirement opentelemetry-exporter-otlp-proto-http==1.33.1, but you have opentelemetry-exporter-otlp-proto-http 1.44.0.",
            "ms-service-profiler 26.0.0 has requirement pandas~=2.2, but you have pandas 3.0.5.",
            "prometheus-fastapi-instrumentator 8.1.0 has requirement starlette<2.0.0,>=1.0.0, but you have starlette 0.50.0.",
            'opencv-python-headless 5.0.0.93 has requirement numpy>=2; python_version >= "3.9", but you have numpy 1.26.4.',
            "vllm 0.1.dev1+g54503ecec.empty has requirement fastapi[standard]<0.137.0,>=0.133.0, but you have fastapi 0.123.10.",
            "vllm 0.1.dev1+g54503ecec.empty has requirement starlette>=1.0.1, but you have starlette 0.50.0.",
            "te 0.4.0 is not supported on this platform",
        )
        for issue in known_issues:
            result = subprocess.run(
                ["grep", "-E", pattern],
                input=f"{issue}\n",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, issue)

        unexpected = subprocess.run(
            ["grep", "-E", pattern],
            input="new-package 1.0 requires missing-package, which is not installed.\n",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(unexpected.returncode, 1)

        self.assertNotIn(
            'packages=("vllm", "vllm-ascend", "mooncake-transfer-engine"',
            dockerfile,
        )
        self.assertIn(
            'print(f"mooncake-store={paths[0]}")',
            dockerfile,
        )

    def test_stress_summary_embeds_exact_source_identity(self):
        runner = read("deployment/run-stress-test.sh")
        for commit in IDENTITY["commits"].values():
            self.assertIn(commit, runner)


if __name__ == "__main__":
    unittest.main()
