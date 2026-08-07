# Mooncake G4 Scatter Range Audit Validation 2026-08-07

## Status And Scope

PASSED. A clean 1P1D request on the rebuilt image audited all 27 Prefill save
layers, all 27 Decode load layers, two fragments per key, per-key byte results,
ordered final commit, Decode hit correlation, and zero whole-key fallback.

## Original Validation

The predecessor is the tracked
[2026-08-04 G4 report](ranged-api-g4-validation-2026-08-04.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Config ID | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Model | DeepSeek-V2-Lite-W8A8, 27 layers |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Prefill scatter | layers `0..26`, 27 events | PASSED |
| Decode scatter | layers `0..26`, 27 events | PASSED |
| Per-key bytes | each `147456 == 131072 + 16384` | PASSED |
| Commit | `[0,0,0,0]` after final save | PASSED |
| Decode hit | `512/512` tokens | PASSED |
| Whole-key path | zero calls | PASSED |
| Final isolation | engines stopped; Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | exact final native image instead of overlay |
| Mooncake path | scatter API from frozen `df3f74ed` |
| Byte oracle | validates per-key two-fragment result arithmetic |
| Ownership | final commit and cleanup retain fail-closed semantics |

## Script Provenance

- Script SHA256: `6d191a7ea135d27beb2a3d8eef82871da20ba819e9df0541e431114858eb56b6` for `deployment/check-range-debug-log.py`.
- Family `SHA256SUMS` digest: `ddf6ee52f57568ef74dc63c9b2deb015387e495195b310ac6189f745b5c34020`.
- Runtime tooling commit: `3bda70d786db46310994afc689af4fc10da4858e`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-75fd46886-pd67q -c prefill-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-545854f777-n9sx4 -c decode-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-decode.sh
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/g4/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .num_layers == 27 and .prefill_range_events == 27 and .decode_range_events == 27 and .per_key_byte_equality == true and .whole_key_calls == 0 and .decode_hit_tokens == 512 and .master_empty == true and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/g4/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/ranged-api-g4-validation-2026-08-07.md
```

## Attempts And Failures

Attempt 1 completed the runtime request and range checker, but an
evidence-local assertion rejected the valid extra response field
`usage.prompt_tokens_details: null`. Failure cleanup stopped both engines and
reset the Master to `0/0/0`. The corrected validator replayed the captured
response, and the complete G4 runtime then reran from the start and passed.

## Limitations And Final State

G4 covers one clean request on the single-group A2 path. Concurrency is covered
by smoke and stress; FabricMem, A3, multi-group, and throughput are not claimed.
Both engines were stopped and the final Master was empty.
