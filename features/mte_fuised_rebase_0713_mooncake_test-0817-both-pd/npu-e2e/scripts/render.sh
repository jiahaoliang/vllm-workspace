#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

usage() {
  echo "usage: $0 RUN_CONFIG RUN_DIR" >&2
  exit 2
}

test "$#" -eq 2 || usage
CONFIG=$1
RUN_DIR=$2

validate_run_config "${CONFIG}"

RUN_ID=$(jq -r '.run_id' "${CONFIG}")
NS=$(jq -r '.namespace' "${CONFIG}")
EXPECTED_RUN_DIR="$(jq -r '.artifact_root' "${CONFIG}")/${RUN_ID}"
test "${RUN_DIR}" = "${EXPECTED_RUN_DIR}" || die "RUN_DIR must equal artifact_root/run_id: ${EXPECTED_RUN_DIR}"
require_canonical_path "${RUN_DIR}"
test ! -L "${RUN_DIR}" || die "RUN_DIR must not be a symlink: ${RUN_DIR}"
if test -e "${RUN_DIR}" && test -n "$(find "${RUN_DIR}" -mindepth 1 -maxdepth 1 -print -quit)"; then
  die "RUN_DIR already exists and is not empty: ${RUN_DIR}"
fi

install -d "${RUN_DIR}/manifests" "${RUN_DIR}/fixtures" "${RUN_DIR}/inputs" "${RUN_DIR}/preflight" "${RUN_DIR}/results"
cp "${CONFIG}" "${RUN_DIR}/run-config.json"
cp "${CASE_CATALOG}" "${RUN_DIR}/inputs/cases.json"
cp "${FIXTURE_TEMPLATE}" "${RUN_DIR}/fixtures/requests.jsonl"

RUN_CONFIG_TEXT=$(jq '.' "${CONFIG}")
PORT=$(jq -r '.client.service_port' "${CONFIG}")
RENDER_TMP=$(mktemp -d)
trap 'rm -rf -- "${RENDER_TMP}"' EXIT

emit_workload() {
  local output=$1 role=$2 name=$3 image=$4 command_key=$5 npu_count=$6 dp_rank=$7
  local command_json
  command_json=$(jq -c --arg key "${command_key}" '.commands[$key]' "${CONFIG}")
  jq \
    --arg run_id "${RUN_ID}" \
    --arg namespace "${NS}" \
    --arg role "${role}" \
    --arg name "${name}" \
    --arg image "${image}" \
    --arg node "$(jq -r '.target_node' "${CONFIG}")" \
    --arg dp_rank "${dp_rank}" \
    --arg npu_name "$(jq -r '.resources.npu_resource_name' "${CONFIG}")" \
    --arg npu_count "${npu_count}" \
    --arg run_config "${RUN_CONFIG_TEXT}" \
    --argjson command "${command_json}" \
    --argjson port "${PORT}" '
      .items[0].metadata.name = ($name + "-config") |
      .items[0].metadata.namespace = $namespace |
      .items[0].metadata.labels["test-run"] = $run_id |
      .items[0].metadata.labels["test-role"] = $role |
      .items[0].metadata.labels["dp-rank"] = $dp_rank |
      .items[0].data["run-config.json"] = $run_config |
      .items[1].metadata.name = $name |
      .items[1].metadata.namespace = $namespace |
      .items[1].metadata.labels["test-run"] = $run_id |
      .items[1].metadata.labels["test-role"] = $role |
      .items[1].metadata.labels["dp-rank"] = $dp_rank |
      .items[1].spec.selector.matchLabels["test-run"] = $run_id |
      .items[1].spec.selector.matchLabels["workload-name"] = $name |
      .items[1].spec.template.metadata.labels["test-run"] = $run_id |
      .items[1].spec.template.metadata.labels["test-role"] = $role |
      .items[1].spec.template.metadata.labels["workload-name"] = $name |
      .items[1].spec.template.metadata.labels["dp-rank"] = $dp_rank |
      .items[1].spec.template.spec.nodeSelector["kubernetes.io/hostname"] = $node |
      .items[1].spec.template.spec.containers[0].image = $image |
      .items[1].spec.template.spec.containers[0].command = $command |
      .items[1].spec.template.spec.containers[0].env[0].value = $run_id |
      .items[1].spec.template.spec.containers[0].env[1].value = $role |
      .items[1].spec.template.spec.containers[0].env[2].value = $dp_rank |
      .items[1].spec.template.spec.containers[0].ports[0].containerPort = $port |
      .items[1].spec.template.spec.containers[0].resources.requests = {($npu_name): $npu_count} |
      .items[1].spec.template.spec.containers[0].resources.limits = {($npu_name): $npu_count} |
      .items[1].spec.template.spec.volumes[0].configMap.name = ($name + "-config") |
      .items[2].metadata.name = $name |
      .items[2].metadata.namespace = $namespace |
      .items[2].metadata.labels["test-run"] = $run_id |
      .items[2].metadata.labels["test-role"] = $role |
      .items[2].metadata.labels["dp-rank"] = $dp_rank |
      .items[2].spec.selector["test-run"] = $run_id |
      .items[2].spec.selector["workload-name"] = $name |
      .items[2].spec.ports[0].port = $port |
      .items[]
    ' "${HARNESS_ROOT}/templates/workload.template.json" >> "${output}"
}

