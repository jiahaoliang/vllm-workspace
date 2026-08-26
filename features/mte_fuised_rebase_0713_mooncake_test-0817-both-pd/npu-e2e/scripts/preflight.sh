#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

usage() {
  echo "usage: $0 (--offline|--live) RUN_DIR" >&2
  exit 2
}

test "$#" -eq 2 || usage
MODE=$1
RUN_DIR=$2
case "${MODE}" in
  --offline) MODE=offline ;;
  --live) MODE=live ;;
  *) usage ;;
esac

require_tool jq
require_tool sha256sum
validate_rendered_run "${RUN_DIR}"
require_canonical_path "${RUN_DIR}"

CONFIG="${RUN_DIR}/run-config.json"
RUN_ID=$(jq -r '.run_id' "${CONFIG}")
NS=$(jq -r '.namespace' "${CONFIG}")
EXPECTED_CONTEXT=$(jq -r '.kube_context' "${CONFIG}")
TARGET_NODE=$(jq -r '.target_node' "${CONFIG}")
CONFIG_SHA=$(sha256_file "${CONFIG}")
PREFLIGHT_DIR="${RUN_DIR}/preflight"
test -z "$(find "${PREFLIGHT_DIR}" -type l -print -quit)" ||
  die "preflight output tree must not contain symlinks"
install -d "${PREFLIGHT_DIR}"

PREFLIGHT_TMP=$(mktemp -d)
trap 'rm -rf -- "${PREFLIGHT_TMP}"' EXIT
CHECKS_JSONL="${PREFLIGHT_TMP}/checks.jsonl"
CASES_JSONL="${PREFLIGHT_TMP}/cases.jsonl"
PRIOR_JSONL="${PREFLIGHT_TMP}/prior.jsonl"

record_check() {
  local name=$1 status=$2 summary=$3 artifact=${4:-}
  jq -cn \
    --arg name "${name}" \
    --arg status "${status}" \
    --arg summary "${summary}" \
    --arg artifact "${artifact}" \
    '{name: $name, status: $status, summary: $summary, artifact: $artifact}' >> "${CHECKS_JSONL}"
}

record_check static_inputs PASS "Run config, frozen inputs, hashes, and all rendered manifests passed local validation." "inputs/rendered-sha256.txt"

if test "${MODE}" = offline; then
  record_check cluster_identity UNKNOWN "Offline mode never queries Kubernetes; context, namespace, and target node identity are unknown."
  record_check cluster_capacity UNKNOWN "Offline mode cannot prove physical Ascend910 capacity."
  record_check server_dry_run UNKNOWN "Offline mode does not contact the API server; server-side admission is unknown."
