# Mooncake Main-Lane Full Validation Rerun

## Status And Scope

Status: **FAILED, TERMINATED AT 1P1D SMOKE**.

The exact main-lane image, CPU-only UT, G0, direct ranged G1, lease-expiry,
and G4 production ranged-audit gates passed. The formal 1P1D smoke then found
a reproducible concurrent warm KV-load correctness failure: case 2 lost its
private `CASE_TWO` marker even though Decode reported all 25 blocks and 3200
tokens loaded through the layerwise path. The same payload passed cold
concurrent computation and serial warm replay.

Per the source-freeze rule, no file under `repos/*` changed. Stress S1-S3 was
not run. Both vLLM processes were stopped and Mooncake Master was reset to zero
keys, zero allocated bytes, and zero active clients.

## Original Validation

The historical baseline is the
[2026-07-23 1P1D validation](deployment/validation-2026-07-23.md). It used an
older source/image identity and passed its final four-request fixture. The
current result supersedes that runtime claim for the 11-commit integrated
source, while preserving the same marker/token/usage hard-gate semantics.

## Identity

| Field | Exact value |
| --- | --- |
| Run ID | `20260731T064607Z` |
| Control branch | `kv-pool-layerwise-reuse` |
| Tooling checkpoint | `e97b41a046c03f1926f096740765ae13a56329e9` |
| vLLM lane | `main-verified`, no `VLLM_VERSION` override |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| vLLM-Ascend base | `a46a1dabbc260e8695002969f29528eb555eb583` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Image manifest | `sha256:866ba89f897464a1e38893a57f6e5c3a035c7aba7dfa196fce9646498eaf6d97` |
| Image config | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Namespace/node | `liangjiahao`, `n1` |

The source range remains exactly 11 linear commits, has no merge commit, and
has merge-base `a46a1dabbc260e8695002969f29528eb555eb583`. The protected local and
origin `feature/mooncake-layerwise-kv-pool` refs remain
`b5b65d9bbe325d009ad887fb87b8883b7ecee156`.

## Gate Results

| Gate | Result | Key evidence |
| --- | --- | --- |
| Tooling r4 | PASSED | 20/20 steps, deployment `67 passed`, static and ten dry-run gates |
| Image r2 | PASSED | exact native ARM64 identity and NPU-backed dynamic proof |
| CPU/mock UT | PASSED | AscendStore `476 passed`, deployment `67 passed`, Ruff/compile/history |
| G0 | PASSED | both engines Ready; old coordinator `TypeError` absent; final empty reset |
| G1 | PASSED | 43 cases, 24 negative cases, three keys across four layers |
| Lease | PASSED | stale session exact `-707`; fresh session exact recovery |
| G4 | PASSED | save/load layers `0..26`, final commit order, zero whole-key calls |
| 1P1D smoke | **FAILED** | direct concurrent case 2 violated marker ownership under warm layerwise load |
| Stress S1-S3 | NOT RUN | blocked by the terminal smoke production defect |
| Failure cleanup | PASSED | both engines stopped; final Master metrics all zero |

## Changes From Original Validation

- Replayed exactly 11 Mooncake commits onto
  `collaborator/kv_offload_0723` base `a46a1dabb` and added only the separately
  tested session-API boundary adaptation.
- Selected the branch-declared vLLM main commit `54503ece` without forcing the
  incompatible `v0.25.1` release override.
- Rebuilt and proved a new exact ARM64 image, then reran CPU/mock UT and every
  runtime family from G0 rather than reusing the old image result.
- Retained marker ownership, token prefix/count, usage, finish reason, routing,
  and per-response hit correlation as hard gates. Full continuation equality
  remained diagnostic only.
- Added a focused warm/cold differential after the formal smoke failure; it did
  not weaken or replace the failed formal gate.

## Script Provenance

The formal entry point was the tracked
`features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh` from tooling
checkpoint `e97b41a046c03f1926f096740765ae13a56329e9`. Its mounted
`smoke-test.py` came from the same committed base ConfigMap. The focused driver
is preserved under the run evidence and consumes the formal response fixtures.

