# Mooncake Revoke Ownership And Full Validation Implementation Plan

> **For agentic workers:** Execute this plan inline, task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt Mooncake `df3f74ed8ebdb0c935554beea6299a9f11c723e2`, retain local ownership until revoke succeeds, build an exact native ARM64 image, and complete A2 full validation.

**Architecture:** `KVPoolWorker` and `KVCacheStoreLayerSendingThread` share mutually exclusive writable and revoke-pending key sets. The sending thread owns ordered, deduplicated revoke retries and releases tracker state only for keys whose Mooncake revoke returns zero. Validation freezes exact source and image identity before running the stable gates serially.

**Tech Stack:** Python 3.12, vLLM-Ascend AscendStore, Mooncake, unittest/pytest, Ruff, Kubernetes, BuildKit, nerdctl, ARM64 Ascend A2.

## Global Constraints

- Mooncake is read-only and fixed at `df3f74ed8ebdb0c935554beea6299a9f11c723e2`.
- vLLM is fixed at `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`.
- Keep all seven Mooncake session/range APIs and the `Backend` interface unchanged.
- Every nonzero revoke result remains a failure; `INVALID_PARAMS=-600` is not success.
- UT, serving, and stress workloads use explicit namespace `liangjiahao`; only `buildkitd` uses `default`.
- CPU/mock UT uses the dedicated CPU-only Pod, tar synchronization, `PYTHONDONTWRITEBYTECODE=1`, and disabled pytest cache.
- Do not enable or claim FabricMem/`ShmHelper` coverage.
- Preserve unrelated `deployment_yaml/`, `dockerfile.vllm23`, and historical evidence.

---

### Task 1: Revoke Ownership Regression Tests

**Files:**
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_worker.py`

**Interfaces:**
- Consumes: `KVCacheStoreLayerSendingThread.add_revoke_request(keys)` and `KVPoolWorker._prepare_mooncake_put_session(request)`.
- Produces: executable expectations for `_put_revoke_pending_keys`, retry order, task deduplication, fail-closed put-start, and tracker transitions.

- [x] Add tests for nonzero-to-success retry, partial success, exception, malformed results, three-attempt exhaustion, and later-request retry.
- [x] Add tests for queued/inflight deduplication, queue failure, pending ranged-write suppression, and pending PutStart suppression.
- [x] Add mixed commit/revoke assertions proving only successful commit/revoke keys release tracker ownership.
- [x] Tar-sync the dirty TDD checkout to an isolated directory in `liangjiahao/vllm-ascend-ut` and verify the new focused tests fail for the expected missing behavior.

### Task 2: Ownership State And Retry Implementation

**Files:**
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`

**Interfaces:**
- Consumes: shared `set[str]` ownership state guarded by the existing put-start lock.
- Produces: `_put_started_keys` for writable sessions and `_put_revoke_pending_keys` for retained sealed sessions, always mutually exclusive.

- [x] Initialize and pass the shared pending set without changing public Backend or Mooncake APIs.
- [x] Move revoke targets from started to pending before cleanup; attempt at most three times, retry only failed keys, and sleep `0.1s` then `0.5s`.
- [x] Clear pending and `MooncakeSessionTracker` only for result-zero keys; retain both after exception, malformed shape, nonzero result, or exhaustion.
- [x] Deduplicate queued/inflight cleanup by key; on queue failure remove only queued markers.
- [x] Make pending keys trigger cleanup and fail closed for the current request; suppress ranged writes for pending keys.
- [x] Commit only successful keys; send failed keys to revoke and retain ownership until revoke succeeds.

### Task 3: Source Gates And Publication