else
  CLUSTER_STATUS=PASS
  CLUSTER_SUMMARY="Configured context, namespace, and target node were read successfully."
  if ! command -v kubectl >/dev/null 2>&1; then
    CLUSTER_STATUS=FAIL
    CLUSTER_SUMMARY="kubectl is missing."
  else
    if ! kubectl config current-context > "${PREFLIGHT_DIR}/kube-context.txt" 2> "${PREFLIGHT_DIR}/kube-context.stderr"; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Unable to read the current kube context."
    elif test "$(tr -d '\r\n' < "${PREFLIGHT_DIR}/kube-context.txt")" != "${EXPECTED_CONTEXT}"; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Current kube context does not match run-config.json."
    elif ! kubectl --context "${EXPECTED_CONTEXT}" get namespace "${NS}" -o json > "${PREFLIGHT_DIR}/namespace.json" 2> "${PREFLIGHT_DIR}/namespace.stderr"; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Namespace liangjiahao is not readable in the configured context."
    elif ! kubectl --context "${EXPECTED_CONTEXT}" get node "${TARGET_NODE}" -o json > "${PREFLIGHT_DIR}/node.json" 2> "${PREFLIGHT_DIR}/node.stderr"; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Target node is not readable in the configured context."
    elif ! kubectl --context "${EXPECTED_CONTEXT}" get pods -A \
      --field-selector "spec.nodeName=${TARGET_NODE}" -o json \
      > "${PREFLIGHT_DIR}/node-pods.json" \
      2> "${PREFLIGHT_DIR}/node-pods.stderr"; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Unable to read Pods assigned to the target node."
    elif ! jq -e --arg resource "$(jq -r '.resources.npu_resource_name' "${CONFIG}")" '
        (.status.allocatable[$resource] // "0" | tonumber) > 0
      ' "${PREFLIGHT_DIR}/node.json" >/dev/null; then
      CLUSTER_STATUS=FAIL
      CLUSTER_SUMMARY="Target node does not report positive physical Ascend910 allocatable capacity."
    fi
  fi
  record_check cluster_identity "${CLUSTER_STATUS}" "${CLUSTER_SUMMARY}" "preflight/node.json"

  CAPACITY_STATUS=UNKNOWN
  CAPACITY_SUMMARY="Physical Ascend910 capacity was not evaluated because cluster identity did not pass."
  if test "${CLUSTER_STATUS}" = PASS; then
    NPU_RESOURCE=$(jq -r '.resources.npu_resource_name' "${CONFIG}")
    REQUIRED_NPU=$(jq '[.resources.baseline_npu, (.resources.prefill_npu + .resources.decode_npu)] | max' "${CONFIG}")
    if jq -n \
      --arg resource "${NPU_RESOURCE}" \
      --arg run_id "${RUN_ID}" \
      --argjson required "${REQUIRED_NPU}" \
      --slurpfile node "${PREFLIGHT_DIR}/node.json" \
      --slurpfile pods "${PREFLIGHT_DIR}/node-pods.json" '
      def requested($container):
        ($container.resources.requests[$resource] // "0" | tonumber);
      def pod_request:
        ([.spec.containers[]? | requested(.)] | add // 0) as $regular |
        ([.spec.initContainers[]? | requested(.)] | max // 0) as $init |
        ([$regular, $init] | max) + (.spec.overhead[$resource] // "0" | tonumber);
      ($node[0].status.allocatable[$resource] // "0" | tonumber) as $allocatable |
      ([$pods[0].items[] |
        select(.status.phase != "Succeeded" and .status.phase != "Failed") |
        select((.metadata.labels["test-run"] // "") != $run_id) |
        pod_request] | add // 0) as $external_requested |
      {
        resource: $resource,
        allocatable: $allocatable,
        external_requested: $external_requested,
        available_for_run: ($allocatable - $external_requested),
        required_for_largest_phase: $required,
        sufficient: (($allocatable - $external_requested) >= $required)
      }
    ' > "${PREFLIGHT_DIR}/npu-capacity.json" &&
      jq -e '.sufficient == true' "${PREFLIGHT_DIR}/npu-capacity.json" >/dev/null; then
      CAPACITY_STATUS=PASS
      CAPACITY_SUMMARY="Physical Ascend910 allocatable capacity minus non-terminal external Pod requests covers the largest run phase."
    else
      CAPACITY_STATUS=FAIL
      CAPACITY_SUMMARY="Physical Ascend910 capacity is insufficient or could not be computed."
    fi
  fi
  record_check cluster_capacity "${CAPACITY_STATUS}" "${CAPACITY_SUMMARY}" "preflight/npu-capacity.json"

  DRY_RUN_STATUS=UNKNOWN
  DRY_RUN_SUMMARY="Server dry-run was skipped because cluster identity did not pass."
  if test "${CLUSTER_STATUS}" = PASS; then
    DRY_RUN_STATUS=PASS
    DRY_RUN_SUMMARY="Every frozen serving and case manifest passed server-side dry-run."
    install -d "${PREFLIGHT_DIR}/server-dry-run"
    for manifest in baseline.json baseline-oracle.json dsa-pd.json default-v1-pd.json NPU-01.json NPU-02.json NPU-03.json NPU-04.json NPU-05.json NPU-06.json NPU-07.json NPU-08.json; do
      if ! kubectl --context "${EXPECTED_CONTEXT}" apply --dry-run=server \
        -n "${NS}" -f "${RUN_DIR}/manifests/${manifest}" -o json \
        > "${PREFLIGHT_DIR}/server-dry-run/${manifest}" \
        2> "${PREFLIGHT_DIR}/server-dry-run/${manifest}.stderr"; then
        DRY_RUN_STATUS=FAIL
        DRY_RUN_SUMMARY="At least one frozen manifest failed server-side dry-run."
      fi
    done
  fi
  record_check server_dry_run "${DRY_RUN_STATUS}" "${DRY_RUN_SUMMARY}" "preflight/server-dry-run"
fi

latest_case_status() {
  local case_id=$1 result_file= attempt_dir=
  local -a attempts=()
  shopt -s nullglob
  attempts=("${RUN_DIR}/results/${case_id}"/attempt-*/result.json)
  shopt -u nullglob
  if test "${#attempts[@]}" -gt 0; then
    result_file=$(printf '%s\n' "${attempts[@]}" | sort | tail -n 1)
  fi
  if test -z "${result_file}"; then
    echo UNKNOWN
  elif attempt_dir=$(dirname "${result_file}") &&
    test -f "${attempt_dir}/artifact-checksums.txt" &&
    (cd "${attempt_dir}" && sha256sum -c artifact-checksums.txt >/dev/null 2>&1) &&
    jq -e '
      if .status == "PASS" then .client.status == "PASS" else true end
    ' "${result_file}" >/dev/null &&
    jq -e --arg run_id "${RUN_ID}" --arg case_id "${case_id}" --arg config_sha "${CONFIG_SHA}" '
    .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
    .run_config_sha256 == $config_sha and
    (.status == "PASS" or .status == "FAIL" or .status == "INVALID") and
    .cleanup.status == "PASS"
  ' "${result_file}" >/dev/null; then
    jq -r '.status' "${result_file}"
  else
    echo UNKNOWN
  fi
}

latest_case_cleanup_health() {
  local case_id=$1 result_file= attempt_dir=
  local -a attempts=()
  shopt -s nullglob
  attempts=("${RUN_DIR}/results/${case_id}"/attempt-*/result.json)
  shopt -u nullglob
  if test "${#attempts[@]}" -gt 0; then
    result_file=$(printf '%s\n' "${attempts[@]}" | sort | tail -n 1)
  fi
  if test -z "${result_file}"; then
    echo NONE
  elif attempt_dir=$(dirname "${result_file}") &&
    test -f "${attempt_dir}/artifact-checksums.txt" &&
    (cd "${attempt_dir}" && sha256sum -c artifact-checksums.txt >/dev/null 2>&1) &&
    jq -e --arg run_id "${RUN_ID}" --arg case_id "${case_id}" --arg config_sha "${CONFIG_SHA}" '
      .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
      .run_config_sha256 == $config_sha and
      (.cleanup.status == "PASS" or .cleanup.status == "FAIL")
    ' "${result_file}" >/dev/null; then
    jq -r '.cleanup.status' "${result_file}"
  else
    echo UNKNOWN
  fi
}

for case_id in NPU-01 NPU-02 NPU-03 NPU-04 NPU-05 NPU-06 NPU-07 NPU-08; do
  jq -cn \
    --arg case_id "${case_id}" \
    --arg status "$(latest_case_status "${case_id}")" \
    --arg cleanup_health "$(latest_case_cleanup_health "${case_id}")" \
    '{case_id: $case_id, status: $status, cleanup_health: $cleanup_health}' >> "${PRIOR_JSONL}"
done
jq -s 'map({(.case_id): del(.case_id)}) | add' "${PRIOR_JSONL}" > "${PREFLIGHT_TMP}/prior.json"

if jq -e 'any(.[]; .cleanup_health == "FAIL")' "${PREFLIGHT_TMP}/prior.json" >/dev/null; then
  record_check prior_cleanup FAIL "At least one latest case attempt has failed cleanup; the run is blocked."
elif jq -e 'any(.[]; .cleanup_health == "UNKNOWN")' "${PREFLIGHT_TMP}/prior.json" >/dev/null; then
  record_check prior_cleanup UNKNOWN "At least one latest case attempt has unverifiable cleanup evidence; the run is blocked."
else
  record_check prior_cleanup PASS "No latest case attempt has failed or unverifiable cleanup evidence."
fi

jq -s 'map({(.name): del(.name)}) | add' "${CHECKS_JSONL}" > "${PREFLIGHT_TMP}/checks.json"
if jq -e 'any(.[]; .status == "FAIL")' "${PREFLIGHT_TMP}/checks.json" >/dev/null; then
  OVERALL_STATUS=FAIL
elif jq -e 'any(.[]; .status == "UNKNOWN")' "${PREFLIGHT_TMP}/checks.json" >/dev/null; then
  OVERALL_STATUS=UNKNOWN
else
  OVERALL_STATUS=PASS
fi

for case_id in NPU-01 NPU-02 NPU-03 NPU-04 NPU-05 NPU-06 NPU-07 NPU-08; do
  FAILED_CAPS=$(jq -c --arg case_id "${case_id}" --slurpfile catalog "${RUN_DIR}/inputs/cases.json" '
    . as $config | [$catalog[0].cases[] | select(.case_id == $case_id) | .required_capabilities[] |
      select(($config.capabilities[.].status // "UNKNOWN") == "FAIL")]
  ' "${CONFIG}")
  UNKNOWN_CAPS=$(jq -c --arg case_id "${case_id}" --slurpfile catalog "${RUN_DIR}/inputs/cases.json" '
    . as $config | [$catalog[0].cases[] | select(.case_id == $case_id) | .required_capabilities[] |
      select(($config.capabilities[.].status // "UNKNOWN") == "UNKNOWN")]
  ' "${CONFIG}")
  UNMET_CASES=$(jq -c --arg case_id "${case_id}" --slurpfile catalog "${RUN_DIR}/inputs/cases.json" '
    . as $prior | [$catalog[0].cases[] | select(.case_id == $case_id) | .required_cases[] |
      select(($prior[.].status // "UNKNOWN") != "PASS")]
  ' "${PREFLIGHT_TMP}/prior.json")

  if test "${OVERALL_STATUS}" = FAIL || test "$(jq 'length' <<< "${FAILED_CAPS}")" -gt 0; then
    CASE_STATUS=FAIL
  elif test "${OVERALL_STATUS}" != PASS ||
    test "$(jq 'length' <<< "${UNKNOWN_CAPS}")" -gt 0 ||
    test "$(jq 'length' <<< "${UNMET_CASES}")" -gt 0; then
    CASE_STATUS=UNKNOWN
  else
    CASE_STATUS=PASS
  fi

  jq -cn \
    --arg case_id "${case_id}" \
    --arg status "${CASE_STATUS}" \
    --arg common_gate "${OVERALL_STATUS}" \
    --argjson failed_capabilities "${FAILED_CAPS}" \
    --argjson unknown_capabilities "${UNKNOWN_CAPS}" \
    --argjson unmet_cases "${UNMET_CASES}" \
    '{
      case_id: $case_id,
      status: $status,
      catalog_status: "planned / not run",
      common_gate: $common_gate,
      failed_capabilities: $failed_capabilities,
      unknown_capabilities: $unknown_capabilities,
      unmet_cases: $unmet_cases
    }' >> "${CASES_JSONL}"
done

GENERATED_AT=$(timestamp_utc)
GENERATED_AT_EPOCH=$(date -u -d "${GENERATED_AT}" +'%s')
jq -n \
  --arg mode "${MODE}" \
  --arg generated_at "${GENERATED_AT}" \
  --argjson generated_at_epoch "${GENERATED_AT_EPOCH}" \
  --arg run_id "${RUN_ID}" \
  --arg namespace "${NS}" \
  --arg config_sha "${CONFIG_SHA}" \
  --arg overall "${OVERALL_STATUS}" \
  --slurpfile checks "${PREFLIGHT_TMP}/checks.json" \
  --slurpfile config "${CONFIG}" \
  --slurpfile cases "${CASES_JSONL}" '
  {
    schema_version: 1,
    mode: $mode,
    generated_at: $generated_at,
    generated_at_epoch: $generated_at_epoch,
    run_id: $run_id,
    namespace: $namespace,
    run_config_sha256: $config_sha,
    overall_status: $overall,
    checks: $checks[0],
    capabilities: $config[0].capabilities,
    cases: $cases
  }
' > "${PREFLIGHT_DIR}/preflight.json"

echo "preflight ${MODE} ${OVERALL_STATUS}: ${PREFLIGHT_DIR}/preflight.json"
case "${OVERALL_STATUS}" in
  PASS) exit 0 ;;
  FAIL) exit 1 ;;
  UNKNOWN) exit 2 ;;
esac
