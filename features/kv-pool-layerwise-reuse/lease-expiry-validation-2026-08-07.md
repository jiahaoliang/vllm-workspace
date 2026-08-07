# Mooncake Lease Expiry Revoke Ownership Validation 2026-08-07

## Status And Scope

PASSED. The direct A2 test crossed the live 30 second Mooncake lease boundary
during put and get phases, observed exact stale-session result `-707`, recovered
through a fresh session, verified two-layer bytes, and returned the Master to
`0/0/0` on the exact native image.

## Original Validation

The predecessor is the tracked
[2026-08-04 lease report](lease-expiry-validation-2026-08-04.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Config ID | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Lease | `30000ms` plus `1500ms` margin |
| Runtime | `liangjiahao`, node `n1`, Ascend910B4 |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Initial Master | `0/0/0` | PASSED |
| Put wait | `31500.128ms` | PASSED |
| Get wait | `31500.090ms` | PASSED |
| Stale ranged read | exact `[-707]` | PASSED |
| Fresh session | start `[0]`; exact two-layer recovery | PASSED |
| Cleanup | before-reset and after-reset `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | rebuilt image at final vLLM-Ascend SHA |
| Python overlay | disabled |
| Revoke ownership | failed cleanup remains locally owned and pending |
| Lease contract | unchanged at live 30 second TTL |

## Script Provenance

- Script SHA256: `8de8030fd0566c71aad5fd2f8f02c5d5f4eda2e9a8eeb701e6ab5296c3468875` for `deployment/lease-expiry-test.py`.
- Family `SHA256SUMS` digest: `6d284a6276915771c56f9fd625908c34012d61a1a6170a8f6a4a53d6e7552223`.
- Runtime tooling commit: `3bda70d786db46310994afc689af4fc10da4858e`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-75fd46886-pd67q -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260807T100722Z/lease-expiry-test.py --output /tmp/full-validation-direct-20260807T100722Z/lease-summary.json --lease-ttl-ms 30000 --wait-margin-ms 1500 --page-size 4096
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/lease/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .gates.live_lease_ttl_ms == 30000 and .gates.stale_get_result == [-707] and .gates.fresh_get_byte_equality == true and .gates.master_empty_after_reset == true and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/lease/family-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/lease-expiry-validation-2026-08-07.md
```

## Attempts And Failures

The final lease family had no semantic, production-source, tooling, or
infrastructure failure. Both configured waits exceeded the live TTL plus the
frozen margin, and cleanup completed before the next gate.

## Limitations And Final State

One configured TTL and the single-group Mooncake backend were tested. The run
does not characterize other TTLs, FabricMem, multi-group sessions, or
throughput. Final Master metrics were `0/0/0`.
