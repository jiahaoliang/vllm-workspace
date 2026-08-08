#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FINAL_MANIFEST = "sha256:e4333425928a1566f07e03e19744e7a88a48a379bbb00afffe8d4e3c8e8bfb01"
FINAL_CONFIG = "sha256:b073f5891dcb131d9c9082e375acb3b192220ec7b4d6a1e2ab958a8b95a6737a"
PARENT_MANIFEST = "sha256:fb3013fdf023e4f7385434f0861c924efbe17c50cadef36c361b8b2ba4259824"
PARENT_CONFIG = "sha256:6cd13b04a4bea4668f386d1c53986e73430727b64588047f6f41f21dfa41ad7b"
NATIVE_MANIFEST = "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
NATIVE_CONFIG = "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
PRE_METADATA_MANIFEST = "sha256:016a8ce2784fb159fe8e1fb581c5f867bcc0b00e4fc9e8d9a11dbc1d4fca8a61"
PRE_METADATA_CONFIG = "sha256:febadf8cdeba76763e61a12860056a9b9650bf7a1337f25e978e7fb69cb72aab"
PATCH_LAYER = "sha256:f225b9279bd546f0711933a464f47b34ab6ee42bf3e27e5cfa9704eda126b818"
PATCH_DIFF_ID = "sha256:cfbcd50ff16ce3279255adb953af769020bbbfb3f3248b8693825891359689f3"
PATCH_SHA256 = "3b60035ecbc363ada645fe0e0c5289271090c574a9bd6e26bdcdbd8e47b8aaa9"
FINAL_SOURCE = "2d179d07c86e5f820fd6591c0c7fdef2b5132c14"
VLLM_SOURCE = "54503ecec0f3ac31e5ecfc5f28652e4cc42307b5"
MOONCAKE_SOURCE = "df3f74ed8ebdb0c935554beea6299a9f11c723e2"


def load(name: str, digest: str) -> dict[str, object]:
    entries = json.loads((ROOT / name).read_text(encoding="utf-8"))
    matches = [entry for entry in entries if entry["ManifestDesc"]["digest"] == digest]
    assert matches, (name, digest)
    return matches[0]


def read_hashes(name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        digest, path = line.split(maxsplit=1)
        normalized = path.removeprefix("/vllm-workspace/vllm-ascend/")
        result[normalized] = digest
    return result


def main() -> int:
    final = load("final-native-inspect.json", FINAL_MANIFEST)
    parent = load("direct-parent-native-inspect.json", PARENT_MANIFEST)
    native = load("native-base-native-inspect.json", NATIVE_MANIFEST)
    pre_metadata = load("pre-metadata-native-inspect.json", PRE_METADATA_MANIFEST)

    assert final["ImageConfigDesc"]["digest"] == FINAL_CONFIG
    assert parent["ImageConfigDesc"]["digest"] == PARENT_CONFIG
    assert native["ImageConfigDesc"]["digest"] == NATIVE_CONFIG
    assert pre_metadata["ImageConfigDesc"]["digest"] == PRE_METADATA_CONFIG
    assert final["ImageConfig"]["os"] == "linux"
    assert final["ImageConfig"]["architecture"] == "arm64"

    labels = final["ImageConfig"]["config"]["Labels"]
    assert labels["org.opencontainers.image.vllm.commit"] == VLLM_SOURCE
    assert labels["org.opencontainers.image.vllm-ascend.commit"] == FINAL_SOURCE
    assert labels["org.opencontainers.image.mooncake.commit"] == MOONCAKE_SOURCE
    assert labels["org.opencontainers.image.base.digest"] == PARENT_MANIFEST
    assert labels["org.opencontainers.image.patch.source-commit"] == FINAL_SOURCE
    assert labels["org.opencontainers.image.patch.sha256"] == PATCH_SHA256

    final_layers = final["Manifest"]["layers"]
    parent_layers = parent["Manifest"]["layers"]
    native_layers = native["Manifest"]["layers"]
    pre_metadata_layers = pre_metadata["Manifest"]["layers"]
    assert len(final_layers) == 27
    assert len(parent_layers) == 26
    assert len(native_layers) == 21
    assert final_layers == pre_metadata_layers
    assert final_layers[:-1] == parent_layers
    assert parent_layers[: len(native_layers)] == native_layers
    assert final_layers[-1]["digest"] == PATCH_LAYER

    final_diff_ids = final["ImageConfig"]["rootfs"]["diff_ids"]
    parent_diff_ids = parent["ImageConfig"]["rootfs"]["diff_ids"]
    native_diff_ids = native["ImageConfig"]["rootfs"]["diff_ids"]
    pre_metadata_diff_ids = pre_metadata["ImageConfig"]["rootfs"]["diff_ids"]
    assert len(final_diff_ids) == 27
    assert final_diff_ids == pre_metadata_diff_ids
    assert final_diff_ids[:-1] == parent_diff_ids
    assert parent_diff_ids[: len(native_diff_ids)] == native_diff_ids
    assert final_diff_ids[-1] == PATCH_DIFF_ID

    checkout_hashes = read_hashes("checkout-production-sha256.txt")
    image_hashes = read_hashes("image-production-sha256.txt")
    assert len(checkout_hashes) == 7
    assert image_hashes == checkout_hashes
    assert image_hashes[
        "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py"
    ] == PATCH_SHA256

    summary = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "platform": "linux/arm64",
        "final_manifest_digest": FINAL_MANIFEST,
        "final_config_digest": FINAL_CONFIG,
        "direct_patch_parent_manifest_digest": PARENT_MANIFEST,
        "direct_patch_parent_config_digest": PARENT_CONFIG,
        "native_runtime_base_manifest_digest": NATIVE_MANIFEST,
        "native_runtime_base_config_digest": NATIVE_CONFIG,
        "pre_metadata_manifest_digest": PRE_METADATA_MANIFEST,
        "pre_metadata_config_digest": PRE_METADATA_CONFIG,
        "metadata_correction_layer_descriptors_unchanged": True,
        "layer_descriptor_count": len(final_layers),
        "patch_layer_digest": PATCH_LAYER,
        "patch_diff_id": PATCH_DIFF_ID,
        "source_labels": {
            "vllm": VLLM_SOURCE,
            "vllm_ascend": FINAL_SOURCE,
            "mooncake": MOONCAKE_SOURCE,
        },
        "production_files_compared": len(image_hashes),
        "production_file_hashes_equal": True,
        "errors": [],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
