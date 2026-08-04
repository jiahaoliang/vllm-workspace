# Single-Group Backports Overlay Full Validation Tracker

## Frozen Run Identity

- Status: runtime validation passed; evidence publication in progress
- Umbrella run ID: `20260804T103209Z`
- Evidence root: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260804T103209Z`
- Control branch: `kv-pool-layerwise-reuse`
- Tooling base: `d2df1843a1f0884da519389b82277edfa455f22b`
- Tooling commit: pending
- Source branch: `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`
- Final source HEAD: `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`
- Image source HEAD: `14beaf161cca6f1e044e20529ca96c6554dbbe50`
- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- Mooncake: `786c77ff7692bed58dd99971afef87d6b690cbe3`
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`
- Validation mode: explicitly authorized Python overlay; no image rebuild
- Kubernetes namespace: `liangjiahao`
- Node/model: `n1`, `vllm-ascend/DeepSeek-V2-Lite-W8A8`

The image remains an artifact of `14beaf161`; this run must not claim it was
built from `d5f0ea7f8`. The serving overlay is exactly these five package
files:

1. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`
2. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
3. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
4. `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py`
5. `vllm_ascend/envs.py`

`vllm_ascend/envs.py` changed only to register opt-in nightly test variables,
but remains in the overlay so runtime provenance exactly matches the final
package tree.

## Scope Decisions

- §5.8 Mooncake multi-group remains deferred and unsupported in this target.
- `0dad9ad94` is excluded.
- `04cb824f6` is represented by the existing `d28c52958` patch.
- `8d9897143`, `189dcdd2c`, and `6451f9010` carry the approved single-group
  backports.
- `d5f0ea7f8` repairs review findings without adding group-local behavior:
  nonnegative ranged results, centralized env registration, direct immutable
  row consumption, a named test pattern constant, and accurate limitations.
- Production source is frozen at `d5f0ea7f8` for this run. A production-source
  failure terminates the run; tooling failures may be repaired with focused
  regression coverage and affected gates rerun.

## Source Gate

- [x] Four new commits after `d28c52958`, all with `Signed-off-by`.
- [x] No merge commit in `d28c52958..d5f0ea7f8`.
- [x] §5.8 group-local symbols absent from the source diff.
- [x] Ranged contract regression: `2 passed, 1 skipped`.
- [x] Environment registration regression: `3 passed`.
- [x] AscendStore plus env CPU/mock gate: `490 passed`.
- [x] Ruff, format, compile, and `git diff --check` passed.
- [x] Source worktree clean and frozen.

## Tooling Gate

- [x] Update identity, workspace lock, and all runner source pins.
- [x] Run focused and complete deployment tooling tests: `81 passed`.
- [x] Run shell syntax, Python compile, Ruff/format, and manifest dry-runs.
- [x] Freeze tooling in local control commits through `20800ac`.

## Formal Validation Gates

- [x] CPU/mock UT through the frozen control runner: `490 passed`.
- [x] G0 identity/startup and empty Master; five overlay checksums exact.
- [x] G1 direct ranged contract `43/43` and negative cases `24/24`.
- [x] Lease expiry `-707` and exact fresh-session recovery.
- [x] G4 27-layer save/load/commit audit with zero whole-key events.
- [x] 1P1D smoke baseline/warmup/direct/proxy and `12/12` correlation.
- [x] Stress S1 `4/4`, 508 keys.
- [x] Stress S2 `16/16`, 288 keys.
- [x] Stress S3 pinned proof plus `4/4`, 348 keys.
- [x] Stop engines, reset Master, and prove final `0/0/0`.

## Attempts And Failures

| Attempt | Family | Status | Classification | Invalidation/Fix |
| --- | --- | --- | --- | --- |
| prior run `20260804T091342Z` | post-freeze review | stopped | test/spec defect | corrected source; no evidence reused for this run |
| G4 attempt 1 | debug configuration | stopped | tooling | preserved under `g4/attempt1-no-debug`; enabled required audit mode |
| G4 attempt 2 | Python overlay | stopped | tooling | preserved under `g4/attempt2-python39-zip-strict`; removed unsupported strict zip use |
| G4 attempt 3 | readiness | stopped | tooling | preserved under `g4/attempt3-master-metrics-readiness`; corrected Master readiness check |
| stress attempts 1-3 | Decode startup | stopped | external hardware | physical NPU 1 repeatedly failed loading `libcpu_kernels.so` with ACL `507018`; quarantined `/dev/davinci1` in `layerwise-npu-quarantine-c` |
| stress attempt 4 | pre-apply runner gate | stopped | tooling | runner required retained engine Pods after scale-to-zero; added clean-start support and regression coverage; complete deployment suite passed `82` tests |
| stress final | S1-S3 | passed | runtime | `162/162` recorded steps passed; S1 `4/4`/508, S2 `16/16`/288, S3 pinned plus `4/4`/348 |

## Publication

- [ ] Generate and replay family/root checksums.
- [ ] Produce and validate six family reports plus umbrella report.
- [ ] Verify origin remains `d28c52958`, then fast-forward push source.
- [ ] Update lock/repo-state/sync-log/status/README.
- [ ] Commit and push control evidence/reports/state.
- [ ] Verify both remotes with `git ls-remote` and left/right `0 0`.
