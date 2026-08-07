# Multi-DP/TP Revoke Ownership Stress Validation 2026-08-07

## Status And Scope

PASSED. S1-S3 validated Prefill DP2/TP2 plus Decode DP1/TP2 on six physical
A2 cards. Coverage includes pinned and proxy cache reuse, 8K/16K/32K contexts,
marker isolation, bounded chunks, all 27 scatter layers, commit ordering,
DP-rank activity, key arithmetic, and zero whole-key fallback.

## Original Validation

The predecessor is the tracked
[2026-08-04 stress report](multi-dp-tp-stress-validation-2026-08-04.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Topology | Prefill 4 NPUs DP2/TP2; Decode 2 NPUs DP1/TP2 |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Capacity | 7 available, 6 required | PASSED |
| Topology | all 10 structural checks | PASSED |
| S1 pinned 16K | `4/4`, ranks 0/1, 508 keys | PASSED |
| S2 concurrent 8K | `16/16` isolated, 288 keys | PASSED |
| S3 long context | pinned proof plus `4/4`, 348 keys | PASSED |
| Marker isolation | `4/4`, `16/16`, `4/4` | PASSED |
| Scatter path | all 27 layers; commit order; zero whole-key | PASSED |
| Runner ledger | `164/164` exit zero | PASSED |
| Final state | engines stopped; Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | exact native image at final source SHA |
| Mooncake | frozen `df3f74ed` scatter/session implementation |
| Revoke ownership | failed cleanup remains pending and fail closed |
| Overlay | disabled throughout stress |

## Script Provenance

- Script SHA256: `87d66b05a5effe8192efa145307323066deeb429a8b4879d965ff6ec81f07a30` for `deployment/run-stress-test.sh`.
- Family `SHA256SUMS` digest: `1fd99b15ad418508d0ff97b162fb563f33b3c097aeffbd9f3dc4d8ae3938c88c` over 392 immutable files.
- Stress ran from control commit `66ed7933e898133ef27c3a9eb967e8e4555cda35`.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
kubectl exec -n liangjiahao prefill-engine-deployment-75fd46886-pd67q -c prefill-engine -- test ! -e /tmp/vllm-prefill.pid
kubectl exec -n liangjiahao decode-engine-deployment-545854f777-n9sx4 -c decode-engine -- test ! -e /tmp/vllm-decode.pid
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/stress/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .scenarios.s1_pinned_16k.actual_key_count == 508 and .scenarios.s1_pinned_16k.marker_prefix_match_count == 4 and .scenarios.s2_concurrent_16x8k.actual_key_count == 288 and .scenarios.s2_concurrent_16x8k.marker_prefix_match_count == 16 and .scenarios.s3_concurrent_4x32k.actual_key_count == 348 and .scenarios.s3_concurrent_4x32k.marker_prefix_match_count == 4 and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/stress/overall-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/multi-dp-tp-stress-validation-2026-08-07.md
```

## Attempts And Failures

The formal stress runner completed once with no failed step, production-source
defect, tooling correction, or infrastructure retry. It reset the Master and
restarted engines between scenarios, then stopped both engines and confirmed
PID absence plus refused HTTP endpoints at completion.

## Limitations And Final State

This is functional and stress-oracle validation, not a throughput benchmark.
It covers the single-group A2 path and excludes FabricMem, A3, and Mooncake
multi-group. The six-NPU Pods remain allocated with vLLM children stopped;
the long-running UT Pod and BuildKit Pod are retained. Final Master metrics are
`0/0/0`.
