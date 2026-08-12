# Mooncake Layerwise High-Hit Performance Validation Implementation Plan

> **For agentic workers:** Execute this plan inline and keep every checkbox current. Do not publish a performance comparison unless the formal requests prove the required external Prefix KV hit rate.

**Goal:** Replace the cold-cache characterization with a DP1 comparison of BULK, LAYERWISE, and REUSE3 under identical 16K requests whose Prefill external KV cache hit rate is 81.25 percent.

**Architecture:** Generate paired seed/formal fixtures: each 13,312-token seed is the exact first 104 blocks of one 16,384-token formal prompt. For each variant, warm the runtime, clear Mooncake, populate all seed prefixes outside the measured interval, run one 64-request formal AISBench attempt without clearing Mooncake, and reject the point unless all 64 Prefill lookups report exactly 13,312 hit tokens.

**Tech Stack:** Python 3.12, pytest, AISBench 3.1.0, Kubernetes, Mooncake, Ascend910, vLLM-Ascend structured runtime rendering.

## Global Constraints

- Work on control branch `kv-pool-layerwise-reuse`; preserve `deployment_yaml/`, `dockerfile.vllm23`, prior evidence, and unrelated changes.
- Use Kubernetes namespace `liangjiahao` explicitly for all client, UT, serving, evidence, and restoration commands.
- Keep the same server image, DP1/TP2 topology, 16,384 formal input tokens, output 1, concurrency 8, 8 warmup requests, 64 seed requests, and 64 formal requests across all three variants.
- Define the cached prefix as 13,312 tokens = 104 blocks at block size 128, yielding 104/128 = 81.25 percent external Prefix KV hits.
- Exclude warmup and seed traffic from performance measurements. Clear Mooncake after warmup and before seed, but never between seed and formal.
- Require 64/64 successful seed and formal responses, exact token counts, exact fixture pairing, `master_key_count=6656` after seed, and exactly 64 formal Prefill log records with `kvpool hit tokens: 13312`.
- Use one formal attempt, no automatic retry, no performance timeout, no outlier removal, and no statistical-significance claim.
- Run CPU/mock tests in the CPU-only `liangjiahao/vllm-ascend-ut` Pod before NPU execution.
- Retain failed serving Pods and logs when startup or execution fails; do not delete a failed diagnostic Pod.

---

### Task 1: Freeze The High-Hit Contract

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/contract.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_contract.py`

**Interfaces:**
- Produces `SEED_TOKENS=13312`, `SEED_BLOCKS=104`, `EXPECTED_HIT_RATE=0.8125`, and `SEED_REQUEST_COUNT=64`.
- Produces exactly three points: `dp1-16384-{bulk,layerwise,reuse3}-o1-c8`.
- Records seed count, seed length, expected hit tokens/blocks/rate, and three expected points in `run-contract.json`.

- [x] Add failing exact-contract tests.
- [x] Implement the constants, matrix, and run-contract fields.
- [x] Run focused contract tests in `liangjiahao/vllm-ascend-ut`; `5 passed`.

### Task 2: Generate Paired Seed And Formal Fixtures

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py`

**Interfaces:**
- Produces `seed.jsonl` with 64 rows and `formal-1.jsonl` with 64 paired rows.
- Guarantees each seed token sequence equals `formal_tokens[:13312]` and each formal suffix contains 3,072 tokens.
- Records `seed_ids`, pair identities, token lengths, and checksums in `manifest.json`.
- Accepts `phase=seed` in attempt contracts while keeping the result point input length at 16,384.

- [x] Add failing pairing, cardinality, checksum, and seed-config tests.
- [x] Build formal prompts first and derive seed text from their exact token prefixes.
- [x] Extend manifest and attempt-contract validation for `seed`.
- [x] Run focused fixture tests; included in the complete `105 passed` suite.

### Task 3: Enforce The Seed-To-Formal Lifecycle

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`

**Interfaces:**
- Executes `warmup -> clear -> seed -> assert seeded -> formal without clear` once per variant.
- Produces `seed/attempt-1/raw/summary.json`, `formal-1/attempt-1/raw/prefill-hit.log`, and `hit-validation.json`.
- Parses the common scheduler line `Reqid: ..., Total tokens 16384, kvpool hit tokens: 13312, need to load: 13312` and requires exactly 64 matches.

- [x] Add failing lifecycle tests proving there is no cleanup between seed and formal.
- [x] Add pure hit-log parsing tests for missing, duplicate, wrong-length, and wrong-hit records.
- [x] Implement seed visibility probes and formal hit validation.
- [x] Preserve failure diagnostics and run focused runner tests; included in the complete `105 passed` suite.

### Task 4: Make Evidence And Reports Fail Closed

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/report.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_report.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/README.md`
- Create: `features/kv-pool-layerwise-reuse/2026-08-12-layerwise-high-hit-performance-validation-design.md`

**Interfaces:**
- Rejects old five-point/cold-cache evidence under the new run contract.
- Requires paired fixtures, one seed attempt and one formal attempt per point, valid seed/formal summaries, and valid formal hit evidence.
- Renders three aggregate rows, 192 formal request rows, hit-contract fields, and direct LAYERWISE/BULK, REUSE3/LAYERWISE, and REUSE3/BULK ratios.

- [x] Add failing evidence-tree and report tests.
- [x] Implement exact high-hit evidence validation and reporting.
- [x] Update the executable runbook and approved design description.
- [x] Run the complete CPU/mock performance test suite (`105 passed`) and `git diff --check`.

### Task 5: Publish The Executable State

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Modify: `workspace.lock.json` only if a nested source/image identity changes.

**Interfaces:**
- Produces a committed control state whose handoff authorizes the high-hit three-point run with the unchanged validated server image.

- [ ] Review exact diffs and source/image identities.
- [ ] Commit and push only owned paths.
- [ ] Advance the handoff generation without claiming new functional validation.
- [ ] Run the handoff checker against the published commit.

### Task 6: Execute And Publish The NPU Run

**Files:**
- Create: `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-high-hit-<run-id>/`
- Create: `features/kv-pool-layerwise-reuse/layerwise-performance-high-hit-validation-2026-08-12.md`
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`

**Interfaces:**
- Consumes the exact published high-hit contract, fixtures, image, and available four-NPU single-node deployment.
- Produces immutable raw evidence, three valid performance rows, 192 formal request rows, exact hit validation, checksums, and restoration proof.

- [ ] Recheck cluster context, `liangjiahao` resources, four replaceable physical Ascend910 devices, and AISBench/Prefill/Decode node placement.
- [ ] Run `prepare` for the published tooling and verify paired fixture checksums.
- [ ] Run the DP1 three-point benchmark once; retain failed Pods/logs if startup fails.
- [ ] Validate the evidence tree, render the report, and independently replay SHA-256 checksums.
- [ ] Compare the three variants without extrapolating beyond 16K, c8, o1, one repetition, and 81.25 percent hits.
- [ ] Import, commit, and push the immutable result artifacts; update the handoff with the usable image and report identity.