emit_aggregate_service() {
  local output=$1 role=$2 name=$3
  jq \
    --arg run_id "${RUN_ID}" \
    --arg namespace "${NS}" \
    --arg role "${role}" \
    --arg name "${name}" \
    --argjson port "${PORT}" '
      .metadata.name = $name |
      .metadata.namespace = $namespace |
      .metadata.labels["test-run"] = $run_id |
      .metadata.labels["test-role"] = $role |
      .spec.selector["test-run"] = $run_id |
      .spec.selector["test-role"] = $role |
      .spec.ports[0].port = $port
    ' "${HARNESS_ROOT}/templates/service.template.json" >> "${output}"
}

finish_list() {
  local source=$1 destination=$2
  jq -s '{apiVersion: "v1", kind: "List", items: .}' "${source}" > "${destination}"
  manifest_static_check "${destination}"
}

BASELINE_ITEMS="${RENDER_TMP}/baseline.items"
BASELINE_IMAGE=$(jq -r '.images.baseline' "${CONFIG}")
emit_workload "${BASELINE_ITEMS}" baseline "${RUN_ID}-baseline" "${BASELINE_IMAGE}" baseline "$(jq -r '.resources.baseline_npu' "${CONFIG}")" 0
finish_list "${BASELINE_ITEMS}" "${RUN_DIR}/manifests/baseline.json"

DSA_ITEMS="${RENDER_TMP}/dsa.items"
PREFILL_IMAGE=$(jq -r '.images.prefill' "${CONFIG}")
DECODE_IMAGE=$(jq -r '.images.decode' "${CONFIG}")
for ((rank = 0; rank < $(jq -r '.topology.prefill_dp' "${CONFIG}"); rank++)); do
  emit_workload "${DSA_ITEMS}" prefill "${RUN_ID}-prefill-dp${rank}" "${PREFILL_IMAGE}" prefill "$(jq -r '.topology.prefill_tp' "${CONFIG}")" "${rank}"
done
for ((rank = 0; rank < $(jq -r '.topology.decode_dp' "${CONFIG}"); rank++)); do
  emit_workload "${DSA_ITEMS}" decode "${RUN_ID}-decode-dp${rank}" "${DECODE_IMAGE}" decode "$(jq -r '.topology.decode_tp' "${CONFIG}")" "${rank}"
done
emit_aggregate_service "${DSA_ITEMS}" prefill "${RUN_ID}-prefill"
emit_aggregate_service "${DSA_ITEMS}" decode "${RUN_ID}-decode"
finish_list "${DSA_ITEMS}" "${RUN_DIR}/manifests/dsa-pd.json"

V1_ITEMS="${RENDER_TMP}/v1.items"
V1_IMAGE=$(jq -r '.images.default_v1' "${CONFIG}")
for ((rank = 0; rank < $(jq -r '.topology.prefill_dp' "${CONFIG}"); rank++)); do
  emit_workload "${V1_ITEMS}" default-v1-prefill "${RUN_ID}-v1-prefill-dp${rank}" "${V1_IMAGE}" default_v1_prefill "$(jq -r '.topology.prefill_tp' "${CONFIG}")" "${rank}"
done
for ((rank = 0; rank < $(jq -r '.topology.decode_dp' "${CONFIG}"); rank++)); do
  emit_workload "${V1_ITEMS}" default-v1-decode "${RUN_ID}-v1-decode-dp${rank}" "${V1_IMAGE}" default_v1_decode "$(jq -r '.topology.decode_tp' "${CONFIG}")" "${rank}"