**Files:**
- Verify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/{pool_worker.py,kv_transfer.py}`
- Verify: `repos/vllm-ascend/tests/ut/distributed/ascend_store`

**Interfaces:**
- Produces: one signed-off source commit named `fix(kv_pool): retain failed Mooncake revoke ownership` and matching local/origin SHA.

- [x] In `liangjiahao/vllm-ascend-ut`, run focused tests and the complete `tests/ut/distributed/ascend_store` suite.
- [x] Run `/workspace/tools/ruff check`, `py_compile`, and `git diff --check` with bytecode/cache disabled.
- [x] Commit the four source/test files, push the feature branch normally, and verify local/origin left-right count is `0 0`.

### Task 4: Freeze Control And Image Identity

**Files:**
- Modify: `workspace.lock.json`
- Modify: `features/kv-pool-layerwise-reuse/Dockerfile.a2`
- Modify: `features/kv-pool-layerwise-reuse/deployment/*`
- Modify: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify: `features/kv-pool-layerwise-reuse/sync-log.md`
- Modify: `features/kv-pool-layerwise-reuse/references/snapshots/research-mooncake-collaborator-update-2026-08-07.md`
- Create: a dated tracker and `evidence/full-validation-rerun-<UTC run ID>/`

**Interfaces:**
- Produces: exact vLLM, vLLM-Ascend, Mooncake, image, platform, namespace, and no-overlay identity consumed by every runner and checker.

- [x] Detach `repos/Mooncake` at `df3f74ed8ebdb0c935554beea6299a9f11c723e2`; do not create or modify a Mooncake branch.
- [x] Update lock, Dockerfile pins, manifests, runners, checker tests, and validation identity to the final source SHAs and one provenance-bearing image tag.
- [x] Set `python_overlay.required` to false and remove old overlay execution from the formal path.
- [x] Create a UTC run ID, tracker, evidence identity, and source/tooling checksums.
- [ ] Commit and push the frozen control/tooling state before image/full validation.

### Task 5: Native ARM64 Image

**Files:**
- Read: `/root/buildkitd.yaml`
- Execute: `features/kv-pool-layerwise-reuse/Dockerfile.a2`
- Record: the new run evidence image directory.

**Interfaces:**
- Produces: a `linux/arm64` image whose labels and in-image Git HEADs match all three frozen SHAs.

- [ ] Verify `/root/buildkitd.yaml` SHA256 is `f7a0c64c330688d6cd6292c3ef3a1022ace0abff7c468aa1b73cb5fe96be5b52`, then apply and wait for `default/buildkitd`.
- [ ] Record Pod imageID, security context, node architecture, and native ARM64 BuildKit worker.
- [ ] Build through `BUILDKIT_HOST=kube-pod://buildkitd?namespace=default` and containerd namespace `k8s.io` with all three exact commit build args.
- [ ] Verify platform, manifest digest, config ID, labels, in-image Git HEADs, native modules, dependency checks, and seven Mooncake APIs.

### Task 6: Full Validation And Final Publication

**Files:**
- Execute: `features/kv-pool-layerwise-reuse/implementation-plans/full-validation-guide.md`
- Create: dated reports and evidence indexes for the frozen run ID.

**Interfaces:**
- Consumes: frozen clean source/control identity and verified native image.
- Produces: checked reports for direct session/range, G0, G1, lease, G4, 1P1D smoke, concurrent smoke, stress S1-S3, final empty pool, checksums, and offline replay.

- [ ] Run installed-module/API and direct multi-key, multi-layer, multi-fragment byte-equality tests, including negative session and same-key PutStart after revoke.
- [ ] Run tooling, native-image CPU/mock, G0, direct G1, lease, G4, 1P1D smoke, concurrent smoke, and stress S1-S3 serially.
- [ ] Prove per-layer scatter coverage, per-key byte results, commit ordering, marker isolation, hit correlation, whole-key zero, and final empty Master metrics.
- [ ] Run checksum replay and all offline report checkers; stop and preserve evidence immediately on any production-source defect.
- [ ] Stop vLLM child processes, retain `liangjiahao/vllm-ascend-ut` and `default/buildkitd`, then commit/push reports, evidence index, final lock, repo state, and sync log.
