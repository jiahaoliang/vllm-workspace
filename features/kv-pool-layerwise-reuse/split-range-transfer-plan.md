# Mooncake Layer Range Transfer Commit Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `87c31d1e8 feat(kv_pool): add Mooncake layer range transfer` into four independently reviewable commits while incorporating the two accepted findings in `review-decisions.md`.

**Architecture:** Keep `LayerBatchBuilder` as the shared key-major metadata boundary, make LayerThread task finalization exception-safe before adding ranged behavior, then add save and load state machines separately. Each commit carries its own focused tests and remains compatible with the later Mooncake session orchestration commit.

**Tech Stack:** Python 3.14, PyTorch CPU test environment, pytest, Ruff, Git interactive-history reconstruction through non-interactive cherry-pick/reset commands.

**Status:** Completed on 2026-07-16. Final source HEAD: `6a825ca54761131c9b73c8871a886381c49513d8`.

## Global Constraints

- Preserve Memcache flat-GVA behavior and Yuanrong/KeyLayer behavior.
- The design snapshot has precedence over `implementation-plan.md`.
- Tests must be written and observed failing before the corresponding production fix.
- Source history changes stay in `repos/vllm-ascend`; the control repo records only plans and workspace state.
- Do not modify or commit the local `review-guide.md`.

---

### Task 1: Build Key-Major Layer Range Batches

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: `ReqMeta.save_block_keys`, `ReqMeta.load_block_keys`, `SharedBlockData`, `LayerRangeReqMeta`.
- Produces: `LayerBatchBuilder.build_shared(..., is_save)` and `build_addrs(...)` support for key-major range batches.

- [ ] Add tests for Memcache `block_keys=None`, key-major buffer/size/offset calculation, and aligned filtering of `None` keys.
- [ ] Confirm the tests fail on the parent of `87c31d1e8` because range building is absent.
- [ ] Add `_request_block_keys`, `_build_key_major_shared`, `_uses_block_keys`, and the `LayerRangeReqMeta` branch in `build_addrs`.
- [ ] Run `TestLayerBatchBuilder` and the complete `test_kv_transfer.py`.
- [ ] Commit as `feat(kv_pool): build Mooncake layer range batches`.

### Task 2: Make Layer Task Finalization Exception-Safe

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: `LayerTransferTask.block_ranges`, sending/receiving layer events, request queues.
- Produces: exactly-once queue/event completion and balanced sending request accounting on success and exception.

- [ ] Add failing tests injecting `build_addrs` exceptions into legacy LayerSending/LayerRecving handlers; assert one `task_done`, one layer event, no `stored_requests` residue, and no successful `BlockStored` event.
- [ ] Move sending request decrement/final-finished accounting into a `finally`-owned helper using request IDs from the original task.
- [ ] Move receiving queue/event completion into a `finally`-owned helper and mark affected blocks invalid on unexpected exceptions.
- [ ] Run the new exception tests and existing GVA LayerThread tests.
- [ ] Commit as `refactor(kv_pool): make layer transfer completion exception-safe`.

### Task 3: Add Mooncake Ranged Layer Save

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: `LayerRangeReqMeta`, Backend `batch_copy_put`, `batch_commit`, `batch_revoke`.
- Produces: per-batch active save keys, per-key revoke/filtering, final commit, and `_put_started_keys` cleanup.

- [ ] Add failing tests for positive ranged results, per-key negative results, short/long/non-integer results, commit failure, and two requests sharing one save key.
- [ ] Make `_build_key_major_shared(..., is_save=True)` stably deduplicate object keys while retaining the first aligned block ID; preserve duplicates for load.
- [ ] Add SendingThread range dispatch, active-key filtering, revoke, commit, and tracker cleanup.
- [ ] Confirm `SharedBlockData`, `batch_copy_put`, and `batch_commit` contain a shared save key once.
- [ ] Run sending tests and complete `test_kv_transfer.py`.
- [ ] Commit as `feat(kv_pool): add Mooncake ranged layer save`.

### Task 4: Add Mooncake Ranged Layer Load

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: `LayerRangeReqMeta`, Backend `batch_copy_get`, shared invalid-block set/lock, load abort event.
- Produces: per-key ranged reads, exact invalid-block reporting, later-layer filtering, and batch abort notification.

- [ ] Add failing tests for negative ranged read, malformed result shapes, read exceptions, and one remote key copied into two local block IDs.
- [ ] Add ReceivingThread range dispatch, active-load state, key-to-block mapping, invalid reporting, and abort handling.
- [ ] Confirm duplicate load keys remain duplicated in `batch_copy_get` with distinct local buffers.
- [ ] Run receiving tests and complete `test_kv_transfer.py`.
- [ ] Commit as `feat(kv_pool): add Mooncake ranged layer load`.

### Task 5: Replay, Verify, and Publish

**Files:**
- Update: `workspace.lock.json`
- Update: `features/kv-pool-layerwise-reuse/repo-state.md`
- Update: `features/kv-pool-layerwise-reuse/status.md`
- Update: `features/kv-pool-layerwise-reuse/sync-log.md`
- Keep untracked: `features/kv-pool-layerwise-reuse/review-guide.md`

- [ ] Cherry-pick the original later orchestration and documentation commits onto the four new commits, resolving dependencies without changing their intended behavior.
- [ ] Run the complete AscendStore CPU suite, focused Ruff, `git diff --check`, and `git show --check` for every feature commit.
- [ ] Force-push the rewritten source branch with `--force-with-lease`.
- [ ] Refresh workspace lock/state files and update `review-decisions.md` to the rewritten range commit SHAs and implementation status.
- [ ] Run `lock-repos.ps1`, `status-all.ps1`, and `validate-workspace.ps1`.
- [ ] Commit and push the control repo state.
