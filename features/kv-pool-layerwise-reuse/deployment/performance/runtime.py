from __future__ import annotations

import json
import shlex
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from performance.contract import RUNTIME_CONSTANTS, TOPOLOGIES, VARIANTS, WorkloadPoint
from performance.issue1_contract import (
    SERVER_SEED,
    Issue1Point,
    long_prefill_token_threshold,
)

MOONCAKE_GLOBAL_SEGMENT_SIZE = "128GB"
KVPOOL_PERF_METRICS_INTERVAL_SECONDS = 1


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


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    max_model_len: int
    max_num_batched_tokens: int
    max_num_seqs: int
    gpu_memory_utilization: float
    async_scheduling: bool = False
    max_num_partial_prefills: int = 1
    max_long_partial_prefills: int = 1
    long_prefill_token_threshold: int | None = None
    enable_per_request_metrics: bool = False
    enable_kvpool_perf_metrics: bool = False
    enable_range_debug: bool = False
    server_seed: int | None = None


def issue1_runtime_profile(
    point: Issue1Point, *, diagnostic: bool = False
) -> RuntimeProfile:
    threshold = long_prefill_token_threshold(point.concurrency)
    suffix = "-diagnostic" if diagnostic else ""
    return RuntimeProfile(
        name=f"private-issue1-{point.test}{suffix}",
        max_model_len=32768,
        max_num_batched_tokens=32768,
        max_num_seqs=point.concurrency,
        gpu_memory_utilization=0.95,
        async_scheduling=True,
        max_num_partial_prefills=point.concurrency,
        max_long_partial_prefills=point.concurrency,
        long_prefill_token_threshold=threshold,
        enable_per_request_metrics=True,
        enable_kvpool_perf_metrics=True,
        enable_range_debug=diagnostic,
        server_seed=SERVER_SEED,
    )


def _default_profile() -> RuntimeProfile:
    return RuntimeProfile(
        name="high-hit-generation16",
        max_model_len=int(RUNTIME_CONSTANTS["max_model_len"]),
        max_num_batched_tokens=int(RUNTIME_CONSTANTS["max_num_batched_tokens"]),
        max_num_seqs=int(RUNTIME_CONSTANTS["max_num_seqs"]),
        gpu_memory_utilization=float(RUNTIME_CONSTANTS["gpu_memory_utilization"]),
    )


def _render_deployment(
    source: dict[str, Any],
    image: str,
    npus: int,
    configmap_name: str,
    node_name: str,
) -> dict[str, Any]:
    deployment = deepcopy(source)
    # The runner starts vLLM explicitly after the replacement Pod is Running.
    # Recreate is required so a non-Ready sleep wrapper cannot deadlock a
    # RollingUpdate while the runner waits for the old Pod to disappear.
    deployment.setdefault("spec", {})["strategy"] = {"type": "Recreate"}
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    pod_spec["nodeName"] = node_name
    container["image"] = image
    for resource_type in ("requests", "limits"):
        container.setdefault("resources", {}).setdefault(resource_type, {})[
            "huawei.com/Ascend910"
        ] = str(npus)
    volumes = [
        volume for volume in pod_spec["volumes"] if volume["name"] == "runtime-config"
    ]
    if len(volumes) != 1:
        raise ValueError("deployment must have exactly one runtime-config volume")
    volumes[0]["configMap"]["name"] = configmap_name
    return deployment


def _kv_transfer_config(role: str, point: WorkloadPoint) -> dict[str, Any]:
    if role not in {"prefill", "decode"}:
        raise ValueError(f"unsupported server role: {role}")
    settings = (
        VARIANTS[point.variant].prefill
        if role == "prefill"
        else VARIANTS[point.variant].decode
    )
    extra = {"backend": "mooncake", **settings, "lookup_rpc_port": 0}
    if role == "decode":
        extra["consumer_is_to_load"] = True
    return {
        "kv_connector": "AscendStoreConnector",
        "kv_role": "kv_producer" if role == "prefill" else "kv_consumer",
        "kv_load_failure_policy": "fail",
        "kv_connector_extra_config": extra,
    }


