#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[4]
SOURCE_ROOT = WORKSPACE / "repos/vllm-ascend"
BASE_IMAGE = "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z"
PRE_METADATA_IMAGE = "docker.io/library/vllm-ascend:kv-pool-layerwise-pre-metadata-1829639a-20260808T111904Z"
FINAL_IMAGE = "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-1829639a-df3f74ed-20260808T111904Z"
BASE_MANIFEST = (
    "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
)
BASE_CONFIG = "sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b"
PRE_METADATA_MANIFEST = (
    "sha256:8148da50b293a315e5a133085a007cb1b2ce588f97584cb5d5bce9d945c85bb2"
)
PRE_METADATA_CONFIG = (
    "sha256:8b88cc3c8f59e4606758353810a648af0a8a6e8b63fb19876aeaf682ea86710b"
)
FINAL_MANIFEST = (
    "sha256:ed0e622f05739bf5202eb18c4565aa4f7f82e653213c49b2379d93f2700034c3"
)
FINAL_CONFIG = "sha256:2bcbaa5ea4b59874f03e8c6c6cc169edece8cac52faa5ea9f7a5313f074a3ff9"
PATCH_LAYER = "sha256:f24d67f3891e8107cf55765e2ebd63a87488fcd8db773c22ec19d462fc4ea409"
PATCH_DIFF_ID = (
    "sha256:7b8f2be1fbd0895cd72c9ffb9ec0fc758c12c76df9bacc42b91b48f05ed50f32"
)
PATCH_SET_SHA256 = "8badc0e5cd49e2e2e3600c9012b9326ec113c2fab527fbabf22d3885b686f439"
FINAL_SOURCE = "1829639a1e019d3ed34055787febc7ee89fb0f68"
VLLM_SOURCE = "54503ecec0f3ac31e5ecfc5f28652e4cc42307b5"
MOONCAKE_SOURCE = "df3f74ed8ebdb0c935554beea6299a9f11c723e2"
PRODUCTION_FILES = (
    "vllm_ascend/attention/mla_v1.py",
    "vllm_ascend/attention/utils.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py",
)


