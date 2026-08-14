#!/usr/bin/env bash
set -euo pipefail

for role in prefill decode; do
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    /bin/bash --noprofile --norc -lc \
    "if [[ -s /tmp/vllm-${role}.pid ]]; then kill \$(cat /tmp/vllm-${role}.pid) 2>/dev/null || true; fi"
done

deadline=$((SECONDS + 180))
for role in prefill decode; do
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  while kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    /bin/bash --noprofile --norc -lc \
    "[[ -s /tmp/vllm-${role}.pid ]] && pid=\$(cat /tmp/vllm-${role}.pid) && kill -0 \${pid} 2>/dev/null && [[ \$(ps -o stat= -p \${pid}) != Z* ]]"; do
    if (( SECONDS >= deadline )); then
      kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
        /bin/bash --noprofile --norc -lc \
        "kill -9 \$(cat /tmp/vllm-${role}.pid) 2>/dev/null || true"
      break
    fi
    sleep 5
  done
done
