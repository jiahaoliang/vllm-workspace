# Mooncake G4 Range Audit Single-Group Validation 2026-08-04

## Status And Scope

PASSED. One clean 1P1D proxy request audited ranged save/load activity for all
27 physical layers, ordered final commit, response usage, and zero whole-key
fallback on the frozen single-group overlay.

## Original Validation

The baseline is the tracked
[2026-08-03 G4 report](ranged-api-g4-validation-2026-08-03.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image/final vLLM-Ascend | `14beaf161` / `d5f0ea7f8` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Model | 27 layers, block size 128 |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Debug inheritance | Prefill and Decode enabled | PASSED |
| Prefill ranges | save layers exactly `0..26` | PASSED |
| Commit | one ordered final commit | PASSED |
| Decode ranges | load layers exactly `0..26` | PASSED |
| Result contract | all aligned results nonnegative | PASSED |
| Whole-key path | zero events | PASSED |
| Final isolation | engines stopped; Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Audit implementation | shared best-effort `range_debug.py` emitter |
| Save hot path | consumes immutable rows directly |
| Success codes | zero and positive values accepted |
| Multi-group | excluded from implementation and claim |

## Script Provenance

- Script SHA256: `6d191a7ea135d27beb2a3d8eef82871da20ba819e9df0541e431114858eb56b6` for `deployment/check-range-debug-log.py`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-85f47466d6-6wn8r -c decode-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-decode.sh
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-g4-20260804T103209Z/run-request.py
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.status == "passed" and .prefill.range_event_count == 27 and .decode.range_event_count == 27' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/g4/range-debug-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/ranged-api-g4-validation-2026-08-04.md
```

## Attempts And Failures

Three tooling attempts were preserved locally: audit mode was initially absent,
one driver used Python 3.10 `zip(strict=True)` on Python 3.9, and one readiness
check read Master metrics too early. Focused fixes were applied to tooling only;
the final G4 family reran in full and passed.

## Limitations And Final State

G4 covers one clean request; concurrency is covered by smoke and stress. It is
an overlay claim and excludes §5.8. Engines are stopped and Master is empty.
