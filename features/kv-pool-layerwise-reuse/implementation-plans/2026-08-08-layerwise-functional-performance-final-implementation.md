# Mooncake Layerwise Functional And Performance Final Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking. The user authorized automatic progression through DP1 and DP2 without further human intervention.

**Goal:** Prove or repair Mooncake compute-side shared-buffer correctness, publish an immutable generation-1 functional handoff, and execute the complete approved DP1/DP2 AISBench characterization with checksummed evidence and restored Kubernetes state.

**Architecture:** Use one serial owner for the shared NPU runtime. First retest the current `2d179d07` candidate in isolation; only modify production source if that clean run reproduces corruption. Freeze one native ARM64 derived image, publish a fail-closed handoff, then let the existing performance runner execute DP1 and automatically resume DP2 in one unchanged run root.

**Tech Stack:** Python 3.12, pytest, vLLM/vLLM-Ascend, Mooncake, Kubernetes, Ascend910, nerdctl/containerd `k8s.io`, AISBench 3.1.0 at `3fd27b4a5fd022fcb5484fb084307f49955491ba`, jq, sha256sum.

## Global Constraints

- Work in `/root/ljh/vllm-workspace` on control branch `kv-pool-layerwise-reuse` and the existing vLLM-Ascend feature branch.
- Use namespace `liangjiahao` explicitly for every UT, serving, benchmark, log, exec, rollout, and cleanup operation.
- Preserve unrelated dirty and untracked paths. Stage only named task-owned files.
- Do not modify memcache behavior or the public slot-release lifecycle.
- CPU/mock tests cover every role. Real NPU functional tests cover `kv_producer` and `kv_both` plus a no-reuse oracle.
- Never rebuild the server with Dockerfile, BuildKit, `nerdctl build`, or `docker build`.
- If source changes, patch all cumulative final Python files into the frozen `45b2e785` base and create the next image with `nerdctl commit`.
- Every functional/performance retry uses a new UTC identifier and preserves prior evidence.
- A production correctness, identity, health, or evidence failure is fail-closed. A valid performance saturation boundary is retained as a result.
- Do not create a control-repository commit between the ready handoff transition and completion of DP2.

## File Map

- Conditional production fix:
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- Remove temporary diagnostics:
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py`
- Conditional regression tests:
  `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`
  and/or
  `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_scheduler.py`
- Handoff transition implementation and tests:
  `features/kv-pool-layerwise-reuse/deployment/performance/handoff.py` and
  `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_handoff.py`
- Functional identity/state:
  `features/kv-pool-layerwise-reuse/deployment/validation-identity.json`,
  `features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml`,
  `features/kv-pool-layerwise-reuse/deployment/60-vllm-ascend-ut-pod.yaml`,
  `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`,
  `workspace.lock.json`, and
  `features/kv-pool-layerwise-reuse/repo-state.md`
- Ready transition:
  `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Generated functional evidence:
  `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-$FUNCTIONAL_RUN_ID/`
- Generated performance evidence:
  `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-$PERFORMANCE_RUN_ID/`
- Final raw report:
  `features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md`

---

### Task 1: Freeze The Plan And Establish Exclusive Runtime Ownership

**Files:**
- Modify: the two implementation-plan files only
- Generate: a new run-local Phase 0 inventory under `/tmp`

**Interfaces:**
- Consumes: current Git state, Pods in `liangjiahao`, exact vLLM engine PIDs, physical NPU processes, and Mooncake metrics.
- Produces: an idle environment with no vLLM NPU process and Mooncake metrics `0/0/0`.

- [ ] Commit the approved status and this final implementation plan as an explicit two-file plan commit.
- [ ] Push the plan commits normally and verify local/remote equality before source execution.
- [ ] Re-query root and nested repository branch, commit, remotes, lock, and dirty state.
- [ ] Capture `kubectl get pods -n liangjiahao -o wide`, exact Prefill/Decode command lines, `npu-smi info`, and Master metrics into a new `/tmp/layerwise-exclusive-audit-$RUN_ID` directory.
- [ ] Confirm no other functional/performance runner or listener process is active.
- [ ] Stop exact residual Prefill and Decode engines with `/opt/vllm-layerwise/stop-engine.sh` and wait for zero NPU processes.
- [ ] Restart only `deployment/mooncake-master-deployment` in `liangjiahao` and require Master `0/0/0`.
- [ ] Recreate the Prefill Pod when its writable layer contains `[DEBUG-8f31]`; verify the fresh container imports the committed tracker.
- [ ] Preserve and revalidate the CPU-only `layerwise-performance-aisbench` Pod on `m1`.

