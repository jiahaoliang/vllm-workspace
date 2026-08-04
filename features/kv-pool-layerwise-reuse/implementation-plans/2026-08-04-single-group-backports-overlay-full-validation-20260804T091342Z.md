# Single-Group Backports Overlay Full Validation Tracker

## Frozen Run Identity

- Status: source frozen; validation tooling preparation in progress
- Umbrella run ID: `20260804T091342Z`
- Evidence root: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T091342Z`
- Control branch: `kv-pool-layerwise-reuse`
- Tooling base: `554aa81cc98a3cb33ab9c70ec3c4ef8e9d766196`
- Tooling commit: pending
- Source branch: `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`
- Final source HEAD: `6451f9010294913da5eedc4a73c0993d5b4a8907`
- Image source HEAD: `14beaf161cca6f1e044e20529ca96c6554dbbe50`
- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- Mooncake: `786c77ff7692bed58dd99971afef87d6b690cbe3`
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`
- Image platform: `linux/arm64`
- Validation mode: explicitly authorized Python overlay; no image rebuild
- Kubernetes context: `bke-cluster-admin@bke-cluster`
- Namespace: `liangjiahao`
- Node: `n1`
- Model: `vllm-ascend/DeepSeek-V2-Lite-W8A8`
- Model layers: `27`

The image remains an artifact of `14beaf161`; this run must not claim that it
was built from `6451f9010`. The complete package overlay is exactly:

1. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`
2. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
3. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
4. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py`

## Scope Decisions

- §5.8 Mooncake multi-group remains deferred.
- `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d` is excluded.
- `04cb824f6` is not replayed because its tree is already represented by
  `d28c52958`.
- The source adds only the approved single-group immutable row/failure
  isolation, shared audit emitter/API documentation, and opt-in performance
  gate.
- After the source gate below, `repos/vllm-ascend` is frozen. A production
  failure terminates the formal run; only validation tooling may be repaired.

## Source Gate

- [x] Three new commits, all with `Signed-off-by`.
- [x] No merge commit in `d28c52958..6451f9010`.
- [x] Protected local/origin `feature/mooncake-layerwise-kv-pool` remain
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`.
- [x] Prohibited §5.8 symbols absent from the source diff.
- [x] Overlay allowlist is exactly four package Python files.
- [x] Opt-in performance test without config: `1 skipped`.
- [x] CPU/mock UT in `liangjiahao/vllm-ascend-ut`: `490 passed`.
- [x] Diff-scoped Ruff: passed for 9 Python files.
- [x] Diff-scoped format: 9 files already formatted.
- [x] `py_compile`: passed for all four overlay package files.
- [x] `git diff --check d28c52958..HEAD`: passed.
- [x] Source worktree clean and frozen at `6451f9010`.

## Cluster Snapshot

Captured before formal runtime execution on 2026-08-04 UTC:

- `m1`: Ready, 8 allocatable `huawei.com/Ascend910`.
- `n1`: Ready, 8 allocatable `huawei.com/Ascend910`.
- `n2`: Ready Unknown; excluded.
- `liangjiahao/vllm-ascend-ut`: Running, CPU-only long-running UT Pod.
- Mooncake Master and proxy: Running/Ready.
- Prefill and Decode Pods: retained Running Pods with application containers
  not Ready because engine children are stopped.
- `default/buildkitd`: absent. This run does not build an image, so the missing
  builder does not affect the authorized overlay validation path.

## Tooling Gate

- [x] Red identity test proved old `d28c52958` and two-file assumptions.
- [x] Identity, workspace lock, and runner source SHA updated to `6451f9010`.
- [x] Sync/UT/smoke allowlists updated to the exact four files.
- [x] Sync helper creates destination directories and compares host/Pod SHA256.
- [x] Focused identity tests: `12 passed`.
- [x] Complete `deployment/tests` collection: `72 passed`.
- [x] Shell syntax, Python compile, Ruff/format, and `git diff --check`.
- [x] Rendered ConfigMap Python compile: 3 mounted Python files.
- [x] Every manifest client dry-run with explicit `-n liangjiahao`.
- [ ] Freeze and record the tooling commit.

## Formal Validation Gates

- [ ] G0 image/source/model/runtime identity and empty Master.
- [ ] G1 direct ranged contract, including all negative cases and cleanup.
- [ ] Lease expiry and exact fresh-session recovery.
- [ ] G4 all-layer save/load/commit audit with zero whole-key events.
- [ ] 1P1D smoke: baseline, five warmups, direct/proxy concurrency, `12/12`
  correlations.
- [ ] Stress S1: `4/4`, expected 508 keys, both Prefill DP ranks.
- [ ] Stress S2: `16/16`, expected 288 keys, both Prefill DP ranks.
- [ ] Stress S3: pinned cold proof plus `4/4`, expected 348 keys.
- [ ] Stop vLLM children and prove final Master `0/0/0`.

## Attempts And Failures

| Attempt | Family | Status | Classification | Invalidation/Fix |
| --- | --- | --- | --- | --- |
| source-red-1 | immutable rows | expected failure | TDD red | missing `LayerRangeRow` |
| source-red-2 | shared emitter | expected failure | TDD red | missing `range_debug.py` |
| tooling-red-1 | identity | expected failure | tooling drift | old SHA and two-file allowlist |

New runtime attempts must use unique family run IDs beneath the evidence root.
Tooling defects require a regression test and affected-family rerun. Production
source defects terminate this formal run with a detailed failure report.

## Publication

- [ ] Push source branch normally after verifying origin still points to
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`.
- [ ] Checksum and commit evidence before reports.
- [ ] Produce and validate ranged, lease, G4, smoke, stress, and umbrella reports.
- [ ] Update lock/repo-state/sync-log/status/README records.
- [ ] Push control branch and verify both remotes with left/right `0 0`.
