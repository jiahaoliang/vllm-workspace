#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly expected_image=${EXPECTED_IMAGE:-docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-a3c97358-df3f74ed-20260808T121828Z}
readonly expected_config=${EXPECTED_CONFIG:-sha256:17b133d3e8ff668f567150ba755a587709e7d600c4bad3f6423f30b77b14f7f3}
readonly asset_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly script_dir=${OUTPUT_DIR:-${asset_dir}}
readonly remote_root=${REMOTE_ROOT:-/tmp/shared-buffer-functional-20260808T121828Z}
readonly producer_config='{"kv_connector":"AscendStoreConnector","kv_role":"kv_producer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_num_shared_buffers":3,"layerwise_prefetch_layers":1,"lookup_rpc_port":0}}'
readonly both_config='{"kv_connector":"AscendStoreConnector","kv_role":"kv_both","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_num_shared_buffers":3,"layerwise_prefetch_layers":1,"lookup_rpc_port":0}}'

prefill_pod=
cleanup_complete=0
active_case_dir=

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
  printf '[%s] END %s exit=%d artifact=%s\n' "${ended}" "${name}" "${rc}" "$(basename -- "${artifact}")" >>"${script_dir}/command-transcript.log"
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

resolve_prefill_pod() {
  kubectl get pods -n "${namespace}" -l app=prefill -o json | jq -r '
    [.items[] | select(.metadata.deletionTimestamp == null and .status.phase == "Running")] |
    if length == 1 then .[0].metadata.name else error("expected exactly one running Prefill Pod") end'
}

wait_http() {
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
import sys
import time
from urllib.request import urlopen

deadline = time.monotonic() + 1800
last_error = None
while time.monotonic() < deadline:
    try:
        with urlopen(sys.argv[1], timeout=5) as response:
            if response.status == 200:
                print(response.read().decode())
                raise SystemExit(0)
    except Exception as error:
        last_error = error
    time.sleep(3)
raise SystemExit(f"HTTP readiness timeout: {last_error}")
' http://127.0.0.1:8100/v1/models
}

capture_metrics() {
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
import time
from urllib.request import urlopen

deadline = time.monotonic() + 60
last_error = None
while time.monotonic() < deadline:
    try:
        print(urlopen("http://mooncake-master-service:9003/metrics", timeout=5).read().decode(), end="")
        raise SystemExit(0)
    except Exception as error:
        last_error = error
    time.sleep(0.5)
raise SystemExit(f"metrics timeout: {last_error}")
'
}

assert_empty() {
  python3 -c '
import sys

values = {}
for line in open(sys.argv[1], encoding="utf-8"):
    fields = line.split()
    if len(fields) == 2 and fields[0] in {
        "master_key_count",
        "master_allocated_bytes",
        "master_active_clients",
    }:
        values[fields[0]] = float(fields[1])
expected = {
    "master_key_count": 0.0,
    "master_allocated_bytes": 0.0,
    "master_active_clients": 0.0,
}
assert values == expected, values
print(values)
' "$1"
}

wait_master_keys() {
  local expected=$1
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
import sys
import time
from urllib.request import urlopen

expected = float(sys.argv[1])
deadline = time.monotonic() + 60
last = None
while time.monotonic() < deadline:
    text = urlopen("http://mooncake-master-service:9003/metrics", timeout=5).read().decode()
    for line in text.splitlines():
        if line.startswith("master_key_count "):
            last = float(line.split()[1])
            break
    if last == expected:
        print(text, end="")
        raise SystemExit(0)
    time.sleep(0.5)
raise SystemExit(f"master_key_count expected {expected:g}, got {last}")
' "${expected}"
}

