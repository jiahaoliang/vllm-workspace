from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from performance import runtime
from performance.contract import WorkloadPoint
from performance.issue1_contract import Issue1Point


def base_inputs() -> runtime.RuntimeInputs:
    def deployment(name: str, container: str) -> dict[str, object]:
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": "liangjiahao"},
            "spec": {
                "template": {
                    "spec": {
                        "nodeName": "n1",
                        "containers": [
                            {
                                "name": container,
                                "image": "base-image",
                                "resources": {
                                    "requests": {"huawei.com/Ascend910": "1"},
                                    "limits": {"huawei.com/Ascend910": "1"},
                                },
                            }
                        ],
                        "volumes": [
                            {
                                "name": "runtime-config",
                                "configMap": {"name": "layerwise-runtime-config"},
                            }
                        ],
                    }
                }
            },
        }

    return runtime.RuntimeInputs(
        prefill_deployment=deployment("prefill-engine-deployment", "prefill-engine"),
        decode_deployment=deployment("decode-engine-deployment", "decode-engine"),
        runtime_configmap={
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "layerwise-runtime-config",
                "namespace": "liangjiahao",
            },
            "data": {"mooncake.json": "{}", "retained": "same"},
        },
    )


def test_topology_allocations_and_image_identity() -> None:
    inputs = base_inputs()
    original = deepcopy(inputs)
    dp1 = runtime.render_resources(inputs, WorkloadPoint("dp1", 16384, 1, "bulk", 8), "image@sha256:x")

    assert (dp1.prefill_npus, dp1.decode_npus) == (2, 2)
    assert dp1.images == ("image@sha256:x", "image@sha256:x")
    assert inputs == original


def test_render_resources_places_engines_on_explicit_node_and_keeps_default() -> None:
    point = WorkloadPoint("dp1", 16384, 1, "bulk", 8)

    default = runtime.render_resources(base_inputs(), point, "image@sha256:x")
    selected = runtime.render_resources(
        base_inputs(), point, "image@sha256:x", node_name="m1"
    )

    assert default.prefill_deployment["spec"]["template"]["spec"]["nodeName"] == "n1"
    assert default.decode_deployment["spec"]["template"]["spec"]["nodeName"] == "n1"
    assert selected.prefill_deployment["spec"]["template"]["spec"]["nodeName"] == "m1"
    assert selected.decode_deployment["spec"]["template"]["spec"]["nodeName"] == "m1"


def test_render_resources_forces_recreate_for_manual_server_start() -> None:
    inputs = base_inputs()
    inputs.prefill_deployment["spec"]["strategy"] = {
        "type": "RollingUpdate",
        "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
    }
    inputs.decode_deployment["spec"]["strategy"] = {
        "type": "RollingUpdate",
        "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
    }

    rendered = runtime.render_resources(
        inputs,
        WorkloadPoint("dp1", 32000, 128, "bulk", 8),
        "image@sha256:x",
    )

    assert rendered.prefill_deployment["spec"]["strategy"] == {
        "type": "Recreate"
    }
    assert rendered.decode_deployment["spec"]["strategy"] == {
        "type": "Recreate"
    }


def test_runtime_keeps_frozen_mooncake_pool_size() -> None:
    for variant in ("bulk", "layerwise", "reuse3"):
        rendered = runtime.render_resources(
            base_inputs(),
            WorkloadPoint("dp1", 16384, 1, variant, 8),
            "image@sha256:x",
        )
        data = rendered.runtime_configmap["data"]
        identity = json.loads(data["runtime-identity.json"])

        assert "MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB" in data["start-prefill.sh"]
        assert "MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB" in data["start-decode.sh"]
        assert identity["mooncake_global_segment_size"] == "128GB"


def _kv_config(argv: tuple[str, ...]) -> dict[str, object]:
    index = argv.index("--kv-transfer-config")
    return json.loads(argv[index + 1])


def test_reuse3_changes_only_prefill_compute_buffers() -> None:
    layerwise = WorkloadPoint("dp1", 16384, 1, "layerwise", 8)
    reuse3 = WorkloadPoint("dp1", 16384, 1, "reuse3", 8)
    layerwise_prefill = _kv_config(runtime.server_argv("prefill", layerwise))
    reuse_prefill = _kv_config(runtime.server_argv("prefill", reuse3))
    reuse_decode = _kv_config(runtime.server_argv("decode", reuse3))

    layer_extra = layerwise_prefill["kv_connector_extra_config"]
    reuse_extra = reuse_prefill["kv_connector_extra_config"]
    decode_extra = reuse_decode["kv_connector_extra_config"]
    assert isinstance(layer_extra, dict)
    assert isinstance(reuse_extra, dict)
    assert isinstance(decode_extra, dict)
    assert layer_extra["layerwise_prefetch_layers"] == 3
    assert "layerwise_num_shared_buffers" not in layer_extra
    assert reuse_extra["layerwise_num_shared_buffers"] == 3
    assert "layerwise_num_shared_buffers" not in decode_extra
    assert reuse_decode["kv_role"] == "kv_consumer"
    assert decode_extra["consumer_is_to_load"] is True


