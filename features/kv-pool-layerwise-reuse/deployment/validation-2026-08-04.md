# Mooncake 1P1D Smoke Single-Group Validation 2026-08-04

## Status And Scope

PASSED. The four-request 1P1D smoke validates cold generation, cache
population, concurrent direct Decode loads, concurrent proxy loads, marker
ownership, token/usage contracts, and per-response cache-hit correlation on
the unchanged image plus five-file Python overlay.

## Original Validation

The baseline is the tracked
[2026-08-03 smoke report](validation-2026-08-03.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image/final vLLM-Ascend | `14beaf161` / `d5f0ea7f8` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| Runtime | `liangjiahao`, node `n1`, 1P1D |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Empty baseline | 4/4 isolated responses | PASSED |
| Warmup | 5 operations | PASSED |
| Direct KV load | 4/4 concurrent responses | PASSED |
| Proxy KV load | 4/4 concurrent responses | PASSED |
| Master arithmetic | exact 64 keys | PASSED |
| Hit correlation | 12/12 | PASSED |
| Cleanup | engines stopped; Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | five-file overlay at `d5f0ea7f8` |
| Request isolation | immutable rows and request-local failures |
| Marker/token oracles | unchanged |
| Multi-group | deferred and unsupported in this claim |

## Script Provenance

- Script SHA256: `2cc5a9b18235e475346ecb3198815506f661ce9b530c198f216a7a306b8c7703` for `deployment/run-smoke-test.sh`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-85f47466d6-6wn8r -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .diagnosis == "passed" and (.phases.empty_pool_baseline.cases | length) == 4 and (.phases.warmup.cases | length) == 5 and (.phases.direct_kv_load.cases | length) == 4 and (.phases.proxy_kv_load.cases | length) == 4' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/smoke/concurrent-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/deployment/validation-2026-08-04.md
```

## Attempts And Failures

The final smoke family passed on the first run for corrected source
`d5f0ea7f8`. No production source changed during runtime validation.

## Limitations And Final State

Smoke covers four concurrent requests and single-group Mooncake only. Broader
DP/TP and context coverage is in stress. Engines are stopped and Master is
empty.
