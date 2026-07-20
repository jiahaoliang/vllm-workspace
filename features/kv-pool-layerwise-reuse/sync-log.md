# kv-pool-layerwise-reuse Sync Log

## 2026-07-03

- Created workspace feature branch `kv-pool-layerwise-reuse`.
- Created `repos/vllm` feature branch from official `v0.20.2`.
- Created `repos/vllm-ascend` feature branch from official `v0.20.2rc1`.
- Checked out `repos/Mooncake` at bundled tag `v0.3.8.post1` for read-only dependency inspection.
- Recorded RFC and reference implementation sources for later design work.

## 2026-07-09

- Archived user-provided preliminary design `DESIGN-mooncake-layerwise-gva-put.md` as a feature snapshot for Mooncake layerwise KVPool put.
- Archived vLLM Ascend PR #11444 as the memcache layerwise KV pooling reference implementation, including a Markdown summary and raw patch.
- Archived vLLM Ascend PR #10733 as the layerwise KV pool reuse coordination target from `ader47/vllm-ascend`, including a Markdown summary and raw patch.
- Updated `references/sources.md` so the design note, PR snapshots, and patch archives are discoverable from the feature source index.

## 2026-07-14

- Documented the Mooncake layerwise configuration and TP-only/session/range/SSD constraints as `c8a977e6d1a0fc17c457b4a0b69dfb1fa1b85366` on `origin/feature/mooncake-layerwise-kv-pool`.
- Re-ran the isolated CPU AscendStore suite: `327 passed`; the focused ruff check and `git diff --check` passed. `format.sh ci` cannot complete here because its `actionlint` hook cannot download Go modules from `proxy.golang.org`, even after supplying the reachable local proxy `http://127.0.0.1:10809`.
- The required Mooncake wheel contract and NPU E2E gates remain pending: the CPU venv has no `mooncake` wheel or `torch_npu`; `pip download mooncake-transfer-engine==0.3.11.post1` has no matching distribution; this host exposes no NPU deployment; and Docker is installed but its Linux engine is not running. The recorded read-only Mooncake source remains PR #2881 head `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`; integrate a wheel built from that commit (or an approved successor) on the target Linux/NPU environment before marking integration validated.
- Implemented and pushed Mooncake block-key scheduling, key-major range metadata, and per-key session orchestration as `631b893e91821f32f0613a7aeb7e169de4b9203e` on `origin/feature/mooncake-layerwise-kv-pool`.
- The implementation uses canonical `model@block@rank` keys, rejects Mooncake PP/PCP/DCP topologies above one, and keeps memcache GVA allocation/lease paths separate from Mooncake ranged session calls.
- Verified on the isolated CPU environment with `pytest --confcutdir=tests/ut/distributed/ascend_store -q tests/ut/distributed/ascend_store`: `327 passed`; `ruff check` and `git diff --check` passed. Mooncake wheel contract and NPU E2E gates remain pending.
- Implemented and pushed the Mooncake layerwise Backend contract as `f2af65e0c51a7597dfec131edd7b8e26dd9afc41` on `origin/feature/mooncake-layerwise-kv-pool`. Frozen Client APIs: `batch_put_start`, `batch_put_from_multi_buffer_ranges`, `batch_put_end`, `batch_put_revoke`, `batch_get_start`, `batch_get_into_multi_buffer_ranges`, and `batch_get_end`.
- Established the implementation baseline: `repos/vllm` is detached at `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`), and `repos/vllm-ascend` is on `feature/mooncake-layerwise-kv-pool` at `b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`.
- Replaced the local collaborator reference with `reference/ader47-new-memcache-layerwise`, tracking `ader47/vllm-ascend` branch `feature/new-memcache-layerwise` at `b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`.
- Mirrored the collaborator branch to the personal fork as `origin/feature/new-memcache-layerwise` without changing the active `kv-pool-layerwise-reuse` baseline branch.
- Checked out `repos/vllm-ascend` to local branch `feature/new-memcache-layerwise`, tracking `origin/feature/new-memcache-layerwise`, and refreshed the workspace lock state.
- Replaced the Mooncake layerwise design snapshot with the latest authoritative HackMD document `HJGESQG4ze`, covering Client sessions, ranged transfers, Backend ABC integration, end-to-end sequencing, tests, and risks.
- Added `ascend-direct-dev/Mooncake` as the Mooncake `collaborator` remote and checked out local branch `feature/layerwise-kv-session`, tracking `collaborator/feature/layerwise-kv-session` at PR #2881 head `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`.
- Archived Mooncake PR #2881 as a WIP implementation source, including a Markdown summary and raw patch fixed to the captured head.
- Confirmed that the PR exposes all seven session/range API names and includes abnormal-session, lease-expiry, and TCP E2E coverage. Recorded the current put-end idempotency and ranged-put `config` signature mismatches as blockers for the real-wheel contract gate.

