#!/usr/bin/env bash
set -euo pipefail

for role in prefill decode; do
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    touch /tmp/direct-sampler.stop
done
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  touch /tmp/direct-sampler.stop

