#!/usr/bin/env bash
set -euo pipefail

deadline=$((SECONDS + 900))
for role in prefill decode; do
  if [[ ${role} == prefill ]]; then
    port=8100
  else
    port=8200
  fi
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  while ! kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    /bin/bash --noprofile --norc -lc \
    "kill -0 \$(cat /tmp/vllm-${role}.pid) && curl -fsS http://127.0.0.1:${port}/health >/dev/null"; do
    if (( SECONDS >= deadline )); then
      kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
        tail -200 "/tmp/vllm-${role}.log"
      exit 124
    fi
    sleep 5
  done
done
