# Mooncake Revoke Ownership Full Validation 2026-08-07

## Status And Scope

PASSED. The complete source, tooling, native ARM64 image, native-image CPU/mock,
G0, direct G1, lease, G4, 1P1D smoke, and stress S1-S3 flow passed for the
revoke-ownership fix at `45b2e785` with Mooncake `df3f74ed`. The run used no
Python overlay and did not enable FabricMem.

## Original Validation

The direct predecessor is the tracked
[2026-08-04 full validation](full-validation-rerun-2026-08-04.md).

## Identity

| Item | Frozen value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Tooling base | `3bda70d786db46310994afc689af4fc10da4858e` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Manifest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Config ID | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Kubernetes | runtime `liangjiahao`; BuildKit `default` |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Source | `495` AscendStore; Ruff, compile, diff | PASSED |
| Tooling | final `84` tests; same-key restart hard gate | PASSED |
| Native image | `linux/arm64`; exact labels, HEADs, modules, APIs | PASSED |
| Native-image UT | `495` AscendStore and `83` deployment | PASSED |
| G0 | exact 1P1D identity; stopped; `0/0/0` | PASSED |
| G1 | `45/45`, `26/26`, exact bytes, same-key restart | PASSED |
| Lease | stale `-707`; fresh exact recovery | PASSED |
| G4 | 27 save + 27 load; per-key bytes; zero whole-key | PASSED |
| Smoke | 17/17 cases; 12/12 correlations; 64 keys | PASSED |
| Stress | S1 `4/4/508`; S2 `16/16/288`; S3 `4/4/348` | PASSED |
| Final | engines stopped; Master `0/0/0` | PASSED |

Family reports: [ranged](ranged-api-validation-2026-08-07.md),
[lease](lease-expiry-validation-2026-08-07.md),
[G4](ranged-api-g4-validation-2026-08-07.md),
[smoke](deployment/validation-2026-08-07.md), and
[stress](multi-dp-tp-stress-validation-2026-08-07.md).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Mooncake | failed revoke retains its local session |
| vLLM-Ascend | shared pending ownership, bounded retries, keyed deduplication |
| Image | rebuilt natively at all three frozen SHAs |
| Overlay | disabled; image source equals final source |
| Validation | same-key restart and per-key scatter byte gates added |

## Script Provenance

- Script SHA256: `caffb192fd6dc47f3a26dcf9a57244d41e31a55e9dac6e7c6aebec7e7147b5c4` for the stable full-validation guide.
- Report checker Script SHA256: `7cf31612e54217023b6b36ca5aa9998a30564c1fb55606ab3dd96b009d0bfb07`.
- Stress `SHA256SUMS` digest: `1fd99b15ad418508d0ff97b162fb563f33b3c097aeffbd9f3dc4d8ae3938c88c`.
- Evidence-root `SHA256SUMS` digest: `e5a13d163cfd98fe547c44ec22dc6c1c9688a07e42609d885f88935892a37f08` over 797 files.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -o wide
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/ut/distributed/ascend_store
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
kubectl get pod -n default buildkitd -o wide
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .families.g1.cases == 45 and .families.stress.recorded_steps == 164 and .final_state.engines_stopped == true and .final_state.master_key_count == 0 and .final_state.master_allocated_bytes == 0 and .final_state.master_active_clients == 0 and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/final/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/full-validation-rerun-2026-08-07.md
```

## Attempts And Failures

G4 attempt 1 was a tooling-only false rejection of a valid optional response
field; cleanup passed, the validator was corrected, and G4 reran completely.
Smoke's first post-rollout metrics read raced the new endpoint; bounded retry
proved `0/0/0`. Stress completed once with all `164/164` steps green. No
production source changed after source freeze, and no Mooncake source was
modified.

## Limitations And Final State

The claim is for native ARM64 Ascend A2, single-group Mooncake, and the frozen
model/configuration. It excludes FabricMem, `ShmHelper`, A3, Mooncake
multi-group, and throughput benchmarking. Prefill and Decode children are
stopped while their six-NPU Pods remain allocated. The long-running
`liangjiahao/vllm-ascend-ut` and `default/buildkitd` Pods are retained; final
Master metrics are `0/0/0`.