def test_all_variants_disable_local_prefix_caching() -> None:
    for variant in ("bulk", "layerwise", "reuse3"):
        for role in ("prefill", "decode"):
            argv = runtime.server_argv(
                role, WorkloadPoint("dp1", 16384, 1, variant, 8)
            )
            assert "--no-enable-prefix-caching" in argv
            assert "--enable-prefix-caching" not in argv


def test_private_issue_test1_runtime_matches_32k_issue_parameters() -> None:
    issue_point = Issue1Point("test1", "dp1", 32000, 128, "layerwise", 8, 125)
    point = WorkloadPoint("dp1", 32000, 128, "layerwise", 8)
    profile = runtime.issue1_runtime_profile(issue_point)
    argv = runtime.server_argv("prefill", point, profile)

    assert argv[argv.index("--max-model-len") + 1] == "32768"
    assert argv[argv.index("--max-num-batched-tokens") + 1] == "32768"
    assert argv[argv.index("--max-num-seqs") + 1] == "8"
    assert argv[argv.index("--gpu-memory-utilization") + 1] == "0.95"
    assert "--async-scheduling" in argv
    assert argv[argv.index("--seed") + 1] == "1024"
    assert argv[argv.index("--max-num-partial-prefills") + 1] == "8"
    assert argv[argv.index("--max-long-partial-prefills") + 1] == "8"
    assert argv[argv.index("--long-prefill-token-threshold") + 1] == "4096"
    assert "--enable-per-request-metrics" in argv


def test_private_issue_test2_runtime_uses_c40_and_768_token_fair_chunks() -> None:
    issue_point = Issue1Point("test2", "dp1", 32000, 1, "reuse3", 40, 100)
    point = WorkloadPoint("dp1", 32000, 1, "reuse3", 40)
    profile = runtime.issue1_runtime_profile(issue_point)
    rendered = runtime.render_resources(
        base_inputs(), point, "image@sha256:x", node_name="m1", profile=profile
    )
    data = rendered.runtime_configmap["data"]
    argv = runtime.server_argv("prefill", point, profile)

    assert argv[argv.index("--max-num-seqs") + 1] == "40"
    assert argv[argv.index("--max-num-partial-prefills") + 1] == "40"
    assert argv[argv.index("--max-long-partial-prefills") + 1] == "40"
    assert argv[argv.index("--long-prefill-token-threshold") + 1] == "768"
    assert argv[argv.index("--seed") + 1] == "1024"
    for variable in (
        "MC_TE_METRIC=1",
        "MC_TE_METRIC_INTERVAL_SECONDS=1",
        "VLLM_ASCEND_KVPOOL_PERF_METRICS=1",
        "VLLM_ASCEND_KVPOOL_PERF_METRICS_INTERVAL_SECONDS=1",
    ):
        assert variable in data["start-prefill.sh"]
        assert variable in data["start-decode.sh"]
    identity = json.loads(data["runtime-identity.json"])
    assert identity["runtime_profile"]["name"] == "private-issue1-test2"
    assert identity["runtime_profile"]["long_prefill_token_threshold"] == 768


def test_private_issue_short_diagnostic_enables_range_debug_only_for_diagnostic() -> None:
    issue_point = Issue1Point("test1", "dp1", 32000, 128, "layerwise", 8, 125)
    point = WorkloadPoint("dp1", 32000, 128, "layerwise", 8)
    formal = runtime.render_resources(
        base_inputs(),
        point,
        "image@sha256:x",
        profile=runtime.issue1_runtime_profile(issue_point),
    )
    diagnostic = runtime.render_resources(
        base_inputs(),
        point,
        "image@sha256:x",
        profile=runtime.issue1_runtime_profile(issue_point, diagnostic=True),
    )

    formal_data = formal.runtime_configmap["data"]
    diagnostic_data = diagnostic.runtime_configmap["data"]
    assert "VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0" in formal_data["start-prefill.sh"]
    assert "VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0" in formal_data["start-decode.sh"]
    assert "VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1" in diagnostic_data["start-prefill.sh"]
    assert "VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1" in diagnostic_data["start-decode.sh"]
    identity = json.loads(diagnostic_data["runtime-identity.json"])
    assert identity["runtime_profile"]["name"] == "private-issue1-test1-diagnostic"
    assert identity["runtime_profile"]["enable_range_debug"] is True