## 2026-07-15

- Fetched `ader47/vllm-ascend` `feature/new-memcache-layerwise` at `5875ff0b366690c64324d71b47f9409f8cd762da` and rebased `feature/mooncake-layerwise-kv-pool` from `c8a977e6d1a0fc17c457b4a0b69dfb1fa1b85366` onto that head.
- Retained the collaborator's rebased layerwise KV-pool implementation (`b0e0eacc8`) instead of replaying its older duplicate (`d6a835d22`), then merged the TP-mismatch helpers and Mooncake session tests without dropping either behavior.
- Added `89b87ee2a1be466939579c165cba9df6b3824643` (`fix(kv_pool): initialize TP mismatch config`) to restore the extracted worker helper's access to `self._extra_config` and correct the TP-mismatch test calls to `use_layerwise`.
- Ran the isolated CPU AscendStore suite after the rebase: `347 passed`; focused `ruff check` and `git diff --check` passed. Pushed the rewritten source history to `origin/feature/mooncake-layerwise-kv-pool` with `--force-with-lease`.
- Split the post-rebase source history into six review-sized commits while preserving a tree identical to `89b87ee2a1be466939579c165cba9df6b3824643`: backend contract (`ce51636e5`), block-key metadata (`48bb7801f`), range transfer (`97ee7414e`), session orchestration (`9cd1ce8a4`), documentation (`729549908`), and TP-mismatch regression fix (`860491661`). Pushed the rewritten history with `--force-with-lease`.
- Folded the accepted `#fixup feat(kv_pool): define Mooncake layerwise backend contract` into the rewritten backend contract commit `ffd266831`, then replayed the remaining five review commits. The resulting source tree is identical to the pre-rebase tip `630c72fffec6471a8cff813b217581fa662094ca`; pushed the six-commit history with `--force-with-lease`.
- Applied the next accepted Backend contract findings as independent fixup `299b873cc81dd7d713f9cb57e97637b1752cd539`: removed the dedicated mock-helper test, made unsupported commit/revoke explicit failures, and removed Memcache no-op overrides. Retained the isolated-test package path because the CPU venv cannot load the standard conftest without `vllm._C`; `349 passed`, Ruff and `git diff --check` passed. The fixup remains unsquashed pending an explicit rebase command.
- Folded fixup `299b873cc81dd7d713f9cb57e97637b1752cd539` into rewritten Backend contract commit `90b16390031c5d9778bc77aafc1774f3064403e6`, replayed the remaining five review commits without conflicts, and force-pushed with `--force-with-lease`. The final tree matches the pre-rebase fixup tip; the isolated CPU suite passed `349` tests and Ruff passed.
- Implemented all accepted metadata review findings: kept `SharedBlockData.block_keys` optional for the existing memcache builder, moved Mooncake block-key activation to the session orchestration commit so scheduler and worker switch together, and made Mooncake `batch_is_exist` reject error or invalid states instead of treating them as cache misses.
- Folded the metadata and orchestration fixups into rewritten commits `6cff8ea86158c69ee32715815af833572922e214` and `0a9b787f59c1c08f0a202813ef40493104ab1139`. The final six-commit history ends at `1143c6470624e8e7d820a841c88117f9df36aebc` and was pushed to `origin/feature/mooncake-layerwise-kv-pool` with `--force-with-lease` against prior remote HEAD `27100c8726953a1c270c102bdf9389a75412c903`.
- Re-ran verification on the final rebased HEAD: the isolated CPU AscendStore suite passed `353` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for each of the six review commits passed.

## 2026-07-16

