#!/usr/bin/env bash
set -uo pipefail

namespace=ai-inference
remote_artifact_dir=/tmp/layerwise-smoke

usage() {
  echo "usage: $0 [output-directory]" >&2
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi

for command_name in kubectl python3; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "required command is not available: ${command_name}" >&2
    exit 2
  fi
done

output_dir=${1:-/tmp/layerwise-smoke-$(date +%Y%m%d-%H%M%S)}
if [[ -e "${output_dir}" && ! -d "${output_dir}" ]]; then
  echo "output path exists and is not a directory: ${output_dir}" >&2
  exit 2
fi
mkdir -p "${output_dir}"
if [[ -n "$(find "${output_dir}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "refusing to overwrite non-empty output directory: ${output_dir}" >&2
  exit 2
fi

resolve_pod() {
  local role=$1
  local selector=$2
  local pod_name
  local pod_phase
  local -a pod_lines

  if ! mapfile -t pod_lines < <(
    kubectl get pods -n "${namespace}" -l "${selector}" \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'
  ); then
    echo "failed to list ${role} Pods with selector ${selector}" >&2
    return 1
  fi
  if [[ ${#pod_lines[@]} -ne 1 ]]; then
    echo "expected exactly one ${role} Pod for ${selector}; found ${#pod_lines[@]}" >&2
    return 1
  fi

  pod_name=${pod_lines[0]%%$'\t'*}
  pod_phase=${pod_lines[0]#*$'\t'}
  if [[ "${pod_phase}" != Running ]]; then
    echo "${role} Pod ${pod_name} is not Running (phase=${pod_phase})" >&2
    return 1
  fi
  printf '%s\n' "${pod_name}"
}

prefill_pod=$(resolve_pod prefiller app=prefill) || exit 2
decode_pod=$(resolve_pod decoder app=decode) || exit 2
proxy_pod=$(resolve_pod proxy app=proxy) || exit 2
master_pod=$(resolve_pod Mooncake-Master app=mooncake-master) || exit 2

cat >"${output_dir}/run-context.txt" <<EOF
captured_at=$(date --iso-8601=seconds)
namespace=${namespace}
prefill_pod=${prefill_pod}
decode_pod=${decode_pod}
proxy_pod=${proxy_pod}
master_pod=${master_pod}
remote_artifact_dir=${remote_artifact_dir}
EOF

collection_failed=0
if ! kubectl get pods -n "${namespace}" \
  "${prefill_pod}" "${decode_pod}" "${proxy_pod}" "${master_pod}" \
  -o yaml >"${output_dir}/pod-state-before.yaml"; then
  echo "failed to collect initial Pod state" >&2
  collection_failed=1
fi

echo "artifacts: ${output_dir}"
echo "prefiller: ${prefill_pod}"
echo "decoder: ${decode_pod}"

# A stale partial summary could make an early test failure look like a later phase.
if ! kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  rm -rf -- "${remote_artifact_dir}"; then
  echo "failed to remove stale Pod-side smoke artifacts" >&2
  exit 2
fi
if ! kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  mkdir -p -- "${remote_artifact_dir}"; then
  echo "failed to create Pod-side smoke artifact directory" >&2
  exit 2
fi

echo "running concurrent KV cache smoke test"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 /opt/vllm-layerwise/smoke-test.py 2>&1 | \
  tee "${output_dir}/smoke-test.log"
pipeline_status=("${PIPESTATUS[@]}")
smoke_rc=${pipeline_status[0]}
if [[ ${pipeline_status[1]} -ne 0 ]]; then
  echo "failed to write smoke-test.log" >&2
  collection_failed=1
fi
printf '%s\n' "${smoke_rc}" >"${output_dir}/smoke-test.exit-code"

collect() {
  local description=$1
  local destination=$2
  shift 2

  if "$@" >"${destination}" 2>&1; then
    return 0
  else
    local status=$?
  fi

  printf '%s (exit=%d)\n' "${description}" "${status}" \
    >>"${output_dir}/collection-errors.log"
  echo "failed to collect ${description}; see ${destination}" >&2
  collection_failed=1
  return 0
}

mkdir -p "${output_dir}/smoke-artifacts"
if ! kubectl cp -n "${namespace}" -c prefill-engine \
  "${prefill_pod}:${remote_artifact_dir}/." \
  "${output_dir}/smoke-artifacts" \
  >"${output_dir}/kubectl-cp.log" 2>&1; then
  echo "failed to copy Pod-side smoke artifacts; see kubectl-cp.log" >&2
  collection_failed=1
fi

summary_path=${output_dir}/smoke-artifacts/concurrent-summary.json
if [[ -f "${summary_path}" ]]; then
  cp "${summary_path}" "${output_dir}/concurrent-summary.json"
else
  collect "concurrent summary fallback" \
    "${output_dir}/concurrent-summary.json" \
    kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    cat "${remote_artifact_dir}/concurrent-summary.json"
fi

collect "Mooncake Master metrics" "${output_dir}/mooncake-master.metrics" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 -c \
  'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics", timeout=10).read().decode(), end="")'
collect "prefiller engine log" "${output_dir}/vllm-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  cat /tmp/vllm-prefill.log
collect "decoder engine log" "${output_dir}/vllm-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  cat /tmp/vllm-decode.log
collect "proxy log" "${output_dir}/proxy.log" \
  kubectl logs -n "${namespace}" "${proxy_pod}" -c proxy-server
collect "Mooncake Master log" "${output_dir}/mooncake-master.log" \
  kubectl logs -n "${namespace}" "${master_pod}" -c mooncake-master
collect "final Pod state" "${output_dir}/pod-state-after.yaml" \
  kubectl get pods -n "${namespace}" \
  "${prefill_pod}" "${decode_pod}" "${proxy_pod}" "${master_pod}" -o yaml

log_validation_rc=0
python3 - "${output_dir}/concurrent-summary.json" \
  "${output_dir}/vllm-prefill.log" "${output_dir}/vllm-decode.log" \
  "${output_dir}/log-validation.json" <<'PY'
import json
import sys
from pathlib import Path

summary_path, prefill_log_path, decode_log_path, output_path = map(Path, sys.argv[1:])
result = {"passed": False, "checks": [], "errors": []}

try:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    prefill_log = prefill_log_path.read_text(encoding="utf-8", errors="replace")
    decode_log = decode_log_path.read_text(encoding="utf-8", errors="replace")
except Exception as error:
    result["errors"].append(f"could not read validation inputs: {error}")
else:
    expected_tokens = summary.get("expected_hit_tokens")
    expected_blocks = summary.get("expected_hit_blocks")
    if not isinstance(expected_tokens, int) or expected_tokens <= 0:
        result["errors"].append("summary has no positive integer expected_hit_tokens")
    if not isinstance(expected_blocks, int) or expected_blocks <= 0:
        result["errors"].append("summary has no positive integer expected_hit_blocks")

    phases = summary.get("phases") or {}
    phase_targets = (
        ("direct_kv_load", (("decoder", decode_log),)),
        (
            "proxy_kv_load",
            (("prefiller", prefill_log), ("decoder", decode_log)),
        ),
    )

    for phase_name, log_targets in phase_targets:
        cases = (phases.get(phase_name) or {}).get("cases") or []
        if len(cases) != 4:
            result["errors"].append(
                f"phase {phase_name} has {len(cases)} cases; expected 4"
            )
        for case in cases:
            response_id = case.get("response_id")
            case_number = case.get("case")
            if not response_id:
                result["errors"].append(
                    f"phase {phase_name} case {case_number} has no response_id"
                )
                continue

            for role, log_text in log_targets:
                response_lines = [
                    line for line in log_text.splitlines() if response_id in line
                ]
                hit_blocks = any(
                    f"hit_blocks={expected_blocks}/{expected_blocks}" in line
                    for line in response_lines
                )
                hit_tokens = any(
                    f"kvpool hit tokens: {expected_tokens}" in line
                    for line in response_lines
                )
                layerwise_load = any(
                    "KV pool load spec created" in line
                    and "use_layerwise=True" in line
                    for line in response_lines
                )
                check = {
                    "phase": phase_name,
                    "case": case_number,
                    "response_id": response_id,
                    "role": role,
                    "hit_blocks": hit_blocks,
                    "hit_tokens": hit_tokens,
                    "layerwise_load": layerwise_load,
                    "matched_lines": response_lines,
                    "passed": hit_blocks and hit_tokens and layerwise_load,
                }
                result["checks"].append(check)
                if not check["passed"]:
                    result["errors"].append(
                        f"{phase_name} case {case_number} ({response_id}) has "
                        f"incomplete {role} KV hit evidence"
                    )

result["passed"] = not result["errors"]
output_path.write_text(
    json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
)
if result["passed"]:
    print(f"KV hit log validation passed: {len(result['checks'])} role/case checks")
else:
    print("KV hit log validation failed:", file=sys.stderr)
    for error in result["errors"]:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
PY
log_validation_rc=$?
printf '%s\n' "${log_validation_rc}" >"${output_dir}/log-validation.exit-code"

overall_rc=0
if [[ ${smoke_rc} -ne 0 ]]; then
  echo "smoke test failed with exit code ${smoke_rc}" >&2
  overall_rc=1
fi
if [[ ${collection_failed} -ne 0 ]]; then
  echo "one or more evidence collection steps failed" >&2
  overall_rc=1
fi
if [[ ${log_validation_rc} -ne 0 ]]; then
  echo "per-response KV hit log validation failed" >&2
  overall_rc=1
fi

if [[ ${overall_rc} -eq 0 ]]; then
  echo "concurrent KV cache smoke test passed; artifacts: ${output_dir}"
else
  echo "concurrent KV cache smoke test failed; artifacts retained at ${output_dir}" >&2
fi
exit "${overall_rc}"
