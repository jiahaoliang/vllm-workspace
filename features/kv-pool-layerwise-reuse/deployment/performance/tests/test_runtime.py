from __future__ import annotations

from copy import deepcopy
import json

from performance import runtime
from performance.contract import WorkloadPoint


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
        prefill_deployment=deployment(
            "prefill-engine-deployment", "prefill-engine"
        ),
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
    dp1 = runtime.render_resources(
        inputs, WorkloadPoint("dp1", 4096, 1, "bulk", 1), "image@sha256:x"
    )
    dp2 = runtime.render_resources(
        inputs, WorkloadPoint("dp2", 4096, 1, "bulk", 2), "image@sha256:x"
    )

    assert (dp1.prefill_npus, dp1.decode_npus) == (2, 2)
    assert (dp2.prefill_npus, dp2.decode_npus) == (4, 2)
    assert dp1.images == ("image@sha256:x", "image@sha256:x")
    assert inputs == original


def _kv_config(argv: tuple[str, ...]) -> dict[str, object]:
    index = argv.index("--kv-transfer-config")
    return json.loads(argv[index + 1])


def test_reuse3_changes_only_prefill_compute_buffers() -> None:
    layerwise = WorkloadPoint("dp2", 16384, 1, "layerwise", 4)
    reuse3 = WorkloadPoint("dp2", 16384, 1, "reuse3", 4)
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


def test_unique_difference_rejects_hidden_runtime_drift() -> None:
    inputs = base_inputs()
    layerwise = runtime.render_resources(
        inputs,
        WorkloadPoint("dp1", 32768, 1, "layerwise", 1),
        "image@sha256:x",
    )
    reuse3 = runtime.render_resources(
        inputs,
        WorkloadPoint("dp1", 32768, 1, "reuse3", 1),
        "image@sha256:x",
    )

    assert runtime.validate_unique_difference(
        {"layerwise": layerwise, "reuse3": reuse3}
    ) == []
    reuse3.decode_deployment["spec"]["template"]["spec"]["nodeName"] = "m2"
    assert any(
        "non-experimental runtime drift" in error
        for error in runtime.validate_unique_difference(
            {"layerwise": layerwise, "reuse3": reuse3}
        )
    )


def test_reuse3_runtime_identity_freezes_slots_and_memory_factor() -> None:
    rendered = runtime.render_resources(
        base_inputs(),
        WorkloadPoint("dp1", 4096, 1, "reuse3", 1),
        "image@sha256:x",
    )
    data = rendered.runtime_configmap["data"]
    identity = json.loads(data["runtime-identity.json"])

    assert identity["logical_layers"] == 27
    assert identity["prefill_physical_slots"] == 5
    assert identity["prefill_logical_memory_factor"] == 5.4
    assert identity["decode_physical_slots"] == 27
    compile(data["check-runtime.py"], "check-runtime.py", "exec")
