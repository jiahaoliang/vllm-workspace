#!/usr/bin/env bash
set -euo pipefail

HARNESS_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CASE_CATALOG="${HARNESS_ROOT}/cases/cases.json"
FIXTURE_TEMPLATE="${HARNESS_ROOT}/fixtures/requests.template.jsonl"
RUN_CONFIG_TEMPLATE="${HARNESS_ROOT}/config/run-config.template.json"
SCHEMA_VALIDATOR="${HARNESS_ROOT}/scripts/validate-json-schema.py"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || die "required tool is missing: $1"
}

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

timestamp_utc() {
  date -u +'%Y-%m-%dT%H:%M:%SZ'
}

require_regular_file() {
  test -f "$1" && test ! -L "$1" ||
    die "required file must be a regular non-symlink: $1"
}

require_canonical_path() {
  local path=$1 canonical
  require_tool realpath
  canonical=$(realpath -m -- "${path}")
  test "${canonical}" = "${path}" ||
    die "path must be absolute, normalized, and contain no symlink component: ${path}"
}

validate_json_schema() {
  local schema=$1 instance=$2 mode=${3:-json}
  require_tool python3
  require_regular_file "${SCHEMA_VALIDATOR}"
  if test "${mode}" = jsonl; then
    python3 "${SCHEMA_VALIDATOR}" "${schema}" "${instance}" --jsonl ||
      die "JSONL schema validation failed: ${instance}"
  else
    python3 "${SCHEMA_VALIDATOR}" "${schema}" "${instance}" ||
      die "JSON schema validation failed: ${instance}"
  fi
}

capability_required_assertions() {
  case "$1" in
    case_client) printf '%s\n' case-client-implementation-validated ;;
    tokenizer_roundtrip) printf '%s\n' frozen-tokenizer-roundtrip-validated ;;
    output_oracle) printf '%s\n' baseline-capture-complete baseline-identity-matched baseline-allocation-released ;;
    cache_probe) printf '%s\n' physical-cache-probe-validated ;;
    lifecycle_probe) printf '%s\n' rank-aware-lifecycle-probe-validated ;;
    leader_replica_evidence) printf '%s\n' fixed-leaders-0-4-complete-replicas-validated ;;
    memory_placement_probe) printf '%s\n' indexer-hbm-main-swapped-host-placement-validated ;;
    fused_d2h_probe) printf '%s\n' fused-d2h-range-and-validity-probe-validated ;;
    reservation_probe) printf '%s\n' request-lifetime-reservation-ledger-validated ;;
    admission_barrier) printf '%s\n' deterministic-hol-admission-barrier-validated ;;
    phase_fault) printf '%s\n' request-tp-phase-occurrence-fault-control-validated ;;
    tp_terminal_barrier) printf '%s\n' exact-tp-terminal-barrier-validated ;;
    preemption_control) printf '%s\n' deterministic-preemption-boundary-control-validated ;;
    cancellation_control) printf '%s\n' inflight-cancellation-barrier-control-validated ;;
    default_v1_probe) printf '%s\n' default-v1-isolation-probe-validated ;;
    session_cleanup) printf '%s\n' exact-session-cleanup-and-resource-delta-validated ;;
    resource_inventory)
      printf '%s\n' source-runtime-image-identity-verified registration-capacity-verified endpoint-session-readiness-verified physical-npu-allocation-inventory-verified
      ;;
    *) die "unknown capability assertion catalog entry: $1" ;;
  esac
}

