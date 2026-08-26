#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

require_tool jq
require_tool bash
require_tool python3

while IFS= read -r file; do
  jq -e . "${file}" >/dev/null || die "invalid JSON: ${file}"
done < <(find "${HARNESS_ROOT}" -type f -name '*.json' | sort)

while IFS= read -r file; do
  bash -n "${file}" || die "invalid shell syntax: ${file}"
done < <(find "${HARNESS_ROOT}/scripts" -type f -name '*.sh' | sort)

validate_json_schema "${HARNESS_ROOT}/schema/case-catalog.schema.json" "${CASE_CATALOG}"
validate_json_schema "${HARNESS_ROOT}/schema/fixture.schema.json" "${FIXTURE_TEMPLATE}" jsonl

jq -e -s '
  length == 10 and
  ([.[].request_id] | unique | length == 10) and
  all(.[];
    ((keys | sort) == ["expected_prompt_tokens", "expected_reservation_blocks", "input_sha256", "max_tokens", "prompt_token_ids", "purpose", "request_id"]) and
    (.request_id | type == "string" and test("^[a-z0-9][a-z0-9-]{0,62}$")) and
    (.prompt_token_ids | type == "array" and length > 0 and all(.[]; type == "number" and . >= 0 and floor == .)) and
    (.max_tokens | type == "number" and . >= 0 and floor == .) and
    (.expected_prompt_tokens | type == "number" and . >= 1 and floor == .) and
    (.expected_reservation_blocks | type == "number" and . >= 1 and floor == .) and
    (.purpose | type == "string" and length > 0) and
    (.prompt_token_ids | length) == .expected_prompt_tokens)
' "${FIXTURE_TEMPLATE}" >/dev/null || die "fixture JSONL is invalid or contains duplicate request IDs"

while IFS= read -r fixture; do
  expected=$(jq -r '.input_sha256' <<< "${fixture}")
  actual=$(jq -cS 'del(.input_sha256)' <<< "${fixture}" | sha256sum | awk '{print $1}')
  test "${actual}" = "${expected}" || die "fixture input_sha256 mismatch"
done < "${FIXTURE_TEMPLATE}"

jq -e '
  .schema_version == 1 and
  (.cases | length == 8) and
  ([.cases[].case_id] | sort) == ["NPU-01", "NPU-02", "NPU-03", "NPU-04", "NPU-05", "NPU-06", "NPU-07", "NPU-08"] and
  all(.cases[];
    .status == "planned / not run" and
    (.request_ids | length > 0) and
    (.required_capabilities | length > 0) and
    (.command | length > 0) and
    (.controls | keys | sort) == ["barriers", "cancellations", "faults", "phase_transitions", "preemptions", "waves"] and
    ([.controls.waves[].request_ids[]] | sort) == (.request_ids | sort) and
    (.oracles | length > 0) and
    (.success_criteria | length > 0) and
    (.failure_evidence | length > 0) and
    (.cleanup | length > 0)
  )
' "${CASE_CATALOG}" >/dev/null || die "mandatory case catalog is incomplete"

jq -e '
  (.cases[] | select(.case_id == "NPU-04") |
    [.controls.faults[].phase] | sort) == ["INDEXER_D2D", "MAIN_D2RH"] and
  (.cases[] | select(.case_id == "NPU-05") |
    .controls.barriers | length) == 1 and
  (.cases[] | select(.case_id == "NPU-06") |
    .controls.preemptions) == [{request_id: "preempt-1", trigger_after_confirmed_main_tokens: 16, expected_new_epoch_delta: 1}] and
  (.cases[] | select(.case_id == "NPU-07") |
    [.controls.cancellations[].phase] | sort) == ["FUSED_D2H", "RECEIVE_REMOTE"] and
  (.cases[] | select(.case_id == "NPU-08") |
    .controls.phase_transitions) == [{
      from_manifest: "manifests/dsa-pd.json",
      cleanup_manifest: "manifests/dsa-pd.json",
      to_manifest: "manifests/default-v1-pd.json"
    }]
' "${CASE_CATALOG}" >/dev/null || die "mandatory case controls are not replayable"

jq -e -n \
  --slurpfile catalog "${CASE_CATALOG}" \
  --slurpfile fixtures "${FIXTURE_TEMPLATE}" \
  --slurpfile config "${HARNESS_ROOT}/config/run-config.template.json" '
  ($fixtures | map(.request_id) | unique) as $fixture_ids |
  ($catalog[0].cases | map(.case_id) | unique) as $case_ids |
  ($config[0].capabilities | keys) as $capabilities |
  all($catalog[0].cases[];
    all(.request_ids[]; . as $id | $fixture_ids | index($id)) and
    all(.required_cases[]; . as $id | $case_ids | index($id)) and
    all(.required_capabilities[]; . as $name | $capabilities | index($name))
  )
' >/dev/null || die "case catalog references unknown fixture, case, or capability"

if rg -n --glob '*.sh' --glob '*.json' --glob '*.md' '(-n|namespace:)[ =]+ai-inference|kubectl[^\n]*-n[ =]+ai-inference' "${HARNESS_ROOT}"; then
  die "executable ai-inference namespace reference is forbidden"
fi

echo "static validation PASS: schemas, templates, fixtures, case catalog, and shell syntax"