done
emit_aggregate_service "${V1_ITEMS}" default-v1-prefill "${RUN_ID}-default-v1-prefill"
emit_aggregate_service "${V1_ITEMS}" default-v1-decode "${RUN_ID}-default-v1-decode"
finish_list "${V1_ITEMS}" "${RUN_DIR}/manifests/default-v1-pd.json"

render_client_manifest() {
  local case_id=$1 case_json=$2 requests_text=$3 target_role=$4 output=$5
  local object_name client_image client_command target_url
  object_name=$(case_object_name "${RUN_ID}" "${case_id}")
  client_image=$(jq -r '.images.client' "${CONFIG}")
  client_command=$(jq -c '.client.command' "${CONFIG}")
  target_url="http://${RUN_ID}-${target_role}.${NS}.svc:${PORT}"
  jq \
    --arg run_id "${RUN_ID}" \
    --arg namespace "${NS}" \
    --arg case_id "${case_id}" \
    --arg object_name "${object_name}" \
    --arg image "${client_image}" \
    --arg target_url "${target_url}" \
    --arg case_json "${case_json}" \
    --arg requests "${requests_text}" \
    --arg run_config "${RUN_CONFIG_TEXT}" \
    --argjson command "${client_command}" \
    --argjson deadline "$(jq '.client.active_deadline_seconds' "${CONFIG}")" '
      .items[0].metadata.name = $object_name |
      .items[0].metadata.namespace = $namespace |
      .items[0].metadata.labels["test-run"] = $run_id |
      .items[0].metadata.labels["case-id"] = $case_id |
      .items[0].data["case.json"] = $case_json |
      .items[0].data["requests.jsonl"] = $requests |
      .items[0].data["run-config.json"] = $run_config |
      .items[1].metadata.name = $object_name |
      .items[1].metadata.namespace = $namespace |
      .items[1].metadata.labels["test-run"] = $run_id |
      .items[1].metadata.labels["case-id"] = $case_id |
      .items[1].spec.activeDeadlineSeconds = $deadline |
      .items[1].spec.template.metadata.labels["test-run"] = $run_id |
      .items[1].spec.template.metadata.labels["case-id"] = $case_id |
      .items[1].spec.template.spec.containers[0].image = $image |
      .items[1].spec.template.spec.containers[0].command = $command |
      .items[1].spec.template.spec.containers[0].args[1] = $run_id |
      .items[1].spec.template.spec.containers[0].args[3] = $case_id |
      .items[1].spec.template.spec.containers[0].args[5] = $target_url |
      .items[1].spec.template.spec.volumes[0].configMap.name = $object_name
    ' "${HARNESS_ROOT}/templates/client-job.template.json" > "${output}"
  manifest_static_check "${output}"
}

ALL_REQUESTS=$(jq -c . "${FIXTURE_TEMPLATE}")
BASELINE_CASE=$(jq -c -n --argjson ids "$(jq -s '[.[].request_id]' "${FIXTURE_TEMPLATE}")" '{case_id: "BASELINE", status: "planned / not run", request_ids: $ids, oracles: ["Frozen output token IDs and finish reason for every fixture"]}')
render_client_manifest BASELINE "${BASELINE_CASE}" "${ALL_REQUESTS}" baseline "${RUN_DIR}/manifests/baseline-oracle.json"

for case_id in NPU-01 NPU-02 NPU-03 NPU-04 NPU-05 NPU-06 NPU-07 NPU-08; do
  case_json=$(jq -c --arg case_id "${case_id}" '.cases[] | select(.case_id == $case_id)' "${CASE_CATALOG}")
  request_ids=$(jq -c '.request_ids' <<< "${case_json}")
  requests_text=$(jq -c --argjson ids "${request_ids}" 'select(.request_id as $id | $ids | index($id))' "${FIXTURE_TEMPLATE}")
  target_role=$(jq -r '.target_service' <<< "${case_json}")
  render_client_manifest "${case_id}" "${case_json}" "${requests_text}" "${target_role}" "${RUN_DIR}/manifests/${case_id}.json"
done

(cd "${RUN_DIR}" && sha256sum run-config.json inputs/cases.json fixtures/requests.jsonl manifests/*.json > inputs/rendered-sha256.txt)
echo "render PASS: ${RUN_DIR}"