validate_capability_evidence() {
  local config=$1
  local name status evidence expected actual run_id artifact_path artifact_expected
  local artifact_root expected_assertions actual_assertions evidence_index artifact_index
  run_id=$(jq -r '.run_id' "${config}")
  artifact_root=$(jq -r '.artifact_root' "${config}")
  evidence_index=$(mktemp)
  artifact_index=$(mktemp)
  while IFS=$'\t' read -r name status evidence expected; do
    case "${status}" in
      PASS)
        test "${evidence#/}" != "${evidence}" || die "PASS capability ${name} evidence must be absolute"
        [[ "${evidence}" == "${artifact_root}/"* ]] ||
          die "PASS capability ${name} evidence must live under artifact_root"
        require_regular_file "${evidence}"
        require_canonical_path "${evidence}"
        actual=$(sha256_file "${evidence}")
        test "${actual}" = "${expected}" || die "capability ${name} evidence SHA256 mismatch"
        validate_json_schema "${HARNESS_ROOT}/schema/capability-evidence.schema.json" "${evidence}"
        jq -e \
          --arg run_id "${run_id}" \
          --arg capability "${name}" '
          (keys | sort) == ["artifacts", "assertions", "capability", "generated_at", "run_id", "schema_version", "status"] and
          .schema_version == 1 and .run_id == $run_id and
          .capability == $capability and .status == "PASS" and
          (.generated_at | type == "string" and
            test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")) and
          (.assertions | type == "array" and length > 0 and
            all(.[]; type == "string" and length > 0)) and
          (.artifacts | type == "array" and length > 0 and
            all(.[];
              (keys | sort) == ["claim_id", "path", "sha256"] and
              (.claim_id | type == "string" and length > 0) and
              (.path | type == "string" and startswith("/") and
                (test("[[:space:]]") | not)) and
              (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))))
        ' "${evidence}" >/dev/null ||
          die "capability ${name} evidence document is malformed or has the wrong identity"
        expected_assertions=$(capability_required_assertions "${name}" | sort | jq -R -s 'split("\n") | map(select(length > 0))')
        actual_assertions=$(jq -c '.assertions | sort' "${evidence}")
        test "${actual_assertions}" = "$(jq -c . <<< "${expected_assertions}")" ||
          die "capability ${name} does not contain the exact required assertion IDs"
        test "$(jq -c '[.artifacts[].claim_id] | sort' "${evidence}")" = "${actual_assertions}" ||
          die "capability ${name} must provide one artifact for each required assertion ID"
        while IFS=$'\t' read -r artifact_path artifact_expected; do
          [[ "${artifact_path}" == "${artifact_root}/"* ]] ||
            die "capability ${name} artifact must live under artifact_root"
          require_regular_file "${artifact_path}"
          require_canonical_path "${artifact_path}"
          actual=$(sha256_file "${artifact_path}")
          test "${actual}" = "${artifact_expected}" ||
            die "capability ${name} artifact SHA256 mismatch: ${artifact_path}"
          printf '%s\t%s\t%s\n' "${artifact_path}" "${artifact_expected}" "${name}" >> "${artifact_index}"
        done < <(jq -r '.artifacts[] | [.path, .sha256] | @tsv' "${evidence}")
        printf '%s\t%s\n' "${evidence}" "${expected}" >> "${evidence_index}"
        ;;
      FAIL|UNKNOWN)
        ;;
      *)
        rm -f -- "${evidence_index}"
        die "capability ${name} has invalid status ${status}"
        ;;
    esac
  done < <(jq -r '.capabilities | to_entries[] | [.key, .value.status, .value.evidence, .value.sha256] | @tsv' "${config}")
  test "$(cut -f1 "${evidence_index}" | sort -u | wc -l)" = "$(wc -l < "${evidence_index}")" || {
    rm -f -- "${evidence_index}" "${artifact_index}"
    die "each PASS capability must use its own evidence document"
  }
  test "$(cut -f1 "${artifact_index}" | sort -u | wc -l)" = "$(wc -l < "${artifact_index}")" || {
    rm -f -- "${evidence_index}" "${artifact_index}"
    die "each PASS capability must use capability-specific artifact files"
  }
  rm -f -- "${evidence_index}" "${artifact_index}"
}

