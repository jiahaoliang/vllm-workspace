# Mooncake 1P1D Smoke Overlay Validation 2026-08-03

## Status And Scope

PASSED. The four-request 1P1D smoke validates the explicit two-file
vLLM-Ascend Python overlay on the unchanged native ARM64 image. It covers cold
baseline generation, cache population, concurrent direct Decode loads,
concurrent proxy loads, marker ownership, foreign-marker exclusion, token and
usage contracts, and per-response cache-hit correlation. It does not claim an
image built at the final overlay commit.

## Original Validation

The comparison baseline is the tracked
[2026-07-23 deployment validation](validation-2026-07-23.md). The immediately
preceding [2026-07-31 full validation](../full-validation-rerun-2026-07-31.md)
failed this same concurrent warm-load gate and supplied the focused
warm-versus-cold reproduction used to diagnose the production defect.

## Identity

| Item | Value |
| --- | --- |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| Kubernetes | `liangjiahao`, node `n1`, base 1P1D |

The overlay consists only of `config_data.py` and `kv_transfer.py`; host,
Prefill, Decode, and UT checksums are equal.

## Gate Results

| Gate | Expected | Actual | Exit | Result |
| --- | --- | --- | --- | --- |
| Empty baseline | 4 isolated HTTP 200 responses | 4/4 | 0 | PASSED |
| Warmup | Populate/reuse all four fixtures | 5/5 | 0 | PASSED |
| Direct KV load | 4 concurrent isolated responses | 4/4 | 0 | PASSED |
| Proxy KV load | 4 concurrent isolated responses | 4/4 | 0 | PASSED |
| Marker oracle | Own marker; no foreign marker | 17/17 phase cases | 0 | PASSED |
| Token/usage oracle | Prompt/completion counts and finish reason | all exact | 0 | PASSED |
| Cache arithmetic | 64 Master keys; 25/25 blocks and 3200 hit tokens | exact | 0 | PASSED |
| Log correlation | 12 required response-role correlations | 12/12 | 0 | PASSED |
| Cleanup | engines stopped; Master keys/bytes/clients `0/0/0` | exact | 0 | PASSED |

Primary evidence: [smoke summary](../evidence/full-validation-rerun-20260803T124415Z/smoke/concurrent-summary.json),
[log checker](../evidence/full-validation-rerun-20260803T124415Z/smoke/log-validation.json),
and [smoke transcript](../evidence/full-validation-rerun-20260803T124415Z/smoke-prep/command-transcript.log).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Four-request fixture | Unchanged |
| Marker/token/usage hard oracles | Unchanged |
| Image/native dependencies | Unchanged |
| vLLM-Ascend runtime | Two-file Python overlay at `d28c52958` |
| Ranged load dispatch | Concurrent requests are isolated into separate Mooncake batches |
| Full continuation equality | Unchanged diagnostic; not an acceptance substitute |

## Script Provenance

- Runtime tooling revision: `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Script SHA256 for `deployment/run-smoke-test.sh`: `60cd20cb08dd6faf2716dfa959115d453a8d875a661b2f8c522ec6ad2126bce7`.
- Smoke `SHA256SUMS` digest:
  `f260e76ba5ed87b7cf864bbd71180f92d026be58be25a24eb619513eeec8289b`.

## Live Reproduction Runbook

The core commands below are the commands executed for this family. The linked
transcript contains the endpoint waits, preflight/final metrics, assertions,
timestamps, and exit codes.

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-56559b48fc-48kcr -c decode-engine -- env PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-decode.sh
env PYTHONDONTWRITEBYTECODE=1 features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n liangjiahao decode-engine-deployment-56559b48fc-48kcr -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke && sha256sum -c SHA256SUMS)
jq -e '.status == "passed" and .validated == true and .diagnosis == "passed" and .concurrency == 4 and .actual_master_key_count == .expected_master_key_count and (.phases.empty_pool_baseline.cases|length) == 4 and (.phases.warmup.cases|length) == 5 and (.phases.direct_kv_load.cases|length) == 4 and (.phases.proxy_kv_load.cases|length) == 4' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke/concurrent-summary.json
jq -e '.passed == true and (.checks|length) == 12 and all(.checks[]; .passed == true)' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke/log-validation.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/smoke/concurrent-summary.json
```

## Attempts And Failures

The previous formal run failed direct concurrent case 2 even with `25/25`
loaded blocks. Focused warm pair 2/3 reproduced `9/30` failures while the
empty-Master cold control passed `30/30`, proving a production warm-load defect
rather than a smoke oracle defect. After source commit `d28c52958`, two focused
warm runs passed `120/120` each and this formal smoke passed every phase.

The first offline summary assertion for this passing run incorrectly required
four warmup cases. The fixture intentionally records five warmup operations.
The corrected phase-specific assertion passed against unchanged runtime output;
no oracle was weakened and no production source changed.

## Limitations And Final State

This is overlay validation, not a rebuilt-image claim. The smoke covers four
concurrent requests; broader DP/TP and context coverage is in the stress
report. After the complete run, the retained stress Pods request six NPUs but
both vLLM child processes are stopped. The retained Master reports zero keys,
zero allocated bytes, and zero active clients.
