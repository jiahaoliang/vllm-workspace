# Mooncake Linear Integration Full Validation Rerun

## Status And Scope

Status: **FAILED, TERMINATED AT G0**.

The exact R4 image, static tooling, image identity, and CPU/mock gates passed.
Both 1P1D engine roles then failed during production scheduler initialization
with the same vLLM-Ascend/vLLM ABI error:

```text
TypeError: get_kv_cache_coordinator() got an unexpected keyword argument 'max_num_batched_tokens'
```

Per the source-freeze rule, validation stopped before G1. No production source
was modified after validation began. This report does not claim direct ranged,
lease-expiry, production ranged-audit, smoke, or stress correctness for the
integrated source.

## Original Validation

The historical baseline is the
[2026-07-23 1P1D validation](deployment/validation-2026-07-23.md). That result
used older source and image identities and is not evidence for this rerun.

## Identity

| Field | Exact value |
| --- | --- |
| Run ID | `20260730T130225Z` |
| Control branch | `kv-pool-layerwise-reuse` |
| Runtime tooling commit | `4b296c18472aec46bddeae9974bad24252fd44dc` |
| Evidence commit | `dfe99a1fa7c246f9d84320deac2f143033cec12b` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| vLLM-Ascend base | `a46a1dabbc260e8695002969f29528eb555eb583` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z-r4` |
| Image manifest | `sha256:d957c3950e54f2b7857b3ddf5e39f81c6e755d41c37bfab178cdcf587a0a8477` |
| Image config ID | `sha256:60ef6bbf63d353e4d3f06057a8b8eb53233bb4f6942a7f8466c35081cf87a358` |
| Model config SHA256 | `229913ea2a346ccdb571bb3cb23414ca3a0ee1a9455fe88a15a5788bc837cb75` |
| Tokenizer SHA256 | `41f3bf64213da8c012d8bd0871a58a1fdf70463e8f08f110ddbb1082f529f669` |
| Script SHA256 | `ca815b3165e390d1b320bd75f8cb2cd80533337f33547be0c08b7f6431770b96` for `run-validation-step.sh` |
| Namespace/node | `liangjiahao`, `n1` |

The source range remains exactly 11 linear commits, has no merge commit, and
has merge-base `a46a1dabbc260e8695002969f29528eb555eb583`. Local and origin protected
`feature/mooncake-layerwise-kv-pool` remain
`b5b65d9bbe325d009ad887fb87b8883b7ecee156`.

## Gate Results

| Gate | Expected | Actual | Exit code | Result | Evidence |
| --- | --- | --- | ---: | --- | --- |
| Tooling r4 | Identity, 65 tests, static checks, 10 dry-runs pass | All passed | 0 | PASSED | [summary](evidence/full-validation-rerun-20260730T130225Z/tooling-r4/summary.json) |
| Image r4 | ARM64 image, exact heads, native libs, seven APIs, NPU health | All passed; config ID matched | 0 | PASSED | [summary](evidence/full-validation-rerun-20260730T130225Z/image-r4/summary.json) |
| CPU/mock UT | Complete AscendStore and deployment collections pass | `476 passed`; deployment `65 passed`; Ruff/compile/diff passed | 0 | PASSED | [summary](evidence/full-validation-rerun-20260730T130225Z/ut/summary.json) |
| G0 prestart | Exact image/source/model/API/NPU identity and empty Master | All checks passed; TTL `30000 ms`; all three pool metrics zero | 0 | PASSED | [prestart assertions](evidence/full-validation-rerun-20260730T130225Z/g0/prestart-identity-assertions.json) |
| G0 engine startup | Prefill and Decode become Ready | Both failed in the same coordinator call | 130 | FAILED | [classification](evidence/full-validation-rerun-20260730T130225Z/g0/source-abi-classification.json) |
| Failure cleanup | No live vLLM, no PID files/endpoints, Master empty | Passed; reset metrics all zero | 0 | PASSED | [G0 summary](evidence/full-validation-rerun-20260730T130225Z/g0/summary.json) |
| Cleanup tooling fix | Zombie PID is not treated as live | Full collection `65 passed`; focused `3 passed`; static gates passed | 0 | PASSED | [summary](evidence/full-validation-rerun-20260730T130225Z/tooling-post-failure/summary.json) |
| G1 direct ranged | Full direct ranged contract | Not executed after production defect | N/A | NOT RUN | [run index](evidence/full-validation-rerun-20260730T130225Z/README.md) |
| Lease expiry | Stale lease `-707`, fresh recovery | Not executed | N/A | NOT RUN | [run index](evidence/full-validation-rerun-20260730T130225Z/README.md) |
| G4 runtime audit | All 27 physical layers and no whole-key calls | Not executed | N/A | NOT RUN | [run index](evidence/full-validation-rerun-20260730T130225Z/README.md) |
| Smoke | Marker/token/usage/routing gates | Not executed | N/A | NOT RUN | [run index](evidence/full-validation-rerun-20260730T130225Z/README.md) |
| Stress S1-S3 | Six-card DP/TP scenarios | Not executed | N/A | NOT RUN | [run index](evidence/full-validation-rerun-20260730T130225Z/README.md) |

## Changes From Original Validation

| Original | Current | Reason | Correctness impact | Commit/evidence |
| --- | --- | --- | --- | --- |
| Older feature source and vLLM 0.24 line | 11/11 integration at `14beaf16` with pinned vLLM `54503ece` | Requested linear integration and target-branch pin | Requires a new image and full rerun | [identity](evidence/full-validation-rerun-20260730T130225Z/image-r4/summary.json) |
| Older Mooncake control API names | Seven renamed session/range APIs at `786c77ff` | Mooncake collaborator update | Static and dynamic API gates passed | [image result](evidence/full-validation-rerun-20260730T130225Z/image-r4/summary.json) |
| Historical image | Unique R4 ARM64 image | Exact source/dependency rebuild | Image identity passed; runtime later failed | [image result](evidence/full-validation-rerun-20260730T130225Z/image-r4/summary.json) |
| Successful historical 1P1D startup | Both current roles fail before serving | Coordinator keyword mismatch | Blocks every production request-level gate | [two-role logs](evidence/full-validation-rerun-20260730T130225Z/g0/source-abi-classification.json) |
| Base stop helper used `kill -0` | Base and stress share `live/absent/zombie` classification | Failed API servers became unreaped zombies under `sleep` PID 1 | Cleanup no longer waits 60 seconds on an inert zombie; production verdict unchanged | [tooling fix](evidence/full-validation-rerun-20260730T130225Z/tooling-post-failure/summary.json) |

## Script Provenance

The G0 runtime used control commit
`4b296c18472aec46bddeae9974bad24252fd44dc`. The recorder did not change during
the run: original/current SHA256 is
`ca815b3165e390d1b320bd75f8cb2cd80533337f33547be0c08b7f6431770b96`.

The base runtime ConfigMap changed only after failure. Its runtime SHA256 was
`6f136dbd11facb631adc98ab40d30e73c83a5034819788092de525d18ca329cc`;
the zombie-aware version in evidence commit `dfe99a1` is
`2c9293ae3f01c51f87f441301abfd49894fa3c9d503f1b302528b528c84f9fea`.
The regression test SHA256 is
`c193b19c3d09ea652c62064e99e3be395c3bcca4da3307d7c7875355e8859ae2`.
No file under `repos/*` changed during validation.

## Live Reproduction Runbook

These are the core commands used against the frozen R4 deployment. They start
the same child processes and reproduce the startup failure before any request
is sent.

```bash
REPORT_NAMESPACE=liangjiahao
PREFILL_POD=prefill-engine-deployment-7bf66dd56b-q5mcx
DECODE_POD=decode-engine-deployment-5c96cd595-qdzds

kubectl exec -n "${REPORT_NAMESPACE}" "${PREFILL_POD}" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${REPORT_NAMESPACE}" "${DECODE_POD}" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl exec -n "${REPORT_NAMESPACE}" "${PREFILL_POD}" -c prefill-engine -- cat /tmp/vllm-prefill.log
kubectl exec -n "${REPORT_NAMESPACE}" "${DECODE_POD}" -c decode-engine -- cat /tmp/vllm-decode.log
```

Expected output: each log reaches Mooncake buffer registration and then reports
the exact `max_num_batched_tokens` TypeError from
`patch_kv_cache_coordinator.py:518`. State change: both API servers exit. Final
state: run both stop helpers and reset Master before any independent scenario.

The matching cleanup commands used by this run were:

```bash
REPORT_NAMESPACE=liangjiahao
PREFILL_POD=prefill-engine-deployment-7bf66dd56b-q5mcx
DECODE_POD=decode-engine-deployment-5c96cd595-qdzds

kubectl exec -n "${REPORT_NAMESPACE}" "${PREFILL_POD}" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${REPORT_NAMESPACE}" "${DECODE_POD}" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
kubectl rollout restart -n "${REPORT_NAMESPACE}" deployment/mooncake-master-deployment
kubectl rollout status -n "${REPORT_NAMESPACE}" deployment/mooncake-master-deployment --timeout=600s
```

Expected output: no live vLLM process or HTTP endpoint remains; Master returns
with `master_key_count=0`, `master_allocated_bytes=0`, and
`master_active_clients=0`.

## Offline Evidence Recheck

All successful and failed attempts are immutable under the run root. The first
image attempt ended before a checksum manifest was created; every later family
listed below has a verified `SHA256SUMS`.

```bash
EVIDENCE_ROOT=features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260730T130225Z
for family in tooling tooling-r2 tooling-r3 tooling-r4 image-r2 image-r3 image-r4 ut g0 tooling-post-failure; do
  (cd "${EVIDENCE_ROOT}/${family}" && sha256sum -c SHA256SUMS)
done
jq -e '.status == "failed" and .failure.classification == "production-code-abi-runtime-defect"' "${EVIDENCE_ROOT}/g0/summary.json"
git ls-files --error-unmatch "${EVIDENCE_ROOT}/g0/summary.json"
git ls-files --error-unmatch "${EVIDENCE_ROOT}/tooling-post-failure/summary.json"
```

The G0 `SHA256SUMS` file itself has SHA256
`35db818c1ec6ec005e838eeeb17f464ed73f600f8837f78d6e64ee7631e6c212`.

## Attempts And Failures

| Attempt | Observation | Classification | Disposition |
| --- | --- | --- | --- |
| Image r1 | Stale vLLM identity reached raw dependency-health failure | Validation identity/tooling defect | Preserved; no image loaded |
| Image r2 | Wheel version used 9-character short SHA, not assumed 8 | Validation tooling defect | Corrected exact allowlist; preserved exit 130 |
| Image r3 | CMake Mooncake install had no wheel distribution metadata | Validation tooling defect | Replaced wheel-only probe with Git/native/API proof |
| Image r4 | Build and all static/dynamic image gates passed | Passed | Used for UT and G0 |
| G0 | Both roles raised the same coordinator keyword TypeError | Production code/ABI/runtime defect | Terminated before G1; no source modification |
| G0 cleanup | Old stop helper waited on zombie PID and sent ineffective SIGKILL | Validation tooling defect | Added shared PID-state helper and regression coverage |
| Post-failure tooling sync | First fixture omitted lock and Dockerfile; `63 passed, 2` missing-file failures | Validation step defect | Preserved; completed fixture passed `65` tests |
| Post-failure Ruff | First path was stale; next format check found a real format delta | Validation step/tooling defect | Used current Pod Ruff 0.14.0, formatted, then lint/format passed |
| Final Master metrics | Immediate post-rollout HTTP read raced admin port and refused once | Transient infrastructure | Preserved; retry passed with all metrics zero |
| Offline checksum invocation | First manual replay ran family-relative manifests from repo root | Validation step defect | Re-ran from each family directory; all listed families passed |

## Limitations And Final State

- The runtime defect is inherited from the collaborator base. The 11-commit
  Mooncake range has an empty diff for
  `vllm_ascend/patch/platform/patch_kv_cache_coordinator.py`.
- The vLLM-Ascend wrapper selects and forwards `max_num_batched_tokens` for the
  declared `v0.25.1` compatibility line. Pinned vLLM commit `54503ece` accepts
  `max_in_flight_tokens` and has no `max_num_batched_tokens` parameter.
- G1, lease, G4, smoke, and S1-S3 were not executed. CPU/mock success and image
  identity do not establish production KVPool correctness.
- No live vLLM API server or EngineCore remained. Failure evidence captured
  unreaped zombie Python PIDs under the `sleep` PID 1 container; PID files were
  removed and the post-failure helper now classifies such PIDs as non-live.
- Final Master, proxy, and CPU-only UT Pod were Running/Ready with restart count
  zero. Prefill and Decode Pods were retained Running but intentionally not
  Ready because their vLLM children were stopped.
- Final `n1` NPU state was 3 requested of 8: two retained engine Pods from this
  run plus one unrelated workload. `n1` had 5 free cards. `m1` had 3 free.
- `pwsh` and `powershell` were unavailable, so the PowerShell workspace scripts
  were not claimed; equivalent Git/JSON validations were run instead.