wait_npu_release() {
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- bash -c '
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

restart_master() {
  kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment
  kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s
}

send_request() {
  local response_path=$1
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    env PYTHONDONTWRITEBYTECODE=1 python3 -c '
import sys
from pathlib import Path
from urllib.request import Request, urlopen

payload = Path(sys.argv[1]).read_bytes()
response = urlopen(
    Request(
        "http://127.0.0.1:8100/v1/completions",
        payload,
        {"Content-Type": "application/json"},
    ),
    timeout=900,
)
body = response.read()
Path(sys.argv[2]).write_bytes(body)
print(response.status)
assert response.status == 200
' "${remote_root}/request.json" "${response_path}"
}

failure_cleanup() {
  local rc=$?
  trap - EXIT
  if (( rc != 0 && cleanup_complete == 0 )); then
    if [[ -n ${prefill_pod} ]]; then
      if [[ -n ${active_case_dir} ]]; then
        kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
          cat /tmp/vllm-prefill.log \
          >"${active_case_dir}/vllm-prefill-failure.log" 2>&1 || true
      fi
      kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
        /opt/vllm-layerwise/stop-engine.sh prefill \
        >"${script_dir}/failure-stop-prefill.log" 2>&1 || true
    fi
    kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment \
      >"${script_dir}/failure-restart-master.log" 2>&1 || true
    kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment \
      --timeout=300s >"${script_dir}/failure-wait-master.log" 2>&1 || true
  fi
  exit "${rc}"
}
trap failure_cleanup EXIT

run_case() {
  local case_name=$1 config=$2 request_count=$3 expected_key_counts=$4 case_dir
  local -a key_counts
  case_dir=${script_dir}/${case_name}
  mkdir -p "${case_dir}"
  active_case_dir=${case_dir}
  IFS=, read -r -a key_counts <<<"${expected_key_counts}"
  [[ ${#key_counts[@]} -eq ${request_count} ]]

  record "${case_name}: restart Master" "${case_dir}/master-restart.log" restart_master
  record "${case_name}: pre-start metrics" "${case_dir}/pre-start.metrics" capture_metrics
  record "${case_name}: assert empty before start" "${case_dir}/pre-start-assert.log" \
    assert_empty "${case_dir}/pre-start.metrics"

  if [[ ${config} == DEFAULT ]]; then
    record "${case_name}: start Prefill" "${case_dir}/start-prefill.log" \
      kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
      env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 \
      /opt/vllm-layerwise/start-prefill.sh
  else
    record "${case_name}: start Prefill" "${case_dir}/start-prefill.log" \
      kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
      env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 \
      "PREFILL_KV_TRANSFER_CONFIG=${config}" \
      /opt/vllm-layerwise/start-prefill.sh
  fi
  record "${case_name}: wait HTTP" "${case_dir}/wait-http.log" wait_http
  record "${case_name}: wait Pod Ready" "${case_dir}/wait-ready.log" \
    kubectl wait -n "${namespace}" --for=condition=Ready "pod/${prefill_pod}" --timeout=1800s
  record "${case_name}: capture command line" "${case_dir}/cmdline.txt" \
    kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- bash -c \
    'pid=$(cat /tmp/vllm-prefill.pid); tr "\0" "\n" <"/proc/${pid}/cmdline"'
  record "${case_name}: active metrics" "${case_dir}/active.metrics" capture_metrics

  local request_index response_remote response_local
  for request_index in $(seq 1 "${request_count}"); do
    response_remote=${remote_root}/${case_name}-response-${request_index}.json
    response_local=${case_dir}/response-${request_index}.json
    record "${case_name}: request ${request_index}" "${case_dir}/request-${request_index}.log" \
      send_request "${response_remote}"
    record "${case_name}: capture response ${request_index}" "${response_local}" \
      kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- cat "${response_remote}"
    record "${case_name}: wait ${key_counts[request_index - 1]} keys ${request_index}" \
      "${case_dir}/keys-${request_index}.metrics" \
      wait_master_keys "${key_counts[request_index - 1]}"
  done

  record "${case_name}: post-request metrics" "${case_dir}/post-request.metrics" capture_metrics
  record "${case_name}: capture engine log" "${case_dir}/vllm-prefill.log" \
    kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- cat /tmp/vllm-prefill.log
  record "${case_name}: stop Prefill" "${case_dir}/stop-prefill.log" \
    kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    /opt/vllm-layerwise/stop-engine.sh prefill
  record "${case_name}: wait NPU release" "${case_dir}/npu-released.txt" wait_npu_release
  record "${case_name}: cleanup Master" "${case_dir}/cleanup-master.log" restart_master
  record "${case_name}: final metrics" "${case_dir}/final.metrics" capture_metrics
  record "${case_name}: assert final empty" "${case_dir}/final-assert.log" \
    assert_empty "${case_dir}/final.metrics"
  active_case_dir=
}

: >"${script_dir}/command-transcript.log"
: >"${script_dir}/steps.jsonl"
prefill_pod=$(resolve_prefill_pod)

record "capture Prefill identity" "${script_dir}/prefill-pod.json" \
  kubectl get pod -n "${namespace}" "${prefill_pod}" -o json
record "assert Prefill identity" "${script_dir}/prefill-identity-assert.log" jq -e \
  --arg image "${expected_image}" --arg config "${expected_config}" '
    .metadata.namespace == "liangjiahao" and
    .metadata.deletionTimestamp == null and
    .status.phase == "Running" and .spec.nodeName == "n1" and
    .spec.containers[0].image == $image and
    .status.containerStatuses[0].imageID == $config and
    .status.containerStatuses[0].restartCount == 0 and
    .spec.containers[0].resources.requests["huawei.com/Ascend910"] == "1" and
    .spec.containers[0].resources.limits["huawei.com/Ascend910"] == "1"
  ' "${script_dir}/prefill-pod.json"
record "create remote directory" "${script_dir}/remote-mkdir.log" \
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${remote_root}"
record "sync request" "${script_dir}/request-sync.log" bash -o pipefail -c \
  'tar -C "$1" -cf - request.json | kubectl exec -i -n liangjiahao "$2" -c prefill-engine -- tar -C "$3" -xf -' \
  bash "${asset_dir}" "${prefill_pod}" "${remote_root}"

run_case baseline DEFAULT 1 4
run_case producer-reuse "${producer_config}" 1 20
run_case both-reuse "${both_config}" 2 20,36

cleanup_complete=1
trap - EXIT
printf 'functional NPU runner completed\n'
