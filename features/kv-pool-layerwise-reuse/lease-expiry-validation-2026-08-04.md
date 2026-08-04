# Mooncake Lease Expiry Single-Group Validation 2026-08-04

## Status And Scope

PASSED. The direct NPU test validates a slow two-layer put across the live
lease TTL, exact stale-session error `-707`, fresh-session recovery, exact
bytes, removal, and empty cleanup on the five-file overlay.

## Original Validation

The baseline is the tracked
[2026-08-03 lease report](lease-expiry-validation-2026-08-03.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay | `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Lease | 30,000 ms plus 1,500 ms margin |
| Runtime | `liangjiahao`, node `n1` |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Initial Master | `0/0/0` | PASSED |
| Slow put gap | at least 31.5 s | PASSED |
| Two ranged layers | both 4096 bytes and commit 0 | PASSED |
| Stale read | exact `-707` | PASSED |
| Fresh session | start 0 and exact recovery | PASSED |
| Cleanup | final `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Lease contract | unchanged |
| Overlay | expanded to five reviewed single-group Python files |
| Result audit | centralized emitter preserves the prior JSON contract |
| Multi-group | deferred and not claimed |

## Script Provenance

- Script SHA256: `8de8030fd0566c71aad5fd2f8f02c5d5f4eda2e9a8eeb701e6ab5296c3468875` for `deployment/lease-expiry-test.py`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260804T103209Z/lease-expiry-test.py --output /tmp/full-validation-direct-20260804T103209Z/lease-summary.json --lease-ttl-ms 30000 --wait-margin-ms 1500 --page-size 4096
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.passed == true and .semantic_result.expired_session_error_code == -707 and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/lease/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/lease-expiry-validation-2026-08-04.md
```

## Attempts And Failures

The final lease family passed without a semantic failure. A later G4 readiness
attempt exposed only a premature metrics read and did not invalidate lease
results.

## Limitations And Final State

One configured TTL boundary was tested. This does not characterize other TTLs
or Mooncake multi-group sessions. Final Master metrics are `0/0/0`.
