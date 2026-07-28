# Multi-DP/TP Stress Deployment

This profile replaces the existing engine Pods with one Prefill Pod using local
`DP=2, TP=2` (4 Ascend910 NPUs) and one Decode Pod using `DP=1, TP=2` (2 NPUs).
Node `n1` must therefore have 6 allocatable NPUs after excluding the two engine
Deployments being replaced.

Apply in this order:

```bash
readonly namespace=liangjiahao
test "${namespace}" = liangjiahao
kubectl get namespace "${namespace}"
kubectl apply -n "${namespace}" -f 10-runtime-config.yaml
kubectl apply -n "${namespace}" -f 40-prefill-engine.yaml
kubectl apply -n "${namespace}" -f 50-decode-engine.yaml
```

Applying the two Deployments recreates the old 1+1-card engine Pods once. Their
container PID 1 remains `sleep infinity`; start and stop vLLM manually:

```bash
PREFILL_POD=$(kubectl get pod -n liangjiahao -l app=prefill -o jsonpath='{.items[0].metadata.name}')
DECODE_POD=$(kubectl get pod -n liangjiahao -l app=decode -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n liangjiahao "$PREFILL_POD" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao "$DECODE_POD" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl exec -n liangjiahao "$PREFILL_POD" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n liangjiahao "$DECODE_POD" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
```

Stopping vLLM does not release the device allocation. The final stress state
retains all 6 NPUs until the base `deployment/40-prefill-engine.yaml` and
`deployment/50-decode-engine.yaml` manifests are deliberately restored.
Restore or delete those exact resources when cleanup is required; do not delete
the `liangjiahao` namespace.
