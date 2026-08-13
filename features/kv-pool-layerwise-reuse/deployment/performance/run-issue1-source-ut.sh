#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly pod_name=vllm-ascend-ut
readonly container_name=ut
readonly expected_source_head=8653c6c5e3b554719c8347a0a36fe2109e6a36d9
readonly remote_parent=/workspace
readonly remote_checkout=${remote_parent}/vllm-ascend-issue1
readonly remote_lock=${remote_parent}/.vllm-ascend-issue1-ut.lock
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly workspace_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
readonly source_repo=${workspace_root}/repos/vllm-ascend

usage() {
  cat >&2 <<'EOF'
usage: run-issue1-source-ut.sh -- <command> [args...]

The current vLLM-Ascend checkout must be clean and match the reviewed Issue #1
candidate commit before it is tar-synced into the CPU-only UT Pod.
EOF
}

if [[ $# -lt 2 || $1 != -- ]]; then
  usage
  exit 2
fi
shift

for command_name in kubectl git tar jq date; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "required command is unavailable: ${command_name}" >&2
    exit 2
  }
done

source_head=$(git -C "${source_repo}" rev-parse HEAD)
if [[ ${source_head} != "${expected_source_head}" ]]; then
  echo "unexpected vLLM-Ascend source HEAD: ${source_head}" >&2
  exit 1
fi
source_branch=$(git -C "${source_repo}" branch --show-current)
source_branch=${source_branch:-DETACHED}
source_status=$(git -C "${source_repo}" status --porcelain=v1 --untracked-files=all)
if [[ -n ${source_status} ]]; then
  echo "Issue #1 source UT requires a clean vLLM-Ascend checkout" >&2
  printf '%s\n' "${source_status}" >&2
  exit 1
fi
source_tree=$(git -C "${source_repo}" rev-parse 'HEAD^{tree}')

current_context=$(kubectl config current-context)
test -n "${current_context}"
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

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
readonly run_id
readonly remote_stage=${remote_parent}/.vllm-ascend-issue1.incoming-${run_id}
lock_acquired=0
cleanup_remote() {
  kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
    rm -rf -- "${remote_stage}" >/dev/null 2>&1 || true
  if (( lock_acquired )); then
    kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
      rmdir "${remote_lock}" >/dev/null 2>&1 || true
  fi
}
trap cleanup_remote EXIT

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  mkdir "${remote_lock}"
lock_acquired=1
kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  mkdir "${remote_stage}"
tar \
  --exclude='./.git' \
  --exclude='./.pytest_cache' \
  --exclude='./.ruff_cache' \
  --exclude='./.tox' \
  --exclude='./.venv' \
  --exclude='./build' \
  --exclude='./dist' \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  -C "${source_repo}" -cf - . | \
  kubectl exec -i -n "${namespace}" "${pod_name}" \
    -c "${container_name}" -- tar -C "${remote_stage}" -xf -
kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  bash -c '
    set -eu
    stage=$1
    target=$2
    rm -rf -- "${target}"
    mv -- "${stage}" "${target}"
  ' bash "${remote_stage}" "${remote_checkout}"

printf 'context=%s\nnamespace=%s\npod=%s\nsource_head=%s\nsource_tree=%s\nsource_branch=%s\nsource_clean=true\n' \
  "${current_context}" "${namespace}" "${pod_name}" "${source_head}" \
  "${source_tree}" "${source_branch}"

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  env TORCH_DEVICE_BACKEND_AUTOLOAD=0 PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_ADDOPTS='-p no:cacheprovider' \
  bash -c '
    set -eu
    checkout=$1
    shift
    cd "${checkout}"
    export PYTHONPATH="${checkout}${PYTHONPATH:+:${PYTHONPATH}}"
    exec "$@"
  ' bash "${remote_checkout}" "$@"
