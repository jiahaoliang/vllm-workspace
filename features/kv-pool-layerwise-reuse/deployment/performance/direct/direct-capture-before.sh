#!/usr/bin/env bash
set -euo pipefail
point=$1
root=${DIRECT_EVIDENCE_ROOT:-/tmp/layerwise-issue1-direct-20260814-rerun}/${point}
mkdir -p "${root}"
for role in prefill decode; do
  kubectl exec -n liangjiahao deploy/${role}-engine-deployment -c ${role}-engine -- \
    stat -c %s /tmp/vllm-${role}.log >"${root}/${role}-formal-start-offset.txt"
  kubectl exec -n liangjiahao deploy/${role}-engine-deployment -c ${role}-engine -- \
    sh -c 'tr "\0" " " </proc/$(cat /tmp/vllm-'${role}'.pid)/cmdline' \
    >"${root}/${role}-argv.txt"
done
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs /bin/bash -lc \
  'python - <<"PY"
from urllib.request import urlopen
for path in ("metrics", "metrics/summary"):
    print(f"### {path}")
    print(urlopen(f"http://mooncake-master-service:9003/{path}", timeout=10).read().decode())
PY' >"${root}/mooncake-before.metrics"
kubectl exec -n liangjiahao deploy/prefill-engine-deployment -c prefill-engine -- npu-smi info \
  >"${root}/npu-before.txt" 2>&1 || true
