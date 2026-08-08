#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
DEPLOYMENT = ROOT.parents[3] / "deployment"
sys.path.insert(0, str(DEPLOYMENT))

from performance import runtime  # noqa: E402
from performance.contract import WorkloadPoint  # noqa: E402


IMAGE = (
    "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-"
    "a2-d74269a0-df3f74ed-20260808T203742Z"
)


def read(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def clean(resource: dict[str, object]) -> dict[str, object]:
    resource.pop("status", None)
    metadata = resource.get("metadata")
    assert isinstance(metadata, dict)
    for field in (
        "creationTimestamp",
        "generation",
        "managedFields",
        "resourceVersion",
        "uid",
    ):
        metadata.pop(field, None)
    annotations = metadata.get("annotations")
    if isinstance(annotations, dict):
        annotations.pop("deployment.kubernetes.io/revision", None)
        annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
    return resource


def write(name: str, resource: dict[str, object]) -> None:
    path = ROOT / "rendered" / name
    path.write_text(
        json.dumps(clean(resource), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    inputs = runtime.RuntimeInputs(
        prefill_deployment=read("source-prefill.json"),
        decode_deployment=read("source-decode.json"),
        runtime_configmap=read("source-runtime-configmap.json"),
    )
    point = WorkloadPoint("dp1", 4096, 1, "layerwise", 1)
    rendered = runtime.render_resources(inputs, point, IMAGE)
    data = rendered.runtime_configmap["data"]
    assert isinstance(data, dict)
    for role in ("prefill", "decode"):
        key = f"start-{role}.sh"
        script = data[key]
        assert isinstance(script, str)
        data[key] = script.replace(
            "nohup env VLLM_USE_V1=1",
            "nohup env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 VLLM_USE_V1=1",
            1,
        )
    write("runtime-configmap.json", rendered.runtime_configmap)
    write("prefill-deployment.json", rendered.prefill_deployment)
    write("decode-deployment.json", rendered.decode_deployment)
    print(
        json.dumps(
            {
                "image": IMAGE,
                "point": point.__dict__,
                "prefill_npus": rendered.prefill_npus,
                "decode_npus": rendered.decode_npus,
                "runtime_configmap": rendered.runtime_configmap["metadata"]["name"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