Expected gate: no server traffic, no NPU process, no Mooncake allocation, and no overlapping owner.

---

### Task 2: Run A Clean Isolated Test Of The Existing Candidate

**Files:**
- Generate: `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-$FUNCTIONAL_RUN_ID/`
- Read: candidate image and committed vLLM-Ascend `2d179d07c86e5f820fd6591c0c7fdef2b5132c14`

**Interfaces:**
- Consumes: the frozen deterministic request and response validator from the latest functional evidence.
- Produces: a clean pass/fail decision for the interference hypothesis.

- [ ] Remove only this session's temporary tracker diagnostics with `apply_patch`; verify the nested diff is empty.
- [ ] Verify candidate image platform, manifest/config digests, source labels, and imported Python SHA256 values.
- [ ] Copy the latest functional runner and validator into a fresh run root, updating only the run ID and expected immutable image identity.
- [ ] Before execution, assert exactly one Prefill Pod, zero Prefill/Decode engine PIDs, zero NPU processes, and Master `0/0/0`.
- [ ] Execute baseline, one `kv_producer` request, and `kv_both` cold/warm requests without a concurrent runner.
- [ ] Run the exact response oracle and archive range traces, command lines, Pod identity, NPU release, and Master cleanup.
- [ ] If every oracle passes, record `SOURCE_FIX_REQUIRED=false` and continue to Task 4.
- [ ] If corruption reproduces, record `SOURCE_FIX_REQUIRED=true` and continue to Task 3 without discarding the failed run.

Expected pass: producer and both responses equal the baseline exactly, usage/finish reason match, and final cleanup is `0/0/0`.

---

### Task 3: Repair The Post-Tracker Decode Filter Only If Required

**Files:**
- Modify conditionally: `pool_worker.py`
- Modify conditionally: `test_kv_transfer.py` and/or `test_pool_scheduler.py`
- Restore: `mooncake_session_tracker.py` with no diagnostics

**Interfaces:**
- Consumes: tracker entries `(key, block_index)` from `prepare_load_entries()` and the observed per-layer transfer key counts.
- Produces: complete committed full-block plus partial-block load metadata for every shared-buffer decode step.

- [ ] Add the smallest temporary observation after `_prepare_mooncake_get_session()` and at `LayerBatchBuilder` input to locate the first point that drops committed full blocks.
- [ ] Run one isolated deterministic producer request and preserve the before/after key-index evidence.
- [ ] Write a failing CPU/mock regression that supplies tracker entries for full block indexes `0..3` plus partial index `4` and asserts the resulting layer load task contains all required indexes.
- [ ] Run the focused test in `liangjiahao/vllm-ascend-ut` and require the expected RED assertion before source implementation.
- [ ] Implement the minimal downstream filtering/range fix while leaving role policy, memcache, and terminal release unchanged.
- [ ] Remove all temporary observations.
- [ ] Run the focused regression and adjacent Mooncake session/range tests to green.
- [ ] Review the production diff for unrelated changes, then commit and push vLLM-Ascend.

Expected gate: the regression proves the same metadata shape observed on NPU and passes with no debug logging.

---

### Task 4: Run Complete CPU/Mock And Static Gates

**Files:**
- Read/test: final vLLM-Ascend source and control performance/deployment tests
- Generate: immutable CPU test logs in the new functional evidence root

**Interfaces:**
- Consumes: final source tree from Task 2 or Task 3.
- Produces: all role, AscendStore, MLA, layerwise, deployment, performance, and static gates.

- [ ] Record source branch/commit/dirty identity before every tar sync.
- [ ] Run focused Mooncake shared-buffer/session tests.
- [ ] Run the complete AscendStore suite plus MLA regression coverage.
- [ ] Run layerwise/model-runner tests.
- [ ] Run deployment/validation/performance mock suites, including all four role-policy cases and the current 44 performance tests.
- [ ] Run Ruff check/format through `/workspace/tools/ruff`, Python compilation, shell syntax, and `git diff --check`.
- [ ] Require every explicit target to pass with bytecode and pytest cache disabled.

