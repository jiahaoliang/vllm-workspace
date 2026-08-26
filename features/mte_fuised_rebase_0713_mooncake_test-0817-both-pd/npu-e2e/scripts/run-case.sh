#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

usage() {
  echo "usage: $0 RUN_DIR NPU-0[1-8]" >&2
  exit 2
}

test "$#" -eq 2 || usage
RUN_DIR=$1
CASE_ID=$2
[[ "${CASE_ID}" =~ ^NPU-0[1-8]$ ]] || usage

require_tool jq
require_tool sha256sum
require_tool base64
validate_rendered_run "${RUN_DIR}"
require_canonical_path "${RUN_DIR}"

CONFIG="${RUN_DIR}/run-config.json"
PREFLIGHT="${RUN_DIR}/preflight/preflight.json"
MANIFEST="${RUN_DIR}/manifests/${CASE_ID}.json"
RUN_ID=$(jq -r '.run_id' "${CONFIG}")
NS=$(jq -r '.namespace' "${CONFIG}")
EXPECTED_CONTEXT=$(jq -r '.kube_context' "${CONFIG}")
CONFIG_SHA=$(sha256_file "${CONFIG}")
OBJECT_NAME=$(case_object_name "${RUN_ID}" "${CASE_ID}")

if ! "${SCRIPT_DIR}/preflight.sh" --live "${RUN_DIR}"; then
  die "runner-generated live preflight did not pass"
fi
require_regular_file "${PREFLIGHT}"
NOW_EPOCH=$(date -u +'%s')
PREFLIGHT_EPOCH=$(jq -er '.generated_at_epoch | numbers | floor' "${PREFLIGHT}") ||
  die "live preflight has no valid generation epoch"
PREFLIGHT_TIMESTAMP=$(jq -er '.generated_at | strings' "${PREFLIGHT}") ||
  die "live preflight has no valid generation timestamp"
PARSED_PREFLIGHT_EPOCH=$(date -u -d "${PREFLIGHT_TIMESTAMP}" +'%s') ||
  die "live preflight generation timestamp is invalid"
test "${PREFLIGHT_EPOCH}" = "${PARSED_PREFLIGHT_EPOCH}" ||
  die "live preflight generation timestamp and epoch disagree"
PREFLIGHT_AGE=$((NOW_EPOCH - PREFLIGHT_EPOCH))
test "${PREFLIGHT_AGE}" -ge -60 && test "${PREFLIGHT_AGE}" -le 600 ||
  die "live preflight must be regenerated within 10 minutes of case execution"
case_manifest_static_check "${MANIFEST}" "${RUN_ID}" "${CASE_ID}"
jq -e \
  --arg run_id "${RUN_ID}" \
  --arg namespace "${NS}" \
  --arg case_id "${CASE_ID}" \
  --arg config_sha "${CONFIG_SHA}" '
  .schema_version == 1 and
  .mode == "live" and
  .run_id == $run_id and
  .namespace == $namespace and
  .run_config_sha256 == $config_sha and
  .overall_status == "PASS" and
  ([.cases[] | select(.case_id == $case_id) | .status] == ["PASS"])
' "${PREFLIGHT}" >/dev/null ||
  die "a current live PASS preflight and PASS gate for ${CASE_ID} are required"

require_tool kubectl
CURRENT_CONTEXT=$(kubectl config current-context) || die "unable to read current kube context"
test "${CURRENT_CONTEXT}" = "${EXPECTED_CONTEXT}" || die "current kube context drifted from run-config.json"
kubectl --context "${EXPECTED_CONTEXT}" get namespace "${NS}" -o name >/dev/null ||
  die "namespace liangjiahao is not readable"

ATTEMPT_ID="attempt-$(date -u +'%Y%m%dT%H%M%SZ')"
ATTEMPT_DIR="${RUN_DIR}/results/${CASE_ID}/${ATTEMPT_ID}"
require_canonical_path "${RUN_DIR}/results/${CASE_ID}"
require_canonical_path "${ATTEMPT_DIR}"
test ! -e "${ATTEMPT_DIR}" || die "attempt directory already exists: ${ATTEMPT_DIR}"
install -d "${ATTEMPT_DIR}"
cp "${MANIFEST}" "${ATTEMPT_DIR}/case-manifest.json"
cp "${PREFLIGHT}" "${ATTEMPT_DIR}/preflight.json"

