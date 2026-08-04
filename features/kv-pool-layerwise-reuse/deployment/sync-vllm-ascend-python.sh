#!/usr/bin/env bash
set -euo pipefail

readonly BASE_COMMIT="14beaf161cca6f1e044e20529ca96c6554dbbe50"
readonly SOURCE_COMMIT="d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873"
readonly EXPECTED_IMAGE="docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1"
readonly NAMESPACE="liangjiahao"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly WORKSPACE_ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
readonly SOURCE_REPO="${WORKSPACE_ROOT}/repos/vllm-ascend"
readonly CONTAINER_SOURCE="/vllm-workspace/vllm-ascend"

if [[ "${NAMESPACE}" != liangjiahao ]]; then
  echo "refusing to sync outside the liangjiahao namespace" >&2
  exit 2
fi
kubectl get namespace -n "${NAMESPACE}" "${NAMESPACE}" >/dev/null

git -C "${SOURCE_REPO}" cat-file -e "${BASE_COMMIT}^{commit}"
if [[ $(git -C "${SOURCE_REPO}" rev-parse HEAD) != "${SOURCE_COMMIT}" || \
      -n $(git -C "${SOURCE_REPO}" status --porcelain=v1) ]]; then
  echo "source must be clean at ${SOURCE_COMMIT}" >&2
  exit 1
fi

mapfile -t unsupported < <(
  {
    git -C "${SOURCE_REPO}" diff --name-only "${BASE_COMMIT}" -- \
      CMakeLists.txt cmake csrc pyproject.toml setup.py requirements
    git -C "${SOURCE_REPO}" ls-files --others --exclude-standard -- \
      CMakeLists.txt cmake csrc pyproject.toml setup.py requirements
  } | sort -u
)
if (( ${#unsupported[@]} > 0 )); then
  printf 'native/build/dependency changes require an image rebuild:\n' >&2
  printf '  %s\n' "${unsupported[@]}" >&2
  exit 1
fi

mapfile -t changed < <(
  {
    git -C "${SOURCE_REPO}" diff --name-only --diff-filter=ACMRT "${BASE_COMMIT}" -- vllm_ascend
    git -C "${SOURCE_REPO}" ls-files --others --exclude-standard -- vllm_ascend
  } | sort -u
)
mapfile -t deleted < <(
  git -C "${SOURCE_REPO}" diff --name-only --diff-filter=D \
    "${BASE_COMMIT}" -- vllm_ascend | LC_ALL=C sort
)

expected_changed=(
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py
  vllm_ascend/envs.py
)
if [[ "${changed[*]}" != "${expected_changed[*]}" || ${#deleted[@]} -ne 0 ]]; then
  echo "Python overlay does not match the frozen ${BASE_COMMIT}..${SOURCE_COMMIT} contract" >&2
  printf 'changed: %s\n' "${changed[*]}" >&2
  printf 'deleted: %s\n' "${deleted[*]}" >&2
  exit 1
fi

if (( ${#changed[@]} == 0 && ${#deleted[@]} == 0 )); then
  echo "no vllm_ascend package changes relative to ${BASE_COMMIT}"
  exit 0
fi

for path in "${changed[@]}" "${deleted[@]}"; do
  if [[ "${path}" != vllm_ascend/* || "${path}" == *".."* ]]; then
    echo "refusing unsafe sync path: ${path}" >&2
    exit 1
  fi
done

for role in prefill decode; do
  mapfile -t pods < <(
    kubectl get pods -n "${NAMESPACE}" -l "app=${role}" \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
  )
  if (( ${#pods[@]} != 1 )); then
    echo "expected exactly one ${role} pod, found ${#pods[@]}" >&2
    exit 1
  fi

  pod="${pods[0]}"
  actual_image=$(kubectl get pod -n "${NAMESPACE}" "${pod}" -o jsonpath='{.spec.containers[0].image}')
  if [[ ${actual_image} != "${EXPECTED_IMAGE}" ]]; then
    echo "refusing source sync into ${pod}: expected ${EXPECTED_IMAGE}, got ${actual_image}" >&2
    exit 1
  fi
  kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
    /opt/vllm-layerwise/stop-engine.sh "${role}"

  if (( ${#changed[@]} > 0 )); then
    mapfile -t destination_dirs < <(
      printf '%s\n' "${changed[@]}" | sed 's#/[^/]*$##' | \
        sed "s#^#${CONTAINER_SOURCE}/#" | sort -u
    )
    kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
      mkdir -p "${destination_dirs[@]}"
    tar -C "${SOURCE_REPO}" -cf - "${changed[@]}" | \
      kubectl exec -i -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
        tar -C "${CONTAINER_SOURCE}" -xf -
  fi

  for path in "${deleted[@]}"; do
    kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
      rm -f -- "${CONTAINER_SOURCE}/${path}"
  done

  kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
    env PYTHONDONTWRITEBYTECODE=1 python3 -c \
      'import pathlib,sys; root=pathlib.Path(sys.argv[1]); [compile((root/path).read_text(), str(root/path), "exec") for path in sys.argv[2:]]' \
      "${CONTAINER_SOURCE}" "${changed[@]}"
  for path in "${changed[@]}"; do
    host_checksum=$(sha256sum "${SOURCE_REPO}/${path}" | awk '{print $1}')
    pod_checksum=$(
      kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
        sha256sum "${CONTAINER_SOURCE}/${path}" | awk '{print $1}'
    )
    if [[ ${pod_checksum} != "${host_checksum}" ]]; then
      echo "checksum mismatch for ${role} ${path}: host=${host_checksum} pod=${pod_checksum}" >&2
      exit 1
    fi
  done
  echo "synced ${role} pod ${pod} to ${SOURCE_COMMIT}; vLLM remains stopped"
done

echo "start the two vLLM processes manually after reviewing the synced files"
