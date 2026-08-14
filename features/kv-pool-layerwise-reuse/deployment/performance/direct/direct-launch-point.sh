#!/usr/bin/env bash
set -euo pipefail

variant=$1
max_num_seqs=$2
threshold=$3

for role in prefill decode; do
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    /bin/bash -lc \
    "rm -f /tmp/vllm-${role}.log /tmp/vllm-${role}.pid; nohup bash /tmp/direct-start-vllm.sh '${role}' '${variant}' '${max_num_seqs}' '${threshold}' > /tmp/vllm-${role}.log 2>&1 & echo \$! > /tmp/vllm-${role}.pid"
done

