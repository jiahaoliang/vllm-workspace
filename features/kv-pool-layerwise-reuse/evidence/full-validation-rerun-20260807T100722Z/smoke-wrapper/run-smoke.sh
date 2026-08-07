#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly evidence_root=$(dirname -- "${script_dir}")
readonly workspace_root=$(git -C "${script_dir}" rev-parse --show-toplevel)
readonly runner=${workspace_root}/features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh

prefill_pod=
decode_pod=
cleanup_complete=0

record() {
  local name=$1 artifact=$2
  shift 2
  local started ended rc command_text
  started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf -v command_text '%q ' "$@"
  command_text=${command_text% }
  printf '[%s] START %s\nCOMMAND %s\n' "${started}" "${name}" "${command_text}" >>"${script_dir}/command-transcript.log"
  set +e
  "$@" >"${artifact}" 2>&1
  rc=$?
  set -e
  ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '[%s] END %s exit=%d artifact=%s\n' "${ended}" "${name}" "${rc}" "${artifact}" >>"${script_dir}/command-transcript.log"
  jq -cn \
    --arg name "${name}" --arg started "${started}" --arg ended "${ended}" \
    --arg command "${command_text}" --arg artifact "$(basename -- "${artifact}")" \
    --argjson exit_code "${rc}" \
    '{name:$name,started_at:$started,ended_at:$ended,command:$command,artifact:$artifact,exit_code:$exit_code}' \
    >>"${script_dir}/steps.jsonl"
  return "${rc}"
}

resolve_pod() {
  kubectl get pods -n "${namespace}" -l "$1" -o json | jq -r '
    [.items[] | select(.metadata.deletionTimestamp == null and .status.phase == "Running")] |
    if length == 1 then .[0].metadata.name else error("expected one running Pod") end'
}

wait_http() {
  kubectl exec -n "${namespace}" "$1" -c "$2" -- python3 -c '
import sys, time
from urllib.request import urlopen
deadline = time.monotonic() + 1800
last = None
while time.monotonic() < deadline:
    try:
        with urlopen(sys.argv[1], timeout=5) as response:
            if response.status == 200:
                print(response.read().decode())
                raise SystemExit(0)
    except Exception as exc:
        last = exc
    time.sleep(3)
raise SystemExit(f"timeout: {last}")' "$3"
}

wait_npu_release() {
  kubectl exec -n "${namespace}" "$1" -c "$2" -- bash -c '
    set -e
    for _ in $(seq 1 90); do
      output=$(npu-smi info)
      if grep -q "No running processes found" <<<"${output}"; then
        printf "%s\n" "${output}"
        exit 0
      fi
      sleep 2
    done
    exit 1'
}

capture_metrics() {
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
from urllib.request import urlopen
print(urlopen("http://mooncake-master-service:9003/metrics", timeout=10).read().decode(), end="")'
}

assert_empty() {
  python3 -c '
import sys
values = {}
for line in open(sys.argv[1], encoding="utf-8"):
    parts = line.split()
    if len(parts) == 2 and parts[0] in {"master_key_count", "master_allocated_bytes", "master_active_clients"}:
        values[parts[0]] = float(parts[1])
assert values == {"master_key_count": 0.0, "master_allocated_bytes": 0.0, "master_active_clients": 0.0}, values
print(values)' "$1"
}

failure_cleanup() {
  local rc=$?
  trap - EXIT
  if (( rc != 0 && cleanup_complete == 0 )); then
    if [[ -n ${prefill_pod} ]]; then
      kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
        /opt/vllm-layerwise/stop-engine.sh prefill \
        >"${script_dir}/failure-cleanup-prefill.log" 2>&1 || true
    fi
    if [[ -n ${decode_pod} ]]; then
      kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
        /opt/vllm-layerwise/stop-engine.sh decode \
        >"${script_dir}/failure-cleanup-decode.log" 2>&1 || true
    fi
    kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment \
      >"${script_dir}/failure-cleanup-master.log" 2>&1 || true
  fi
  exit "${rc}"
}
trap failure_cleanup EXIT

: >"${script_dir}/command-transcript.log"
: >"${script_dir}/steps.jsonl"
prefill_pod=$(resolve_pod app=prefill)
decode_pod=$(resolve_pod app=decode)

record "preflight stop Prefill" "${script_dir}/preflight-stop-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
record "preflight stop Decode" "${script_dir}/preflight-stop-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode
record "preflight wait Prefill NPU release" "${script_dir}/preflight-prefill-npu-released.log" \
  wait_npu_release "${prefill_pod}" prefill-engine
record "preflight wait Decode NPU release" "${script_dir}/preflight-decode-npu-released.log" \
  wait_npu_release "${decode_pod}" decode-engine
