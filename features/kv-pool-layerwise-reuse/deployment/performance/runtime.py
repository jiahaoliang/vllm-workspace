from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import shlex
from typing import Any

from performance.contract import RUNTIME_CONSTANTS, TOPOLOGIES, VARIANTS, WorkloadPoint


@dataclass(frozen=True)
class RuntimeInputs:
    prefill_deployment: dict[str, Any]
    decode_deployment: dict[str, Any]
    runtime_configmap: dict[str, Any]


@dataclass(frozen=True)
class RenderedResources:
    prefill_deployment: dict[str, Any]
    decode_deployment: dict[str, Any]
    runtime_configmap: dict[str, Any]
    prefill_npus: int
    decode_npus: int

    @property
    def images(self) -> tuple[str, str]:
        return (
            self.prefill_deployment["spec"]["template"]["spec"]["containers"][0][
                "image"
            ],
            self.decode_deployment["spec"]["template"]["spec"]["containers"][0][
                "image"
            ],
        )


def _render_deployment(
    source: dict[str, Any], image: str, npus: int, configmap_name: str
) -> dict[str, Any]:
    deployment = deepcopy(source)
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    container["image"] = image
    for resource_type in ("requests", "limits"):
        container.setdefault("resources", {}).setdefault(resource_type, {})[
            "huawei.com/Ascend910"
        ] = str(npus)
    volumes = [volume for volume in pod_spec["volumes"] if volume["name"] == "runtime-config"]
    if len(volumes) != 1:
        raise ValueError("deployment must have exactly one runtime-config volume")
    volumes[0]["configMap"]["name"] = configmap_name
    return deployment


def _kv_transfer_config(role: str, point: WorkloadPoint) -> dict[str, Any]:
    if role not in {"prefill", "decode"}:
        raise ValueError(f"unsupported server role: {role}")
    settings = VARIANTS[point.variant].prefill if role == "prefill" else VARIANTS[
        point.variant
    ].decode
    extra = {"backend": "mooncake", **settings, "lookup_rpc_port": 0}
    if role == "decode":
        extra["consumer_is_to_load"] = True
    return {
        "kv_connector": "AscendStoreConnector",
        "kv_role": "kv_producer" if role == "prefill" else "kv_consumer",
        "kv_load_failure_policy": "fail",
        "kv_connector_extra_config": extra,
    }


def server_argv(role: str, point: WorkloadPoint) -> tuple[str, ...]:
    topology = TOPOLOGIES[point.topology]
    data_parallel = topology.prefill_dp if role == "prefill" else topology.decode_dp
    port = "8100" if role == "prefill" else "8200"
    argv = [
        "python3",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--model",
        "/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8",
        "--served-model-name",
        "vllm-ascend/DeepSeek-V2-Lite-W8A8",
        "--quantization",
        "ascend",
        "--trust-remote-code",
        "--enforce-eager",
        "--distributed-executor-backend",
        "mp",
        "--data-parallel-size",
        str(data_parallel),
    ]
    if role == "prefill" and data_parallel > 1:
        argv.extend(("--data-parallel-size-local", str(data_parallel)))
    argv.extend(
        (
            "--data-parallel-backend",
            "mp",
            "--tensor-parallel-size",
            str(RUNTIME_CONSTANTS["tensor_parallel_size"]),
            "--pipeline-parallel-size",
            str(RUNTIME_CONSTANTS["pipeline_parallel_size"]),
            "--prefill-context-parallel-size",
            str(RUNTIME_CONSTANTS["prefill_context_parallel_size"]),
            "--decode-context-parallel-size",
            str(RUNTIME_CONSTANTS["decode_context_parallel_size"]),
            "--block-size",
            str(RUNTIME_CONSTANTS["block_size"]),
            "--enable-chunked-prefill",
            "--max-model-len",
            str(RUNTIME_CONSTANTS["max_model_len"]),
            "--max-num-batched-tokens",
            str(RUNTIME_CONSTANTS["max_num_batched_tokens"]),
            "--max-num-seqs",
            str(RUNTIME_CONSTANTS["max_num_seqs"]),
            "--no-enable-prefix-caching",
            "--enable-logging-iteration-details",
            "--gpu-memory-utilization",
            str(RUNTIME_CONSTANTS["gpu_memory_utilization"]),
            "--kv-transfer-config",
            json.dumps(_kv_transfer_config(role, point), separators=(",", ":"), sort_keys=True),
        )
    )
    return tuple(argv)


def _start_script(role: str, point: WorkloadPoint) -> str:
    command = shlex.join(server_argv(role, point))
    return f"""#!/usr/bin/env bash
set -euo pipefail
pid_file=/tmp/vllm-{role}.pid
log_file=/tmp/vllm-{role}.log
if [[ -e ${{pid_file}} ]] && kill -0 "$(<"${{pid_file}}")" 2>/dev/null; then
  echo "{role} vLLM is already running" >&2
  exit 1
fi
: >"${{log_file}}"
nohup env VLLM_USE_V1=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \\
  {command} >"${{log_file}}" 2>&1 </dev/null &
echo "$!" >"${{pid_file}}"
"""


