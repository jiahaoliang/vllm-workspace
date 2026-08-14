# Direct Four-Point Helpers

These files are the byte-identical helper scripts used for the 2026-08-14
REUSE3 lightweight four-point run. They are an auditable run snapshot, not a
replacement for the maintained performance runner.

Run host-side helpers from the workspace root. Before launching a point, copy
`direct-start-vllm.sh` into both sleep-style serving Pods because
`direct-launch-point.sh` executes it at `/tmp/direct-start-vllm.sh` inside each
Pod:

```bash
DIRECT_DIR=features/kv-pool-layerwise-reuse/deployment/performance/direct
PREFILL_POD=$(kubectl get pod -n liangjiahao -l app=prefill \
  --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
DECODE_POD=$(kubectl get pod -n liangjiahao -l app=decode \
  --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

kubectl cp -n liangjiahao -c prefill-engine \
  "${DIRECT_DIR}/direct-start-vllm.sh" \
  "${PREFILL_POD}:/tmp/direct-start-vllm.sh"
kubectl cp -n liangjiahao -c decode-engine \
  "${DIRECT_DIR}/direct-start-vllm.sh" \
  "${DECODE_POD}:/tmp/direct-start-vllm.sh"
```

Verify the archived snapshot with:

```bash
(cd features/kv-pool-layerwise-reuse/deployment/performance/direct && \
  sha256sum -c SHA256SUMS)
```