Script SHA256: `780c94383e3fa01f01aa082ddeddf914d7e631b04620af1429c04b40a8360591` for
`smoke/diagnostics/focused-replay.py`.

Evidence commit: `25bc3f55546de727fcdddfba0110b3d1d2b93614`.

## Exact Failure

The formal smoke started from an empty Master, passed four concurrent cold
baselines, populated exactly 64 keys, and passed warmup. During four-way direct
Decode concurrency, response `cmpl-b4925b9042a7f091` corresponded to case 2's
exact prompt token digest but returned:

```text
The private cache branch identity marker is the identity marker of the private cache branch.
```

Expected text began with ` CASE_TWO`. Token count, prompt/completion usage, and
`finish_reason=length` were correct. Decode logged for the same response:

```text
hit_blocks=25/25
kvpool hit tokens: 3200
load_async=False use_layerwise=True
```

The identical case 2 payload immediately passed a serial replay. The later
four-way proxy phase passed 4/4, and the formal per-response log checker passed
12/12 hit correlations. These facts preserve the hard marker oracle while
showing that the failure is concurrency-dependent and intermittent.

## Minimal Reproduction And Differential

The evidence-only focused driver reuses the exact formal prompt token IDs,
seeds, baseline signatures, endpoint discovery, and Decode API:

| Scenario | Result |
| --- | --- |
| case 2 alone, warm | 10/10 passed |
| pair 0/2, warm | 10/10 passed |
| pair 1/2, warm | 10/10 passed |
| pair 2/3, warm first sample | 1 failure in 10 |
| pair 2/3, warm repeat | 9 failures in 30 |
| pair 2/3, empty-Master cold control | 30/30 passed |

All nine repeat failures affected only case 2 and produced the same
shared-prefix-derived continuation; case 3 stayed correct. The cold control
was run after stopping both engines and resetting Master. All 60 cold response
IDs correlated with `hit_blocks=0/25`, and none correlated with a full hit.

This differential falsifies these test-only explanations:

- `asyncio.gather` response ordering or case mapping;
- marker text/token-prefix checker behavior;
- fixed-seed generation variation;
- generic concurrent model generation independent of KVPool;
- a single malformed prompt or one-request load problem.

The remaining failing boundary is concurrent warm layerwise KV load. The
highest-risk source path is the request/key/local-block row construction and
shared ranged-load dispatch spanning
`pool_worker.py::_prepare_mooncake_layerwise_sessions`,
`_open_mooncake_get_sessions`, `_build_shared_load_data`,
`LayerBatchBuilder._build_key_major_shared`, and
`KVCacheStoreLayerRecvingThread._handle_range_request`. This run does not claim
the exact defective statement because the source-freeze contract forbids
production instrumentation or repair after validation begins.

## Validation Tooling Issues Corrected

Only control/test tooling and execution steps changed. No production source
changed. The final report includes every correction encountered in this run:

- image Pod wait initially selected a terminating old Pod;
- Kubernetes JSONPath used an unsupported null predicate;
- summary JSON generation had Python/shell quoting errors;
- binary runtime evidence needed explicit `.gitattributes` handling;
- a G0 command repeated the `pod` resource type;
- G1 `pgrep` matched its own command;
- host Python 3.9 does not support `zip(strict=True)`;
- the focused diagnostic initially assumed nonexistent `decode-engine-service`
  DNS and was corrected to use proxy `/listEndPoints` discovery;
- the UT Pod has a fixed `/workspace/tools/ruff` binary but no importable
  `ruff` module; final lint/format used the fixed binary;
- an early host `py_compile` wrote `__pycache__` under diagnostics; it was
  removed before checksumming, and final compilation used in-memory `compile`
  with `PYTHONDONTWRITEBYTECODE=1`;
