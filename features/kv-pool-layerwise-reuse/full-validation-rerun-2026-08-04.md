# Mooncake Single-Group Full Validation Rerun 2026-08-04

## Status And Scope

PASSED. The complete CPU/mock, G0, direct ranged G1, lease, G4, 1P1D smoke,
and S1-S3 flow passed for `d5f0ea7f8` using the unchanged native ARM64 image
from `14beaf161` plus an exact five-file Python overlay. §5.8 Mooncake
multi-group remains deferred and is not part of this claim.

## Original Validation

The direct predecessor is the tracked
[2026-08-03 full validation](full-validation-rerun-2026-08-03.md).

## Identity

| Item | Frozen value |
| --- | --- |
| Run ID | `20260804T103209Z` |
| Evidence commit policy | `cc773ea399dac36111fe3df11ab0ca8155d26def` records tooling and local-only evidence exclusion |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay vLLM-Ascend | `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8`, 27 layers |
| Kubernetes | `liangjiahao`, node `n1` |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Source | 4 signed commits after `d28c52958`; no merges or §5.8 symbols | PASSED |
| Standards review | no findings after `d5f0ea7f8` | PASSED |
| CPU/mock | 490 passed | PASSED |
| Tooling | 82 passed after clean-start regression fix | PASSED |
| G0/G1 | five checksums; 43/43 and 24/24 | PASSED |
| Lease | stale `-707`, fresh recovery | PASSED |
| G4 | 27 save + 27 load layers; zero whole-key | PASSED |
| Smoke | 4/4 baseline, 5 warmups, 4/4 direct, 4/4 proxy, 12/12 correlations | PASSED |
| Stress | S1 4/4/508; S2 16/16/288; S3 pinned + 4/4/348 | PASSED |
| Final | engines stopped; Master `0/0/0`; quarantine removed | PASSED |
| Source push | origin `d5f0ea7f8`; left/right `0 0`; protected ref unchanged | PASSED |

Family reports: [ranged](ranged-api-validation-2026-08-04.md),
[lease](lease-expiry-validation-2026-08-04.md),
[G4](ranged-api-g4-validation-2026-08-04.md),
[smoke](deployment/validation-2026-08-04.md), and
[stress](multi-dp-tp-stress-validation-2026-08-04.md).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Source | three approved WIP single-group backports plus one review correction |
| Row model | immutable rows and request-local malformed-result isolation |
| Audit | centralized range/commit/whole-key events |
| Nightly gate | registered envs, nonnegative success contract, named pattern constant |
| Multi-group | explicitly deferred; `0dad9ad94` excluded |
| Validation tooling | dead-engine fail-fast and clean-start support |

## Script Provenance

- Script SHA256: `caffb192fd6dc47f3a26dcf9a57244d41e31a55e9dac6e7c6aebec7e7147b5c4` for the stable full-validation guide.
- Report checker Script SHA256: `7cf31612e54217023b6b36ca5aa9998a30564c1fb55606ab3dd96b009d0bfb07`.
- Local curated `SHA256SUMS` digest: `dc369993a4dc3075bfcfed58d8a6a7bc9f55d1c9b521ab1dbb6f1028f659415f`.
- The workspace safety gate blocked external upload of raw and curated runtime evidence; all checksummed evidence remains local.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -o wide
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/ut/distributed/ascend_store tests/ut/test_envs.py
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/publication/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .final_state.master_key_count == 0 and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z/final/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/full-validation-rerun-2026-08-04.md
```

## Attempts And Failures

G4 had three tooling-only attempts. Stress startup attempts 1-3 isolated a
physical NPU 1 AICPU failure before KVPool traffic. Stress attempt 4 exposed a
runner clean-start assumption and was fixed test-first; the final run passed.
No production source changed after source freeze.

## Limitations And Final State

This does not claim a rebuilt image, benchmark throughput, or Mooncake
multi-group support. Complete raw evidence is local-only due the external
publication safety boundary. The source and control tooling refs are pushed;
engines are stopped, Master is empty, and temporary quarantine resources are
removed.