- Replaced monolithic range-transfer commit `87c31d1e8` with four review-sized commits: `2b2ae920e` (key-major range batches), `29f2a8e69` (exception-safe LayerThread finalization), `ff2557f74` (ranged save), and `89b1a88ea` (ranged load). The accepted request-accounting and save-key deduplication fixes were implemented test-first and folded into their owning commits.
- Replayed orchestration as `552541f94` and documentation as `6a825ca54`; force-pushed final source HEAD `6a825ca54761131c9b73c8871a886381c49513d8` with an exact lease against prior remote `a018212f32b057f1bdd75b4cbaccd2b132d2e30b`.
- Verified the rewritten source with `361 passed`; focused Ruff, full-range `git diff --check`, and all 8 feature commit checks passed.
- Fetched the force-updated `ader47/vllm-ascend` `feature/new-memcache-layerwise` branch at `6d0b2b70c33f70ca8d708870668514afafd1cb7e`; its history is not a fast-forward from the previous captured head `5875ff0b366690c64324d71b47f9409f8cd762da` and includes a refreshed layerwise base plus current main.
- Rebased the Mooncake work with `--onto`, replaying only the local review commits above the prior collaborator head. Git dropped `1143c6470 fix(kv_pool): initialize TP mismatch config` because collaborator commit `d7affe61e` already provides the patch.
- Adapted the Mooncake Backend contract to the new public `ensure_initialized()` method and folded the compatibility fix into rewritten Backend commit `a60c62a58`. The resulting five review commits end at `bfe69745025c732a03dc46e81d2729a6696d2e6e` and were pushed with `--force-with-lease` against prior remote HEAD `1143c6470624e8e7d820a841c88117f9df36aebc`.
- Verified the final rebased source: the isolated CPU AscendStore suite passed `354` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all five review commits passed.
- The collaborator history now includes `15818534e` upgrading its CI baseline to vLLM 0.24.0. This workspace remains locked to vLLM v0.23.0 under the existing D03 decision, and the isolated CPU venv has no importable real `vllm` package; therefore this checkpoint does not claim cross-repo vLLM 0.24 compatibility.
- Updated `repos/vllm` from v0.23.0 to the official v0.24.0 tag `ee0da84ab9e04ac7610e28580af62c365e898389`, aligning the workspace source baseline with the latest collaborator vLLM Ascend history.
- Re-reviewed the pending Memcache TP-only change against vLLM v0.24.0 and vLLM Ascend `bfe697450`: PP/TP/PCP/DCP field names and positive-integer constraints remain compatible; both block-key backends still use the simplified key without PP/PCP/DCP coordinates. Updated the plan to cover both backends and to read the guaranteed v0.24.0 fields directly instead of silently defaulting invalid configuration to one.
- A real vLLM v0.24.0 import in the Windows CPU venv stops at missing `vllm._C_stable_libtorch`; existing AscendStore tests mock vLLM dependencies. Real cross-repo and NPU integration gates remain pending.
- Re-ran the isolated AscendStore suite after the vLLM checkout update: `354 passed`.
- Implemented the accepted Memcache TP-only review decision as three GitExtensions-style fixups: backend-neutral topology helper and direct-field validation, connector/scheduler/worker gate coverage, and user documentation. TDD red checks confirmed the missing helper, Memcache bypass, and permissive missing-field behavior before the fixes.
- Folded the fixups into rewritten commits `59f4b2076` (metadata), `916410252` (orchestration), and `7ba9937d7` (documentation), then force-pushed with `--force-with-lease` against prior remote HEAD `bfe69745025c732a03dc46e81d2729a6696d2e6e`.
- Verified the final source HEAD `7ba9937d77189e9bb5703d0bc86727f63d0fd9a9`: the isolated AscendStore suite passed `360` tests; focused Ruff, full-range `git diff --check`, and all five `git show --check` checks passed.
- Replaced abbreviated topology error labels with `pipeline_parallel_size`, `prefill_context_parallel_size`, and `decode_context_parallel_size`, then folded the GitExtensions-style fixups into rewritten metadata commit `e629ef6b6` and orchestration commit `d05a32570`.
- Rebased the five review commits onto the latest fetched `ader47/feature/new-memcache-layerwise` head `6d0b2b70c33f70ca8d708870668514afafd1cb7e` and force-pushed final HEAD `a018212f32b057f1bdd75b4cbaccd2b132d2e30b` with `--force-with-lease`.
- Verified the rewritten source with `360 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.

## 2026-07-17

- Folded `6bb780019 #fixup feat(kv_pool): build Mooncake layer range batches` into rewritten range-batch builder commit `21bd87100`, adding a test that reuses one `SharedBlockData` across layer 0 and layer 2.
- Replayed the next five review commits without conflicts and force-pushed final source HEAD `8cfd1e22f92ee1a40139ea40b487fa5001d1c81f` with an exact `--force-with-lease` against prior remote `6a825ca54761131c9b73c8871a886381c49513d8`.
- Verified `362 passed`; focused Ruff and format checks, full-range `git diff --check`, all six rewritten commit checks, and range-diff passed. The temporary `review/mooncake-layer-range-batches` branch was deleted.
- Folded `c2c817574 #fixup refactor(kv_pool): make layer transfer completion exception-safe` into rewritten commit `e0bec4ca4`, making the Layer receiver share the Worker's invalid-block set/lock and restoring the transfer lifecycle comments accepted during review.
- Replayed ranged save as `e9893579a`, ranged load as `ff4c810b6`, orchestration as `9af376c37`, and docs as `1d56db71e`. Resolved ranged-load and orchestration overlap by keeping the invalid-block wiring in the exception-safe commit and leaving `load_abort_event` ownership in orchestration; deleted the temporary review branch.
- Verified `363 passed`; Ruff check, full-range `git diff --check`, all five rewritten commit checks, and range-diff passed. Force-pushed final source HEAD `1d56db71e19130ddb4c22e23f21f76756c3d6295` with an exact `--force-with-lease` against prior remote `8cfd1e22f92ee1a40139ea40b487fa5001d1c81f`.

