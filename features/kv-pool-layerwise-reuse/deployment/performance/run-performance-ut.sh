#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly pod_name=vllm-ascend-ut
readonly container_name=ut
readonly remote_root=/workspace/layerwise-performance-tests
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly package_parent="$(dirname -- "${script_dir}")"

usage() {
  echo "usage: run-performance-ut.sh -- <command> [args...]" >&2
}

if [[ $# -lt 2 || $1 != -- ]]; then
  usage
  exit 2
fi
shift

for command_name in kubectl jq tar date; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "required command is unavailable: ${command_name}" >&2
    exit 2
  }
done

kubectl wait -n "${namespace}" --for=jsonpath='{.status.phase}'=Running \
  "pod/${pod_name}" --timeout=120s >/dev/null
kubectl get pod -n "${namespace}" "${pod_name}" -o json | jq -e \
  --arg namespace "${namespace}" \
  --arg pod "${pod_name}" \
  --arg container "${container_name}" '
    .metadata.namespace == $namespace
    and .metadata.name == $pod
    and .metadata.deletionTimestamp == null
    and .status.phase == "Running"
    and any(.status.containerStatuses[]?;
      .name == $container and .ready == true)
    and all(.spec.containers[];
      ((.resources.requests // {}) | has("huawei.com/Ascend910") | not)
      and ((.resources.limits // {}) | has("huawei.com/Ascend910") | not)
      and ((.resources.requests // {}) | has("huawei.com/vnpu-number") | not)
      and ((.resources.limits // {}) | has("huawei.com/vnpu-number") | not))
    and all(.spec.volumes[]?; has("hostPath") | not)
  ' >/dev/null

readonly run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
readonly remote_stage="${remote_root}.incoming-${run_id}"
cleanup() {
  kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
    rm -rf -- "${remote_stage}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  mkdir "${remote_stage}"
tar --exclude='*/__pycache__' --exclude='*.pyc' \
  --exclude='./performance/.pytest_cache' --exclude='./performance/.ruff_cache' \
  -C "${package_parent}" -cf - performance | \
  kubectl exec -i -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
    tar -C "${remote_stage}" -xf -

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  bash -c '
    set -eu
    stage=$1
    target=$2
    rm -rf -- "${target}"
    mv -- "${stage}" "${target}"
  ' bash "${remote_stage}" "${remote_root}"

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${remote_root}" \
  PYTEST_ADDOPTS='-p no:cacheprovider' bash -c '
    set -eu
    root=$1
    shift
    cd "${root}"
    exec "$@"
  ' bash "${remote_root}" "$@"
