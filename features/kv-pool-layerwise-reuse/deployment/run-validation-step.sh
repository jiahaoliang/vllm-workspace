#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 5 || $4 != -- ]]; then
  echo "usage: $0 OUTPUT_DIR STEP_NAME ARTIFACT -- COMMAND [ARG ...]" >&2
  exit 2
fi

readonly output_dir=$1
readonly step_name=$2
readonly artifact_name=$3
shift 4

if [[ ${artifact_name} == /* || ${artifact_name} == *..* ]]; then
  echo "artifact must be a safe path relative to OUTPUT_DIR" >&2
  exit 2
fi
for command_name in date jq; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "required command is unavailable: ${command_name}" >&2
    exit 2
  }
done

mkdir -p "${output_dir}/$(dirname -- "${artifact_name}")"
readonly artifact="${output_dir}/${artifact_name}"
readonly transcript="${output_dir}/command-transcript.log"
readonly steps="${output_dir}/steps.jsonl"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf -v command_text '%q ' "$@"
printf '[%s] START %s\nCOMMAND %s\n' "${started}" "${step_name}" "${command_text}" >>"${transcript}"

"$@" >"${artifact}" 2>&1
rc=$?
ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '[%s] END %s exit=%d artifact=%s\n' "${ended}" "${step_name}" "${rc}" "${artifact_name}" >>"${transcript}"
jq -cn \
  --arg name "${step_name}" \
  --arg started "${started}" \
  --arg ended "${ended}" \
  --arg command "${command_text}" \
  --arg artifact "${artifact_name}" \
  --argjson exit_code "${rc}" \
  '{name:$name,started_at:$started,ended_at:$ended,command:$command,artifact:$artifact,exit_code:$exit_code}' \
  >>"${steps}"
exit "${rc}"
