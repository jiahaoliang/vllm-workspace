# Private Issue #1 Equivalent Performance Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the minimum four Mooncake performance points derived from `jiahaoliang/vllm-private#1` while proving server-side context admission and attributing any LAYERWISE or REUSE3 slowdown.

**Architecture:** Preserve the accepted A2 DeepSeek-V2-Lite Mooncake implementation and translate the private Issue's workload and scheduler intent into the current PD/TP2 lane. Add opt-in aggregated KVPool timing before traffic, validate it in CPU/mock UT and a new immutable image, then run Test 1 at output 128 and Test 2 at one capacity-bound output-1 point. Existing evidence and handoff machinery remain fail-closed; the old high-hit c8 result is historical evidence, not authorization for this new matrix.

**Tech Stack:** Python 3.12, vLLM/vLLM-Ascend V1 scheduler, Mooncake Transfer Engine, AISBench, pytest, Kubernetes namespace `liangjiahao`, Ascend910 A2, DP/TP multiprocessing.

## Global Constraints

- Preserve untracked `deployment_yaml/`, `dockerfile.vllm23`, and all unrelated user work.
- Use source identities frozen at control `a2df810a`, vLLM `54503ece`, vLLM-Ascend `57d3c214`, and Mooncake `df3f74ed` as the starting point; any source edit creates a new candidate identity.
- Use the private Issue snapshot at `references/snapshots/private-issue-1-performance-test-sample-2026-08-12.md`, not the older `vllm-workspace#1` snapshot, for concrete workload parameters.
- Keep the current Mooncake-backed `AscendStoreConnector`; do not replace it with memcache, `MooncakeLayerwiseConnector`, A3, TP16, GLM-4.7, or DeepSeek-V3.2.
- Test 1 is complete PD inference with output 128 and only BULK versus LAYERWISE.
- Test 2 is output 1 and only BULK versus REUSE3 at one capacity-bound concurrency point; no concurrency staircase.
- Every request fixture has exactly 32,000 input tokens and shares one exact
  28,800-token external prefix (`90%`, 225 of 250 128-token blocks). One
  unmeasured seed request populates that prefix; local vLLM prefix caching
  remains disabled.
- The client is closed-loop (`request_rate=0`) with deterministic fixture seed
  1023. Both Prefill and Decode servers use the private Issue's model seed 1024.
- Formal traffic is invalid unless iteration logs and `/metrics` prove multiple context requests are admitted; client concurrency alone is not evidence.
- Formal performance logs use aggregated timing only. Per-layer range debug and global DEBUG logging are limited to a separate short diagnostic attempt.
- Aggregate KVPool timings are flushed across phase boundaries and retained by
  Prefill/Decode role. Their summed milliseconds are aggregated rank-time for
  same-topology A/B attribution, not end-to-end critical-path wall time.
- All Kubernetes commands explicitly use `-n liangjiahao`; BuildKit, if required, explicitly uses `-n default`.
- Do not mutate serving workloads until a new handoff authorizes the exact source, image, matrix, node, and evidence contract.
- On a confirmed production-source correctness defect, preserve diagnostics and stop performance execution.

---

## File Structure

- Create `references/snapshots/private-issue-1-performance-test-sample-2026-08-12.md`: user-provided private Issue source and parameter mapping.
- Modify `references/sources.md`: index the new external requirement snapshot.
- Create `deployment/performance/issue1_contract.py`: immutable four-point matrix and 90-percent prefix contract.
- Create `deployment/performance/tests/test_issue1_contract.py`: exact matrix, scheduling, and fixture-count tests.
- Modify `deployment/performance/fixtures.py`: generate exact 32K/28.8K
  shared-prefix fixtures for arbitrary supported concurrency.
- Modify `deployment/performance/runtime.py`: render Issue-equivalent scheduler flags and opt-in performance metrics.
- Create `deployment/performance/issue1_runner.py`: execute warmup, one shared
  seed, admission canary, reseed, and formal phases while capturing scheduler,
  vLLM, Mooncake, and KVPool timing evidence. Keep the generation-16 entrypoint
  unchanged.
- Create `deployment/performance/issue1_diagnostics.py` and
  `issue1_report.py`: structure the evidence, classify slowdown, and reject a
  slower result that lacks a cause.