def server_argv(
    role: str,
    point: WorkloadPoint,
    profile: RuntimeProfile | None = None,
) -> tuple[str, ...]:
    profile = profile or _default_profile()
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
            str(profile.max_model_len),
            "--max-num-batched-tokens",
            str(profile.max_num_batched_tokens),
            "--max-num-seqs",
            str(profile.max_num_seqs),
            "--no-enable-prefix-caching",
            "--enable-logging-iteration-details",
            "--gpu-memory-utilization",
            str(profile.gpu_memory_utilization),
            "--kv-transfer-config",
            json.dumps(
                _kv_transfer_config(role, point), separators=(",", ":"), sort_keys=True
            ),
        )
    )
    if profile.async_scheduling:
        argv.append("--async-scheduling")
    if profile.server_seed is not None:
        argv.extend(("--seed", str(profile.server_seed)))
    if (
        profile.max_num_partial_prefills != 1
        or profile.max_long_partial_prefills != 1
    ):
        argv.extend(
            (
                "--max-num-partial-prefills",
                str(profile.max_num_partial_prefills),
                "--max-long-partial-prefills",
                str(profile.max_long_partial_prefills),
            )
        )
    if profile.long_prefill_token_threshold is not None:
        argv.extend(
            (
                "--long-prefill-token-threshold",
                str(profile.long_prefill_token_threshold),
            )
        )
    if profile.enable_per_request_metrics:
        argv.append("--enable-per-request-metrics")
    return tuple(argv)


def _start_script(
    role: str,
    point: WorkloadPoint,
    profile: RuntimeProfile | None = None,
) -> str:
    profile = profile or _default_profile()
    command = shlex.join(server_argv(role, point, profile))
    metrics_enabled = "1" if profile.enable_kvpool_perf_metrics else "0"
    range_debug_enabled = "1" if profile.enable_range_debug else "0"
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
  MOONCAKE_GLOBAL_SEGMENT_SIZE={MOONCAKE_GLOBAL_SEGMENT_SIZE} \\
  MC_TE_METRIC={metrics_enabled} MC_TE_METRIC_INTERVAL_SECONDS=1 \\
  VLLM_ASCEND_KVPOOL_PERF_METRICS={metrics_enabled} \\
  VLLM_ASCEND_KVPOOL_PERF_METRICS_INTERVAL_SECONDS={KVPOOL_PERF_METRICS_INTERVAL_SECONDS} \\
  VLLM_ASCEND_KVPOOL_RANGE_DEBUG={range_debug_enabled} \\
  {command} >"${{log_file}}" 2>&1 </dev/null &
echo "$!" >"${{pid_file}}"
"""


def _runtime_identity(
    point: WorkloadPoint,
    image: str,
    profile: RuntimeProfile | None = None,
) -> dict[str, Any]:
    profile = profile or _default_profile()
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
        "mooncake_global_segment_size": MOONCAKE_GLOBAL_SEGMENT_SIZE,
        "runtime_profile": {
            "name": profile.name,
            "max_model_len": profile.max_model_len,
            "max_num_batched_tokens": profile.max_num_batched_tokens,
            "max_num_seqs": profile.max_num_seqs,
            "gpu_memory_utilization": profile.gpu_memory_utilization,
            "async_scheduling": profile.async_scheduling,
            "max_num_partial_prefills": profile.max_num_partial_prefills,
            "max_long_partial_prefills": profile.max_long_partial_prefills,
            "long_prefill_token_threshold": profile.long_prefill_token_threshold,
            "enable_per_request_metrics": profile.enable_per_request_metrics,
            "enable_kvpool_perf_metrics": profile.enable_kvpool_perf_metrics,
            "enable_range_debug": profile.enable_range_debug,
            "server_seed": profile.server_seed,
        },
        "prefill_kv": _kv_transfer_config("prefill", point),
        "decode_kv": _kv_transfer_config("decode", point),
    }


def _check_runtime_script() -> str:
    return """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--role", choices=("prefill", "decode"), required=True)
parser.add_argument(
    "--identity",
    type=Path,
    default=Path("/opt/vllm-layerwise/runtime-identity.json"),
)
parser.add_argument("--cmdline", type=Path)
parser.add_argument("--log-file", type=Path)
args = parser.parse_args()
identity = json.loads(args.identity.read_text())
pid_file = Path(f"/tmp/vllm-{args.role}.pid")
if args.cmdline is None:
    pid = int(pid_file.read_text().strip())
    cmdline_path = Path(f"/proc/{pid}/cmdline")
else:
    cmdline_path = args.cmdline
log_file = args.log_file or Path(f"/tmp/vllm-{args.role}.log")
argv = [value.decode() for value in cmdline_path.read_bytes().split(b"\\0") if value]