STARTED_AT=$(timestamp_utc)
MUTATION_ATTEMPTED=0
FINALIZED=0
CONFIGMAP_UID=
JOB_UID=

delete_owned_object() {
  local kind=$1 uid=$2 output=$3 current
  test -n "${uid}" || return 0
  current="${ATTEMPT_DIR}/${kind}-before-delete.json"
  if ! kubectl --context "${EXPECTED_CONTEXT}" get -n "${NS}" \
    "${kind}/${OBJECT_NAME}" --ignore-not-found -o json > "${current}" 2>> "${output}"; then
    echo "unable to inspect ${kind}/${OBJECT_NAME} before cleanup" >> "${output}"
    return 1
  fi
  if test ! -s "${current}"; then
    return 0
  fi
  if ! jq -e \
    --arg uid "${uid}" --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" '
    .metadata.uid == $uid and
    .metadata.labels["app.kubernetes.io/managed-by"] == "dsa-npu-e2e" and
    .metadata.labels["test-run"] == $run_id and
    .metadata.labels["case-id"] == $case_id
  ' "${current}" >/dev/null; then
    echo "refusing to delete ${kind}/${OBJECT_NAME}: UID or ownership labels drifted" >> "${output}"
    return 1
  fi
  kubectl --context "${EXPECTED_CONTEXT}" delete -n "${NS}" \
    "${kind}/${OBJECT_NAME}" --wait=true >> "${output}" 2>&1
}

emergency_cleanup() {
  local exit_code=$?
  if test "${MUTATION_ATTEMPTED}" -eq 1 && test "${FINALIZED}" -eq 0; then
    mapfile -t emergency_command < <(render_cleanup_command "${CONFIG}" "${RUN_ID}" "${CASE_ID}")
    "${emergency_command[@]}" >> "${ATTEMPT_DIR}/emergency-cleanup.log" 2>&1 || true
    delete_owned_object job "${JOB_UID}" "${ATTEMPT_DIR}/emergency-cleanup.log" || true
    delete_owned_object configmap "${CONFIGMAP_UID}" "${ATTEMPT_DIR}/emergency-cleanup.log" || true
  fi
  return "${exit_code}"
}
trap emergency_cleanup EXIT

set +e
kubectl --context "${EXPECTED_CONTEXT}" apply --dry-run=server \
  -n "${NS}" -f "${MANIFEST}" -o json \
  > "${ATTEMPT_DIR}/server-dry-run.json" \
  2> "${ATTEMPT_DIR}/server-dry-run.stderr"
DRY_RUN_RC=$?
set -e

if test "${DRY_RUN_RC}" -ne 0; then
  FINALIZED=1
  trap - EXIT
  die "case manifest failed server-side dry-run; no cluster mutation was attempted"
fi

kubectl --context "${EXPECTED_CONTEXT}" get -n "${NS}" \
  "job/${OBJECT_NAME}" "configmap/${OBJECT_NAME}" \
  --ignore-not-found -o name > "${ATTEMPT_DIR}/objects-before-create.txt" \
  2> "${ATTEMPT_DIR}/objects-before-create.stderr" || {
    FINALIZED=1
    trap - EXIT
    die "unable to prove that the case Job and ConfigMap names are unused"
  }
if test -s "${ATTEMPT_DIR}/objects-before-create.txt"; then
  FINALIZED=1
  trap - EXIT
  die "refusing to mutate pre-existing case Job or ConfigMap"
fi

jq '.items[] | select(.kind == "ConfigMap")' "${MANIFEST}" > "${ATTEMPT_DIR}/configmap-manifest.json"
jq '.items[] | select(.kind == "Job")' "${MANIFEST}" > "${ATTEMPT_DIR}/job-manifest.json"
CONFIGMAP_CREATE_RC=1
JOB_CREATE_RC=1
WAIT_RC=1
MUTATION_ATTEMPTED=1
set +e
kubectl --context "${EXPECTED_CONTEXT}" create -n "${NS}" \
  -f "${ATTEMPT_DIR}/configmap-manifest.json" -o json \
  > "${ATTEMPT_DIR}/configmap-created.json" \
  2> "${ATTEMPT_DIR}/configmap-create.stderr"
