#!/usr/bin/env bash
set -euo pipefail

readonly namespace=k8s.io
readonly source_manifest=sha256:757f82b41f7c68cd02b95a345e62df0a86a8a1f7b7ee3688d39759554d3f341a
readonly source_config=sha256:88b2802de954f2cb7085caeb1dc8357b8a7b12397ce9c246ce69d0a3e8bb54c3
readonly import_base=docker.io/library/vllm-ascend/kv-pool-layerwise-label-fix-d74269a0

oci_tmp=$(mktemp -d /tmp/kvpool-oci-labels-d74269a0-XXXXXX)
case ${oci_tmp} in
  /tmp/kvpool-oci-labels-d74269a0-*) ;;
  *) echo "unexpected temp path: ${oci_tmp}" >&2; exit 1 ;;
esac
trap 'rm -rf -- "${oci_tmp}"' EXIT

ctr -n "${namespace}" content get "${source_config}" |
  jq -c '
    .config.Labels["org.opencontainers.image.base.name"] =
      "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z"
    | .config.Labels["org.opencontainers.image.base.digest"] =
      "sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351"
    | .config.Labels["org.opencontainers.image.creation"] =
      "nerdctl-commit-eight-python-patches"
    | .config.Labels["org.opencontainers.image.patch.path"] =
      "/vllm-workspace/vllm-ascend/vllm_ascend/attention/mla_v1.py,/vllm-workspace/vllm-ascend/vllm_ascend/attention/utils.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py"
    | .config.Labels["org.opencontainers.image.patch.sha256"] =
      "7fd7860a94110cad2dc9c4c70d0162f3160bf942457778a04adcc944de2d7fe6"
    | .config.Labels["org.opencontainers.image.patch.mla-v1.sha256"] =
      "0e7c64fd572bc32234972c402fb7a42098b56288703be5e91570b0d026f70bfb"
    | .config.Labels["org.opencontainers.image.patch.attention-utils.sha256"] =
      "ebf1d53368925d966d219b0c954ba221d278626e9945209b5230db8ff19c806a"
    | .config.Labels["org.opencontainers.image.patch.ascend-store-connector.sha256"] =
      "7b55f8d5bd56a1edcd94eb629c383410bd1d8293d83727a3641abfb84993ca56"
    | .config.Labels["org.opencontainers.image.patch.config-data.sha256"] =
      "e9819771b1f26b1e860a9bc03968e721dddd85e04de23cab9ec063ad9008d6c3"
    | .config.Labels["org.opencontainers.image.patch.kv-transfer.sha256"] =
      "7649e19fe127a7300af02ed9df364ed22012c77da6a15c366b9a3ad27113e36a"
    | .config.Labels["org.opencontainers.image.patch.layerwise-config.sha256"] =
      "384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040"
    | .config.Labels["org.opencontainers.image.patch.pool-scheduler.sha256"] =
      "06e8ad911c20b956811053f463fbe86c4435ae052235180817896acda1b9269a"
    | .config.Labels["org.opencontainers.image.patch.pool-worker.sha256"] =
      "ef18371a5bde62a27080d4d74bc351358b12338c61328fd947684a461f502fb0"
    | .config.Labels["org.opencontainers.image.patch.source-commit"] =
      "d74269a08e48e3b5b097f9a34f5c421696ddda40"
    | .config.Labels["org.opencontainers.image.validation.run"] =
      "20260808T203742Z"
    | .config.Labels["org.opencontainers.image.vllm-ascend.commit"] =
      "d74269a08e48e3b5b097f9a34f5c421696ddda40"
    | .history += [{
        "created": "2026-08-08T20:37:42Z",
        "created_by": "LABEL cumulative Mooncake shared-buffer patch provenance",
        "author": "jiahaoliang <gzliangjiahao@gmail.com>",
        "comment": "OCI config metadata correction after nerdctl commit",
        "empty_layer": true
      }]
  ' >"${oci_tmp}/config.json"

config_hex=$(sha256sum "${oci_tmp}/config.json" | awk '{print $1}')
config_digest=sha256:${config_hex}
config_size=$(wc -c <"${oci_tmp}/config.json")

ctr -n "${namespace}" content get "${source_manifest}" |
  jq -c --arg digest "${config_digest}" --argjson size "${config_size}" '
    .config.digest = $digest | .config.size = $size
  ' >"${oci_tmp}/manifest.json"

manifest_hex=$(sha256sum "${oci_tmp}/manifest.json" | awk '{print $1}')
manifest_digest=sha256:${manifest_hex}
manifest_size=$(wc -c <"${oci_tmp}/manifest.json")

ctr -n "${namespace}" content ingest \
  --expected-size "${config_size}" \
  --expected-digest "${config_digest}" \
  "kvpool-config-${config_hex}" <"${oci_tmp}/config.json"
ctr -n "${namespace}" content ingest \
  --expected-size "${manifest_size}" \
  --expected-digest "${manifest_digest}" \
  "kvpool-manifest-${manifest_hex}" <"${oci_tmp}/manifest.json"

mkdir -p "${oci_tmp}/layout/blobs/sha256"
cp "${oci_tmp}/config.json" "${oci_tmp}/layout/blobs/sha256/${config_hex}"
cp "${oci_tmp}/manifest.json" "${oci_tmp}/layout/blobs/sha256/${manifest_hex}"
printf '%s\n' '{"imageLayoutVersion":"1.0.0"}' >"${oci_tmp}/layout/oci-layout"
jq -cn \
  --arg digest "${manifest_digest}" \
  --argjson size "${manifest_size}" '
  {
    schemaVersion: 2,
    manifests: [{
      mediaType: "application/vnd.oci.image.manifest.v1+json",
      digest: $digest,
      size: $size,
      platform: {architecture: "arm64", os: "linux"},
      annotations: {"org.opencontainers.image.ref.name": "metadata-corrected"}
    }]
  }' >"${oci_tmp}/layout/index.json"
tar -C "${oci_tmp}/layout" -cf "${oci_tmp}/layout.tar" .

ctr -n "${namespace}" images import \
  --no-unpack \
  --platform linux/arm64 \
  --base-name "${import_base}" \
  "${oci_tmp}/layout.tar"

printf 'config_digest=%s\nconfig_size=%s\nmanifest_digest=%s\nmanifest_size=%s\ntemporary_image=%s:metadata-corrected\n' \
  "${config_digest}" "${config_size}" "${manifest_digest}" "${manifest_size}" "${import_base}"
