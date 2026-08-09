#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[4]
SOURCE_COMMIT = "5355559175f9998f5d70866734fb79569dfc86f9"
FINAL_IMAGE = (
    "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-"
    "a2-535555917-df3f74ed-20260809T070557Z"
)


def native(name: str) -> dict[str, object]:
    value = json.loads((ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, list) and value
    assert isinstance(value[0], dict)
    return value[0]


def hashes(name: str) -> list[str]:
    result = []
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        fields = line.split()
        assert len(fields) == 2, (name, line)
        assert len(fields[0]) == 64
        result.append(fields[0])
    return result


def main() -> int:
    base = native("native-base-native-inspect.json")
    pre = native("pre-metadata-native-inspect.json")
    final = native("final-native-inspect.json")

    base_manifest = base["ManifestDesc"]["digest"]
    base_config = base["ImageConfigDesc"]["digest"]
    pre_manifest = pre["ManifestDesc"]["digest"]
    pre_config = pre["ImageConfigDesc"]["digest"]
    final_manifest = final["ManifestDesc"]["digest"]
    final_config = final["ImageConfigDesc"]["digest"]
    assert base_manifest == (
        "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
    )
    assert base_config == (
        "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
    )
    assert pre_manifest == (
        "sha256:0cac821008e646ad953a5fa1e6b625e5b9b7a2bf3df14045f1098d76cee21483"
    )
    assert pre_config == (
        "sha256:26691aea3c4d44a2409f87b35797df4b76ff166e47a1955eb696187170c0fef4"
    )
    assert final_manifest == (
        "sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc"
    )
    assert final_config == (
        "sha256:b138ce816ae0b4183f77a6e9b83bc95061a6c1053f770d2f0462699de86a7a0c"
    )

    for value in (base, pre, final):
        image_config = value["ImageConfig"]
        assert image_config["architecture"] == "arm64"
        assert image_config["os"] == "linux"

    base_layers = base["Manifest"]["layers"]
    pre_layers = pre["Manifest"]["layers"]
    final_layers = final["Manifest"]["layers"]
    assert len(base_layers) == 21
    assert len(pre_layers) == len(final_layers) == 22
    assert pre_layers == final_layers
    assert base_layers == pre_layers[:-1]
    assert pre_layers[-1]["digest"] == (
        "sha256:a35b3719277716bb4b9eeb5e001b26bf151752f6d4943addb94696e47f8402c1"
    )
    assert pre["ImageConfig"]["rootfs"]["diff_ids"][-1] == (
        "sha256:f45796141de51193decb7ef5ba9c4f5096075b844ea0257a68bf568ed1c0892a"
    )

    source_hashes = hashes("checkout-production-sha256-retry.txt")
    image_hashes = hashes("image-production-sha256.txt")
    assert len(source_hashes) == len(image_hashes) == 8
    assert source_hashes == image_hashes
    aggregate = hashlib.sha256(
        (ROOT / "checkout-production-sha256-retry.txt").read_bytes()
    ).hexdigest()
    assert aggregate == (
        "7b80604faad9d32750aa072d0540536d6e376a95f158a6e7483af7a9e445d44f"
    )

    labels = final["ImageConfig"]["config"]["Labels"]
    assert labels["org.opencontainers.image.vllm.commit"] == (
        "54503ecec0f3ac31e5ecfc5f28652e4cc42307b5"
    )
    assert labels["org.opencontainers.image.vllm-ascend.commit"] == SOURCE_COMMIT
    assert labels["org.opencontainers.image.mooncake.commit"] == (
        "df3f74ed8ebdb0c935554beea6299a9f11c723e2"
    )
    assert labels["org.opencontainers.image.patch.sha256"] == aggregate
    assert labels["org.opencontainers.image.patch.pool-worker.sha256"] == source_hashes[-1]
    assert labels["org.opencontainers.image.validation.run"] == "20260809T070557Z"

    source_repo = WORKSPACE / "repos" / "vllm-ascend"
    source_head = subprocess.check_output(
        ("git", "-C", str(source_repo), "rev-parse", "HEAD"), text=True
    ).strip()
    source_status = subprocess.check_output(
        ("git", "-C", str(source_repo), "status", "--porcelain=v1"), text=True
    )
    assert source_head == SOURCE_COMMIT
    assert source_status == ""

    result = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "source_head": source_head,
        "source_dirty": False,
        "base_image": (
            "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-"
            "a2-45b2e785-df3f74ed-20260807T100722Z"
        ),
        "base_manifest_digest": base_manifest,
        "base_config_digest": base_config,
        "pre_metadata_image": (
            "docker.io/library/vllm-ascend:kv-pool-layerwise-pre-metadata-"
            "535555917-20260809T070557Z"
        ),
        "pre_metadata_manifest_digest": pre_manifest,
        "pre_metadata_config_digest": pre_config,
        "final_image": FINAL_IMAGE,
        "final_manifest_digest": final_manifest,
        "final_config_digest": final_config,
        "platform": "linux/arm64",
        "layer_descriptor_count": len(final_layers),
        "patch_layer_digest": pre_layers[-1]["digest"],
        "patch_diff_id": pre["ImageConfig"]["rootfs"]["diff_ids"][-1],
        "metadata_correction_layer_descriptors_unchanged": True,
        "production_files_compared": len(source_hashes),
        "production_file_hashes_equal": True,
        "patched_files_sha256": aggregate,
        "source_labels": {
            "vllm": labels["org.opencontainers.image.vllm.commit"],
            "vllm_ascend": labels[
                "org.opencontainers.image.vllm-ascend.commit"
            ],
            "mooncake": labels["org.opencontainers.image.mooncake.commit"],
        },
        "errors": [],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
