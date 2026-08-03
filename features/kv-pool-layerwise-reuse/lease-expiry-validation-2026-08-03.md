# Mooncake Lease Expiry Overlay Validation 2026-08-03

## Status And Scope

PASSED. The direct NPU test validates a slow two-layer put across the live read
lease TTL, stale read-session expiry with exact code `-707`, fresh-session
recovery, exact data, object removal, and empty cleanup on the Python overlay.

## Original Validation

The baseline is the tracked
[2026-07-27 lease report](lease-expiry-validation-2026-07-27.md). The API
sequence and semantic contract are unchanged; this run repeats them against the
post-smoke source fix.

## Identity

| Item | Value |
| --- | --- |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Live lease | 30,000 ms with 1,500 ms margin |
| Kubernetes | `liangjiahao`, Prefill NPU Pod on `n1` |

## Gate Results

| Gate | Expected | Actual | Exit | Result |
| --- | --- | --- | --- | --- |
| Initial pool | keys/bytes/clients `0/0/0` | `0/0/0` | 0 | PASSED |
| Put gap | elapsed at least 30,000 ms | 31,500.155 ms | 0 | PASSED |
| Slow put | both 4096-byte layers commit | 2/2 and commit 0 | 0 | PASSED |
| Read gap | elapsed at least 30,000 ms | 31,500.084 ms | 0 | PASSED |
| Stale read | exact `-707` | `-707` | 0 | PASSED |
| Fresh session | start 0 and recover layer 1 | 0 and 4096 bytes | 0 | PASSED |
| Data oracle | full two-layer bytes equal | equal | 0 | PASSED |
| Cleanup | keys/bytes/clients `0/0/0` | `0/0/0` | 0 | PASSED |

Evidence: [lease summary](evidence/full-validation-rerun-20260803T124415Z/lease/summary.json),
[driver log](evidence/full-validation-rerun-20260803T124415Z/lease/lease-expiry.log),
and [cleanup metrics](evidence/full-validation-rerun-20260803T124415Z/lease/master-final.metrics).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Lease TTL and margin | Unchanged |
| `LEASE_EXPIRED` code | Unchanged at `-707` |
| Session API order | Unchanged |
| Image/native state | Unchanged |
| Python package state | Explicit two-file overlay at `d28c52958` |
| Evidence reset read | Added accounting for one post-rollout endpoint race |

## Script Provenance

- Runtime script revision: `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Script SHA256 for `deployment/lease-expiry-test.py`: `8de8030fd0566c71aad5fd2f8f02c5d5f4eda2e9a8eeb701e6ab5296c3468875`.
- Lease `SHA256SUMS` digest:
  `a02bf3df8826985c3f006e36abd371c2fa99cfe02e7258e260032bead4530f14`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260803T124415Z/lease-expiry-test.py --output /tmp/full-validation-direct-20260803T124415Z/lease-summary.json --lease-ttl-ms 30000 --wait-margin-ms 1500 --page-size 4096
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- python3 -c 'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics",timeout=10).read().decode(),end="")'
```

The complete sequence is in the
[lease transcript](evidence/full-validation-rerun-20260803T124415Z/lease/command-transcript.log).

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/lease && sha256sum -c SHA256SUMS)
jq -e '.passed == true and .semantic_result.expired_session_error_code == -707 and .semantic_result.fresh_batch_get_session_start_after_expiry_finds_object == true and (.errors|length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/lease/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/lease/summary.json
```

## Attempts And Failures

The semantic driver and its cleanup passed on the first attempt. After an
independent Master restart, the first immediate metrics read saw one
`ConnectionRefused` while the new service endpoint was starting. The same reset
was later captured at the G4 preflight with zero keys, bytes, and clients; that
replacement assertion is recorded in `reset-recovery-assert.log`. No source
change or lease rerun was needed.

## Limitations And Final State

This is an overlay claim, not a rebuilt-image claim. The lease duration is a
single configured 30-second boundary and does not characterize other TTLs.
Final vLLM child processes are stopped, the retained Master is empty, and the
stress Pods remain allocated but idle.
