# Mooncake 1P1D Revoke Ownership Smoke Validation 2026-08-07

## Status And Scope

PASSED. The native-image 1P1D smoke validated cold generation, cache
population, concurrent direct Decode loads, concurrent proxy loads, marker
ownership, token/usage/finish-reason contracts, hit correlation, and cleanup.

## Original Validation

The predecessor is the tracked
[2026-08-04 smoke report](validation-2026-08-04.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Runtime | `liangjiahao`, node `n1`, 1P1D |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Empty-pool baseline | `4/4` | PASSED |
| Warmup | 5 operations | PASSED |
| Direct KV load | `4/4` concurrent | PASSED |
| Proxy KV load | `4/4` concurrent | PASSED |
| Hit correlation | `12/12` | PASSED |
| Isolation | marker/token/usage/finish reason | PASSED |
| Pool arithmetic | exact 64 keys | PASSED |
| Cleanup | engines stopped; Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | rebuilt final image; no overlay |
| Mooncake | new failed-revoke session retention semantics |
| Ownership | pending keys suppress restart until cleanup succeeds |
| Smoke oracles | same marker and hit-correlation hard gates |

## Script Provenance

- Script SHA256: `d4ac22d17a208e10b46be6bca70dfabf5ffca9ec06e25649d46b3045a7b39cd8` for `deployment/run-smoke-test.sh`.
- Runtime `SHA256SUMS` digest: `1e4282da9b074f0accc7b0a8570a6aa6a41fbaaf643827945a8d234c6596681b`.
- Wrapper `SHA256SUMS` digest: `da1787bc9486b36e29fa45d9ca8a80db4deb97cb97525e535a072690e0204977`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-75fd46886-pd67q -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-545854f777-n9sx4 -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/smoke-wrapper/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .gates.case_count == 17 and .gates.hit_correlation_checks == 12 and .gates.marker_isolation == true and .gates.expected_master_key_count == 64 and .gates.master_empty_after_retry == true and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/smoke-wrapper/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/deployment/validation-2026-08-07.md
```

## Attempts And Failures

All 17 runtime cases passed. The immediate metrics read after cleanup raced the
new Master endpoint and failed once after the rollout itself succeeded. The
wrapper's 60-second retry captured `0/0/0`; this was classified as an
endpoint-read race, not a source or runtime semantic failure.

## Limitations And Final State

Smoke covers four concurrent requests in a 1P1D single-group topology. Broader
DP/TP and context coverage is in stress. FabricMem, A3, multi-group, and
throughput are not claimed. Engines are stopped and Master is empty.