record "preflight restart Master" "${script_dir}/preflight-master-restart.log" \
  kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment
record "preflight wait Master" "${script_dir}/preflight-master-rollout.log" \
  kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s
record "capture preflight Master" "${script_dir}/preflight.metrics" capture_metrics
record "assert preflight Master empty" "${script_dir}/preflight-assert.log" \
  assert_empty "${script_dir}/preflight.metrics"

record "start Prefill" "${script_dir}/start-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  env PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-prefill.sh
record "wait Prefill" "${script_dir}/wait-prefill.log" \
  wait_http "${prefill_pod}" prefill-engine http://127.0.0.1:8100/v1/models
record "start Decode" "${script_dir}/start-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  env PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-decode.sh
record "wait Decode" "${script_dir}/wait-decode.log" \
  wait_http "${decode_pod}" decode-engine http://127.0.0.1:8200/v1/models
record "wait Prefill Ready" "${script_dir}/ready-prefill.log" \
  kubectl wait -n "${namespace}" --for=condition=Ready "pod/${prefill_pod}" --timeout=1800s
record "wait Decode Ready" "${script_dir}/ready-decode.log" \
  kubectl wait -n "${namespace}" --for=condition=Ready "pod/${decode_pod}" --timeout=1800s
record "wait proxy" "${script_dir}/wait-proxy.log" \
  wait_http "${prefill_pod}" prefill-engine http://vllm-proxy-service:8000/health
record "run formal smoke" "${script_dir}/run-smoke.log" \
  "${runner}" "${evidence_root}/smoke"
record "assert smoke contract" "${script_dir}/smoke-contract.json" python3 -c '
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
summary = json.loads((root / "concurrent-summary.json").read_text())
assert summary["status"] == "passed" and summary["validated"] is True and summary["diagnosis"] == "passed"
assert summary["concurrency"] == 4 and summary["block_size"] == 128
assert summary["expected_hit_blocks"] == 25 and summary["expected_hit_tokens"] == 3200
assert summary["expected_master_key_count"] == 64
expected_counts = {"empty_pool_baseline": 4, "warmup": 5, "direct_kv_load": 4, "proxy_kv_load": 4}
for name, count in expected_counts.items():
    phase = summary["phases"][name]
    assert phase["status"] == "passed" and phase["validated"] is True and len(phase["cases"]) == count
    for case in phase["cases"]:
        assert case["http_status"] == 200 and case["validated"] is True
        checks = case["hard_gate_checks"]
        assert checks["validated"] is True and checks["generated_token_count_match"] is True
        assert checks["marker_token_prefix_match"] is True and checks["text_marker_prefix_match"] is True
        assert checks["isolated"] is True and checks["foreign_markers"] == []
        assert checks["prompt_tokens_match"] is True and checks["completion_tokens_match"] is True
        assert checks["finish_reason_match"] is True and checks["errors"] == []
log_validation = json.loads((root / "log-validation.json").read_text())
assert log_validation["passed"] is True and len(log_validation["checks"]) == 12
assert all(check["passed"] for check in log_validation["checks"])
metrics = (root / "mooncake-master.metrics").read_text()
assert "master_key_count 64" in metrics
print(json.dumps({"validated": True, "case_count": 17, "hit_correlation_checks": 12, "marker_isolation": True, "master_key_count": 64}, indent=2, sort_keys=True))' \
  "${evidence_root}/smoke"

record "stop Prefill" "${script_dir}/stop-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
record "stop Decode" "${script_dir}/stop-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode
record "wait Prefill NPU release" "${script_dir}/prefill-npu-released.log" \
  wait_npu_release "${prefill_pod}" prefill-engine
record "wait Decode NPU release" "${script_dir}/decode-npu-released.log" \
  wait_npu_release "${decode_pod}" decode-engine
record "restart Master for cleanup" "${script_dir}/master-restart.log" \
  kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment
record "wait Master cleanup" "${script_dir}/master-rollout.log" \
  kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s
record "capture final Master" "${script_dir}/final-empty.metrics" capture_metrics
record "assert final Master empty" "${script_dir}/final-empty-assert.log" \
  assert_empty "${script_dir}/final-empty.metrics"
cleanup_complete=1

jq -n \
  --arg tooling_commit 3bda70d786db46310994afc689af4fc10da4858e \
  '{schema_version:1,gate:"smoke",status:"passed",validated:true,tooling_commit:$tooling_commit,case_count:17,hit_correlation_checks:12,marker_isolation:true,expected_hit_blocks:25,expected_hit_tokens:3200,expected_master_key_count:64,engines_stopped:true,master_empty:true,errors:[]}' \
  >"${script_dir}/summary.json"