def _runtime_identity(point: WorkloadPoint, image: str) -> dict[str, Any]:
    topology = TOPOLOGIES[point.topology]
    prefill_slots = 5 if point.variant == "reuse3" else 27
    return {
        "variant": point.variant,
        "topology": point.topology,
        "input_tokens": point.input_tokens,
        "image": image,
        "prefill_dp": topology.prefill_dp,
        "decode_dp": topology.decode_dp,
        "tensor_parallel_size": RUNTIME_CONSTANTS["tensor_parallel_size"],
        "layerwise_prefetch_layers": RUNTIME_CONSTANTS["layerwise_prefetch_layers"],
        "logical_layers": 27,
        "prefill_physical_slots": prefill_slots,
        "prefill_logical_memory_factor": 27 / prefill_slots,
        "decode_physical_slots": 27,
        "decode_logical_memory_factor": 1.0,
        "prefill_kv": _kv_transfer_config("prefill", point),
        "decode_kv": _kv_transfer_config("decode", point),
    }


def _check_runtime_script() -> str:
    return '''import argparse
import json
from pathlib import Path

import vllm_ascend
from vllm_ascend.distributed.kv_transfer.kv_pool.ascend_store.layerwise_config import (
    get_layerwise_kv_cache_num_tensors,
)

parser = argparse.ArgumentParser()
parser.add_argument("--role", choices=("prefill", "decode"), required=True)
args = parser.parse_args()
identity = json.loads(Path("/opt/vllm-layerwise/runtime-identity.json").read_text())
logical_layers = identity["logical_layers"]
extra = identity[f"{args.role}_kv"]["kv_connector_extra_config"]
slots = get_layerwise_kv_cache_num_tensors(logical_layers, extra) or logical_layers
factor = logical_layers / slots
assert slots == identity[f"{args.role}_physical_slots"]
assert factor == identity[f"{args.role}_logical_memory_factor"]
print(json.dumps({
    "role": args.role,
    "logical_layers": logical_layers,
    "physical_slots": slots,
    "logical_memory_factor": factor,
    "vllm_ascend_source": str(Path(vllm_ascend.__file__).resolve()),
}, sort_keys=True))
'''


def render_resources(
    inputs: RuntimeInputs, point: WorkloadPoint, image: str
) -> RenderedResources:
    topology = TOPOLOGIES[point.topology]
    configmap_name = (
        f"layerwise-performance-{point.topology}-{point.input_tokens}-{point.variant}"
    )
    configmap = deepcopy(inputs.runtime_configmap)
    configmap["metadata"]["name"] = configmap_name
    data = configmap.setdefault("data", {})
    data["start-prefill.sh"] = _start_script("prefill", point)
    data["start-decode.sh"] = _start_script("decode", point)
    data["runtime-identity.json"] = json.dumps(
        _runtime_identity(point, image), indent=2, sort_keys=True
    ) + "\n"
    data["check-runtime.py"] = _check_runtime_script()
    prefill = _render_deployment(
        inputs.prefill_deployment, image, topology.prefill_npus, configmap_name
    )
    decode = _render_deployment(
        inputs.decode_deployment, image, topology.decode_npus, configmap_name
    )
    return RenderedResources(
        prefill,
        decode,
        configmap,
        topology.prefill_npus,
        topology.decode_npus,
    )


def _normalized(resources: RenderedResources) -> str:
    value = {
        "prefill": deepcopy(resources.prefill_deployment),
        "decode": deepcopy(resources.decode_deployment),
        "configmap": deepcopy(resources.runtime_configmap),
    }
    value["configmap"]["metadata"]["name"] = "<runtime-config>"
    for key in (
        "start-prefill.sh",
        "start-decode.sh",
        "runtime-identity.json",
        "check-runtime.py",
    ):
        value["configmap"]["data"].pop(key, None)
    for role in ("prefill", "decode"):
        pod_spec = value[role]["spec"]["template"]["spec"]
        for volume in pod_spec["volumes"]:
            if volume["name"] == "runtime-config":
                volume["configMap"]["name"] = "<runtime-config>"
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def validate_unique_difference(
    variants: dict[str, RenderedResources],
) -> list[str]:
    errors: list[str] = []
    normalized: str | None = None
    for variant, resources in variants.items():
        try:
            identity = json.loads(resources.runtime_configmap["data"]["runtime-identity.json"])
        except (KeyError, TypeError, json.JSONDecodeError):
            errors.append(f"runtime identity is missing or malformed: {variant}")
            continue
        if identity.get("variant") != variant:
            errors.append(f"runtime identity variant mismatch: {variant}")
        expected_point = WorkloadPoint(
            identity.get("topology", ""),
            int(identity.get("input_tokens", 0)),
            1,
            variant,
            1,
        )
        if identity.get("prefill_kv") != _kv_transfer_config("prefill", expected_point):
            errors.append(f"unexpected Prefill KV config: {variant}")
        if identity.get("decode_kv") != _kv_transfer_config("decode", expected_point):
            errors.append(f"unexpected Decode KV config: {variant}")
        current = _normalized(resources)
        if normalized is None:
            normalized = current
        elif current != normalized:
            errors.append(f"non-experimental runtime drift: {variant}")
    return errors
