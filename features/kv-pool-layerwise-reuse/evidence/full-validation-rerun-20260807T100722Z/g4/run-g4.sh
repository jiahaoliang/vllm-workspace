#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly source_head=45b2e785b10ca4604cd6314819ed15f3ff674781
readonly mooncake_head=df3f74ed8ebdb0c935554beea6299a9f11c723e2
readonly tooling_commit=3bda70d786db46310994afc689af4fc10da4858e
readonly image=docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z
readonly config_id=sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b
readonly script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly workspace_root=$(git -C "${script_dir}" rev-parse --show-toplevel)
readonly deployment_dir=${workspace_root}/features/kv-pool-layerwise-reuse/deployment
readonly request_source=${workspace_root}/features/kv-pool-layerwise-reuse/evidence/ranged-api-g4-20260723T132919Z/runtime-audit/request.json
readonly remote_root=/tmp/full-validation-20260807T100722Z/g4

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
    --arg name "${name}" \
    --arg started "${started}" \
    --arg ended "${ended}" \
    --arg command "${command_text}" \
    --arg artifact "$(basename -- "${artifact}")" \
    --argjson exit_code "${rc}" \
    '{name:$name,started_at:$started,ended_at:$ended,command:$command,artifact:$artifact,exit_code:$exit_code}' \
    >>"${script_dir}/steps.jsonl"
  return "${rc}"
}

resolve_pod() {
  local selector=$1
  kubectl get pods -n "${namespace}" -l "${selector}" -o json | jq -r '
    [.items[] | select(.metadata.deletionTimestamp == null and .status.phase == "Running")] |
    if length == 1 then .[0].metadata.name else error("expected one running Pod") end'
}

wait_http() {
  local pod=$1 container=$2 url=$3
  kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- python3 -c '
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
raise SystemExit(f"timeout: {last}")' "${url}"
}

wait_npu_release() {
  local pod=$1 container=$2
  kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- bash -c '
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
import time
from urllib.request import urlopen
deadline = time.monotonic() + 60
last = None
while time.monotonic() < deadline:
    try:
        print(urlopen("http://mooncake-master-service:9003/metrics", timeout=5).read().decode(), end="")
        raise SystemExit(0)
    except Exception as exc:
        last = exc
    time.sleep(0.5)
raise SystemExit(f"metrics timeout: {last}")'
}

