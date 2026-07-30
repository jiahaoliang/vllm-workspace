#!/usr/bin/env bash
set -euo pipefail

readonly BASE_COMMIT="14beaf161cca6f1e044e20529ca96c6554dbbe50"
readonly EXPECTED_IMAGE="docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z-r3"
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
  git -C "${SOURCE_REPO}" diff --name-only --diff-filter=D "${BASE_COMMIT}" -- vllm_ascend
)

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
    tar -C "${SOURCE_REPO}" -cf - "${changed[@]}" | \
      kubectl exec -i -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
        tar -C "${CONTAINER_SOURCE}" -xf -
  fi

  for path in "${deleted[@]}"; do
    kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
      rm -f -- "${CONTAINER_SOURCE}/${path}"
  done

  kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
    python3 -m compileall -q "${CONTAINER_SOURCE}/vllm_ascend"
  echo "synced ${role} pod ${pod}; vLLM remains stopped"
done

echo "start the two vLLM processes manually after reviewing the synced files"
