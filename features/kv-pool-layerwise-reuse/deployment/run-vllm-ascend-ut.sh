#!/usr/bin/env bash
set -euo pipefail

readonly namespace=liangjiahao
readonly pod_name=vllm-ascend-ut
readonly container_name=ut
readonly node_name=n1
readonly expected_image=docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-2770cd3a-df3f74ed-20260808T042014Z-r1
readonly image_source_head=2770cd3ae66522c2eccb1c568889a55137836c0d
readonly expected_source_head=2770cd3ae66522c2eccb1c568889a55137836c0d
readonly remote_parent=/workspace
readonly remote_checkout=${remote_parent}/vllm-ascend
readonly remote_lock=${remote_parent}/.vllm-ascend-ut.lock
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly workspace_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
readonly source_repo="${workspace_root}/repos/vllm-ascend"

usage() {
  cat >&2 <<'EOF'
usage: run-vllm-ascend-ut.sh -- <command> [args...]

Examples:
  run-vllm-ascend-ut.sh -- python3 -m pytest -q tests/ut/test_envs.py
  run-vllm-ascend-ut.sh -- python3 -m pytest --collect-only -q tests/ut
EOF
}

if [[ $# -lt 2 || $1 != -- ]]; then
  usage
  exit 2
fi
shift

for command_name in kubectl git tar jq date; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "required command is unavailable: ${command_name}" >&2
    exit 2
  fi
done

if [[ ! -d ${source_repo}/vllm_ascend || ! -d ${source_repo}/tests/ut ]]; then
  echo "vLLM-Ascend checkout is incomplete: ${source_repo}" >&2
  exit 2
fi

mapfile -t overlay_files < <(
  git -C "${source_repo}" diff --name-only "${image_source_head}" -- \
    vllm_ascend | LC_ALL=C sort
)
expected_overlay_files=(
)
if [[ "${overlay_files[*]}" != "${expected_overlay_files[*]}" ]]; then
  printf 'unexpected Python overlay relative to image source %s:\n' \
    "${image_source_head}" >&2
  printf '  %s\n' "${overlay_files[@]}" >&2
  exit 1
fi

current_context=$(kubectl -n "${namespace}" config current-context)
if [[ -z ${current_context} ]]; then
  echo "kubectl has no current context" >&2
  exit 2
fi

kubectl wait -n "${namespace}" --for=jsonpath='{.status.phase}'=Running \
  "pod/${pod_name}" --timeout=120s >/dev/null

kubectl get pod -n "${namespace}" "${pod_name}" -o json | jq -e \
  --arg namespace "${namespace}" \
  --arg pod "${pod_name}" \
  --arg container "${container_name}" \
  --arg node "${node_name}" \
  --arg image "${expected_image}" '
    .metadata.namespace == $namespace
    and .metadata.name == $pod
    and .metadata.deletionTimestamp == null
    and .status.phase == "Running"
    and .spec.nodeName == $node
    and any(.status.containerStatuses[]?;
      .name == $container and .ready == true)
    and any(.spec.containers[];
      .name == $container and .image == $image)
    and all(.spec.containers[];
      ((.resources.requests // {}) | has("huawei.com/Ascend910") | not)
      and ((.resources.limits // {}) | has("huawei.com/Ascend910") | not))
    and all(.spec.volumes[]?; has("hostPath") | not)
  ' >/dev/null

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
readonly run_id
readonly remote_stage=${remote_parent}/.vllm-ascend.incoming-${run_id}
readonly remote_previous=${remote_parent}/.vllm-ascend.previous-${run_id}
lock_acquired=0

cleanup() {
  local cleanup_rc=0
  kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
    rm -rf -- "${remote_stage}" "${remote_previous}" >/dev/null 2>&1 \
    || cleanup_rc=1
  if (( lock_acquired )); then
    kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
      rmdir "${remote_lock}" >/dev/null 2>&1 || cleanup_rc=1
  fi
  return "${cleanup_rc}"
}
trap 'cleanup || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
    mkdir "${remote_lock}"; then
  echo "UT Pod is locked by another sync or test: ${remote_lock}" >&2
  echo "inspect the Pod before removing a stale lock" >&2
  exit 1
fi
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

source_head=$(git -C "${source_repo}" rev-parse HEAD)
source_branch=$(git -C "${source_repo}" branch --show-current)
source_branch=${source_branch:-DETACHED}
if [[ -n $(git -C "${source_repo}" status --porcelain=v1) ]]; then
  source_dirty=true
else
  source_dirty=false
fi
if [[ ${source_head} != "${expected_source_head}" || ${source_dirty} != false ]]; then
  echo "source identity mismatch: expected clean ${expected_source_head}, got ${source_head} dirty=${source_dirty}" >&2
  exit 1
fi
synced_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  bash -c 'printf "%s\n" \
    "head=$2" "branch=$3" "dirty=$4" "synced_at=$5" \
    "image_source_head=$6" >"$1"' \
  bash "${remote_stage}/.workspace-source" "${source_head}" \
  "${source_branch}" "${source_dirty}" "${synced_at}" \
  "${image_source_head}"

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  bash -c '
    set -eu
    stage=$1
    current=$2
    previous=$3
    test -d "${stage}"
    rm -rf -- "${previous}"
    if test -e "${current}"; then
      mv -- "${current}" "${previous}"
    fi
    if mv -- "${stage}" "${current}"; then
      rm -rf -- "${previous}"
    else
      if test -e "${previous}"; then
        mv -- "${previous}" "${current}"
      fi
      exit 1
    fi
  ' bash "${remote_stage}" "${remote_checkout}" "${remote_previous}"

printf 'context=%s\nnamespace=%s\npod=%s\nimage_source_head=%s\nsource_head=%s\nsource_branch=%s\nsource_dirty=%s\n' \
  "${current_context}" "${namespace}" "${pod_name}" "${image_source_head}" \
  "${source_head}" "${source_branch}" "${source_dirty}"

kubectl exec -n "${namespace}" "${pod_name}" -c "${container_name}" -- \
  bash -c '
    set -e
    checkout=$1
    shift
    cd "${checkout}"
    export PYTHONPATH="${checkout}${PYTHONPATH:+:${PYTHONPATH}}"
    exec "$@"
  ' bash "${remote_checkout}" "$@"