Expected gate: no failed required target; real Mooncake/NPU-only tests may skip only when explicitly documented as outside CPU/mock.

---

### Task 5: Freeze Source And Materialize The Final Image

**Files:**
- Modify: lock, repo-state, validation identity, Prefill/UT image references, and source runner identity as required
- Generate: OCI inspection and patched-file evidence

**Interfaces:**
- Consumes: final source commit and the frozen native base image.
- Produces: one reusable native `linux/arm64` image for functional and performance execution.

- [ ] Verify and push final vLLM-Ascend source; capture local/remote equality.
- [ ] If no source fix was required, revalidate and reuse the existing `2d179d07` derived image without changing its manifest.
- [ ] If source changed, create a temporary container from the exact `45b2e785` base, patch every cumulative final production Python file by tar, and verify host/container SHA256 equality.
- [ ] Create the derived image with `nerdctl -n k8s.io commit`, including exact vLLM, vLLM-Ascend, and Mooncake source labels.
- [ ] Remove the temporary container after inspection and record the removal.
- [ ] Verify platform, manifest/config digests, parent layers, patched paths, import resolution, and all file SHA256 values.
- [ ] Update only functional-owned identity/manifests/state paths; run their CPU tests and static checks.

Expected gate: the image imports the exact final checkout and can be reused without a runtime source overlay.

---

### Task 6: Execute Formal Functional Acceptance

**Files:**
- Generate: the final `shared-buffer-functional-$FUNCTIONAL_RUN_ID` evidence tree, report, config snapshot, and `SHA256SUMS`

**Interfaces:**
- Consumes: final source/image identity and deterministic request.
- Produces: all handoff functional gates with immutable evidence.

- [ ] Start from a clean Prefill Pod, zero NPU processes, and Master `0/0/0`.
- [ ] Run the no-reuse baseline oracle.
- [ ] Run real-NPU `kv_producer` reuse and real-NPU `kv_both` cold/warm reuse.
- [ ] Require exact response equality, usage/finish reason equality, correct ranged transfers, 27-layer physical-slot proof, expected KV-memory factor, and no save-gate timeout/corruption.
- [ ] Stop engines, wait for NPU release, and require final Master `0/0/0`.
- [ ] Generate the functional report and validation config snapshot.
- [ ] Generate and replay root `SHA256SUMS`; run the fail-closed functional report checker.

Expected gate: every Functional Acceptance row has direct PASS evidence.

---

### Task 7: Implement And Test The Handoff Transition Commit Rule

**Files:**
- Modify: `deployment/performance/handoff.py`
- Modify: `deployment/performance/tests/test_handoff.py`

**Interfaces:**
- Consumes: the recorded control source commit and current control `HEAD`.
- Produces: acceptance of exact equality or one direct handoff-only transition child, while rejecting unrelated drift.

- [ ] Write a failing test where recorded control commit is `HEAD^`, current `HEAD` changes only `performance-validation-handoff.md`, and nested source identities remain exact.
- [ ] Write rejecting tests for a non-parent commit and for a transition commit that changes any path other than the handoff.
- [ ] Run `test_handoff.py` in the CPU-only UT Pod and prove RED.
- [ ] Implement the minimal control-source validator using `git rev-parse HEAD^` and `git diff-tree --name-only` for the current commit; preserve exact checks for nested repositories.
- [ ] Run focused and full performance tests in the UT Pod, then Ruff, compile, and `git diff --check`.
- [ ] Commit the validator together with final functional state/evidence, before the handoff transition commit.

Expected gate: only the direct, handoff-only child is accepted.

---

### Task 8: Publish And Verify The Generation-1 Handoff

**Files:**
- Modify: `performance-validation-handoff.md`

**Interfaces:**
- Consumes: committed functional control parent, exact nested commits, final image, and functional checksum root.
- Produces: one committed `READY_FOR_PERFORMANCE_VALIDATION` generation accepted by the listener.