validate_run_config() {
  local config=$1
  local artifact_root fixture_hash catalog_hash image route_count decode_dp
  require_tool jq
  require_tool sha256sum
  require_regular_file "${config}"
  jq -e . "${config}" >/dev/null || die "run config is not valid JSON"
  validate_json_schema "${HARNESS_ROOT}/schema/run-config.schema.json" "${config}"

  jq -e '
    .schema_version == 1 and
    (keys | sort) == ["artifact_root", "capabilities", "client", "commands", "identity", "images", "kube_context", "model", "namespace", "oracle", "resources", "revisions", "run_id", "schema_version", "target_node", "topology"] and
    .namespace == "liangjiahao" and
    (.run_id | test("^dsa-npu-[a-z0-9]([-a-z0-9]*[a-z0-9])?$")) and
    (.run_id | length <= 35) and
    (.artifact_root | startswith("/")) and
    ([paths(scalars) as $p | getpath($p) | strings |
      select(contains("REQUIRED") or contains("UNRESOLVED") or test("<[^>]+>"))] | length == 0)
  ' "${config}" >/dev/null || die "run identity is unresolved or violates the namespace/name contract"

  artifact_root=$(jq -r '.artifact_root' "${config}")
  [[ "${artifact_root}" != "/" && "${artifact_root}" != *[[:space:]]* && "${artifact_root}" != */ && "${artifact_root}" != *'/../'* && "${artifact_root}" != *'/./'* ]] ||
    die "artifact_root must be a normalized absolute path without whitespace or a trailing slash"
  require_canonical_path "${artifact_root}"

  jq -e '
    (.images | keys | sort) == ["baseline", "client", "decode", "default_v1", "prefill"] and
    (.model | keys | sort) == ["block_size", "cache_dtype", "configuration_fingerprint", "max_model_len", "model_id", "model_revision", "sampling", "tokenizer_revision"] and
    (.model.model_id | type == "string" and length > 0) and
    (.model.model_revision | type == "string" and length > 0) and
    (.model.tokenizer_revision | type == "string" and length > 0) and
    (.model.cache_dtype | type == "string" and length > 0) and
    (.model.block_size | type == "number" and floor == . and . >= 1) and
    (.model.max_model_len | type == "number" and floor == . and . >= 1) and
    (.model.sampling | keys | sort) == ["seed", "temperature", "top_p"] and
    .model.sampling.temperature == 0 and .model.sampling.top_p == 1 and
    (.model.sampling.seed | type == "number" and floor == . and . >= 0) and
    (.topology | keys | sort) == ["decode_dcp", "decode_dp", "decode_pcp", "decode_pp", "decode_tp", "prefill_dp", "prefill_tp", "routes"] and
    all(.topology.prefill_tp, .topology.prefill_dp, .topology.decode_tp,
      .topology.decode_dp, .topology.decode_pp, .topology.decode_dcp,
      .topology.decode_pcp; type == "number" and floor == . and . >= 1) and
    all(.topology.routes[];
      (keys | sort) == ["decode_dp_rank", "decode_tp_leaders", "prefill_dp_rank", "prefill_endpoint"] and
      (.decode_dp_rank | type == "number" and floor == . and . >= 0) and
      (.prefill_dp_rank | type == "number" and floor == . and . >= 0) and
      (.prefill_endpoint | type == "string" and length > 0) and
      (.decode_tp_leaders | type == "array" and length > 0 and
        all(.[]; type == "number" and floor == . and . >= 0))) and
    (.resources | keys | sort) == ["baseline_npu", "decode_npu", "npu_resource_name", "prefill_npu"] and
    all(.resources.baseline_npu, .resources.prefill_npu, .resources.decode_npu;
      type == "number" and floor == . and . >= 1) and
    (.commands | keys | sort) == ["baseline", "decode", "default_v1_decode", "default_v1_prefill", "prefill", "session_cleanup"] and
    (.client | keys | sort) == ["active_deadline_seconds", "command", "service_port"] and
    (.client.service_port | type == "number" and floor == . and . >= 1 and . <= 65535) and
    (.client.active_deadline_seconds | type == "number" and floor == . and . >= 1 and . <= 7200) and
    (.oracle | keys | sort) == ["atol", "cache_layers", "rtol"] and
    (.oracle.atol | type == "number" and . >= 0) and
    (.oracle.rtol | type == "number" and . >= 0) and
    (.oracle.cache_layers | type == "array" and length >= 3 and
      all(.[]; type == "number" and floor == . and . >= 0)) and
    (.identity | keys | sort) == ["case_catalog_sha256", "fixture_sha256", "positional_abi_fingerprint"]
  ' "${config}" >/dev/null || die "run config does not satisfy the closed structural contract"

  while IFS= read -r image; do
    [[ "${image}" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || die "image is not immutable: ${image}"
  done < <(jq -r '.images[]' "${config}")
  jq -e '.images.prefill == .images.decode' "${config}" >/dev/null || die "Prefill and Decode image digests must match"

  jq -e '
    (.revisions | keys | sort) == ["cann", "mooncake", "torch_npu", "vllm", "vllm_ascend"] and
    all(.revisions[]; type == "string" and length > 0) and
    (.model.configuration_fingerprint | test("^[0-9a-f]{64}$")) and
    (.identity.positional_abi_fingerprint | test("^[0-9a-f]{64}$")) and
    all(.commands[], .client.command;
      type == "array" and length > 0 and
      all(.[]; type == "string" and length > 0 and (contains("\n") | not)) and
      (.[0] | startswith("/"))) and
    (.commands.session_cleanup | map(select(. == "{RUN_ID}")) | length) == 1 and
    (.commands.session_cleanup | map(select(. == "{CASE_ID}")) | length) == 1
  ' "${config}" >/dev/null || die "revision, fingerprint, or command contract is invalid"

  jq -e '
    . as $root |
    ($root.topology.prefill_tp >= $root.topology.decode_tp) and
    ($root.topology.prefill_tp % $root.topology.decode_tp == 0) and
    ($root.topology.decode_pp == 1) and
    ($root.topology.decode_dcp * $root.topology.decode_pcp == 1) and
    (($root.topology.routes | length) == $root.topology.decode_dp)
  ' "${config}" >/dev/null || die "topology constraints are not satisfied"

  decode_dp=$(jq -r '.topology.decode_dp' "${config}")
  route_count=$(jq -r '[.topology.routes[].decode_dp_rank] | unique | length' "${config}")
  test "${route_count}" = "${decode_dp}" || die "Decode DP route ranks are not unique and complete"
  jq -e '
    . as $root |
    ($root.topology.prefill_tp / $root.topology.decode_tp) as $ratio |
    ([range(0; $root.topology.decode_dp)] == ([$root.topology.routes[].decode_dp_rank] | sort)) and
    (([$root.topology.routes[].prefill_dp_rank] | unique | length) == $root.topology.prefill_dp) and
    all($root.topology.routes[];
      .prefill_dp_rank < $root.topology.prefill_dp and
      .prefill_endpoint == ($root.run_id + "-prefill-dp" + (.prefill_dp_rank | tostring) + ".liangjiahao.svc") and
      .decode_tp_leaders == [range(0; $root.topology.decode_tp) | . * $ratio]
    )
  ' "${config}" >/dev/null || die "explicit Decode-DP to Prefill-DP leader routes are invalid"

  jq -e '
    . as $root |
    ($root.resources.npu_resource_name == "huawei.com/Ascend910") and
    ($root.resources.prefill_npu == ($root.topology.prefill_tp * $root.topology.prefill_dp)) and
    ($root.resources.decode_npu == ($root.topology.decode_tp * $root.topology.decode_dp))
  ' "${config}" >/dev/null || die "NPU totals do not match the topology"

  fixture_hash=$(sha256_file "${FIXTURE_TEMPLATE}")
  catalog_hash=$(sha256_file "${CASE_CATALOG}")
  test "$(jq -r '.identity.fixture_sha256' "${config}")" = "${fixture_hash}" || die "fixture SHA256 is not frozen to the versioned fixture"
  test "$(jq -r '.identity.case_catalog_sha256' "${config}")" = "${catalog_hash}" || die "case catalog SHA256 is not frozen"

  jq -e -s --argjson block_size "$(jq '.model.block_size' "${config}")" '
    all(.[];
      (.prompt_token_ids | length) == .expected_prompt_tokens and
      ((((.prompt_token_ids | length) + .max_tokens + $block_size - 1) / $block_size | floor) == .expected_reservation_blocks)
    )
  ' "${FIXTURE_TEMPLATE}" >/dev/null || die "fixture token/block expectations do not match run-config block size"

  jq -e --slurpfile template "${RUN_CONFIG_TEMPLATE}" '
    (.capabilities | keys) == ($template[0].capabilities | keys) and
    all(.capabilities[];
      ((keys | sort) == ["evidence", "notes", "sha256", "status"]) and
      (.status == "PASS" or .status == "FAIL" or .status == "UNKNOWN") and
      (.evidence | type == "string") and
      (.sha256 | type == "string" and test("^$|^[0-9a-f]{64}$")) and
      (.notes | type == "string"))
  ' "${config}" >/dev/null || die "capability catalog is missing or malformed"
  validate_capability_evidence "${config}"
}

manifest_static_check() {
  local manifest=$1
  require_regular_file "${manifest}"
  jq -e '
    .kind == "List" and
    (.items | length > 0) and
    all(.items[];
      .metadata.namespace == "liangjiahao" and
      .metadata.labels["app.kubernetes.io/managed-by"] == "dsa-npu-e2e" and
      (.metadata.name | length <= 63) and
      (.metadata.name | test("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"))
    ) and
    ([paths(scalars) as $p | getpath($p) | strings |
      select(contains("REQUIRED") or contains("UNRESOLVED") or test("<[^>]+>"))] | length == 0) and
    all(.items[] | select(.kind == "Deployment" or .kind == "Job") |
      .spec.template.spec.containers[];
      (.image | test("^[^ @]+@sha256:[0-9a-f]{64}$"))
    )
  ' "${manifest}" >/dev/null || die "rendered manifest failed static checks: ${manifest}"
}

case_object_name() {
  local run_id=$1
  local case_id=$2
  echo "${run_id}-$(printf '%s' "${case_id}" | tr '[:upper:]' '[:lower:]')"
}

case_manifest_static_check() {
  local manifest=$1 run_id=$2 case_id=$3 object_name
  object_name=$(case_object_name "${run_id}" "${case_id}")
  manifest_static_check "${manifest}"
  jq -e --arg run_id "${run_id}" --arg case_id "${case_id}" --arg name "${object_name}" '
    (.items | length == 2) and
    ([.items[].kind] | sort) == ["ConfigMap", "Job"] and
    all(.items[];
      .metadata.name == $name and
      .metadata.labels["test-run"] == $run_id and
      .metadata.labels["case-id"] == $case_id) and
    (.items[] | select(.kind == "ConfigMap") |
      (.data["case.json"] | fromjson | .case_id == $case_id) and
      (.data["requests.jsonl"] | split("\n") | map(select(length > 0) | fromjson) | length > 0) and
      (.data["run-config.json"] | fromjson | .run_id == $run_id)) and
    (.items[] | select(.kind == "Job") |
      .spec.template.spec.restartPolicy == "Never" and
      .spec.backoffLimit == 0 and
      .spec.template.spec.volumes[0].configMap.name == $name)
  ' "${manifest}" >/dev/null || die "case manifest is not the exact ConfigMap/Job pair for ${case_id}"
}

validate_rendered_run() {
  local run_dir=$1 config run_id expected_run_dir case_id manifest expected_ids child
  test -d "${run_dir}" && test ! -L "${run_dir}" ||
    die "RUN_DIR must be a real directory, not a symlink: ${run_dir}"
  require_canonical_path "${run_dir}"
  for child in manifests fixtures inputs preflight results; do
    test -d "${run_dir}/${child}" && test ! -L "${run_dir}/${child}" ||
      die "rendered child directory must be real and non-symlink: ${run_dir}/${child}"
    require_canonical_path "${run_dir}/${child}"
  done
  config="${run_dir}/run-config.json"
  validate_run_config "${config}"
  run_id=$(jq -r '.run_id' "${config}")
  expected_run_dir="$(jq -r '.artifact_root' "${config}")/${run_id}"
  test "${run_dir}" = "${expected_run_dir}" || die "RUN_DIR must equal artifact_root/run_id: ${expected_run_dir}"

  require_regular_file "${run_dir}/inputs/cases.json"
  require_regular_file "${run_dir}/fixtures/requests.jsonl"
  require_regular_file "${run_dir}/inputs/rendered-sha256.txt"
  test "$(sha256_file "${run_dir}/inputs/cases.json")" = "$(sha256_file "${CASE_CATALOG}")" || die "rendered case catalog drifted"
  test "$(sha256_file "${run_dir}/fixtures/requests.jsonl")" = "$(sha256_file "${FIXTURE_TEMPLATE}")" || die "rendered fixture drifted"
  (cd "${run_dir}" && sha256sum -c inputs/rendered-sha256.txt >/dev/null) || die "rendered input SHA256 verification failed"

  for manifest in baseline.json baseline-oracle.json dsa-pd.json default-v1-pd.json; do
    manifest_static_check "${run_dir}/manifests/${manifest}"
  done
  for case_id in NPU-01 NPU-02 NPU-03 NPU-04 NPU-05 NPU-06 NPU-07 NPU-08; do
    manifest="${run_dir}/manifests/${case_id}.json"
    case_manifest_static_check "${manifest}" "${run_id}" "${case_id}"
    expected_ids=$(jq -c --arg case_id "${case_id}" '.cases[] | select(.case_id == $case_id) | .request_ids' "${run_dir}/inputs/cases.json")
    jq -e --argjson expected_ids "${expected_ids}" '
      [.items[] | select(.kind == "ConfigMap") | .data["requests.jsonl"] |
        split("\n")[] | select(length > 0) | fromjson | .request_id] == $expected_ids
    ' "${manifest}" >/dev/null || die "case manifest request fixture order drifted for ${case_id}"
  done
}

render_cleanup_command() {
  local config=$1 run_id=$2 case_id=$3 argument
  while IFS= read -r argument; do
    case "${argument}" in
      '{RUN_ID}') printf '%s\n' "${run_id}" ;;
      '{CASE_ID}') printf '%s\n' "${case_id}" ;;
      *) printf '%s\n' "${argument}" ;;
    esac
  done < <(jq -r '.commands.session_cleanup[]' "${config}")
}
