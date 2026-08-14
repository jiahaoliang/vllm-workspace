#!/usr/bin/env bash
set -euo pipefail

point=$1
variant=$2
concurrency=$3
output_tokens=$4
phase=$5
request_count=$6
fixture_concurrency=$7

namespace=liangjiahao
pod=layerwise-performance-aisbench
rootfs=/performance-workspace/rootfs
run_dir=/client-tools/direct-runs/${point}/${phase}
fixture=/client-tools/fixtures/tokens-32000-c${fixture_concurrency}

case ${phase} in
  warmup) source_name=warmup.jsonl ;;
  seed) source_name=seed.jsonl ;;
  admission) source_name=admission.jsonl ;;
  formal-1) source_name=formal-1.jsonl ;;
  *) echo "unsupported phase: ${phase}" >&2; exit 2 ;;
esac

kubectl exec -n "${namespace}" "${pod}" -c aisbench -- \
  chroot "${rootfs}" /bin/bash -lc \
  "rm -rf '${run_dir}' && mkdir -p '${run_dir}' && cp '${fixture}/${source_name}' '${run_dir}/dataset.jsonl'"

input_tokens=32000
config_output_tokens=${output_tokens}
if [[ ${phase} == seed ]]; then
  config_output_tokens=1
elif [[ ${phase} == admission ]]; then
  config_output_tokens=1
fi

kubectl exec -n "${namespace}" "${pod}" -c aisbench -- \
  chroot "${rootfs}" env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/client-tools/tooling /client-tools/venv/bin/python \
  -m performance.fixtures config \
  --topology dp1 \
  --input-tokens "${input_tokens}" \
  --output-tokens "${config_output_tokens}" \
  --variant "${variant}" \
  --concurrency "${concurrency}" \
  --dataset "${run_dir}/dataset.jsonl" \
  --request-count "${request_count}" \
  --phase "${phase}" \
  --fixture-manifest "${fixture}/manifest.json" \
  --output "${run_dir}/config.py"

if [[ ${phase} == seed ]]; then
  kubectl exec -n "${namespace}" "${pod}" -c aisbench -- \
    chroot "${rootfs}" /bin/bash -lc \
    "cp '${fixture}/seed.jsonl' '${run_dir}/dataset.jsonl'"
fi

kubectl exec -n "${namespace}" "${pod}" -c aisbench -- \
  chroot "${rootfs}" env TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
  PYTHONDONTWRITEBYTECODE=1 /client-tools/venv/bin/ais_bench \
  -m perf --num-warmups 0 "${run_dir}/config.py"

deadline=$((SECONDS + 1200))
while true; do
  completed=$(kubectl exec -n "${namespace}" "${pod}" -c aisbench -- sh -c \
    "file=\$(find '${rootfs}${run_dir}/aisbench-output' -name '*_details.jsonl' -type f -print -quit); test -n \"\$file\" && test \"\$(wc -l <\"\$file\")\" -eq '${request_count}' && echo yes" || true)
  [[ ${completed} == yes ]] && break
  if (( SECONDS >= deadline )); then
    echo "AISBench phase timed out: ${point}/${phase}" >&2
    exit 124
  fi
  sleep 5
done