def run(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def capture_inspect(image: str, filename: str) -> list[dict[str, object]]:
    entries = json.loads(
        run(["nerdctl", "-n", "k8s.io", "image", "inspect", "--mode=native", image])
    )
    (ROOT / filename).write_text(
        json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return entries


def select(entries: list[dict[str, object]], digest: str) -> dict[str, object]:
    matches = [entry for entry in entries if entry["ManifestDesc"]["digest"] == digest]
    assert matches, digest
    return matches[0]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_hashes(hashes: dict[str, str], prefix: str = "") -> str:
    return "".join(f"{hashes[path]}  {prefix}{path}\n" for path in PRODUCTION_FILES)


def main() -> int:
    source_head = run(["git", "-C", str(SOURCE_ROOT), "rev-parse", "HEAD"]).strip()
    source_dirty = run(
        ["git", "-C", str(SOURCE_ROOT), "status", "--porcelain=v1"]
    ).strip()
    assert source_head == FINAL_SOURCE
    assert not source_dirty

    base = select(
        capture_inspect(BASE_IMAGE, "native-base-native-inspect.json"), BASE_MANIFEST
    )
    pre_metadata = select(
        capture_inspect(PRE_METADATA_IMAGE, "pre-metadata-native-inspect.json"),
        PRE_METADATA_MANIFEST,
    )
    final = select(
        capture_inspect(FINAL_IMAGE, "final-native-inspect.json"), FINAL_MANIFEST
    )

    assert base["ImageConfigDesc"]["digest"] == BASE_CONFIG
    assert pre_metadata["ImageConfigDesc"]["digest"] == PRE_METADATA_CONFIG
    assert final["ImageConfigDesc"]["digest"] == FINAL_CONFIG
    assert final["ImageConfig"]["os"] == "linux"
    assert final["ImageConfig"]["architecture"] == "arm64"

    labels = final["ImageConfig"]["config"]["Labels"]
    assert labels["org.opencontainers.image.vllm.commit"] == VLLM_SOURCE
    assert labels["org.opencontainers.image.vllm-ascend.commit"] == FINAL_SOURCE
    assert labels["org.opencontainers.image.mooncake.commit"] == MOONCAKE_SOURCE
    assert labels["org.opencontainers.image.base.name"] == BASE_IMAGE
    assert labels["org.opencontainers.image.base.digest"] == BASE_MANIFEST
    assert labels["org.opencontainers.image.patch.source-commit"] == FINAL_SOURCE
    assert labels["org.opencontainers.image.patch.sha256"] == PATCH_SET_SHA256
    assert labels["org.opencontainers.image.creation"] == (
        "nerdctl-commit-seven-python-patches"
    )

    base_layers = base["Manifest"]["layers"]
    pre_metadata_layers = pre_metadata["Manifest"]["layers"]
    final_layers = final["Manifest"]["layers"]
    assert len(base_layers) == 21
    assert len(final_layers) == 22
    assert final_layers == pre_metadata_layers
    assert final_layers[:-1] == base_layers
    assert final_layers[-1]["digest"] == PATCH_LAYER

    base_diff_ids = base["ImageConfig"]["rootfs"]["diff_ids"]
    pre_metadata_diff_ids = pre_metadata["ImageConfig"]["rootfs"]["diff_ids"]
    final_diff_ids = final["ImageConfig"]["rootfs"]["diff_ids"]
    assert final_diff_ids == pre_metadata_diff_ids
    assert final_diff_ids[:-1] == base_diff_ids
    assert final_diff_ids[-1] == PATCH_DIFF_ID

    checkout_hashes = {path: file_hash(SOURCE_ROOT / path) for path in PRODUCTION_FILES}
    checkout_text = format_hashes(checkout_hashes)
    assert hashlib.sha256(checkout_text.encode()).hexdigest() == PATCH_SET_SHA256
    (ROOT / "checkout-production-sha256.txt").write_text(
        checkout_text, encoding="utf-8"
    )

    image_paths = [f"/vllm-workspace/vllm-ascend/{path}" for path in PRODUCTION_FILES]
    image_text = run(
        [
            "nerdctl",
            "-n",
            "k8s.io",
            "run",
            "--rm",
            "--name",
            "kv-pool-layerwise-evidence-1829639a-20260808T111904Z",
            "--net",
            "none",
            "--pull",
            "never",
            "--entrypoint",
            "sha256sum",
            FINAL_IMAGE,
            *image_paths,
        ]
    )
    (ROOT / "image-production-sha256.txt").write_text(image_text, encoding="utf-8")
    image_hashes = {
        path.removeprefix("/vllm-workspace/vllm-ascend/"): digest
        for digest, path in (line.split(maxsplit=1) for line in image_text.splitlines())
    }
    assert image_hashes == checkout_hashes

    for path, digest in checkout_hashes.items():
        label_key = (
            "org.opencontainers.image.patch."
            + {
                "vllm_ascend/attention/mla_v1.py": "mla-v1",
                "vllm_ascend/attention/utils.py": "attention-utils",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py": "ascend-store-connector",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py": "config-data",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py": "layerwise-config",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py": "pool-scheduler",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py": "pool-worker",
            }[path]
            + ".sha256"
        )
        assert labels[label_key] == digest

    summary = {
        "schema_version": 1,
        "status": "passed",
        "validated": True,
        "platform": "linux/arm64",
        "source_head": source_head,
        "source_dirty": False,
        "base_image": BASE_IMAGE,
        "base_manifest_digest": BASE_MANIFEST,
        "base_config_digest": BASE_CONFIG,
        "pre_metadata_image": PRE_METADATA_IMAGE,
        "pre_metadata_manifest_digest": PRE_METADATA_MANIFEST,
        "pre_metadata_config_digest": PRE_METADATA_CONFIG,
        "final_image": FINAL_IMAGE,
        "final_manifest_digest": FINAL_MANIFEST,
        "final_config_digest": FINAL_CONFIG,
        "metadata_correction_layer_descriptors_unchanged": True,
        "layer_descriptor_count": len(final_layers),
        "patch_layer_digest": PATCH_LAYER,
        "patch_diff_id": PATCH_DIFF_ID,
        "patched_files_sha256": PATCH_SET_SHA256,
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
