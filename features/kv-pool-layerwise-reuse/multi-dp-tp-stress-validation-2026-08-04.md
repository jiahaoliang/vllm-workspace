# Multi-DP/TP Stress Single-Group Validation 2026-08-04

## Status And Scope

PASSED. S1-S3 validate Prefill DP2/TP2 plus Decode DP1/TP2, pinned and proxy
cache reuse, medium/long contexts, concurrency, marker isolation, chunk bounds,
27-layer ranges, commit order, key arithmetic, and zero whole-key fallback.

## Original Validation

The baseline is the tracked
[2026-08-03 stress report](multi-dp-tp-stress-validation-2026-08-03.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image/final vLLM-Ascend | `14beaf161` / `d5f0ea7f8` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Topology | Prefill 4 NPUs DP2/TP2; Decode 2 NPUs DP1/TP2 |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Capacity | 7 available before six-NPU allocation | PASSED |
| Topology | all 10 checks true | PASSED |
| S1 pinned 16K | 4/4, ranks 0/1, 508 keys | PASSED |
| S2 concurrent 8K | 16/16, ranks 0/1, 288 keys | PASSED |
| S3 32K | pinned proof plus 4/4, 348 keys | PASSED |
| Whole-key path | zero in every scenario | PASSED |
| Runner ledger | 162/162 recorded steps | PASSED |
| Final state | child processes stopped | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | five-file single-group overlay at `d5f0ea7f8` |
| Result contract | nonnegative ranged success accepted |
| Runner startup | now supports clean start after old deployments scale to zero |
| Hardware recovery | physical `/dev/davinci1` quarantined during final run, then released after completion |

## Script Provenance

- Script SHA256: `1e734170430af074a4e59d93f5393116f2a45221722e345ae21e7a14bae8a9ad` for `deployment/run-stress-test.sh`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
kubectl get node -n liangjiahao n1 -o json
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- test ! -e /tmp/vllm-prefill.pid
kubectl exec -n liangjiahao decode-engine-deployment-85f47466d6-6wn8r -c decode-engine -- test ! -e /tmp/vllm-decode.pid
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .topology.validated == true and .scenarios.s1_pinned_16k.validated == true and .scenarios.s2_concurrent_16x8k.validated == true and .scenarios.s3_concurrent_4x32k.validated == true' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/stress/overall-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/multi-dp-tp-stress-validation-2026-08-04.md
```

## Attempts And Failures

Three startup attempts failed before KVPool traffic because physical NPU 1
could not load `libcpu_kernels.so` and returned ACL `507018`. A seven-Pod
allocation probe identified `/dev/davinci1`, which was quarantined. Attempt 4
then found a runner-only clean-start defect; a regression test went red/green,
the complete deployment suite passed 82 tests, and the final S1-S3 run passed.

## Limitations And Final State

This is single-group overlay validation, not an image rebuild or multi-group
claim. Stress Pods remain allocated but their vLLM child processes are stopped;
the temporary quarantine Pod was deleted and Master is `0/0/0`.
