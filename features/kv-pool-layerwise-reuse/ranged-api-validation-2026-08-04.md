# Mooncake Ranged API Single-Group Validation 2026-08-04

## Status And Scope

PASSED. G0 and G1 validated the unchanged ARM64 image with the exact five-file
vLLM-Ascend Python overlay at `d5f0ea7f8`. The claim covers image/source
identity, empty-pool isolation, aligned nonnegative ranged results, 43 direct
cases, 24 negative cases, exact bytes, and cleanup. Mooncake multi-group is
explicitly outside scope.

## Original Validation

The direct baseline is the tracked
[2026-08-03 ranged API report](ranged-api-validation-2026-08-03.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay vLLM-Ascend | `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Runtime | `liangjiahao`, node `n1` |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| CPU/mock | 490 passed | PASSED |
| G0 overlay | five host/Prefill/Decode checksums exact | PASSED |
| G0 cleanup | keys/bytes/clients `0/0/0` | PASSED |
| G1 positive | 43/43 cases | PASSED |
| G1 negative | 24/24 cases | PASSED |
| Result contract | aligned integer values, every result nonnegative | PASSED |
| Byte oracle | source and destination exact | PASSED |

The persistent execution state is in the
[dated tracker](implementation-plans/2026-08-04-single-group-backports-overlay-full-validation-20260804T103209Z.md).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Single-group rows | immutable `LayerRangeRow` with legacy positional compatibility |
| Failure isolation | exception and malformed-result failures remain request-local |
| Audit | centralized best-effort range emitters |
| Result success | accepts `0` or positive aligned results |
| Multi-group | deferred; no §5.8 code in the source range |

## Script Provenance

- Script SHA256: `b10fbc18f59ff442390c6cebef0855a53fbf8a22eb3b91fef371941df3f1b125` for `deployment/range-api-smoke.py`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.
- Raw runtime evidence and checksums remain local because external publication was blocked by the workspace safety gate.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/ut/distributed/ascend_store tests/ut/test_envs.py
kubectl exec -n liangjiahao prefill-engine-deployment-7b8549d6fc-nz28h -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260804T103209Z/range-api-smoke.py --output /tmp/full-validation-direct-20260804T103209Z/g1-summary.json --num-keys 3 --num-layers 4 --page-size 4096 --run-negative
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.passed == true and (.cases | length) == 43 and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/g1/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/ranged-api-validation-2026-08-04.md
```

## Attempts And Failures

No G1 production failure occurred. Earlier source review found that the nightly
gate incorrectly required byte-count results; the source was corrected before
this frozen run to accept every aligned nonnegative ranged success value.

## Limitations And Final State

This is an overlay result, not a rebuilt-image result. The performance nightly
test collected and skipped without external benchmark configuration; it is not
a throughput claim. Engines are stopped and final Master metrics are `0/0/0`.
