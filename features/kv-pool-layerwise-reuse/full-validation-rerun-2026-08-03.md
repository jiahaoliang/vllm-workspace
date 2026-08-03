# Mooncake Python Overlay Full Validation Rerun 2026-08-03

## Status And Scope

PASSED. The complete CPU/mock, G0, direct ranged G1, lease-expiry, G4 runtime
audit, 1P1D smoke, and stress S1-S3 flow passed for the unchanged native ARM64
image plus the exact user-authorized two-file Python overlay. This result fixes
and supersedes the 2026-07-31 concurrent warm-load failure for this frozen
identity. It is not evidence for an image built at the final source commit.

## Original Validation

The direct predecessor is the tracked
[2026-07-31 failed full validation](full-validation-rerun-2026-07-31.md).
That run passed through G4, then terminated because concurrent warm case 2 lost
its private marker. This rerun preserves the same hard oracles and reruns every
source-dependent gate after the separate source fix.

## Identity

| Item | Frozen value |
| --- | --- |
| Run ID | `20260803T124415Z` |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling commit | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay vLLM-Ascend | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8`, 27 layers |
| Kubernetes | `bke-cluster-admin@bke-cluster`, `liangjiahao`, node `n1` |

Only `config_data.py` and `kv_transfer.py` differ between image source and
final source. The commit range contains no native, build, dependency, or
packaging change. Host, Prefill, Decode, and UT checksums match for both files.

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| T0 tooling | 69 tests before runtime; shell, compile, Ruff, manifests, identity passed | PASSED |
| U0-U2 CPU/mock | dedicated CPU-only Pod; 478 AscendStore and 69 deployment tests | PASSED |
| G0 | original ImageID plus four-way overlay checksums; 1P1D Ready; empty cleanup | PASSED |
| G1 | 3 keys, 4 layers, 40 API calls, 43 cases, 24 negative cases | PASSED |
| Lease | two 31.5 s waits, exact stale `-707`, fresh exact recovery | PASSED |
| G4 | 27 Prefill saves, one ordered commit, 27 Decode loads, zero whole-key calls | PASSED |
| 1P1D smoke | baseline/direct/proxy 4/4; warmup 5/5; 12/12 hit correlations | PASSED |
| S1 | 4/4 pinned 16k cases, both Prefill DP ranks, 508 keys | PASSED |
| S2 | 16/16 concurrent 8k cases, both Prefill DP ranks, 288 keys | PASSED |
| S3 | pinned cold probe plus 4/4 proxy 32k cases, 348 keys | PASSED |
| Runtime ledger | all stress commands | 163/163 PASSED |
| Final state | engines stopped; Master keys/bytes/clients `0/0/0` | PASSED |
| Evidence | 616 files; root checksum replay | PASSED |

Family reports:
[ranged G0/G1](ranged-api-validation-2026-08-03.md),
[lease](lease-expiry-validation-2026-08-03.md),
[G4](ranged-api-g4-validation-2026-08-03.md),
[1P1D smoke](deployment/validation-2026-08-03.md), and
[stress](multi-dp-tp-stress-validation-2026-08-03.md).
The [run evidence index](evidence/full-validation-rerun-20260803T124415Z/README.md)
links every structured summary and checksum family.

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Native image and dependencies | Unchanged |
| Source fix | `d28c52958` records ranged-row request ownership and dispatches one key-major batch per request |
| Regression coverage | Added separate concurrent batches and row-local failure filtering |
| Marker/token/usage oracles | Unchanged |
| Stress scenarios/topology | Unchanged |
| Python bytecode policy | Explicitly disabled in UT and serving processes |
| Capacity evidence | Recorder now projects only resource fields; runtime arithmetic unchanged |

## Script Provenance

- Runtime tooling commit: `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Script SHA256 for the stable validation contract: `7bb73b2a639ca8baf1f8604c4373a9e236c378a62b9e497950d4e3ac70362cc2`.
- Runtime recorder Script SHA256: `79dccb4d2117d79ab637ac5a1e02f4dc6b1cedaa008498a9435cf0aa20eed396`.
- Root `SHA256SUMS` digest:
  `e66b4909df7a3bcf6e870c434f37590aad3927f800dfdfadc1f5c710fc7f4aa5`.

## Live Reproduction Runbook

The dated tracker and family transcripts contain every setup, wait, reset,
request, checker, and finalization command. The top-level entries executed were:

```bash
env PYTHONDONTWRITEBYTECODE=1 features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh tests/ut/distributed/ascend_store
kubectl apply -n liangjiahao -f features/kv-pool-layerwise-reuse/deployment/30-mooncake-master.yaml
env PYTHONDONTWRITEBYTECODE=1 features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke
env PYTHONDONTWRITEBYTECODE=1 features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress
```

G1, lease, and G4 exact Pod commands are reproduced in their family reports.

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z && sha256sum -c SHA256SUMS)
jq -e '.status == "passed" and .validated == true' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke/concurrent-summary.json
jq -e '.status == "passed" and .validated == true and .scenarios.s1_pinned_16k.validated == true and .scenarios.s2_concurrent_16x8k.validated == true and .scenarios.s3_concurrent_4x32k.validated == true' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress/overall-summary.json
jq -e '.validated == true and .engines_stopped == true and .master_empty == true' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/final/final-state.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/SHA256SUMS
```

## Attempts And Failures

The prior run's production failure was reproduced at `20/120` on the unchanged
image and Pod identities. Duplicate-key splitting (`26/120`) and per-call NPU
synchronization (`19/120`) were falsified and reverted. Per-request ranged
dispatch then passed two independent `120/120` loops, focused regression tests,
the complete UT suite, and this formal run.

Tooling/execution corrections were preserved without changing production
source after the formal freeze: an over-escaped UT checksum command; one lease
post-rollout endpoint race superseded by later empty proof; a G4 pre-request
active-client oracle corrected before any request; a smoke offline assertion
corrected from four to five warmups; and the capacity recorder narrowed to
credential-safe resource fields with its regression test. A completion-audit
`pgrep` command later matched itself; a bracketed process pattern confirmed
both retained engines were stopped. None weakened a runtime hard gate.

## Limitations And Final State

This result validates an explicit Python overlay. Native extensions and
dependencies remain those of image source `14beaf161`, so the result must not
be represented as a new image at `d28c52958`. The control evidence is
checksummed and tracked at commit `03d1356`.

The retained Prefill Pod requests four NPUs and the retained Decode Pod requests
two; both containers are Running but their vLLM child processes and HTTP
endpoints are stopped. Master, proxy, and the CPU-only UT Pod remain retained.
Final Master metrics are zero keys, zero allocated bytes, and zero active
clients. A live completion audit confirmed the same Pod UIDs, imageID, source
checksums, node `n1` UID, stopped processes, and empty Master; the Kubernetes
cluster was not reorganized.