- Create `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/perf_metrics.py`: thread-safe, opt-in aggregated timing collector.
- Modify `pool_worker.py` and `kv_transfer.py`: record session, copy, gate-wait, and final-tail timings.
- Modify `repos/vllm-ascend/vllm_ascend/envs.py`: declare strict opt-in metric controls.
- Create focused vLLM-Ascend UT beside existing AscendStore tests.
- Create a new evidence root and final report under `features/kv-pool-layerwise-reuse/evidence/` and the feature root.

### Task 1: Freeze The Issue-Equivalent Contract

**Files:**
- Create: `features/kv-pool-layerwise-reuse/deployment/performance/issue1_contract.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_issue1_contract.py`
- Modify: `features/kv-pool-layerwise-reuse/references/sources.md`

**Interfaces:**
- Produces: `Issue1Point`, `TEST1_POINTS`, `test2_points(concurrency)`, `build_issue1_run_contract(capacities)`.
- Consumes: exact tokenizer fixtures and existing `Variant` names.

- [x] **Step 1: Write failing contract tests**

Assert that Test 1 contains only `bulk/layerwise`, input 32000, output 128,
concurrency 8, and 125 formal requests. Assert that Test 2 contains only
`bulk/reuse3`, input 32000, output 1, the chosen single concurrency, and 100
formal requests. Assert seed length 28800 and block counts 225/250.

- [x] **Step 2: Run the focused test and verify import failure**

Run through `run-performance-ut.sh` with bytecode and pytest cache disabled.
The expected failure is `ModuleNotFoundError: performance.issue1_contract`.

- [x] **Step 3: Implement immutable contract objects**

Freeze `max_model_len=32768`, `max_num_batched_tokens=32768`,
`gpu_memory_utilization=0.95`, `max_num_seqs` at the target concurrency,
chunked Prefill, async scheduling, no local prefix cache, server seed 1024,
client fixture seed 1023, and request rate zero. Explicitly set Test 1
`long_prefill_token_threshold=4096`
and Test 2 `=768`; otherwise a single long Prefill consumes the full iteration
token budget, reproducing the historical one-context result. Freeze
`max_num_partial_prefills/max_long_partial_prefills` to `8/8` and `40/40` so
future vLLM defaults cannot narrow the intended concurrency.

- [ ] **Step 4: Run the focused test and commit the control-repo files**

Stage only the new snapshot, source index, contract, tests, and this plan.

### Task 2: Add Aggregated KVPool Performance Timing