assert_empty() {
  python3 -c '
import sys
values = {}
for line in open(sys.argv[1], encoding="utf-8"):
    parts = line.split()
    if len(parts) == 2 and parts[0] in {"master_key_count", "master_allocated_bytes", "master_active_clients"}:
        values[parts[0]] = float(parts[1])
expected = {"master_key_count": 0.0, "master_allocated_bytes": 0.0, "master_active_clients": 0.0}
assert values == expected, values
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

record "capture engine Pods" "${script_dir}/engine-pods.json" \
  kubectl get pods -n "${namespace}" -l 'app in (prefill,decode)' -o json
record "assert engine identity" "${script_dir}/engine-identity.txt" jq -er \
  --arg image "${image}" --arg config "${config_id}" '
    (.items | length) == 2 and
    all(.items[];
      .metadata.deletionTimestamp == null and .status.phase == "Running" and
      .spec.nodeName == "n1" and .spec.containers[0].image == $image and
      .status.containerStatuses[0].imageID == $config and
      .status.containerStatuses[0].restartCount == 0 and
      .spec.containers[0].resources.requests["huawei.com/Ascend910"] == "1" and
      .spec.containers[0].resources.limits["huawei.com/Ascend910"] == "1")' \
  "${script_dir}/engine-pods.json"
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

record "start debug Prefill" "${script_dir}/start-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 \
  /opt/vllm-layerwise/start-prefill.sh
record "wait Prefill HTTP" "${script_dir}/wait-prefill.log" \
  wait_http "${prefill_pod}" prefill-engine http://127.0.0.1:8100/v1/models
record "start debug Decode" "${script_dir}/start-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 \
  /opt/vllm-layerwise/start-decode.sh
record "wait Decode HTTP" "${script_dir}/wait-decode.log" \
  wait_http "${decode_pod}" decode-engine http://127.0.0.1:8200/v1/models
record "wait Prefill Ready" "${script_dir}/ready-prefill.log" \
  kubectl wait -n "${namespace}" --for=condition=Ready "pod/${prefill_pod}" --timeout=1800s
record "wait Decode Ready" "${script_dir}/ready-decode.log" \
  kubectl wait -n "${namespace}" --for=condition=Ready "pod/${decode_pod}" --timeout=1800s
record "wait proxy health" "${script_dir}/wait-proxy.log" \
  wait_http "${prefill_pod}" prefill-engine http://vllm-proxy-service:8000/health
record "assert Prefill debug env" "${script_dir}/prefill-debug-env.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- bash -c \
  'pid=$(cat /tmp/vllm-prefill.pid); tr "\0" "\n" <"/proc/${pid}/environ" | grep -Fx VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1'
record "assert Decode debug env" "${script_dir}/decode-debug-env.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- bash -c \
  'pid=$(cat /tmp/vllm-decode.pid); tr "\0" "\n" <"/proc/${pid}/environ" | grep -Fx VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1'
record "capture proxy endpoints" "${script_dir}/proxy-endpoints.json" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
from urllib.request import urlopen
print(urlopen("http://vllm-proxy-service:8000/listEndPoints", timeout=10).read().decode(), end="")'
record "capture pre-request Master" "${script_dir}/pre-request.metrics" capture_metrics

record "copy request fixture" "${script_dir}/request-copy.log" \
  cp "${request_source}" "${script_dir}/request.json"
record "hash request fixture" "${script_dir}/request-sha256.txt" \
  sha256sum "${script_dir}/request.json"
record "create remote request directory" "${script_dir}/remote-mkdir.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${remote_root}"
record "sync request fixture" "${script_dir}/request-sync.log" bash -o pipefail -c \
  'tar -C "$1" -cf - request.json | kubectl exec -i -n liangjiahao "$2" -c prefill-engine -- tar -C "$3" -xf -' \
  bash "${script_dir}" "${prefill_pod}" "${remote_root}"
record "send G4 proxy request" "${script_dir}/http-status.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  env PYTHONDONTWRITEBYTECODE=1 python3 -c '
import sys
from pathlib import Path
from urllib.request import Request, urlopen
payload = Path(sys.argv[2]).read_bytes()
response = urlopen(Request(sys.argv[1], payload, {"Content-Type": "application/json"}), timeout=600)
body = response.read()
Path(sys.argv[3]).write_bytes(body)
print(response.status)
assert response.status == 200' \
  http://vllm-proxy-service:8000/v1/completions \
  "${remote_root}/request.json" "${remote_root}/response.json"
record "capture response" "${script_dir}/response.json" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  cat "${remote_root}/response.json"
record "capture post-request Master" "${script_dir}/post-request.metrics" capture_metrics
record "capture Prefill log" "${script_dir}/vllm-prefill.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- cat /tmp/vllm-prefill.log
record "capture Decode log" "${script_dir}/vllm-decode.log" \
  kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- cat /tmp/vllm-decode.log
record "copy frozen checker" "${script_dir}/checker-copy.log" \
  cp "${deployment_dir}/check-range-debug-log.py" "${script_dir}/check-range-debug-log.py"
record "check 27-layer ranged audit" "${script_dir}/range-debug-check.log" \
  env PYTHONDONTWRITEBYTECODE=1 python3 "${script_dir}/check-range-debug-log.py" \
  --prefill-log "${script_dir}/vllm-prefill.log" \
  --decode-log "${script_dir}/vllm-decode.log" \
  --num-layers 27 --output "${script_dir}/range-debug-summary.json"
record "assert G4 contract" "${script_dir}/g4-contract.json" \
  env PYTHONDONTWRITEBYTECODE=1 python3 "${script_dir}/validate-contract.py" "${script_dir}"

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
  --arg source_head "${source_head}" \
  --arg mooncake_head "${mooncake_head}" \
  --arg tooling_commit "${tooling_commit}" \
  --arg image "${image}" \
  --arg config_id "${config_id}" \
  --arg response_id "$(jq -r .id "${script_dir}/response.json")" \
  '{schema_version:1,gate:"G4",status:"passed",validated:true,source_head:$source_head,mooncake_head:$mooncake_head,tooling_commit:$tooling_commit,image:$image,config_id:$config_id,num_layers:27,prefill_range_events:27,prefill_commits:1,decode_range_events:27,per_key_byte_equality:true,whole_key_calls:0,decode_hit_tokens:512,response_id:$response_id,engines_stopped:true,master_empty:true,errors:[]}' \
  >"${script_dir}/summary.json"