CONFIGMAP_CREATE_RC=$?
if test "${CONFIGMAP_CREATE_RC}" -eq 0; then
  CONFIGMAP_UID=$(jq -r '.metadata.uid // empty' "${ATTEMPT_DIR}/configmap-created.json")
  if test -z "${CONFIGMAP_UID}"; then
    CONFIGMAP_CREATE_RC=1
  fi
fi

if test "${CONFIGMAP_CREATE_RC}" -eq 0; then
  kubectl --context "${EXPECTED_CONTEXT}" create -n "${NS}" \
    -f "${ATTEMPT_DIR}/job-manifest.json" -o json \
    > "${ATTEMPT_DIR}/job-created.json" \
    2> "${ATTEMPT_DIR}/job-create.stderr"
  JOB_CREATE_RC=$?
  if test "${JOB_CREATE_RC}" -eq 0; then
    JOB_UID=$(jq -r '.metadata.uid // empty' "${ATTEMPT_DIR}/job-created.json")
    if test -z "${JOB_UID}"; then
      JOB_CREATE_RC=1
    fi
  fi
fi

if test "${CONFIGMAP_CREATE_RC}" -eq 0 && test "${JOB_CREATE_RC}" -eq 0; then
  DEADLINE=$(jq -r '.client.active_deadline_seconds' "${CONFIG}")
  kubectl --context "${EXPECTED_CONTEXT}" wait -n "${NS}" \
    --for=condition=complete --timeout="${DEADLINE}s" "job/${OBJECT_NAME}" \
    > "${ATTEMPT_DIR}/wait.log" \
    2> "${ATTEMPT_DIR}/wait.stderr"
  WAIT_RC=$?
fi

kubectl --context "${EXPECTED_CONTEXT}" logs -n "${NS}" \
  "job/${OBJECT_NAME}" --all-containers=true \
  > "${ATTEMPT_DIR}/client.log" \
  2> "${ATTEMPT_DIR}/client.stderr"
LOG_RC=$?
kubectl --context "${EXPECTED_CONTEXT}" get job -n "${NS}" \
  "${OBJECT_NAME}" -o json > "${ATTEMPT_DIR}/job.json" \
  2> "${ATTEMPT_DIR}/job.stderr"
kubectl --context "${EXPECTED_CONTEXT}" get pods -n "${NS}" \
  -l "test-run=${RUN_ID}" -o json > "${ATTEMPT_DIR}/pods.json" \
  2> "${ATTEMPT_DIR}/pods.stderr"
kubectl --context "${EXPECTED_CONTEXT}" get events -n "${NS}" \
  --field-selector "involvedObject.kind=Job,involvedObject.name=${OBJECT_NAME}" \
  -o json > "${ATTEMPT_DIR}/events.json" \
  2> "${ATTEMPT_DIR}/events.stderr"
kubectl --context "${EXPECTED_CONTEXT}" logs -n "${NS}" \
  -l "test-run=${RUN_ID}" --all-containers=true --prefix=true \
  > "${ATTEMPT_DIR}/run-workloads.log" \
  2> "${ATTEMPT_DIR}/run-workloads.stderr"
set -e