def test_unique_difference_rejects_hidden_runtime_drift() -> None:
    inputs = base_inputs()
    layerwise = runtime.render_resources(
        inputs,
        WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        "image@sha256:x",
    )
    reuse3 = runtime.render_resources(
        inputs,
        WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
        "image@sha256:x",
    )

    assert (
        runtime.validate_unique_difference({"layerwise": layerwise, "reuse3": reuse3}) == []
    )
    reuse3.decode_deployment["spec"]["template"]["spec"]["nodeName"] = "m2"
    assert any(
        "non-experimental runtime drift" in error
        for error in runtime.validate_unique_difference({"layerwise": layerwise, "reuse3": reuse3})
    )


def test_reuse3_runtime_identity_freezes_slots_and_memory_factor() -> None:
    rendered = runtime.render_resources(
        base_inputs(),
        WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
        "image@sha256:x",
    )
    data = rendered.runtime_configmap["data"]
    identity = json.loads(data["runtime-identity.json"])

    assert identity["logical_layers"] == 27
    assert identity["prefill_physical_slots"] == 5
    assert identity["prefill_logical_memory_factor"] == 5.4
    assert identity["decode_physical_slots"] == 27
    compile(data["check-runtime.py"], "check-runtime.py", "exec")


def test_runtime_check_avoids_loading_a_second_npu_runtime(tmp_path: Path) -> None:
    for variant in ("bulk", "layerwise", "reuse3"):
        rendered = runtime.render_resources(
            base_inputs(),
            WorkloadPoint("dp1", 16384, 1, variant, 8),
            "image@sha256:x",
        )
        data = rendered.runtime_configmap["data"]
        script = data["check-runtime.py"]
        assert "import vllm_ascend" not in script
        identity = tmp_path / f"{variant}.json"
        identity.write_text(data["runtime-identity.json"], encoding="utf-8")
        for role in ("prefill", "decode"):
            cmdline = tmp_path / f"{variant}-{role}.cmdline"
            cmdline.write_bytes(
                b"\0".join(
                    value.encode()
                    for value in runtime.server_argv(
                        role,
                        WorkloadPoint("dp1", 16384, 1, variant, 8),
                    )
                )
                + b"\0"
            )
            log_file = tmp_path / f"{variant}-{role}.log"
            log_file.write_text("server ready\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    "--role",
                    role,
                    "--identity",
                    str(identity),
                    "--cmdline",
                    str(cmdline),
                    "--log-file",
                    str(log_file),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            checked = json.loads(result.stdout)
            assert (
                checked["physical_slots"] == json.loads(data["runtime-identity.json"])[f"{role}_physical_slots"]
            )


def test_private_issue_runtime_check_rejects_partial_prefill_reset_warning(
    tmp_path: Path,
) -> None:
    issue_point = Issue1Point("test2", "dp1", 32000, 1, "reuse3", 40, 100)
    point = WorkloadPoint("dp1", 32000, 1, "reuse3", 40)
    profile = runtime.issue1_runtime_profile(issue_point)
    rendered = runtime.render_resources(
        base_inputs(), point, "image@sha256:x", profile=profile
    )
    data = rendered.runtime_configmap["data"]
    identity = tmp_path / "identity.json"
    identity.write_text(data["runtime-identity.json"], encoding="utf-8")
    cmdline = tmp_path / "cmdline"
    cmdline.write_bytes(
        b"\0".join(
            value.encode()
            for value in runtime.server_argv("prefill", point, profile)
        )
        + b"\0"
    )
    log_file = tmp_path / "vllm.log"
    log_file.write_text(
        "parameter=max_num_partial_prefills, action: resetting to default (1)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            data["check-runtime.py"],
            "--role",
            "prefill",
            "--identity",
            str(identity),
            "--cmdline",
            str(cmdline),
            "--log-file",
            str(log_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "reset concurrent partial-prefill scheduling" in result.stderr


def test_all_rendered_start_scripts_have_valid_bash_syntax() -> None:
    profiles = {
        "test1": Issue1Point("test1", "dp1", 32000, 128, "bulk", 8, 125),
        "test2": Issue1Point("test2", "dp1", 32000, 1, "bulk", 40, 100),
    }
    checked = 0
    for test, issue_point in profiles.items():
        for variant in ("bulk", "layerwise", "reuse3"):
            point = WorkloadPoint(
                "dp1",
                32000,
                issue_point.output_tokens,
                variant,
                issue_point.concurrency,
            )
            profile = runtime.issue1_runtime_profile(
                Issue1Point(
                    test,
                    "dp1",
                    32000,
                    issue_point.output_tokens,
                    variant,
                    issue_point.concurrency,
                    issue_point.formal_requests,
                )
            )
            rendered = runtime.render_resources(
                base_inputs(), point, "image@sha256:x", profile=profile
            )
            for role in ("prefill", "decode"):
                result = subprocess.run(
                    ["bash", "-n"],
                    input=rendered.runtime_configmap["data"][f"start-{role}.sh"],
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0, result.stderr
                checked += 1
    assert checked == 12
