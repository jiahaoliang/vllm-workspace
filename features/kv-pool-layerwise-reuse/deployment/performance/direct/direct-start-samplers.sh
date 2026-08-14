#!/usr/bin/env bash
set -euo pipefail

for role in prefill decode; do
  if [[ ${role} == prefill ]]; then
    port=8100
  else
    port=8200
  fi
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n liangjiahao "${pod}" -c "${role}-engine" -- \
    /bin/bash --noprofile --norc -lc \
    "rm -f /tmp/direct-sampler.stop /tmp/${role}-prometheus.log /tmp/${role}-npu-timeseries.log; nohup /bin/bash --noprofile --norc -c 'while [[ ! -e /tmp/direct-sampler.stop ]]; do date -Ins; curl -fsS http://127.0.0.1:${port}/metrics || true; sleep 1; done' > /tmp/${role}-prometheus.log 2>&1 & nohup /bin/bash --noprofile --norc -c 'while [[ ! -e /tmp/direct-sampler.stop ]]; do date -Ins; npu-smi info || true; sleep 10; done' > /tmp/${role}-npu-timeseries.log 2>&1 &"
done

kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  /bin/bash --noprofile --norc -lc \
  "rm -f /tmp/direct-sampler.stop /tmp/mooncake-timeseries.log; nohup /bin/bash --noprofile --norc -c 'while [[ ! -e /tmp/direct-sampler.stop ]]; do date -Ins; curl -fsS http://mooncake-master-service:9003/metrics || true; curl -fsS http://mooncake-master-service:9003/metrics/summary || true; sleep 1; done' > /tmp/mooncake-timeseries.log 2>&1 &"