- the report checker requires `Script SHA256` and its digest on one line;
- the first Linux `status-all.ps1` equivalent forced nine-character detached
  abbreviations instead of Git's default, and the first
  `validate-workspace.ps1` equivalent enumerated nested README directories
  instead of only direct feature children; both were corrected to match
  `common.ps1` exactly;
- one stale-reference `rg` command used unescaped backticks in the shell; it
  was replaced with literal-safe searches and caused no repository change.

Each correction was limited to validation logic or evidence collection. The
invalid attempts are preserved where they materially explain the audit trail.

## Live Reproduction Runbook

These commands describe the exact retained base topology. Revalidate Pod names,
image identity, NPU availability, and empty output directories before a new
run. They are not permission to modify frozen production source.

```bash
NAMESPACE=liangjiahao
PREFILL_POD=prefill-engine-deployment-7f4fc6ddc7-n884l
DECODE_POD=decode-engine-deployment-f6f4b9988-gxlwd
EVIDENCE_DIR=features/kv-pool-layerwise-reuse/evidence/new-run/smoke

kubectl exec -n "${NAMESPACE}" "${PREFILL_POD}" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${NAMESPACE}" "${DECODE_POD}" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
kubectl rollout restart -n "${NAMESPACE}" deployment/mooncake-master-deployment
kubectl rollout status -n "${NAMESPACE}" deployment/mooncake-master-deployment --timeout=180s
kubectl exec -n "${NAMESPACE}" "${PREFILL_POD}" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${NAMESPACE}" "${DECODE_POD}" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
env PYTHONDONTWRITEBYTECODE=1 features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh "${EVIDENCE_DIR}"
```

## Offline Evidence Recheck

Run from the control-repo root after fetching evidence commit
`25bc3f55546de727fcdddfba0110b3d1d2b93614`:

```bash
SMOKE_DIR=features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/smoke
SUMMARY=features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/smoke/summary.json
REPORT=features/kv-pool-layerwise-reuse/full-validation-rerun-2026-07-31.md

sha256sum -c "${SMOKE_DIR}/SHA256SUMS"
jq -e '.status == "failed" and .classification == "production_concurrent_layerwise_kv_load_defect" and .focused_warm_replay.pair_2_3_repeat.failed_rounds == 9 and .focused_cold_control.failed_rounds == 0' "${SUMMARY}"
git ls-files --error-unmatch "${SMOKE_DIR}/SHA256SUMS" "${SUMMARY}" "${REPORT}"
```

## Attempts And Failures

- Formal smoke: direct concurrent case 2 failed the marker hard gate; its
  serial replay passed and the runner exited 1 as designed.
- Focused driver r1: a nonexistent `decode-engine-service` DNS name failed
  before reaching the target path. The evidence-only driver was corrected to
  use proxy `/listEndPoints`, matching the formal runner.
- Focused warm minimization: case 2 alone and pairs 0/2 and 1/2 passed; pair 2/3
  reproduced first at 1/10 and then at 9/30.
- Focused cold control: the stopped-engine empty-Master reset and Decode-only
  restart produced 30/30 passing pair 2/3 rounds and 60/60 zero-hit log
  correlations.
- Stress was not attempted because the confirmed production failure is a
  terminal condition, not a retryable validation-step error.

## Limitations And Final State

The complete run index is
[evidence/full-validation-rerun-20260731T064607Z/README.md](evidence/full-validation-rerun-20260731T064607Z/README.md).
The smoke family contains the formal runner output, full response artifacts,
engine logs, focused warm/cold results, response-ID hit correlation, machine
summary, final reset metrics, and `SHA256SUMS`.

Final cleanup retained the long-running UT, Master, proxy, Prefill, and Decode
Pods. No vLLM API-server child or PID file remains. The final Master reports:

```text
master_key_count 0
master_allocated_bytes 0
master_active_clients 0
```

The confirmed production defect requires a separately authorized source fix
and a new image/run identity. This failed run must not resume at Stress S1.
The evidence establishes the defective concurrent warm-load boundary but does
not identify the exact statement. Frozen source prevented production
instrumentation or repair, and this image has no Stress S1-S3 result.
