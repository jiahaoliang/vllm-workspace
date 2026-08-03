# Multi-DP/TP Stress Overlay Validation 2026-08-03

## Status And Scope

PASSED. The complete S1-S3 sequence validates Prefill DP2/TP2 plus Decode
DP1/TP2, pinned and proxy cache reuse, medium and long contexts, concurrency,
marker isolation, token/usage contracts, chunk bounds, 27-layer ranged events,
commit order, key arithmetic, and whole-key exclusion.

## Original Validation

The comparison baseline is the tracked
[2026-07-25 stress report](multi-dp-tp-stress-validation-2026-07-25.md). The
scenario definitions remain the same; the current run validates the post-smoke
request-isolation fix and uses a newer main-verified vLLM image lineage.

## Identity

| Item | Value |
| --- | --- |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Topology | Prefill 4 NPUs DP2/TP2; Decode 2 NPUs DP1/TP2 |
| Kubernetes | `liangjiahao`, node `n1` |

## Gate Results

| Gate | Expected | Actual | Exit | Result |
| --- | --- | --- | --- | --- |
| Capacity | at least 6 available NPUs | 7 | 0 | PASSED |
| Topology | Prefill DP2/TP2; Decode DP1/TP2 | all 10 topology checks true | 0 | PASSED |
| S1 pinned 16k | 4 isolated cases, both DP ranks, 508 keys | 4/4, ranks 0/1, 508 | 0 | PASSED |
| S1 chunk/range | at least 16 iterations, max 1024, layers `0..26` | passed | 0 | PASSED |
| S2 concurrent 8k | 16 isolated cases, both DP ranks, 288 keys | 16/16, ranks 0/1, 288 | 0 | PASSED |
| S3 32k | pinned plus 4 proxy cases, 348 keys | 1 pinned + 4/4 proxy, 348 | 0 | PASSED |
| S3 context/range | at least 32 pinned iterations and all layers | passed | 0 | PASSED |
| Whole-key path | zero in every scenario | zero | 0 | PASSED |
| Runner ledger | every recorded step exit 0 | 163/163 | 0 | PASSED |
| Final process state | both child processes stopped | stopped | 0 | PASSED |

Evidence: [overall summary](evidence/full-validation-rerun-20260803T124415Z/stress/overall-summary.json),
[topology checker](evidence/full-validation-rerun-20260803T124415Z/stress/topology/check.json),
[S1 summary](evidence/full-validation-rerun-20260803T124415Z/stress/s1-pinned-16k/artifacts/scenario-summary.json),
[S2 summary](evidence/full-validation-rerun-20260803T124415Z/stress/s2-concurrent-16x8k/artifacts/scenario-summary.json),
and [S3 summary](evidence/full-validation-rerun-20260803T124415Z/stress/s3-concurrent-4x32k/artifacts/scenario-summary.json).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| S1-S3 scenario definitions | Unchanged |
| Marker/token hard oracles | Unchanged |
| DP/TP topology | Unchanged |
| Native image | Reused current main-verified image |
| vLLM-Ascend runtime | Two-file Python overlay at `d28c52958` |
| Capacity evidence | Published snapshot reduced to non-sensitive resource fields |

## Script Provenance

- Runtime script revision: `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Runtime Script SHA256 for `deployment/run-stress-test.sh`: `3071e3031e358ceaf8fdef97b92b4007d3e6a360bdbd2524fbd288f1fff3e1d7`.
- Published Script SHA256 after the capacity-recorder privacy fix: `4f03d9314bcf54ebc177c0fca84706a105e123e2068fe2d0fc8d786684238ea2`.
- Checker SHA256 for `deployment/check-stress-log.py`:
  `9532588cabf345d7effa5621d6abeb361414c886704dbe9ff0beb6165b6e33b7`.
- Stress `SHA256SUMS` digest:
  `da8b8880f80bfef620c0553c6688e26b1eafbee17c312e5a8a6d3be6e8d0bbcf`.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress
```

The runner transcript records every apply, reset, start, request, log window,
checker, metrics, and final stop command:
[stress transcript](evidence/full-validation-rerun-20260803T124415Z/stress/command-transcript.log).

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress && sha256sum -c SHA256SUMS)
jq -e '.status == "passed" and .validated == true and .topology.validated == true and .scenarios.s1_pinned_16k.validated == true and .scenarios.s2_concurrent_16x8k.validated == true and .scenarios.s3_concurrent_4x32k.validated == true and (.errors|length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress/overall-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/stress/overall-summary.json
```

## Attempts And Failures

All 163 runtime stress steps exited 0. During E0, credential scan found that the
cluster-wide capacity snapshot also contained unrelated Pod command arguments.
The recorder was narrowed to namespace/name/node/phase/resources, a regression
test was added, and the full deployment collection passed 70 tests. The two
snapshots were projected through the same structure; capacity replay remained
8 allocatable, 1 other requested, and 7 available. Runtime results were not
changed or rerun.

## Limitations And Final State

This remains a Python-overlay validation rather than a rebuilt-image result.
The six-NPU stress Pods, Master, proxy, and CPU-only UT Pod are retained. Both
vLLM child processes are stopped, HTTP endpoints are closed, and the Master was
finally reset to zero keys, zero allocated bytes, and zero active clients.
