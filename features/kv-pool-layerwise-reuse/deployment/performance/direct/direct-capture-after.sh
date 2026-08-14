#!/usr/bin/env bash
set -euo pipefail
point=$1
root=${DIRECT_EVIDENCE_ROOT:-/tmp/layerwise-issue1-direct-20260814-rerun}/${point}
for role in prefill decode; do
  pod=$(kubectl get pod -n liangjiahao -l "app=${role}" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n liangjiahao deploy/${role}-engine-deployment -c ${role}-engine -- \
    cat /tmp/vllm-${role}.log >"${root}/${role}-full.log"
  kubectl cp -n liangjiahao -c ${role}-engine \
    ${pod}:/tmp/${role}-prometheus.log \
    "${root}/${role}-prometheus.log"
  kubectl cp -n liangjiahao -c ${role}-engine \
    ${pod}:/tmp/${role}-npu-timeseries.log \
    "${root}/${role}-npu-timeseries.log"
done
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs /bin/bash -lc \
  'python - <<"PY"
from urllib.request import urlopen
for path in ("metrics", "metrics/summary"):
    print(f"### {path}")
    print(urlopen(f"http://mooncake-master-service:9003/{path}", timeout=10).read().decode())
PY' >"${root}/mooncake-after.metrics"
kubectl exec -n liangjiahao deploy/prefill-engine-deployment -c prefill-engine -- npu-smi info \
  >"${root}/npu-after.txt" 2>&1 || true
kubectl cp -n liangjiahao -c aisbench \
  layerwise-performance-aisbench:/performance-workspace/rootfs/client-tools/direct-runs/${point}/formal-1 \
  "${root}/aisbench-formal"
kubectl cp -n liangjiahao -c aisbench \
  layerwise-performance-aisbench:/tmp/mooncake-timeseries.log \
  "${root}/mooncake-timeseries.log"