**Files:**
- Create: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/perf_metrics.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Modify: `repos/vllm-ascend/vllm_ascend/envs.py`
- Test: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_perf_metrics.py`

**Interfaces:**
- Produces: `KVPoolPerfMetrics.record(name, elapsed_ns, bytes_count=0, layer_id=None)`, `time_operation(...)`, `emit(reset)`.
- Emits: one schema-v2 `KVPOOL_PERF_METRICS` JSON object per interval/rank
  containing count, bytes, inclusive sum, nested-safe exclusive sum, p50, p95,
  and max milliseconds.

- [x] **Step 1: Write failing unit tests**

Cover disabled zero-overhead behavior, strict environment parsing, concurrent
recording, percentile calculation, reset semantics, layer grouping, and valid
JSON output. Reject empty, negative, or non-decimal interval values.

- [x] **Step 2: Implement the collector**

Use `time.perf_counter_ns`, a lock, bounded per-event samples, and one daemon
emitter thread only when `VLLM_ASCEND_KVPOOL_PERF_METRICS=1`. Default is off.
Use interval `VLLM_ASCEND_KVPOOL_PERF_METRICS_INTERVAL_SECONDS`, default 10;
the Issue #1 runtime explicitly selects one second and flushes two intervals
before and after admission/formal log capture.

Maintain a thread-local measurement stack when metrics are enabled. Preserve
inclusive duration for audit, but use exclusive duration for causal categories
so nested `reuse3.slot_reload -> layerwise.batch_copy_get ->
mooncake.batch_copy_get` measurements are never added or mislabeled as three
independent costs. The disabled path remains one shared `nullcontext`.

- [x] **Step 3: Instrument causal boundaries**

Record `batch_put_start`, `batch_get_start`, `batch_copy_put`,
`batch_copy_get`, `batch_commit`, `batch_get_end`, `wait_for_layer_load`,
`wait_for_save_layer`, `attention_start_gate`, slot reload, per-layer load wait,
and final save tail. Per-layer `wait_for_layer_load` includes the final layer;
final save has its own tail event. Attach transferred bytes and layer IDs
without logging individual calls.

- [x] **Step 4: Run focused and complete AscendStore CPU/mock UT**

Use the dedicated CPU-only `vllm-ascend-ut` Pod, tar-sync the checkout into a
new temporary workspace, and run explicit pytest targets with bytecode/cache
disabled. Run Ruff and `git diff --check` on the exact source delta.

- [ ] **Step 5: Commit and push vLLM-Ascend**

Commit only the collector, integration points, env declaration, and tests;
push the feature branch, then update `workspace.lock.json` and `repo-state.md`.

### Task 3: Extend Fixtures And Runtime Rendering

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runtime.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Test: corresponding focused performance tests.

**Interfaces:**
- Consumes: `Issue1Point` and the new metric environment variables.
- Produces: exact paired seed/formal JSONL, canonical rendered Kubernetes JSON, and append-only evidence.

- [x] **Step 1: Write failing exact-fixture and render tests**

Prove 32000-token round-trip, one 28800-token shared seed, disjoint
warmup/seed/admission/formal request IDs, exact data counts, target
concurrency, and unique variant differences. Assert every admission/formal
request begins with the same seed tokens and Prefill/Decode both receive
Mooncake TE metrics and KVPool aggregated metric settings.

- [x] **Step 2: Implement fixture and runtime support**

Keep block size 128 and render DP1/TP2 for both tests. Test 1 uses threshold
4096 (`8 * 4096 = 32768`); Test 2 uses threshold 768
(`40 * 768 = 30720 <= 32768`). These are the largest 128-token multiples that
let every intended context receive one chunk in the same iteration budget.

- [x] **Step 3: Implement evidence collection and validity gates**

Capture startup KV capacity, Prefill/Decode per-iteration context requests,
running/waiting/waiting-reason/KV-usage/preemption and request-phase counter
deltas, TE bandwidth/task latency, KVPool aggregate transfer/gate/slot-reload
timing, per-request TTFT/E2E/TPOT/ITL, output correctness, exact external-hit
records, source/image identity, and cleanup. The admission canary stops a point
before formal traffic if client concurrency is not converted to server
contexts.

Require KVPool schema v2 from both roles before formal traffic. The independent
report checker must recompute request fingerprints, server admission,
Prometheus, KVPool timing/schema, and Transfer Engine metrics from raw AISBench
details and server artifacts instead of trusting derived diagnosis JSON.

- [ ] **Step 4: Run all performance tooling UT and commit**

Run the dedicated CPU-only UT entrypoint and compile the changed Python files
without producing bytecode in the checkout.

### Task 4: Build And Revalidate The Instrumented Candidate

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md` only through the functional acceptance workflow.
- Create: new immutable image and functional evidence root.

**Interfaces:**
- Consumes: pushed vLLM-Ascend commit and exact lock.
- Produces: ARM64 image manifest/config digests, source labels, focused/full UT evidence, and real-NPU correctness evidence.

- [x] **Step 1: Verify live cluster and BuildKit state read-only**

Record kube context, Ready nodes, allocatable/requested physical Ascend910,
current serving workloads, BuildKit in `default`, and exact image availability.

- [ ] **Step 2: Build a native ARM64 candidate**

Pin exact vLLM, vLLM-Ascend, and Mooncake commits. Verify embedded HEADs,
labels, platform, manifest/config digests, and metric source hashes.

- [ ] **Step 3: Repeat functional acceptance**

Run focused and complete AscendStore UT plus the existing `kv_producer` and
`kv_both` Mooncake/NPU correctness gates. Verify 27 logical layers, five
physical REUSE3 slots, factor 5.4, no corruption, and final Mooncake cleanup.

- [ ] **Step 4: Publish a new ready handoff generation**

Authorize exactly the four points, topology, 32K/90-percent fixtures, timing
environment, node, image, and evidence checksums. Do not inherit generation 16
traffic authorization implicitly.

### Task 5: Execute The Minimum Four Points

**Files:**
- Create: `features/kv-pool-layerwise-reuse/evidence/layerwise-private-issue1-<run-id>/`
- Create: `features/kv-pool-layerwise-reuse/layerwise-private-issue1-validation-2026-08-12.md`

**Interfaces:**
- Consumes: new ready handoff and prepared fixtures.
- Produces: raw point evidence, direct ratios, capacity/admission proof, and causal timing attribution.

- [ ] **Step 1: Preflight and prepare**