- [ ] Populate every Source, Image, Functional Acceptance, and Evidence Identity field with immutable values.
- [ ] Authorize Mooncake `BULK(use_layerwise=false)`, `LAYERWISE`, Prefill `REUSE3`, and the no-reuse pure-consumer Decode companion without authorizing consumer-side reuse.
- [ ] Remove the blocker, replace every handoff placeholder with verified evidence, set generation 1, and set ready/status fields last.
- [ ] Commit only the handoff as the direct child of the recorded functional control commit and push normally.
- [ ] Run the listener/check command against the committed file and require zero validation errors.
- [ ] Freeze this control checkout until DP2 completes.

Expected gate: listener observation has `valid=true`, generation 1, and the committed handoff digest.

---

### Task 9: Revalidate Performance Preparation And Preflight

**Files:**
- Read/replay: `evidence/performance-preparation-20260808T170000Z/`
- Generate if drifted: a new preparation evidence root
- Generate: the new performance run root and pre-run snapshot

**Interfaces:**
- Consumes: ready handoff, retained CPU-only client Pod, exact fixtures, and six-card server capacity.
- Produces: a preflight-authorized DP1 run root.

- [ ] Replay the preparation `SHA256SUMS` and verify `server_authorized=false` in preparation steps.
- [ ] Verify client Pod placement/resources/rootfs, Python, uv, AISBench, tokenizer, fixtures, and package lock.
- [ ] Re-run all performance CPU tests.
- [ ] If client state drifted, execute `prepare` under a new ID and use the new checksummed state.
- [ ] Invoke `run --topology dp1`, which must revalidate handoff/source/image/functional evidence before mutation.
- [ ] Capture pre-run Deployments, ConfigMaps, Pods, processes, physical NPU allocation, and Mooncake state.
- [ ] Require the BULK, LAYERWISE, and REUSE3 correctness/transfer-path canaries to pass.

Expected gate: the first formal benchmark request is impossible until every preflight check is green.

---

### Task 10: Execute DP1, Automatically Resume DP2, And Check Evidence

**Files:**
- Generate: one unchanged `/tmp/layerwise-performance-$PERFORMANCE_RUN_ID` run root

**Interfaces:**
- Consumes: approved matrix and preflight-authorized server/client state.
- Produces: complete DP1/DP2 raw measurements, attempts, telemetry, and stop decisions.

- [ ] Complete DP1 4K/16K/32K rotations, output profiles, concurrency scan, warmups, three formal repetitions, Master resets, telemetry, stable checks, and adaptive stops.
- [ ] Run `python3 -m performance.report check --root "$RUN_ROOT" --scope dp1`.
- [ ] If DP1 is valid, revalidate unchanged handoff/source/image/client identities and immediately run `run --topology dp2 --output "$RUN_ROOT" --resume`.
- [ ] Complete DP2 reverse rotations and aggregate concurrency `2/4/8/16/32/64`, including per-rank imbalance evidence.
- [ ] Run the full report checker and replay `$RUN_ROOT/SHA256SUMS`.
- [ ] Preserve every failed or insufficient attempt under a unique attempt ID.

Expected gate: all required points exist or have a contract-valid adaptive/hard boundary, with no identity or correctness failure.

---

### Task 11: Restore, Publish, And Complete The Audit

**Files:**
- Create: repository performance evidence root
- Create: final raw report
- Modify: evidence index and performance-owned documentation

**Interfaces:**
- Consumes: valid run root and pre-run Kubernetes snapshot.
- Produces: restored cluster, immutable repository evidence, published report, and remote equality.

- [ ] Stop all run-owned engines and prove physical NPU release.
- [ ] Return Mooncake to its required empty state.
- [ ] Restore exact pre-run Deployments and ConfigMaps; retain the CPU-only AISBench Pod unless its contract requires replacement.
- [ ] Render raw rows, direct ratios, diagnostics, attempts, capacity boundaries, and exclusions without performance PASS/FAIL or significance claims.
- [ ] Import the run root without rewriting raw artifacts and generate repository-root checksums.
- [ ] Run full performance UT, Ruff, compile, shell syntax, report checker, checksum replay, namespace scan, image/source replay, and matrix-to-evidence audit.
- [ ] Commit only performance-owned paths, reconcile state only if endpoint identity requires it, push normally, and verify remote equality.
- [ ] Verify that `performance-validation-handoff.md` contains the usable final image identity and that every completion criterion in the approved execution plan has direct evidence.

Expected gate: functional and performance deliverables are reproducible, checksummed, committed, pushed, and the cluster is restored.