def require_option(name, expected):
    assert name in argv, (name, argv)
    index = argv.index(name)
    assert index + 1 < len(argv), (name, argv)
    actual = argv[index + 1]
    assert actual == str(expected), (name, expected, actual)

profile = identity["runtime_profile"]
require_option("--max-model-len", profile["max_model_len"])
require_option("--max-num-batched-tokens", profile["max_num_batched_tokens"])
require_option("--max-num-seqs", profile["max_num_seqs"])
if profile["max_num_partial_prefills"] > 1:
    require_option(
        "--max-num-partial-prefills", profile["max_num_partial_prefills"]
    )
    require_option(
        "--max-long-partial-prefills", profile["max_long_partial_prefills"]
    )
    require_option(
        "--long-prefill-token-threshold",
        profile["long_prefill_token_threshold"],
    )
if profile["server_seed"] is not None:
    require_option("--seed", profile["server_seed"])
log_text = log_file.read_text(errors="replace")
assert not (
    "parameter=max_num_partial_prefills" in log_text
    and "resetting to default (1)" in log_text
), "Ascend reset concurrent partial-prefill scheduling to one context"

logical_layers = identity["logical_layers"]
extra = identity[f"{args.role}_kv"]["kv_connector_extra_config"]
shared_value = extra.get("layerwise_num_shared_buffers")
if shared_value is None:
    slots = logical_layers
else:
    shared = int(shared_value)
    independent_value = extra.get("layerwise_independent_layers")
    if independent_value is None:
        independent = [0, logical_layers - 1]
    elif isinstance(independent_value, str):
        if independent_value.strip().lower() == "all":
            independent = list(range(logical_layers))
        else:
            independent = [
                int(value.strip())
                for value in independent_value.split(",")
                if value.strip()
            ]
    elif isinstance(independent_value, int):
        independent = [independent_value]
    else:
        independent = [int(value) for value in independent_value]
    independent = sorted({
        value + logical_layers if value < 0 else value for value in independent
    })
    assert all(0 <= value < logical_layers for value in independent)
    reused_layers = logical_layers - len(independent)
    slots = len(independent) + shared if reused_layers > shared else logical_layers
factor = logical_layers / slots
assert slots == identity[f"{args.role}_physical_slots"]
assert factor == identity[f"{args.role}_logical_memory_factor"]
print(json.dumps({
    "role": args.role,
    "logical_layers": logical_layers,
    "physical_slots": slots,
    "logical_memory_factor": factor,
    "scheduler": {
        "max_num_seqs": profile["max_num_seqs"],
        "max_num_partial_prefills": profile["max_num_partial_prefills"],
        "max_long_partial_prefills": profile["max_long_partial_prefills"],
        "long_prefill_token_threshold": profile[
            "long_prefill_token_threshold"
        ],
    },
    "vllm_ascend_source": str(Path(
        "/vllm-workspace/vllm-ascend/vllm_ascend/__init__.py"
    )),
}, sort_keys=True))
"""


def render_resources(
    inputs: RuntimeInputs,
    point: WorkloadPoint,
    image: str,
    node_name: str = "n1",
    profile: RuntimeProfile | None = None,
) -> RenderedResources:
    profile = profile or _default_profile()
    topology = TOPOLOGIES[point.topology]
    if profile.name.startswith("private-issue1-"):
        test_name = profile.name.removeprefix("private-issue1-")
        configmap_name = (
            f"layerwise-issue1-{test_name}-{point.variant}-c{profile.max_num_seqs}"
        )
    else:
        configmap_name = (
            f"layerwise-performance-{point.topology}-{point.input_tokens}-{point.variant}"
        )
    configmap = deepcopy(inputs.runtime_configmap)
    configmap["metadata"]["name"] = configmap_name
    data = configmap.setdefault("data", {})
    data["start-prefill.sh"] = _start_script("prefill", point, profile)
    data["start-decode.sh"] = _start_script("decode", point, profile)
    data["runtime-identity.json"] = (
        json.dumps(_runtime_identity(point, image, profile), indent=2, sort_keys=True) + "\n"
    )
    data["check-runtime.py"] = _check_runtime_script()
    prefill = _render_deployment(
        inputs.prefill_deployment,
        image,
        topology.prefill_npus,
        configmap_name,
        node_name,
    )
    decode = _render_deployment(
        inputs.decode_deployment,
        image,
        topology.decode_npus,
        configmap_name,
        node_name,
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
            identity = json.loads(
                resources.runtime_configmap["data"]["runtime-identity.json"]
            )
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
