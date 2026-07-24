#!/usr/bin/env bash
set -uo pipefail

readonly namespace=ai-inference
readonly node_name=n1
readonly image=docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2
readonly model_path=/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly workspace_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
readonly remote_tools=/tmp/layerwise-stress-tools

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [output-directory]" >&2
  exit 2
fi
output_dir=${1:-/tmp/layerwise-stress-$(date -u +%Y%m%dT%H%M%SZ)}
run_id=$(basename -- "${output_dir}")
if [[ ! ${run_id} =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "output directory basename must contain only letters, digits, dot, underscore, or hyphen" >&2
  exit 2
fi
readonly remote_root="/tmp/layerwise-stress-run-${run_id}"
overall_rc=0
collection_failed=0
prefill_pod=
decode_pod=
proxy_pod=
master_pod=
trap_active=0

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "required command is unavailable: $1" >&2; return 1; }
}

resolve_running_pod() {
  local role=$1 selector=$2
  local -a lines
  mapfile -t lines < <(kubectl get pods -n "${namespace}" -l "${selector}" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}') || return 1
  if (( ${#lines[@]} != 1 )) || [[ ${lines[0]#*$'\t'} != Running ]]; then
    echo "expected exactly one Running ${role} Pod, got: ${lines[*]:-none}" >&2
    return 1
  fi
  printf '%s\n' "${lines[0]%%$'\t'*}"
}

record_step() {
  local name=$1 artifact=$2
  shift 2
  local started ended rc command_text
  started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf -v command_text '%q ' "$@"
  printf '[%s] START %s\nCOMMAND %s\n' "${started}" "${name}" "${command_text}" >>"${output_dir}/command-transcript.log"
  "$@" >"${artifact}" 2>&1
  rc=$?
  ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '[%s] END %s exit=%d artifact=%s\n' "${ended}" "${name}" "${rc}" "${artifact}" >>"${output_dir}/command-transcript.log"
  jq -cn --arg name "${name}" --arg started "${started}" --arg ended "${ended}" --arg command "${command_text}" --arg artifact "${artifact}" --argjson exit_code "${rc}" \
    '{name:$name,started_at:$started,ended_at:$ended,command:$command,exit_code:$exit_code,artifact:$artifact}' >>"${output_dir}/steps.jsonl" || collection_failed=1
  return "${rc}"
}

collect() {
  local description=$1 destination=$2
  shift 2
  mkdir -p "$(dirname -- "${destination}")"
  record_step "collect: ${description}" "${destination}" "$@" || {
    collection_failed=1
    printf '%s\n' "collection failed: ${description}" >>"${output_dir}/collection-errors.log"
    return 1
  }
}

stop_engines() {
  local rc=0
  [[ -z ${prefill_pod} ]] || kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill || rc=1
  [[ -z ${decode_pod} ]] || kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode || rc=1
  return "${rc}"
}

wait_running() {
  local selector=$1 expected_npus=$2 deadline=$((SECONDS + 600)) value
  while (( SECONDS < deadline )); do
    value=$(kubectl get pods -n "${namespace}" -l "${selector}" -o json | jq -r --arg expected "${expected_npus}" '
      [.items[] | select(
        .metadata.deletionTimestamp == null and
        .status.phase == "Running" and
        .spec.containers[0].resources.requests["huawei.com/Ascend910"] == $expected and
        any(.spec.volumes[]?; .configMap.name? == "layerwise-stress-runtime-config")
      )] | if length == 1 then .[0].metadata.name else empty end
    ') || return 1
    if [[ -n ${value} ]]; then
      printf '%s\n' "${value}"
      return 0
    fi
    sleep 3
  done
  echo "timed out waiting for one Running Pod: ${selector}" >&2
  return 1
}

reset_master() {
  record_step "restart Mooncake Master" "${output_dir}/master-reset-$(date -u +%H%M%S).log" kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment || return 1
  record_step "wait Mooncake Master rollout" "${output_dir}/master-rollout-$(date -u +%H%M%S).log" kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s || return 1
  master_pod=$(resolve_running_pod master app=mooncake-master)
}

start_engines() {
  record_step "start Prefill" "${output_dir}/start-prefill-$(date -u +%H%M%S).log" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh || return 1
  record_step "start Decode" "${output_dir}/start-decode-$(date -u +%H%M%S).log" kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
}

wait_engine_ready() {
  local label=$1 pod=$2
  record_step "wait Kubernetes Ready: ${label}" "${output_dir}/wait-ready-${label}-$(date -u +%H%M%S).log" \
    kubectl wait -n "${namespace}" --for=condition=Ready "pod/${pod}" --timeout=1800s
}

wait_for_http() {
  local pod=$1 container=$2 url=$3 description=$4
  record_step "wait HTTP: ${description}" "${output_dir}/wait-http-${description// /-}-$(date -u +%H%M%S).log" kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- \
    python3 -c 'import sys,time,urllib.request
url=sys.argv[1]; deadline=time.monotonic()+1800; last=None
while time.monotonic()<deadline:
 try:
  with urllib.request.urlopen(url,timeout=5) as response:
   if response.status==200: print(response.read().decode()); raise SystemExit(0)
 except Exception as exc: last=exc
 time.sleep(3)
raise SystemExit(f"timeout waiting for {url}: {last}")' "${url}"
}

capture_metrics() {
  collect "Mooncake metrics" "$1" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c \
    'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics",timeout=10).read().decode(),end="")'
}

wait_for_key_count() {
  local destination=$1 expected=$2
  record_step "wait for Master key count ${expected}" "${destination}" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    python3 -c 'import sys,time
from urllib.request import urlopen
expected=int(sys.argv[1]); deadline=time.monotonic()+60; last=""
while time.monotonic()<deadline:
 last=urlopen("http://mooncake-master-service:9003/metrics",timeout=10).read().decode()
 values={line.split()[0]:float(line.split()[1]) for line in last.splitlines() if len(line.split())==2}
 actual=values.get("master_key_count")
 if actual==expected: print(last,end=""); raise SystemExit(0)
 if actual is not None and actual>expected: raise SystemExit(f"key count exceeded expected value: {actual}>{expected}")
 time.sleep(0.5)
raise SystemExit(f"key count did not reach {expected}; last metrics:\n{last}")' "${expected}"
}

assert_metrics() {
  local path=$1 expected_keys=$2 require_empty=${3:-false}
  python3 -c 'import sys
values={}
for line in open(sys.argv[1],encoding="utf-8"):
 parts=line.split()
 if len(parts)==2 and parts[0] in {"master_key_count","master_allocated_bytes","master_active_clients"}: values[parts[0]]=float(parts[1])
assert values.get("master_key_count")==int(sys.argv[2]), values
if sys.argv[3]=="true": assert values.get("master_allocated_bytes")==0 and values.get("master_active_clients")==0, values' "${path}" "${expected_keys}" "${require_empty}"
}

capture_role_log() {
  local role=$1 destination=$2 pod container log
  if [[ ${role} == prefill ]]; then pod=${prefill_pod}; container=prefill-engine; log=/tmp/vllm-prefill.log; else pod=${decode_pod}; container=decode-engine; log=/tmp/vllm-decode.log; fi
  collect "${role} engine log" "${destination}" kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- cat "${log}"
}

remote_line_count() {
  local role=$1 pod container log
  if [[ ${role} == prefill ]]; then pod=${prefill_pod}; container=prefill-engine; log=/tmp/vllm-prefill.log; else pod=${decode_pod}; container=decode-engine; log=/tmp/vllm-decode.log; fi
  kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- wc -l "${log}" | awk '{print $1}'
}

capture_log_window() {
  local role=$1 start=$2 destination=$3 pod container log
  if [[ ${role} == prefill ]]; then pod=${prefill_pod}; container=prefill-engine; log=/tmp/vllm-prefill.log; else pod=${decode_pod}; container=decode-engine; log=/tmp/vllm-decode.log; fi
  collect "${role} log window" "${destination}" kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- sed -n "$((start + 1)),\$p" "${log}"
}

run_remote_driver() {
  local artifact=$1 action=$2
  shift 2
  record_step "remote driver: ${action}" "${artifact}" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 "${remote_tools}/stress-test.py" "${action}" "$@"
}

run_log_checker() {
  local artifact=$1 mode=$2
  shift 2
  record_step "log checker: ${mode}" "${artifact}.log" python3 "${script_dir}/check-stress-log.py" "${mode}" "$@"
}

fail_run() {
  overall_rc=1
  printf '%s\n' "$*" | tee -a "${output_dir}/failure.txt" >&2
  return 1
}

copy_remote_scenario() {
  local remote=$1 local_path=$2
  mkdir -p "${local_path}"
  record_step "copy scenario ${remote}" "${local_path}/kubectl-cp.log" kubectl cp -n "${namespace}" -c prefill-engine "${prefill_pod}:${remote}/." "${local_path}"
}

finalize_run() {
  local incoming_rc=$?
  (( trap_active == 1 )) || return
  trap_active=0
  trap - EXIT
  (( incoming_rc == 0 )) || overall_rc=1
  mkdir -p "${output_dir}/final"
  if [[ -n ${prefill_pod} && -n ${decode_pod} ]]; then
    capture_role_log prefill "${output_dir}/final/vllm-prefill.log" || true
    capture_role_log decode "${output_dir}/final/vllm-decode.log" || true
    stop_engines >>"${output_dir}/final/stop-engines.log" 2>&1 || collection_failed=1
    collect "final engine Pod state" "${output_dir}/final/engine-pods.yaml" kubectl get pod -n "${namespace}" "${prefill_pod}" "${decode_pod}" -o yaml || true
  fi
  [[ -z ${proxy_pod} ]] || collect "final proxy log" "${output_dir}/final/proxy.log" kubectl logs -n "${namespace}" "${proxy_pod}" -c proxy-server || true
  [[ -z ${master_pod} ]] || collect "final Master log" "${output_dir}/final/mooncake-master.log" kubectl logs -n "${namespace}" "${master_pod}" -c mooncake-master || true
  (( collection_failed == 0 )) || overall_rc=1
  jq -n --arg finished_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson exit_code "${overall_rc}" --arg prefill_pod "${prefill_pod}" --arg decode_pod "${decode_pod}" \
    '{finished_at:$finished_at,exit_code:$exit_code,prefill_pod:$prefill_pod,decode_pod:$decode_pod,engines_stopped:true,stress_pods_retained:true,allocated_npus_retained:6}' >"${output_dir}/final-run-state.json" || overall_rc=1
  printf '%d\n' "${overall_rc}" >"${output_dir}/runner.exit-code"
  exit "${overall_rc}"
}

reset_between_scenarios() {
  local label=$1
  stop_engines >"${output_dir}/${label}-stop.log" 2>&1 || return 1
  for role in prefill decode; do
    local pod_variable pod container
    pod_variable=${role}_pod
    pod=${!pod_variable}
    container=${role}-engine
    collect "${label} ${role} stopped process state" "${output_dir}/${label}-${role}-stopped-ps.txt" \
      kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- sh -c \
      "test ! -e /tmp/vllm-${role}.pid && ps -efww" || return 1
  done
  reset_master || return 1
  capture_metrics "${output_dir}/${label}-empty.metrics" || return 1
  assert_metrics "${output_dir}/${label}-empty.metrics" 0 true || return 1
  start_engines || return 1
  wait_for_http "${prefill_pod}" prefill-engine http://127.0.0.1:8100/v1/models "${label}-Prefill" || return 1
  wait_for_http "${decode_pod}" decode-engine http://127.0.0.1:8200/v1/models "${label}-Decode" || return 1
  wait_engine_ready "${label}-Prefill" "${prefill_pod}" || return 1
  wait_engine_ready "${label}-Decode" "${decode_pod}" || return 1
  wait_for_http "${prefill_pod}" prefill-engine http://vllm-proxy-service:8000/health "${label}-proxy" || return 1
  for role in prefill decode; do
    local pod_variable pod container
    pod_variable=${role}_pod
    pod=${!pod_variable}
    container=${role}-engine
    collect "${label} ${role} fresh log head" "${output_dir}/${label}-${role}-fresh-log.txt" \
      kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- sh -c \
      "test \$(wc -l < /tmp/vllm-${role}.log) -gt 0 && sed -n '1,20p' /tmp/vllm-${role}.log" || return 1
  done
}

for command_name in kubectl git jq python3 sha256sum nerdctl; do
  require_command "${command_name}" || exit 2
done
if [[ -e ${output_dir} && ! -d ${output_dir} ]]; then
  echo "output path is not a directory: ${output_dir}" >&2
  exit 2
fi
mkdir -p "${output_dir}"
if [[ -n $(find "${output_dir}" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
  echo "refusing non-empty output directory: ${output_dir}" >&2
  exit 2
fi
touch "${output_dir}/command-transcript.log" "${output_dir}/steps.jsonl"
trap_active=1
trap finalize_run EXIT

identity_check() {
  test "$(git branch --show-current)" = kv-pool-layerwise-reuse
  test "$(git -C repos/vllm rev-parse HEAD)" = ee0da84ab9e04ac7610e28580af62c365e898389
  test "$(git -C repos/vllm-ascend rev-parse HEAD)" = 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6
  test "$(git -C repos/Mooncake rev-parse HEAD)" = 74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5
  test -z "$(git -C repos/vllm status --porcelain)"
  test -z "$(git -C repos/vllm-ascend status --porcelain)"
  test -z "$(git -C repos/Mooncake status --porcelain)"
  git rev-parse HEAD
  git -C repos/vllm rev-parse HEAD
  git -C repos/vllm-ascend rev-parse HEAD
  git -C repos/Mooncake rev-parse HEAD
}

# All gates above the first kubectl apply are read-only.
record_step "control and source identity" "${output_dir}/identity.txt" identity_check || { fail_run "identity gate failed"; exit 1; }
collect "control repo status" "${output_dir}/git-status.txt" git status --short --branch || { fail_run "Git status capture failed"; exit 1; }
collect "remote feature HEAD" "${output_dir}/remote-head.txt" git ls-remote origin refs/heads/kv-pool-layerwise-reuse || { fail_run "remote HEAD capture failed"; exit 1; }
record_step "capture workspace lock" "${output_dir}/workspace-lock-copy.log" cp "${workspace_root}/workspace.lock.json" "${output_dir}/workspace.lock.json" || { fail_run "lock capture failed"; exit 1; }
for revision in ee0da84ab9e04ac7610e28580af62c365e898389 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6 74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5; do
  jq -e --arg revision "${revision}" '.. | strings | select(. == $revision)' "${workspace_root}/workspace.lock.json" >/dev/null || { fail_run "workspace lock is missing ${revision}"; exit 1; }
done
collect "node JSON" "${output_dir}/node.json" kubectl get node "${node_name}" -o json || { fail_run "node query failed"; exit 1; }
collect "all cluster Pods" "${output_dir}/pods-before.json" kubectl get pods -A -o json || { fail_run "Pod capacity query failed"; exit 1; }
python3 -c 'import json,sys
node=json.load(open(sys.argv[1])); pods=json.load(open(sys.argv[2]))["items"]
alloc=int(node["status"]["allocatable"]["huawei.com/Ascend910"]); used=0; counted=[]
for pod in pods:
 spec=pod.get("spec",{}); status=pod.get("status",{}); metadata=pod.get("metadata",{})
 if spec.get("nodeName")!="n1" or status.get("phase") not in {"Running","Pending"}: continue
 name=metadata.get("name",""); namespace=metadata.get("namespace")
 replaced=namespace=="ai-inference" and (name.startswith("prefill-engine-deployment-") or name.startswith("decode-engine-deployment-"))
 if replaced: continue
 request=sum(int(c.get("resources",{}).get("requests",{}).get("huawei.com/Ascend910",0)) for c in spec.get("containers",[]))
 if request: counted.append({"namespace":pod["metadata"]["namespace"],"pod":pod["metadata"]["name"],"request":request}); used+=request
result={"allocatable":alloc,"used_excluding_replaced_engines":used,"available":alloc-used,"required":6,"counted_pods":counted}
print(json.dumps(result,indent=2)); assert result["available"]>=6, result' "${output_dir}/node.json" "${output_dir}/pods-before.json" >"${output_dir}/npu-capacity.json" || { fail_run "fewer than 6 NPUs are available"; exit 1; }
record_step "local image identity" "${output_dir}/image-inspect.json" nerdctl -n k8s.io image inspect "${image}" || { fail_run "local image unavailable"; exit 1; }

prefill_pod=$(resolve_running_pod prefill app=prefill) || { fail_run "current Prefill Pod unavailable"; exit 1; }
decode_pod=$(resolve_running_pod decode app=decode) || { fail_run "current Decode Pod unavailable"; exit 1; }
proxy_pod=$(resolve_running_pod proxy app=proxy) || { fail_run "proxy Pod unavailable"; exit 1; }
master_pod=$(resolve_running_pod master app=mooncake-master) || { fail_run "Master Pod unavailable"; exit 1; }
collect "current engine image on n1" "${output_dir}/current-engine-image.json" kubectl get pod -n "${namespace}" \
  "${prefill_pod}" "${decode_pod}" -o json || { fail_run "current engine image capture failed"; exit 1; }
jq -e --arg image "${image}" '
  (.items | length) == 2 and
  all(.items[];
    .spec.nodeName == "n1" and
    .spec.containers[0].image == $image and
    (.status.containerStatuses[0].imageID | type == "string" and length > 0))
' "${output_dir}/current-engine-image.json" >/dev/null || { fail_run "image is not confirmed on n1"; exit 1; }
record_step "model identity" "${output_dir}/model-identity.json" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 -c 'import json,sys; p=sys.argv[1]; c=json.load(open(p+"/config.json")); assert c["max_position_embeddings"]>=65536; print(json.dumps({"path":p,"max_position_embeddings":c["max_position_embeddings"]}))' "${model_path}" || { fail_run "model identity gate failed"; exit 1; }
for role in prefill decode; do
  pod_variable=${role}_pod
  pod=${!pod_variable}
  record_step "${role} pre-replacement runtime check" "${output_dir}/${role}-runtime-check-before.log" kubectl exec -n "${namespace}" "${pod}" -c "${role}-engine" -- python3 /opt/vllm-layerwise/check-runtime.py || { fail_run "${role} pre-replacement runtime check failed"; exit 1; }
done

stop_engines >"${output_dir}/stop-before-apply.log" 2>&1 || { fail_run "could not stop old engines"; exit 1; }
record_step "apply stress ConfigMap" "${output_dir}/apply-config.log" kubectl apply -f "${script_dir}/stress/10-runtime-config.yaml" || { fail_run "stress ConfigMap apply failed"; exit 1; }
record_step "apply stress Prefill" "${output_dir}/apply-prefill.log" kubectl apply -f "${script_dir}/stress/40-prefill-engine.yaml" || { fail_run "stress Prefill apply failed"; exit 1; }
record_step "apply stress Decode" "${output_dir}/apply-decode.log" kubectl apply -f "${script_dir}/stress/50-decode-engine.yaml" || { fail_run "stress Decode apply failed"; exit 1; }
prefill_pod=$(wait_running app=prefill 4) || { fail_run "stress Prefill Pod did not run"; exit 1; }
decode_pod=$(wait_running app=decode 2) || { fail_run "stress Decode Pod did not run"; exit 1; }
record_step "sync vLLM-Ascend Python" "${output_dir}/source-sync.log" "${script_dir}/sync-vllm-ascend-python.sh" || { fail_run "source sync failed"; exit 1; }
for role in prefill decode; do
  pod_variable=${role}_pod
  pod=${!pod_variable}
  record_step "${role} runtime check" "${output_dir}/${role}-runtime-check.log" kubectl exec -n "${namespace}" "${pod}" -c "${role}-engine" -- python3 /opt/vllm-layerwise/check-runtime.py || { fail_run "${role} runtime check failed"; exit 1; }
done

{
  git -C "${workspace_root}/repos/vllm-ascend" diff --name-only --diff-filter=ACMRT 663209fd6208a59a48742f75116345bf5f5281ec -- vllm_ascend
  git -C "${workspace_root}/repos/vllm-ascend" ls-files --others --exclude-standard -- vllm_ascend
} | sort -u | awk '/\.py$/' >"${output_dir}/synced-python-files.txt"
: >"${output_dir}/source-checksums.tsv"
while IFS= read -r path; do
  [[ -n ${path} ]] || continue
  host_sum=$(sha256sum "${workspace_root}/repos/vllm-ascend/${path}" | awk '{print $1}')
  prefill_sum=$(kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- sha256sum "/vllm-workspace/vllm-ascend/${path}" | awk '{print $1}')
  decode_sum=$(kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- sha256sum "/vllm-workspace/vllm-ascend/${path}" | awk '{print $1}')
  printf '%s\t%s\t%s\t%s\n' "${path}" "${host_sum}" "${prefill_sum}" "${decode_sum}" >>"${output_dir}/source-checksums.tsv"
  [[ ${host_sum} == "${prefill_sum}" && ${host_sum} == "${decode_sum}" ]] || { fail_run "source checksum mismatch: ${path}"; exit 1; }
done <"${output_dir}/synced-python-files.txt"

reset_master || { fail_run "initial Master reset failed"; exit 1; }
capture_metrics "${output_dir}/master-empty-initial.metrics" || { fail_run "initial metrics capture failed"; exit 1; }
assert_metrics "${output_dir}/master-empty-initial.metrics" 0 true || { fail_run "Master was not empty"; exit 1; }
start_engines || { fail_run "engine startup failed"; exit 1; }
wait_for_http "${prefill_pod}" prefill-engine http://127.0.0.1:8100/v1/models Prefill || { fail_run "Prefill readiness failed"; exit 1; }
wait_for_http "${decode_pod}" decode-engine http://127.0.0.1:8200/v1/models Decode || { fail_run "Decode readiness failed"; exit 1; }
wait_engine_ready Prefill "${prefill_pod}" || { fail_run "Prefill Pod did not become Ready"; exit 1; }
wait_engine_ready Decode "${decode_pod}" || { fail_run "Decode Pod did not become Ready"; exit 1; }
wait_for_http "${prefill_pod}" prefill-engine http://vllm-proxy-service:8000/health proxy || { fail_run "proxy health failed"; exit 1; }
collect "proxy endpoints before topology" "${output_dir}/proxy-endpoints-initial.json" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 -c 'import json
from urllib.request import urlopen
body=json.load(urlopen("http://vllm-proxy-service:8000/listEndPoints",timeout=10))
assert len(body.get("prefill_nodes",[]))==1 and len(body.get("decode_nodes",[]))==1, body
print(json.dumps(body,indent=2))' || { fail_run "proxy endpoint discovery gate failed"; exit 1; }

mkdir -p "${output_dir}/topology"
capture_role_log prefill "${output_dir}/topology/vllm-prefill.log" || true
capture_role_log decode "${output_dir}/topology/vllm-decode.log" || true
collect "Prefill Pod YAML" "${output_dir}/topology/prefill-pod.yaml" kubectl get pod -n "${namespace}" "${prefill_pod}" -o yaml || true
collect "Decode Pod YAML" "${output_dir}/topology/decode-pod.yaml" kubectl get pod -n "${namespace}" "${decode_pod}" -o yaml || true
collect "Prefill process tree" "${output_dir}/topology/prefill-ps.txt" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- ps -efww || true
collect "Decode process tree" "${output_dir}/topology/decode-ps.txt" kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- ps -efww || true
collect "Prefill NPU info" "${output_dir}/topology/prefill-npu-info.txt" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- npu-smi info || true
collect "Decode NPU info" "${output_dir}/topology/decode-npu-info.txt" kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- npu-smi info || true
run_log_checker "${output_dir}/topology/check" topology \
  --prefill-log "${output_dir}/topology/vllm-prefill.log" --decode-log "${output_dir}/topology/vllm-decode.log" \
  --prefill-pod-yaml "${output_dir}/topology/prefill-pod.yaml" --decode-pod-yaml "${output_dir}/topology/decode-pod.yaml" \
  --prefill-ps "${output_dir}/topology/prefill-ps.txt" --decode-ps "${output_dir}/topology/decode-ps.txt" \
  --prefill-npu-info "${output_dir}/topology/prefill-npu-info.txt" --decode-npu-info "${output_dir}/topology/decode-npu-info.txt" \
  --output "${output_dir}/topology/check.json" || { fail_run "topology checker failed"; exit 1; }

record_step "create remote tool directories" "${output_dir}/install-driver.log" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${remote_tools}" "${remote_root}" || { fail_run "remote tool directory failed"; exit 1; }
record_step "copy remote stress driver" "${output_dir}/copy-driver.log" kubectl cp -n "${namespace}" -c prefill-engine "${script_dir}/stress-test.py" "${prefill_pod}:${remote_tools}/stress-test.py" || { fail_run "driver copy failed"; exit 1; }

# S1: four isolated 16K requests pinned to Prefill ranks 0,1,0,1.
s1_remote=${remote_root}/s1-pinned-16k
s1_host=${output_dir}/s1-pinned-16k
mkdir -p "${s1_host}"
record_step "create S1 remote directory" "${s1_host}/mkdir.log" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${s1_remote}" || { fail_run "S1 mkdir failed"; exit 1; }
run_remote_driver "${s1_host}/prepare.log" prepare --scenario s1 --output "${s1_remote}" || { fail_run "S1 prepare failed"; exit 1; }
run_remote_driver "${s1_host}/baseline.log" baseline --scenario s1 --output "${s1_remote}" || { fail_run "S1 baseline failed"; exit 1; }
capture_metrics "${s1_host}/after-baseline.metrics" && assert_metrics "${s1_host}/after-baseline.metrics" 0 || { fail_run "S1 baseline changed pool"; exit 1; }
s1_rank=(0 1 0 1)
s1_check_args=()
for index in 0 1 2 3; do
  before_prefill=$(remote_line_count prefill) || { fail_run "S1 Prefill line count failed"; exit 1; }
  before_decode=$(remote_line_count decode) || { fail_run "S1 Decode line count failed"; exit 1; }
  run_remote_driver "${s1_host}/pinned-${index}.log" pinned-load --scenario s1 --output "${s1_remote}" --case-index "${index}" --prefill-rank "${s1_rank[index]}" --decode-rank 0 || { fail_run "S1 case ${index} failed"; exit 1; }
  capture_log_window prefill "${before_prefill}" "${s1_host}/case-${index}-prefill.log" || { fail_run "S1 Prefill window failed"; exit 1; }
  capture_log_window decode "${before_decode}" "${s1_host}/case-${index}-decode.log" || { fail_run "S1 Decode window failed"; exit 1; }
  copy_remote_scenario "${s1_remote}" "${s1_host}/snapshot-${index}" || { fail_run "S1 fixture snapshot failed"; exit 1; }
  prompt_tokens=$(jq -r ".prompt_tokens[${index}]" "${s1_host}/snapshot-${index}/fixture.json")
  run_log_checker "${s1_host}/case-${index}-check" pinned --prefill-log-window "${s1_host}/case-${index}-prefill.log" \
    --decode-log-window "${s1_host}/case-${index}-decode.log" --expected-prefill-dp-rank "${s1_rank[index]}" \
    --expected-prompt-tokens "${prompt_tokens}" --expected-hit-tokens 16256 --min-context-iterations 16 \
    --max-context-tokens 1024 --num-layers 27 --output "${s1_host}/case-${index}-check.json" || { fail_run "S1 checker case ${index} failed"; exit 1; }
  record_step "copy S1 checker ${index} remote" "${s1_host}/copy-check-${index}.log" kubectl cp -n "${namespace}" -c prefill-engine \
    "${s1_host}/case-${index}-check.json" "${prefill_pod}:${s1_remote}/case-${index}-check.json" || { fail_run "S1 checker copy failed"; exit 1; }
  wait_for_key_count "${s1_host}/after-case-${index}.metrics" "$((127 * (index + 1)))" || { fail_run "S1 key count mismatch"; exit 1; }
  s1_check_args+=(--log-check-summary "${s1_remote}/case-${index}-check.json")
done
wait_for_key_count "${s1_host}/final.metrics" 508 || { fail_run "S1 final key count mismatch"; exit 1; }
record_step "copy S1 final metrics remote" "${s1_host}/copy-metrics.log" kubectl cp -n "${namespace}" -c prefill-engine "${s1_host}/final.metrics" "${prefill_pod}:${s1_remote}/final.metrics" || { fail_run "S1 metrics copy failed"; exit 1; }
run_remote_driver "${s1_host}/finalize.log" finalize --scenario s1 --output "${s1_remote}" --master-metrics "${s1_remote}/final.metrics" "${s1_check_args[@]}" || { fail_run "S1 finalize failed"; exit 1; }
copy_remote_scenario "${s1_remote}" "${s1_host}/artifacts" || { fail_run "S1 artifact copy failed"; exit 1; }
capture_role_log prefill "${s1_host}/vllm-prefill-full.log" || true
capture_role_log decode "${s1_host}/vllm-decode-full.log" || true

reset_between_scenarios before-s2 || { fail_run "S1 to S2 reset failed"; exit 1; }

# S2: sixteen concurrent 8K requests through proxy.
s2_remote=${remote_root}/s2-concurrent-16x8k
s2_host=${output_dir}/s2-concurrent-16x8k
mkdir -p "${s2_host}"
record_step "create S2 remote directory" "${s2_host}/mkdir.log" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${s2_remote}" || { fail_run "S2 mkdir failed"; exit 1; }
run_remote_driver "${s2_host}/prepare.log" prepare --scenario s2 --output "${s2_remote}" || { fail_run "S2 prepare failed"; exit 1; }
run_remote_driver "${s2_host}/baseline.log" baseline --scenario s2 --output "${s2_remote}" || { fail_run "S2 baseline failed"; exit 1; }
capture_metrics "${s2_host}/after-baseline.metrics" && assert_metrics "${s2_host}/after-baseline.metrics" 0 || { fail_run "S2 baseline changed pool"; exit 1; }
before_prefill=$(remote_line_count prefill) || { fail_run "S2 Prefill line count failed"; exit 1; }
before_decode=$(remote_line_count decode) || { fail_run "S2 Decode line count failed"; exit 1; }
run_remote_driver "${s2_host}/proxy-load.log" proxy-load --scenario s2 --output "${s2_remote}" || { fail_run "S2 proxy load failed"; exit 1; }
capture_log_window prefill "${before_prefill}" "${s2_host}/prefill-window.log" || { fail_run "S2 Prefill window failed"; exit 1; }
capture_log_window decode "${before_decode}" "${s2_host}/decode-window.log" || { fail_run "S2 Decode window failed"; exit 1; }
run_log_checker "${s2_host}/aggregate-check" aggregate --prefill-log-window "${s2_host}/prefill-window.log" --decode-log-window "${s2_host}/decode-window.log" \
  --required-prefill-dp-ranks 0,1 --max-context-tokens 1024 --num-layers 27 --output "${s2_host}/aggregate-check.json" || { fail_run "S2 aggregate checker failed"; exit 1; }
wait_for_key_count "${s2_host}/final.metrics" 288 || { fail_run "S2 key count mismatch"; exit 1; }
for file in aggregate-check.json final.metrics; do
  record_step "copy S2 ${file} remote" "${s2_host}/copy-${file}.log" kubectl cp -n "${namespace}" -c prefill-engine "${s2_host}/${file}" "${prefill_pod}:${s2_remote}/${file}" || { fail_run "S2 support artifact copy failed"; exit 1; }
done
run_remote_driver "${s2_host}/finalize.log" finalize --scenario s2 --output "${s2_remote}" --master-metrics "${s2_remote}/final.metrics" --log-check-summary "${s2_remote}/aggregate-check.json" || { fail_run "S2 finalize failed"; exit 1; }
copy_remote_scenario "${s2_remote}" "${s2_host}/artifacts" || { fail_run "S2 artifact copy failed"; exit 1; }
capture_role_log prefill "${s2_host}/vllm-prefill-full.log" || true
capture_role_log decode "${s2_host}/vllm-decode-full.log" || true

reset_between_scenarios before-s3 || { fail_run "S2 to S3 reset failed"; exit 1; }

# S3: one isolated cold 32K proof, then four concurrent 32K proxy requests.
s3_remote=${remote_root}/s3-concurrent-4x32k
s3_host=${output_dir}/s3-concurrent-4x32k
mkdir -p "${s3_host}"
record_step "create S3 remote directory" "${s3_host}/mkdir.log" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${s3_remote}" || { fail_run "S3 mkdir failed"; exit 1; }
run_remote_driver "${s3_host}/prepare.log" prepare --scenario s3 --output "${s3_remote}" || { fail_run "S3 prepare failed"; exit 1; }
run_remote_driver "${s3_host}/baseline.log" baseline --scenario s3 --output "${s3_remote}" || { fail_run "S3 baseline failed"; exit 1; }
capture_metrics "${s3_host}/after-baseline.metrics" && assert_metrics "${s3_host}/after-baseline.metrics" 0 || { fail_run "S3 baseline changed pool"; exit 1; }
before_prefill=$(remote_line_count prefill) || { fail_run "S3 Prefill line count failed"; exit 1; }
before_decode=$(remote_line_count decode) || { fail_run "S3 Decode line count failed"; exit 1; }
run_remote_driver "${s3_host}/pinned-0.log" pinned-load --scenario s3 --output "${s3_remote}" --case-index 0 --prefill-rank 0 --decode-rank 0 || { fail_run "S3 cold probe failed"; exit 1; }
capture_log_window prefill "${before_prefill}" "${s3_host}/pinned-prefill.log" || { fail_run "S3 pinned Prefill window failed"; exit 1; }
capture_log_window decode "${before_decode}" "${s3_host}/pinned-decode.log" || { fail_run "S3 pinned Decode window failed"; exit 1; }
copy_remote_scenario "${s3_remote}" "${s3_host}/snapshot-pinned" || { fail_run "S3 fixture snapshot failed"; exit 1; }
s3_prompt_tokens=$(jq -r '.prompt_tokens[0]' "${s3_host}/snapshot-pinned/fixture.json")
run_log_checker "${s3_host}/pinned-check" pinned --prefill-log-window "${s3_host}/pinned-prefill.log" --decode-log-window "${s3_host}/pinned-decode.log" \
  --expected-prefill-dp-rank 0 --expected-prompt-tokens "${s3_prompt_tokens}" --expected-hit-tokens 32640 --min-context-iterations 32 \
  --max-context-tokens 1024 --num-layers 27 --output "${s3_host}/pinned-check.json" || { fail_run "S3 pinned checker failed"; exit 1; }
wait_for_key_count "${s3_host}/after-pinned.metrics" 255 || { fail_run "S3 pinned key count mismatch"; exit 1; }
before_prefill=$(remote_line_count prefill) || { fail_run "S3 aggregate Prefill line count failed"; exit 1; }
before_decode=$(remote_line_count decode) || { fail_run "S3 aggregate Decode line count failed"; exit 1; }
run_remote_driver "${s3_host}/proxy-load.log" proxy-load --scenario s3 --output "${s3_remote}" || { fail_run "S3 proxy load failed"; exit 1; }
capture_log_window prefill "${before_prefill}" "${s3_host}/aggregate-prefill.log" || { fail_run "S3 aggregate Prefill window failed"; exit 1; }
capture_log_window decode "${before_decode}" "${s3_host}/aggregate-decode.log" || { fail_run "S3 aggregate Decode window failed"; exit 1; }
run_log_checker "${s3_host}/aggregate-check" aggregate --prefill-log-window "${s3_host}/aggregate-prefill.log" --decode-log-window "${s3_host}/aggregate-decode.log" \
  --required-prefill-dp-ranks 0,1 --max-context-tokens 1024 --num-layers 27 --output "${s3_host}/aggregate-check.json" || { fail_run "S3 aggregate checker failed"; exit 1; }
wait_for_key_count "${s3_host}/final.metrics" 348 || { fail_run "S3 key count mismatch"; exit 1; }
for file in pinned-check.json aggregate-check.json final.metrics; do
  record_step "copy S3 ${file} remote" "${s3_host}/copy-${file}.log" kubectl cp -n "${namespace}" -c prefill-engine "${s3_host}/${file}" "${prefill_pod}:${s3_remote}/${file}" || { fail_run "S3 support artifact copy failed"; exit 1; }
done
run_remote_driver "${s3_host}/finalize.log" finalize --scenario s3 --output "${s3_remote}" --master-metrics "${s3_remote}/final.metrics" \
  --log-check-summary "${s3_remote}/pinned-check.json" --log-check-summary "${s3_remote}/aggregate-check.json" || { fail_run "S3 finalize failed"; exit 1; }
copy_remote_scenario "${s3_remote}" "${s3_host}/artifacts" || { fail_run "S3 artifact copy failed"; exit 1; }
capture_role_log prefill "${s3_host}/vllm-prefill-full.log" || true
capture_role_log decode "${s3_host}/vllm-decode-full.log" || true

jq -n --slurpfile topology "${output_dir}/topology/check.json" --slurpfile s1 "${s1_host}/artifacts/scenario-summary.json" \
  --slurpfile s2 "${s2_host}/artifacts/scenario-summary.json" --slurpfile s3 "${s3_host}/artifacts/scenario-summary.json" \
  --arg control_commit "$(git rev-parse HEAD)" --arg image "${image}" --arg prefill_pod "${prefill_pod}" --arg decode_pod "${decode_pod}" \
  '{schema_version:1,status:(if ($topology[0].validated and $s1[0].validated and $s2[0].validated and $s3[0].validated) then "passed" else "failed" end),validated:($topology[0].validated and $s1[0].validated and $s2[0].validated and $s3[0].validated),identity:{control_commit:$control_commit,image:$image,vllm:"ee0da84ab9e04ac7610e28580af62c365e898389",vllm_ascend:"3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6",mooncake:"74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5",prefill_pod:$prefill_pod,decode_pod:$decode_pod},topology:$topology[0],scenarios:{s1_pinned_16k:$s1[0],s2_concurrent_16x8k:$s2[0],s3_concurrent_4x32k:$s3[0]},errors:[]}' \
  >"${output_dir}/overall-summary.json" || { fail_run "overall summary creation failed"; exit 1; }
jq -e '.status == "passed" and .validated == true and .topology.validated == true and .scenarios.s1_pinned_16k.validated == true and .scenarios.s2_concurrent_16x8k.validated == true and .scenarios.s3_concurrent_4x32k.validated == true and (.errors|length)==0' \
  "${output_dir}/overall-summary.json" >/dev/null || { fail_run "overall assertion failed"; exit 1; }
jq -e '.validated == true and .exact_match_count == 4 and .isolated_count == 4 and .actual_key_count == 508' \
  "${s1_host}/artifacts/scenario-summary.json" >/dev/null || { fail_run "S1 final assertion failed"; exit 1; }
jq -e '.validated == true and .exact_match_count == 16 and .isolated_count == 16 and .actual_key_count == 288' \
  "${s2_host}/artifacts/scenario-summary.json" >/dev/null || { fail_run "S2 final assertion failed"; exit 1; }
jq -e '.validated == true and .exact_match_count == 4 and .isolated_count == 4 and .actual_key_count == 348' \
  "${s3_host}/artifacts/scenario-summary.json" >/dev/null || { fail_run "S3 final assertion failed"; exit 1; }

capture_metrics "${output_dir}/master-final.metrics" || { fail_run "final metrics capture failed"; exit 1; }
collect "final proxy endpoints" "${output_dir}/proxy-endpoints-final.json" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 -c 'from urllib.request import urlopen; print(urlopen("http://vllm-proxy-service:8000/listEndPoints",timeout=10).read().decode(),end="")' || true
collect "final Prefill NPU info" "${output_dir}/prefill-npu-final.txt" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- npu-smi info || true
collect "final Decode NPU info" "${output_dir}/decode-npu-final.txt" kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- npu-smi info || true
collect "final Prefill process tree" "${output_dir}/prefill-ps-final.txt" kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- ps -efww || true
collect "final Decode process tree" "${output_dir}/decode-ps-final.txt" kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- ps -efww || true
stop_engines >"${output_dir}/final-stop-engines.log" 2>&1 || { fail_run "final engine stop failed"; exit 1; }
collect "final stopped engine Pod state" "${output_dir}/final-stopped-pods.yaml" kubectl get pods -n "${namespace}" -l 'app in (prefill,decode)' -o yaml || true
for role in prefill decode; do
  pod_variable=${role}_pod
  pod=${!pod_variable}
  container=${role}-engine
  record_step "confirm ${role} PID absent" "${output_dir}/${role}-pid-absent.log" kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- test ! -e "/tmp/vllm-${role}.pid" || { fail_run "${role} PID file remains"; exit 1; }
  port=8100
  [[ ${role} == decode ]] && port=8200
  record_step "confirm ${role} HTTP stopped" "${output_dir}/${role}-http-stopped.log" kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- \
    python3 -c 'import sys,urllib.request
try: urllib.request.urlopen(sys.argv[1],timeout=2)
except Exception as exc: print(type(exc).__name__,exc); raise SystemExit(0)
raise SystemExit("HTTP endpoint still accepts requests")' "http://127.0.0.1:${port}/v1/models" || { fail_run "${role} HTTP endpoint remains live"; exit 1; }
done
collect "retained six-NPU allocation" "${output_dir}/retained-allocation.json" kubectl get pod -n "${namespace}" \
  "${prefill_pod}" "${decode_pod}" -o json || { fail_run "retained allocation capture failed"; exit 1; }
overall_rc=0