CLIENT_STATUS=INVALID
CLIENT_REASON="Client Job did not complete with one valid DSA_NPU_RESULT record."
mapfile -t RESULT_LINES < <(sed -n 's/^DSA_NPU_RESULT=//p' "${ATTEMPT_DIR}/client.log")
mapfile -t ARTIFACT_LINES < <(sed -n 's/^DSA_NPU_ARTIFACT=//p' "${ATTEMPT_DIR}/client.log")
ARTIFACTS_VALID=1
ARTIFACT_HASHES='[]'
install -d "${ATTEMPT_DIR}/client-artifacts"
ARTIFACT_JSONL="${ATTEMPT_DIR}/client-artifacts.jsonl"
for artifact_line in "${ARTIFACT_LINES[@]}"; do
  if ! printf '%s\n' "${artifact_line}" | jq -e \
    --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" '
    (keys | sort) == ["case_id", "content_base64", "index", "kind", "name", "run_id", "schema_version", "sha256"] and
    .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
    (.kind == "oracle" or .kind == "criterion" or .kind == "failure") and
    (.index | type == "number" and floor == . and . >= 0) and
    (.name | type == "string" and test("^[a-z0-9][a-z0-9._-]{0,127}$")) and
    (.content_base64 | type == "string" and length > 0) and
    (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
  ' >/dev/null; then
    ARTIFACTS_VALID=0
    continue
  fi
  ARTIFACT_NAME=$(jq -r '.name' <<< "${artifact_line}")
  ARTIFACT_SHA=$(jq -r '.sha256' <<< "${artifact_line}")
  ARTIFACT_PATH="${ATTEMPT_DIR}/client-artifacts/${ARTIFACT_NAME}"
  if test -e "${ARTIFACT_PATH}" ||
    ! jq -r '.content_base64' <<< "${artifact_line}" | base64 -d > "${ARTIFACT_PATH}" 2>/dev/null ||
    test "$(sha256_file "${ARTIFACT_PATH}")" != "${ARTIFACT_SHA}"; then
    ARTIFACTS_VALID=0
    continue
  fi
  jq -c '{name, sha256, kind, index}' <<< "${artifact_line}" >> "${ARTIFACT_JSONL}"
done
if test -s "${ARTIFACT_JSONL}"; then
  ARTIFACT_RECORDS=$(jq -s '.' "${ARTIFACT_JSONL}")
  ARTIFACT_HASHES=$(jq '[.[].sha256]' <<< "${ARTIFACT_RECORDS}")
  test "$(jq 'unique | length' <<< "${ARTIFACT_HASHES}")" = "${#ARTIFACT_LINES[@]}" || ARTIFACTS_VALID=0
else
  ARTIFACT_RECORDS='[]'
fi
EXPECTED_IDS=$(jq -c --arg case_id "${CASE_ID}" '.cases[] | select(.case_id == $case_id) | .request_ids' "${RUN_DIR}/inputs/cases.json")
ORACLE_COUNT=$(jq -r --arg case_id "${CASE_ID}" '.cases[] | select(.case_id == $case_id) | .oracles | length' "${RUN_DIR}/inputs/cases.json")
CRITERIA_COUNT=$(jq -r --arg case_id "${CASE_ID}" '.cases[] | select(.case_id == $case_id) | .success_criteria | length' "${RUN_DIR}/inputs/cases.json")
if test "${DRY_RUN_RC}" -eq 0 &&
  test "${CONFIGMAP_CREATE_RC}" -eq 0 && test "${JOB_CREATE_RC}" -eq 0 &&
  test "${WAIT_RC}" -eq 0 && test "${LOG_RC}" -eq 0 &&
  test "${#RESULT_LINES[@]}" -eq 1 &&
  test "${#ARTIFACT_LINES[@]}" -gt 0 && test "${ARTIFACTS_VALID}" -eq 1; then
  printf '%s\n' "${RESULT_LINES[0]}" > "${ATTEMPT_DIR}/client-result.json"
  if jq -e \
    --arg run_id "${RUN_ID}" \
    --arg case_id "${CASE_ID}" \
    --arg config_sha "${CONFIG_SHA}" \
    --argjson expected_ids "${EXPECTED_IDS}" \
    --argjson oracle_count "${ORACLE_COUNT}" \
    --argjson criteria_count "${CRITERIA_COUNT}" \
    --argjson artifact_hashes "${ARTIFACT_HASHES}" \
    --argjson artifact_records "${ARTIFACT_RECORDS}" '
    def valid_evidence($kind; $index):
      type == "array" and length > 0 and
      all(.[];
        type == "string" and test("^[0-9a-f]{64}$") and
        (. as $hash | any($artifact_records[];
          .sha256 == $hash and .kind == $kind and .index == $index)));
    def all_result_evidence:
      ([.oracle_results[].evidence_sha256[],
        .success_criteria_results[].evidence_sha256[],
        .failure_evidence[]]);
    .schema_version == 1 and
    .run_id == $run_id and .case_id == $case_id and
    .run_config_sha256 == $config_sha and
    (.status == "PASS" or .status == "FAIL" or .status == "INVALID") and
    .request_ids == $expected_ids and
    (.oracle_results | type == "array" and length == $oracle_count) and
    ([.oracle_results[].index] | sort) == [range(0; $oracle_count)] and
    all(.oracle_results[];
      . as $result |
      (.status == "PASS" or .status == "FAIL" or .status == "INVALID") and
      (.evidence_sha256 | valid_evidence("oracle"; $result.index))) and
    (.success_criteria_results | type == "array" and length == $criteria_count) and
    ([.success_criteria_results[].index] | sort) == [range(0; $criteria_count)] and
    all(.success_criteria_results[];
      . as $result |
      (.status == "PASS" or .status == "FAIL" or .status == "INVALID") and
      (.evidence_sha256 | valid_evidence("criterion"; $result.index))) and
    (.failure_evidence | type == "array" and
      all(to_entries[];
        . as $result |
        $result.value | type == "string" and test("^[0-9a-f]{64}$") and
        (. as $hash | any($artifact_records[];
          .sha256 == $hash and .kind == "failure" and .index == $result.key)))) and
    (all_result_evidence | length) == ($artifact_hashes | length) and
    (all_result_evidence | unique | length) == (all_result_evidence | length) and
    (all_result_evidence | sort) == ($artifact_hashes | sort) and
    (if .status == "PASS" then
      all(.oracle_results[], .success_criteria_results[]; .status == "PASS") and
      (.failure_evidence | length == 0)
    else
      (.failure_evidence | length > 0)
    end)
  ' "${ATTEMPT_DIR}/client-result.json" >/dev/null; then
    CLIENT_STATUS=$(jq -r '.status' "${ATTEMPT_DIR}/client-result.json")
    CLIENT_REASON="Structured client result passed identity and completeness validation."
  else
    CLIENT_REASON="DSA_NPU_RESULT was malformed, incomplete, or inconsistent with the frozen case."
  fi
fi

mapfile -t CLEANUP_COMMAND < <(render_cleanup_command "${CONFIG}" "${RUN_ID}" "${CASE_ID}")
set +e
"${CLEANUP_COMMAND[@]}" > "${ATTEMPT_DIR}/session-cleanup.log" 2> "${ATTEMPT_DIR}/session-cleanup.stderr"
SESSION_CLEANUP_RC=$?
mapfile -t CLEANUP_LINES < <(sed -n 's/^DSA_NPU_CLEANUP=//p' "${ATTEMPT_DIR}/session-cleanup.log")
mapfile -t CLEANUP_ARTIFACT_LINES < <(sed -n 's/^DSA_NPU_CLEANUP_ARTIFACT=//p' "${ATTEMPT_DIR}/session-cleanup.log")
CLEANUP_ARTIFACTS_VALID=1
CLEANUP_ARTIFACT_HASHES='[]'
CLEANUP_ARTIFACT_JSONL="${ATTEMPT_DIR}/cleanup-artifacts.jsonl"
install -d "${ATTEMPT_DIR}/cleanup-artifacts"
for artifact_line in "${CLEANUP_ARTIFACT_LINES[@]}"; do
  if ! printf '%s\n' "${artifact_line}" | jq -e \
    --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" '
    (keys | sort) == ["case_id", "content_base64", "name", "run_id", "schema_version", "sha256"] and
    .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
    (.name == "resource-delta.json" or .name == "session-inventory.json") and
    (.content_base64 | type == "string" and length > 0) and
    (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
  ' >/dev/null; then
    CLEANUP_ARTIFACTS_VALID=0
    continue
  fi
  ARTIFACT_NAME=$(jq -r '.name' <<< "${artifact_line}")
  ARTIFACT_SHA=$(jq -r '.sha256' <<< "${artifact_line}")
  ARTIFACT_PATH="${ATTEMPT_DIR}/cleanup-artifacts/${ARTIFACT_NAME}"
  if test -e "${ARTIFACT_PATH}" ||
    ! jq -r '.content_base64' <<< "${artifact_line}" | base64 -d > "${ARTIFACT_PATH}" 2>/dev/null ||
    test "$(sha256_file "${ARTIFACT_PATH}")" != "${ARTIFACT_SHA}"; then
    CLEANUP_ARTIFACTS_VALID=0
    continue
  fi
  if test "${ARTIFACT_NAME}" = session-inventory.json; then
    jq -e --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" '
      (keys | sort) == ["active_barriers", "case_id", "open_sessions", "run_id", "schema_version"] and
      .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
      .open_sessions == [] and .active_barriers == []
    ' "${ARTIFACT_PATH}" >/dev/null || CLEANUP_ARTIFACTS_VALID=0
  else
    jq -e --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" '
      (keys | sort) == ["active_commands_delta", "case_id", "delayed_npu_blocks_delta", "npu_requests_delta", "reservation_delta", "run_id", "schema_version", "tracker_entries_delta"] and
      .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
      .reservation_delta == 0 and .delayed_npu_blocks_delta == 0 and
      .active_commands_delta == 0 and .tracker_entries_delta == 0 and
      .npu_requests_delta == 0
    ' "${ARTIFACT_PATH}" >/dev/null || CLEANUP_ARTIFACTS_VALID=0
  fi
  jq -cn --arg name "${ARTIFACT_NAME}" --arg sha256 "${ARTIFACT_SHA}" \
    '{name: $name, sha256: $sha256}' >> "${CLEANUP_ARTIFACT_JSONL}"
done
if test -s "${CLEANUP_ARTIFACT_JSONL}"; then
  CLEANUP_ARTIFACT_NAMES=$(jq -sc '[.[].name] | sort' "${CLEANUP_ARTIFACT_JSONL}")
  CLEANUP_ARTIFACT_HASHES=$(jq -sc '[.[].sha256]' "${CLEANUP_ARTIFACT_JSONL}")
  test "${CLEANUP_ARTIFACT_NAMES}" = '["resource-delta.json","session-inventory.json"]' ||
    CLEANUP_ARTIFACTS_VALID=0
  test "$(jq 'unique | length' <<< "${CLEANUP_ARTIFACT_HASHES}")" -eq 2 ||
    CLEANUP_ARTIFACTS_VALID=0
else
  CLEANUP_ARTIFACTS_VALID=0
fi
CLEANUP_RECORD_PASS=0
if test "${SESSION_CLEANUP_RC}" -eq 0 && test "${#CLEANUP_LINES[@]}" -eq 1 &&
  test "${CLEANUP_ARTIFACTS_VALID}" -eq 1; then
  printf '%s\n' "${CLEANUP_LINES[0]}" > "${ATTEMPT_DIR}/session-cleanup.json"
  if jq -e \
    --arg run_id "${RUN_ID}" --arg case_id "${CASE_ID}" \
    --argjson evidence_hashes "${CLEANUP_ARTIFACT_HASHES}" '
    .schema_version == 1 and .run_id == $run_id and .case_id == $case_id and
    .status == "PASS" and .sessions_closed == true and
    .barriers_reset == true and .resource_baseline_restored == true and
    (.evidence_sha256 | sort) == ($evidence_hashes | sort)
  ' "${ATTEMPT_DIR}/session-cleanup.json" >/dev/null; then
    CLEANUP_RECORD_PASS=1
  fi
fi

DELETE_LOG="${ATTEMPT_DIR}/delete.log"
delete_owned_object job "${JOB_UID}" "${DELETE_LOG}"
JOB_DELETE_RC=$?
delete_owned_object configmap "${CONFIGMAP_UID}" "${DELETE_LOG}"
CONFIGMAP_DELETE_RC=$?
DELETE_RC=0
if test "${JOB_DELETE_RC}" -ne 0 || test "${CONFIGMAP_DELETE_RC}" -ne 0; then
  DELETE_RC=1
fi
kubectl --context "${EXPECTED_CONTEXT}" get -n "${NS}" \
  "job/${OBJECT_NAME}" "configmap/${OBJECT_NAME}" \
  --ignore-not-found -o name > "${ATTEMPT_DIR}/objects-after-delete.txt" \
  2> "${ATTEMPT_DIR}/objects-after-delete.stderr"
VERIFY_DELETE_RC=$?
set -e

CLEANUP_STATUS=FAIL
if test "${CLEANUP_RECORD_PASS}" -eq 1 &&
  test "${DELETE_RC}" -eq 0 &&
  test "${VERIFY_DELETE_RC}" -eq 0 &&
  test ! -s "${ATTEMPT_DIR}/objects-after-delete.txt"; then
  CLEANUP_STATUS=PASS
fi

if test "${CLEANUP_STATUS}" = FAIL; then
  FINAL_STATUS=FAIL
elif test "${CLIENT_STATUS}" = PASS; then
  FINAL_STATUS=PASS
elif test "${CLIENT_STATUS}" = FAIL; then
  FINAL_STATUS=FAIL
else
  FINAL_STATUS=INVALID
fi

FINISHED_AT=$(timestamp_utc)
jq -n \
  --arg run_id "${RUN_ID}" \
  --arg case_id "${CASE_ID}" \
  --arg attempt_id "${ATTEMPT_ID}" \
  --arg started_at "${STARTED_AT}" \
  --arg finished_at "${FINISHED_AT}" \
  --arg config_sha "${CONFIG_SHA}" \
  --arg status "${FINAL_STATUS}" \
  --arg client_status "${CLIENT_STATUS}" \
  --arg client_reason "${CLIENT_REASON}" \
  --arg cleanup_status "${CLEANUP_STATUS}" \
  --arg configmap_uid "${CONFIGMAP_UID}" \
  --arg job_uid "${JOB_UID}" \
  --arg manifest_sha "$(sha256_file "${MANIFEST}")" \
  --arg fixture_sha "$(sha256_file "${RUN_DIR}/fixtures/requests.jsonl")" \
  --arg catalog_sha "$(sha256_file "${RUN_DIR}/inputs/cases.json")" \
  --argjson request_ids "${EXPECTED_IDS}" \
  --argjson client_artifacts "${ARTIFACT_RECORDS}" \
  --argjson cleanup_evidence "${CLEANUP_ARTIFACT_HASHES}" \
  --argjson dry_run_rc "${DRY_RUN_RC}" \
  --argjson configmap_create_rc "${CONFIGMAP_CREATE_RC}" \
  --argjson job_create_rc "${JOB_CREATE_RC}" \
  --argjson wait_rc "${WAIT_RC}" \
  --argjson session_cleanup_rc "${SESSION_CLEANUP_RC}" \
  --argjson delete_rc "${DELETE_RC}" '
  {
    schema_version: 1,
    run_id: $run_id,
    case_id: $case_id,
    attempt_id: $attempt_id,
    status: $status,
    started_at: $started_at,
    finished_at: $finished_at,
    run_config_sha256: $config_sha,
    inputs: {
      manifest_sha256: $manifest_sha,
      fixture_sha256: $fixture_sha,
      case_catalog_sha256: $catalog_sha,
      request_ids: $request_ids
    },
    client: {
      status: $client_status,
      reason: $client_reason,
      artifacts: $client_artifacts
    },
    execution: {
      server_dry_run_rc: $dry_run_rc,
      configmap_create_rc: $configmap_create_rc,
      job_create_rc: $job_create_rc,
      wait_rc: $wait_rc
    },
    created_objects: {configmap_uid: $configmap_uid, job_uid: $job_uid},
    cleanup: {
      status: $cleanup_status,
      session_cleanup_rc: $session_cleanup_rc,
      manifest_delete_rc: $delete_rc,
      evidence_sha256: $cleanup_evidence
    },
    artifact_checksums: "artifact-checksums.txt"
  }
' > "${ATTEMPT_DIR}/result.json"

(
  cd "${ATTEMPT_DIR}"
  find . -type f ! -name artifact-checksums.txt -print0 |
    sort -z | xargs -0 sha256sum > artifact-checksums.txt
)
FINALIZED=1
trap - EXIT

echo "${CASE_ID} ${FINAL_STATUS}: ${ATTEMPT_DIR}/result.json"
case "${FINAL_STATUS}" in
  PASS) exit 0 ;;
  FAIL) exit 1 ;;
  INVALID) exit 2 ;;
esac