## 2026-07-18

- Reviewed `feat(kv_pool): add Mooncake ranged layer save` against the Mooncake
  layerwise design and implementation plan. Added active-subset payload alignment
  assertions, commit/revoke exception and malformed-result coverage, and lifecycle
  comments for `_handle_range_request` and `_put_started_keys` cleanup.
- Folded `d53c64768 #fixup feat(kv_pool): add Mooncake ranged layer save` into
  rewritten ranged-save commit `a3611520dfd204ab6349637680fb43235513bc03`.
  Replayed ranged load as `29c5f2cfa9089f584d6502fe9daa153cee0f36fc`,
  orchestration as `54e6684f1eee86fcf6f98a7cb01826726486605d`, and docs as
  `8bf9ac9c34397b2fd4ab1c21c1e6965b5a55eb0b`; deleted the temporary review
  branch.
- `py_compile`, focused Ruff, `git diff --check`, all rewritten commit checks,
  final-tree comparison, and range-diff passed. The focused pytest class could not
  complete collection on this Windows CPU environment: the normal conftest needs
  generated Ascend `_build_info`, while isolated collection exposes the existing
  `_mock_deps.py` `zmq` stub lacking vLLM v0.24.0 `zmq.asyncio`.
- Force-pushed final source HEAD `8bf9ac9c34397b2fd4ab1c21c1e6965b5a55eb0b`
  to `origin/feature/mooncake-layerwise-kv-pool` with an exact
  `--force-with-lease` against prior remote HEAD
  `1d56db71e19130ddb4c22e23f21f76756c3d6295`.
- Fetched the force-updated Mooncake collaborator branch and verified that
  `collaborator/feature/layerwise-kv-session` and upstream PR #2881 both point to
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`. The PR squashed the previous five
  feature commits into one; its source tree is identical to captured head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`. Updated the local read-only branch,
  workspace lock and PR snapshot. The put-end idempotency and ranged-put
  optional `config` contract gaps remain open.
- Folded `f635cca8b #fixup feat(kv_pool): orchestrate Mooncake layerwise sessions`
  into rewritten orchestration commit `6aa38e791198a60f90e34bf34d6875bf5a9d2956`,
  replayed the documentation commit as `867dd424318d88e9bb2b831cdbd5b16bb723184a`,
  and deleted the temporary review/integration branches. Range-diff confirmed the
  documentation commit remained patch-equivalent, and the final tree delta's
  patch-id matched the original fixup.
- Reverified the final feature HEAD with the dedicated CPU venv: the complete
  `tests/ut/distributed/ascend_store` suite passed `373` tests; focused Ruff,
  `py_compile`, feature diff checks, and both rewritten commit checks passed.
  Force-pushed `origin/feature/mooncake-layerwise-kv-pool` with an exact lease
  against prior remote HEAD `8bf9ac9c34397b2fd4ab1c21c1e6965b5a55eb0b`
  and confirmed the remote now points to `867dd424318d88e9bb2b831cdbd5b16bb723184a`.

## 2026-07-20

- Synced the authoritative HackMD design update that adds §5.7 Chunked Prefill
  session hooks and archived the companion sequence diagram. The source-backed
  review confirmed that Mooncake already refreshes `lease_deadline` on repeated
  `batch_get_start`; the vLLM Ascend Worker lifecycle was the missing layer.
- Implemented the accepted Worker-side ownership design in signed source commit
  `a1e888b46dbaa3c76a9c0dd1060a3631148fe8af`
  (`feat(kv_pool): support Mooncake chunked prefill sessions`) and pushed it to
  `origin/feature/mooncake-layerwise-kv-pool`.
- Added a thread-safe request/key registry. Each chunk renews the request's
  accumulated load keys; SendingThread promotes only successful PutEnd keys;
  mixed-lastness requests sharing a prefix key keep the Client session until
  the final active owner releases it. Preempt/finished/abort cleanup is covered.
- Verified the final source with the isolated full AscendStore CPU suite:
  `394 passed`. Focused Ruff lint, `py_compile`, and `git diff --check` passed.
  Real Mooncake wheel and NPU chunked-prefill E2E remain pending.
