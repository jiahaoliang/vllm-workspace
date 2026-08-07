#!/usr/bin/env bash
set -euo pipefail

readonly VLLM_COMMIT="54503ecec0f3ac31e5ecfc5f28652e4cc42307b5"
readonly IMAGE_SOURCE_COMMIT="45b2e785b10ca4604cd6314819ed15f3ff674781"
readonly SOURCE_COMMIT="45b2e785b10ca4604cd6314819ed15f3ff674781"
readonly MOONCAKE_COMMIT="df3f74ed8ebdb0c935554beea6299a9f11c723e2"
readonly EXPECTED_IMAGE="docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z"
readonly NAMESPACE="liangjiahao"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly WORKSPACE_ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
readonly SOURCE_REPO="${WORKSPACE_ROOT}/repos/vllm-ascend"

if [[ "${NAMESPACE}" != liangjiahao ]]; then
  echo "refusing to verify outside the liangjiahao namespace" >&2
  exit 2
fi
kubectl get namespace -n "${NAMESPACE}" "${NAMESPACE}" >/dev/null

if [[ $(git -C "${SOURCE_REPO}" rev-parse HEAD) != "${SOURCE_COMMIT}" || \
      -n $(git -C "${SOURCE_REPO}" status --porcelain=v1) ]]; then
  echo "source must be clean at ${SOURCE_COMMIT}" >&2
  exit 1
fi
if [[ ${IMAGE_SOURCE_COMMIT} != "${SOURCE_COMMIT}" ]]; then
  echo "Python overlay is disabled: image and source commits must match" >&2
  exit 1
fi

expected_changed=(
)
mapfile -t changed < <(
  git -C "${SOURCE_REPO}" diff --name-only "${IMAGE_SOURCE_COMMIT}" -- vllm_ascend
)
if [[ "${changed[*]}" != "${expected_changed[*]}" ]]; then
  printf 'native image source has an unexpected overlay: %s\n' "${changed[*]}" >&2
  exit 1
fi

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
    echo "native image mismatch for ${pod}: expected ${EXPECTED_IMAGE}, got ${actual_image}" >&2
    exit 1
  fi
  for component in \
    "vllm:${VLLM_COMMIT}" \
    "vllm-ascend:${SOURCE_COMMIT}" \
    "Mooncake:${MOONCAKE_COMMIT}"; do
    repo=${component%%:*}
    expected=${component#*:}
    actual=$(kubectl exec -n "${NAMESPACE}" "${pod}" -c "${role}-engine" -- \
      git -C "/vllm-workspace/${repo}" rev-parse HEAD)
    if [[ ${actual} != "${expected}" ]]; then
      echo "${role} ${repo} source mismatch: expected ${expected}, got ${actual}" >&2
      exit 1
    fi
  done
done

echo "native image source identity passed; Python overlay is disabled"