Replay source/image/checksums, verify exact NPU co-location and capacity, create
the CPU-only AISBench client, and generate/replay the 32K paired fixtures.

- [ ] **Step 2: Run Test 1**

Run BULK then LAYERWISE with 8 unmeasured runtime warmups, one shared seed,
one c8 admission canary, a clean reseed, and 125 formal requests at input
32000/output 128/c8. Accept the comparison only if both variants show at least
eight Prefill context requests in an iteration, multiple running requests in
Prometheus, and exact 28,800-token external hits.

- [ ] **Step 3: Select and run Test 2 without a staircase**

Read the post-start Test-2 BULK and REUSE3 capacities. Use c40 only when it
exceeds BULK 32K capacity and fits REUSE3. A different nearest multiple of
eight requires a newly frozen handoff; the runner never changes it silently.
Run 100 formal requests for BULK then REUSE3 at output 1. Prove REUSE3 converts
HBM capacity into higher sustained active contexts, fewer capacity waits, or
fewer preemptions. Higher peak contexts alone are observational evidence and
cannot pass this gate.

- [ ] **Step 4: Attribute any slowdown**

Classify it in order: Prefill scheduler/admission, KV capacity not converted to
running contexts, deferred KV waits, Decode capacity/admission, Mooncake
transport/session overhead, layer/final-tail/reuse-slot gates, or compute batch
efficiency. Preserve Prefill and Decode timing separately. A slower result is
complete only when its classification is backed by raw evidence and marked
resolved. Otherwise automatically run one targeted short diagnostic A/B for
Test 1 and do not repeat the 125-request formal point. For Test 2, run one c40
wave each for BULK, LAYERWISE, and REUSE3 without adding a formal point:
`LAYERWISE/BULK` isolates ordinary layerwise cost and `REUSE3/LAYERWISE`
isolates buffer-reuse cost. It may replace the cause only when every diagnostic
role emits valid range events, outputs match per `data_id`, the slowdown
reproduces, and measured exclusive timing is material. Background-thread
transfer or gate rank-time additionally requires a same-role main-thread
`critical.*` wait/tail delta that explains at least 50 percent of the observed
wall-time gap; otherwise preserve `unresolved`.

- [ ] **Step 5: Validate, restore, report, and publish**

Require all requests successful, output correctness, exact hit evidence,
complete timing summaries, checksum replay, restored workloads, empty
Mooncake, and released NPU memory. Report raw values and ratios without a
statistical significance claim.

## Self-Review

- The plan preserves the private Issue's 32K, 90-percent prefix, deterministic,
  closed-loop workload while explicitly excluding incompatible A3/TP16/
  memcache components.
- It retains Test 1 output 128 and Test 2 output 1 as required by the user.
- It replaces the rejected concurrency staircase with one capacity-bound point.
- It preserves exactly four formal points; the conditional Test-2 LAYERWISE c40
  point is a one-wave diagnostic control only.
- It cannot produce another un-attributable slow result because instrumentation
  and service-side admission are preconditions, not post-run follow-ups.
- It cannot reuse generation 16 beyond its authorization because a new source,
  image, correctness root, and handoff generation are mandatory.

## Execution Status (2026-08-13)

- Final local vLLM-Ascend candidate:
  `8653c6c5e3b554719c8347a0a36fe2109e6a36d9`, tree
  `156a2ebe414aa82bc68102479a61fcca88f3332f`, clean and DCO-signed.
- Real frozen-vLLM Scheduler/KV allocator validation passed with a 28,800-token
  external match: c8 scheduled eight running requests at 3,200 tokens each;
  c40 scheduled forty running requests at 768 tokens each; both had zero
  waiting requests after the first schedule call.
- Final-tree CPU/mock results: focused instrumentation `191 passed`, complete
  AscendStore `529 passed`, env plus platform `53 passed, 1 skipped`, and
  control performance harness `183 passed`.
- Static gates passed with Ruff 0.16.2 rules `E4,E7,E9,F,I`, Bash syntax,
  in-memory compilation of all 15 changed Python files, and `git diff --check`.
- Generation 16 was replayed through the new `run` entrypoint and rejected
  before cluster mutation because its source identity and authorized scope do
  not cover this four-point lane.
- The candidate is not yet fetchable from the configured source remote. The
  remote feature branch remains at parent `57d3c214e642cdbb529400f0742d1a98a8d38708`;
  image build, lock refresh, control commit, functional acceptance, handoff,
  and formal traffic remain pending explicit authorization for that push.
