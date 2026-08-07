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
- Folded
  `78d84d7e0ee382a3869836f533fd208118055e9f #fixup feat(kv_pool): support Mooncake chunked prefill sessions`
  into rewritten source commit `e5989049e9cb27f218b52b8e03af8e5dc841ac74`.
  The final tree is identical to the pre-rebase review HEAD. Reverified the full
  isolated AscendStore CPU suite with `397 passed`; focused Ruff, `py_compile`,
  tracker/test format checks, feature diff checks, and rewritten commit checks
  passed.
- Force-pushed `origin/feature/mooncake-layerwise-kv-pool` with an exact lease
  against prior remote HEAD `a1e888b46dbaa3c76a9c0dd1060a3631148fe8af` and
  confirmed the remote now points to `e5989049e9cb27f218b52b8e03af8e5dc841ac74`.
  Deleted `review/mooncake-chunked-prefill-sessions` locally and remotely.
- Accepted R1 from the final commit review. Added a regression where a second
  request reuses an already-started shared key while its new key put-start
  fails; the red test reproduced the lost pending owner, then passed after the
  exception path stopped clearing `previously_started`.
- Created
  `526df69bb4e984ae3081d028268ac777863eb3de #fixup feat(kv_pool): support Mooncake chunked prefill sessions`
  and folded it into rewritten source commit
  `8da904ff7048d88aed240645dd1293ca0abdf4ee`. The final tree matches the
  pre-rebase fixup HEAD.
- Reverified the rewritten source with the isolated full AscendStore CPU suite:
  `398 passed`; the related focused range passed `35` tests. Ruff lint,
  `py_compile`, feature diff checks, and rewritten commit checks passed.
- Force-pushed with an exact lease against remote
  `e5989049e9cb27f218b52b8e03af8e5dc841ac74` and confirmed local and remote
  both point to `8da904ff7048d88aed240645dd1293ca0abdf4ee`.
- Fetched latest `vllm-project/vllm-ascend` `upstream/main` at
  `9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384` and rebased
  `feature/mooncake-layerwise-kv-pool` from `8da904ff7048d88aed240645dd1293ca0abdf4ee`.
- The rebase had overlapping semantic conflicts in `kv_transfer.py`,
  `pool_scheduler.py`, and `pool_worker.py`. Resolutions retained upstream
  multi-group `group_id` / `layer_idx_in_group` behavior together with Mooncake
  key-major ranges, exception-safe finalization, and chunked-prefill owner tracking.
  Upstream-equivalent commits `efb3e85a0` and `d7affe61e` were not replayed.
- Reverified the rebased source with the isolated full AscendStore CPU suite:
  `398 passed`. Ruff lint, `py_compile`, and `git diff --check` passed. The stale
  FlashComm2 test sentinel was updated to verify the real `parallel_state` module
  after upstream removed FlashComm2 in `f583c2fa1`.
- Force-pushed rewritten source HEAD
  `1c75b507fe268b91a6f4183da0ae6221ffd05568` with an exact lease against remote
  `8da904ff7048d88aed240645dd1293ca0abdf4ee` and confirmed local and remote match.
- Implemented the final feature-branch review decisions in independent
  vLLM-Ascend fixup `cfe97c8de2cce781750be05e34ac7d0030fd9c0b`: MC2 adds a bounded
  Mooncake-only fatal drain timeout without racing `batch_get_end`, and D3 sends
  uncertain put-start revokes through `KVCacheStoreLayerSendingThread`.
- The user then narrowed implementation scope to vLLM-Ascend only. Restored
  Mooncake to unchanged collaborator HEAD
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`; no Mooncake commit was pushed.
  Added vLLM-Ascend adapter fixup `f5ab64a1f` so the final tree continues using
  the collaborator wheel's current two-argument put-start and four-argument
  ranged-put signatures.
- Pushed vLLM-Ascend HEAD `f5ab64a1f` to
  `origin/feature/mooncake-layerwise-kv-pool`. The isolated AscendStore CPU suite
  passed `402` tests; Ruff, `py_compile`, `git diff --check`, and fixup commit
  checks passed. No real Mooncake wheel, memcache E2E, or NPU E2E was run.
- Autosquashed all three review fixups into their owning commits. D3/MC2 are now
  part of orchestration commit `9f2aefa59c239171d5e31c800b8979e67ff62c18`;
  the two Backend contract fixups cancel inside patch-equivalent commit
  `0e5c41c00c0f893dd8fe7bd87533a93aab47ac9f`. The rewritten feature contains
  nine commits and no `fixup!` subjects.
- Resolved two `pool_worker.py` autosquash conflicts by retaining the historical
  lifecycle appropriate to the orchestration commit, then allowing the later
  chunked-prefill commit to install request-owner tracking while preserving the
  asynchronous revoke path. The final tree hash stayed exactly
  `96cb96b70854e4f69f5598feab74c3e7e1fd6605`.
- Reverified `402 passed`, focused Ruff, `py_compile`, `git diff --check`, and
  all nine rewritten commit checks. Force-pushed final HEAD
  `663209fd6208a59a48742f75116345bf5f5281ec` with an exact lease against
  `f5ab64a1f574896c2894283e09a7a7e867b597d4`.

## 2026-07-23

- Entered the approved G4/D1 runtime-audit gate and added default-disabled
  `VLLM_ASCEND_KVPOOL_RANGE_DEBUG` instrumentation in signed vLLM-Ascend commit
  `849c1a7f1f4643e03de74f6784b69504dd5174b5`.
- The source change is limited to the six production/test files allowed by the
  validation plan. It records physical-layer ranged save/load byte results,
  final commit results, and legacy whole-key backstop events without recording
  keys, request IDs, pointers, GVA values, prompts, or generated text.
- Pushed the source commit to
  `origin/feature/mooncake-layerwise-kv-pool`. The three affected test files
  passed `138` tests, and the complete four-file AscendStore target passed
  `248` tests. Both existing engine Pods received the three production Python
  files; the prefill Pod also received the three Python test files for Pod-local
  pytest because the host had no pytest installation. Production-file SHA-256
  digests in both Pods match the committed local files.
- `bash format.sh ci` was attempted but its markdownlint hook could not run in
  this environment because the downloaded Node binary requires unavailable
  `libatomic.so.1`. Focused Ruff check and codespell passed; Ruff's unrelated
  baseline reformatting was discarded after review.
- Ran one clean standard-proxy request after stopping both engines, restarting
  Master to `master_key_count=0`, and starting the same engine Pods with
  `VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1`. Both `/v1/models` endpoints returned HTTP
  200 and the request returned HTTP 200 with a non-empty choice.
- The fail-closed checker passed: save and load each covered exactly physical
  layers `0..26`; all four per-layer key results equaled the `147456`-byte
  fragment sum; the final commit followed the last save; whole-key events were
  zero. Decoder KVPool load was `512/512` tokens.
- Persisted the independent G4 artifact under
  `/root/ljh/validation-artifacts/ranged-api-g4-20260723T132919Z/runtime-audit`.
  Destination `sha256sum -c SHA256SUMS` passed and the manifest digest is
  `af533b69d6128088bad74dc12dfab95fd31201882ae92577cf0c5908f754181d`.
  The prior G0-G3 artifact was not modified. Both debug engines were stopped
  after evidence collection; the original engine Pods remain in place.

## 2026-07-29

- Fetched the force-updated Mooncake collaborator branch
  `feature/layerwise-kv-session` and moved the read-only Mooncake worktree from
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` to detached collaborator tip
  `786c77ff7692bed58dd99971afef87d6b690cbe3`.
- The updated Mooncake client renames the five session-control methods to
  `batch_put_session_start`, `batch_put_session_end`,
  `batch_put_session_revoke`, `batch_get_session_start`, and
  `batch_get_session_end`. The two ranged transfer method names remain
  unchanged. vLLM-Ascend adaptation and image validation are tracked in
  `implementation-plans/2026-07-29-mooncake-session-api-adaptation.md`.
- Adapted the vLLM-Ascend Mooncake boundary without changing the internal
  Backend interface, committed it as
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`, and pushed the feature branch to
  the personal fork so the existing clone-based image build could consume the
  exact commit.
- In the dedicated CPU-only `liangjiahao/vllm-ascend-ut` Pod, the strict
  adapter test produced the expected red result (`4 failed, 1 passed`) before
  implementation and passed after it (`5 passed`). The complete backend file
  passed `80` tests and the complete AscendStore suite passed `408` tests.
  Ruff 0.14.0 lint, in-memory Python compilation, and `git diff --check`
  passed; both changed Python files retained their pre-existing whole-file
  format delta relative to parent `3f0cbf59c`.
- Preserved the original remote-clone Dockerfile flow, pinning vLLM-Ascend to
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156` and Mooncake to
  `786c77ff7692bed58dd99971afef87d6b690cbe3`. The shared `buildkitd` is the
  only namespace exception and runs in `default`; UT and serving workloads
  remain in `liangjiahao`.
- Built native `linux/arm64` image
  `vllm-ascend:kv-pool-layerwise-v0.24.0-a2-session-api-20260729` into
  containerd namespace `k8s.io`. Its manifest digest is
  `sha256:bd3c7b2324d799c4a1f360bcbc8191cee2e4fa05c58f66bddc5d09bba9ee710f`,
  config is
  `sha256:7e190798aee3cecae8bf3c91020ce2efab82d5900b290e2d659c724bf6ee313c`,
  unpacked size is `19.23 GB`, and blob size is `6.803 GB`. Image labels match
  vLLM `ee0da84ab`, vLLM-Ascend `b5b65d9bb`, and Mooncake `786c77ff`; the
  binary symbol gate passed all seven required session/ranged APIs.

## 2026-07-30

- Re-inspected image
  `vllm-ascend:kv-pool-layerwise-v0.24.0-a2-session-api-20260729` in the local
  containerd `k8s.io` store and recorded its exact manifest, config, platform,
  creation time, and full vLLM/vLLM-Ascend/Mooncake commit labels in
  `image-component-commits.md`. This immutable image mapping is intentionally
  separate from the newer commits in `workspace.lock.json`.
- Fetched `vllm-project/vllm-ascend` `upstream/main` at
  `b2f683ca35a59b4f74f1c29367cb31db4125214e` and rebased the 11 commits on
  `feature/mooncake-layerwise-redesign` from prior HEAD
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`.
- Resolved overlapping backend, metadata, transfer-finalization, ranged-save,
  and Scheduler conflicts by preserving upstream Memcache finalization and hit
  semantics alongside the Mooncake layerwise session/range behavior. Added
  post-rebase fix `4e9bb3246` for the renamed Memcache GVA flag and lightweight
  CPU test dependencies.
- Force-pushed the rewritten source branch with an exact lease against
  `b5b65d9b`; local and `origin/feature/mooncake-layerwise-redesign` now match at
  `4e9bb324613b08e86eaaf95c8d6554ae9ddb5845`.
- Updated `repos/vllm` from `v0.24.0` to verified main commit
  `d02df748bf9efd99022f1a062597dc3cb3808485`, read directly from
  `upstream/main:.github/vllm-main-verified.commit`; the corresponding release
  line is `v0.25.1`.
- Verified the rebased tree with the isolated local CPU/mock AscendStore suite:
  `417 passed, 63 subtests passed`. Python compilation and `git diff --check`
  passed. No kube context was configured, so the dedicated `liangjiahao` UT Pod
  was unavailable; Ruff was also unavailable locally. No NPU workload was run.
- Fixed public workspace ref handling on `main` in `66d62fd`: exact tags are now
  queried without treating an untagged detached HEAD as an error, and
  `lock-repos.ps1` falls back to the longest matching feature-directory prefix.
  Merged `main` into `kv-pool-layerwise-reuse-redesign`; `lock-repos.ps1` and
  `status-all.ps1` now complete with all three repos matching the lock.
- Folded `565b48dea fix(kv_pool): adapt renamed Mooncake session APIs` into
  rewritten Backend contract commit `700e56cfd`, replayed the later commits, and
  force-pushed final source HEAD
  `08b4f531d585fbfa5e365fa7d5f5e812bc80ab16` with an exact lease against
  `4e9bb324613b08e86eaaf95c8d6554ae9ddb5845`. The final tree remains exactly
  `665e691662fec0292c9f2258e4193dcce01ae949`; the CPU/mock AscendStore suite
  passed `417` tests and `63` subtests, Python compilation passed, and
  `git diff --check` passed.
- Aborted the conflicting merge on
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` and started the
  requested linear integration by replaying the Mooncake commits directly onto
  `collaborator/kv_offload_0723` at
  `a46a1dabbc260e8695002969f29528eb555eb583`.
- Published a partial `3/11` checkpoint at
  `baa547632fcc6ebec37f1e6922469652b7cec90b`. The applied commits are
  `3676b98f1`, `7f8bdf290`, and `baa547632`; the remaining source range starts
  with original commit `3eddb06c6` and ends at protected branch HEAD
  `b5b65d9bb`. Local and
  `origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` match.
- Conflict resolution preserves collaborator `GroupTransferData`,
  `TransferCompletion`, and `LayerTransferArrayBuilder` behavior alongside the
  Mooncake `SharedBlockData`, `LayerBatchReqMeta`, and key-major ranged batch
  path. `git diff --check`, Python compilation, and the linear ancestry/count
  checks passed. CPU/mock pytest did not complete on Windows: normal collection
  requires unavailable `uvloop`, while isolated collection replaces real `zmq`
  with the existing `_mock_deps.py` stub and then cannot import `zmq.asyncio`.
  Resume validation in the K8s environment before applying commits `4/11` to
  `11/11`.
- Completed commits `4/11` through `11/11` on
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`, producing frozen
  source HEAD `14beaf161cca6f1e044e20529ca96c6554dbbe50`. The merge base remains
  `collaborator/kv_offload_0723` at
  `a46a1dabbc260e8695002969f29528eb555eb583`; the range contains exactly 11
  commits, matches the original Mooncake subject order, and contains no merge
  commit.
- Conflict resolutions retain collaborator `GroupBatchPlan`,
  `LayerwisePreparation`, `GroupTransferData`, `TransferCompletion`,
  `LayerTransferArrayBuilder`, lease/fatal-poll handling, and group-aware
  shared-buffer GVA transfers. Mooncake `SharedBlockData`, session ownership,
  chunk renewal, key-major ranged batches, ranged audit, and session/range
  save/load remain available through explicit backend/range dispatch. The
  positional `LayerTransferTask` constructor contract is unchanged.
- Fixed Ruff `B023` in the chunked-prefill test closure by binding the loop
  worker as a lambda default and folded it into commit `a2d654419`; Ruff 0.14.0
  formatting was absorbed into the existing final commit so the history stayed
  at 11 commits. On the existing CPU-only
  `liangjiahao/vllm-ascend-ut` Pod, the complete
  `tests/ut/distributed/ascend_store` collection passed `476` tests in
  `18.09s`. Ruff lint and format, Python compilation, and range
  `git diff --check` also passed.
- Confirmed protected local and remote
  `feature/mooncake-layerwise-kv-pool` remain at
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`. Before push, the target remote
  was still `baa547632fcc6ebec37f1e6922469652b7cec90b`; the normal fast-forward
  push advanced it to `14beaf161cca6f1e044e20529ca96c6554dbbe50`.
  Post-push `git ls-remote` matched the local HEAD and
  `git rev-list --left-right --count` returned `0 0`.
- `pwsh` was unavailable on this Linux host, so the state files were refreshed
  according to `scripts/lock-repos.ps1` and checked with equivalent Git/JSON
  commands; no PowerShell script result is claimed for this checkpoint.
- The first full-validation image attempt used stale vLLM identity
  `d02df748bf9efd99022f1a062597dc3cb3808485` inherited from the earlier
  redesign checkpoint. Mooncake and vLLM-Ascend native builds completed, but
  the final dependency-health gate failed after 68 minutes because that vLLM
  metadata and the target release branch require incompatible FastAPI versions;
  no image was loaded. The failed build remains under run
  `20260730T130225Z/image`.
- Re-derived vLLM from the integrated branch's own
  `.github/vllm-main-verified.commit`, fetched and checked out clean detached
  `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`, and refreshed the lock/state.
  The r2 validation identity uses a new image tag and preserves the first
  attempt. The Dockerfile still executes `pip check`; its wrapper permits only
  the exact known CANN-base and official vLLM/vLLM-Ascend compatibility lines
  and fails on every unexpected dependency issue.
- Formal r2 tooling passed with identity `6/6`, deployment `64/64`, shell,
  Python, Ruff, rendered ConfigMap, source-history, remote-identity, and ten
  manifest dry-run gates. During the r2 build, package metadata proved the
  generated wheel version is `0.1.dev1+g54503ecec.empty`, not the assumed
  8-character `g54503ece` form. The build was terminated with exit 130 before
  its inevitable final-gate failure, and the r2 tag remained absent.
- The r2 interruption also showed that `run-validation-step.sh` did not record
  an END entry when its process group received SIGINT. Attempt r3 fixes the
  exact wheel allowlist and signal terminal recording in the control repo,
  adds regression coverage, selects a new `-r3` image tag, and requires all
  affected tooling/image gates to rerun. No `repos/*` source was modified.
- The first signal regression used the recorder START line as its synchronization
  point and reproduced one timeout in ten runs because the child was not always
  ready. The test now waits for a child-written artifact marker; it passed 50
  consecutive host runs and the complete dedicated-Pod deployment collection
  passed `65` tests with cache and bytecode disabled.
- Attempt r3 completed the Mooncake and vLLM-Ascend native builds, all seven
  required session/range symbols, and the exact raw `pip check` allowlist. The
  next package-report command failed on
  `importlib.metadata.version("mooncake-transfer-engine")`. Source inspection
  and the prior ranged-API report confirm this CMake install writes the
  `mooncake` package and native extensions directly into Ascend site-packages
  without wheel distribution metadata; the r3 tag was never loaded.
- Attempt r4 removes only that invalid distribution lookup and adds a native
  module-path assertion. The exact Mooncake Git HEAD, store/engine binaries,
  seven static symbols, and later NPU runtime APIs remain hard gates. Identity
  regression coverage prevents reintroducing the wheel-only probe; no
  `repos/*` source was modified.
- Attempt r4 built and loaded native ARM64 image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z-r4`.
  Manifest digest is
  `sha256:d957c3950e54f2b7857b3ddf5e39f81c6e755d41c37bfab178cdcf587a0a8477`
  and config ID is
  `sha256:60ef6bbf63d353e4d3f06057a8b8eb53233bb4f6942a7f8466c35081cf87a358`.
  Exact source heads, raw dependency-health allowlist, native libraries, seven
  Mooncake APIs, NPU availability/health, and imageID matching all passed.
- Recreated only the dedicated CPU-only `liangjiahao/vllm-ascend-ut` Pod on
  the R4 image. It retained CPU/memory-only resources with no NPU, driver,
  model, or hostPath mount. AscendStore passed `476` tests, deployment tooling
  passed `65`, and Ruff lint/format, Python compilation, source history, clean
  tree, and diff checks passed with bytecode/cache disabled.
- G0 static and dynamic identity passed in both engine Pods: exact imageID and
  source heads, package versions, seven session/range APIs, `torch_npu` NPU
  availability, `npu-smi` health, native `ldd`, model/tokenizer hashes, Master
  `30000 ms` lease TTL, and an initially empty pool were all proven.
- Both Prefill and Decode failed deterministically during scheduler startup
  before serving. vLLM-Ascend
  `patch_kv_cache_coordinator.py:518` forwarded
  `max_num_batched_tokens`, while pinned vLLM commit `54503ecec` exposes
  `max_in_flight_tokens` and no such keyword. The exact TypeError appeared in
  both full logs. The wrapper file has no diff across
  `a46a1dabb..14beaf161`, so this is an inherited collaborator-base
  production ABI defect, not a Mooncake conflict-resolution change.
- Terminated the validation before G1 under the source-freeze rule. No
  `repos/*` file changed. All live vLLM processes and endpoints were stopped,
  Master was reset to zero keys, zero allocated bytes, and zero active clients,
  and the final source target/protected remote refs remained
  `14beaf161cca6f1e044e20529ca96c6554dbbe50` and
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156` respectively.
- Failure cleanup exposed a separate control-tooling issue: `kill -0` treated
  unreaped API-server zombies as live and waited 60 seconds per role. The base
  ConfigMap now shares the stress runtime's `live/absent/zombie` PID helper;
  base/stress regression coverage passed `3` tests, the full deployment
  collection passed `65`, and rendered scripts, Ruff, compile, diff, and
  manifest dry-run gates passed. Fixture-sync, stale-Ruff-path, format, Master
  metrics race, and checksum-cwd retries are preserved in evidence.
- Committed immutable run evidence and the control-only cleanup fix as
  `dfe99a1fa7c246f9d84320deac2f143033cec12b`. The self-contained termination
  report is `full-validation-rerun-2026-07-30.md`; G1, lease, G4, smoke, and
  stress were not run and must start under a new image/run identity after a
  separately authorized production source fix.
- `pwsh` and `powershell` remained unavailable. Linux equivalents of
  `lock-repos.ps1`, `status-all.ps1`, and `validate-workspace.ps1` passed. The
  lock refresh corrected Mooncake's checkout label from the stale local branch
  name to actual clean detached state `detached:786c77ff`; no Mooncake ref or
  source file was changed.

## 2026-07-31

- Corrected the full-validation compatibility identity to the source branch's
  `main-verified` vLLM commit `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
  with no `VLLM_VERSION` release override. Rebuilt exact native ARM64 image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`;
  manifest is
  `sha256:866ba89f897464a1e38893a57f6e5c3a035c7aba7dfa196fce9646498eaf6d97`
  and config is
  `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`.
- The dedicated CPU-only `liangjiahao/vllm-ascend-ut` Pod passed the complete
  AscendStore suite (`476 passed`) and deployment tests (`67 passed`). G0
  started both engines without the historical coordinator `TypeError`; G1
  passed 43 direct ranged cases including 24 negative cases; lease validation
  returned exact stale-session `-707` and recovered with a fresh session; G4
  proved ranged save/load layers `0..26` and zero whole-key calls.
- Formal smoke failed only direct concurrent case 2. Response
  `cmpl-b4925b9042a7f091` had the exact case 2 prompt digest, usage, and finish
  reason but omitted `CASE_TWO` while Decode logged `25/25`, 3200 hit tokens,
  and `use_layerwise=True`. Its serial replay passed; proxy concurrency and
  the 12/12 response-log correlation checker passed.
- An evidence-only focused replay reduced the trigger to warm pair 2/3. Case 2
  alone, pair 0/2, and pair 1/2 each passed 10/10; pair 2/3 failed 1/10 and then
  9/30, always case 2. After stopping both engines and resetting Master, the
  identical cold pair passed 30/30, with all 60 response IDs correlated to
  `hit_blocks=0/25`. This warm/cold differential falsified response ordering,
  marker checker, fixed seed, and generic concurrent-generation explanations.
- Classified the result as a production concurrent layerwise warm-load defect
  and terminated before Stress S1-S3. No `repos/*` file changed. Final cleanup
  stopped both vLLM children and reset Master to zero keys, zero allocated
  bytes, and zero active clients.
- Validation-only issues repaired during the run were: terminating-old-Pod
  image wait selection, unsupported JSONPath null predicate, summary
  JSON/Python quoting, raw binary evidence attributes, duplicate G0 `pod`
  resource type, self-matching G1 `pgrep`, host Python 3.9
  `zip(strict=True)`, and the focused driver's nonexistent Decode service DNS.
  The final issue was corrected to proxy `/listEndPoints` discovery. No
  production behavior or hard oracle was weakened.
- Finalization also corrected execution-only assumptions: using the fixed
  `/workspace/tools/ruff` binary instead of a missing Python module, removing
  an early `py_compile` bytecode directory before checksumming, placing the
  report's script digest on the checker-required line, matching Git's default
  detached abbreviation in the Linux status equivalent, limiting workspace
  feature enumeration to direct children, and replacing one shell search that
  had unescaped backticks. All corrected checks passed afterward.
- Checksummed smoke evidence has manifest digest
  `b781d2598c1d7a397a11d650abb9b7448b8354bf20f46762a15844164e35bffb`.
  Evidence commit `25bc3f55546de727fcdddfba0110b3d1d2b93614` was pushed normally from
  remote checkpoint `456726bcda5bbce6e73d5a36672f308b82765435`;
  post-push `git ls-remote` matched and left/right count was `0 0`.
- `pwsh` and `powershell` were unavailable. Linux equivalents of
  `lock-repos.ps1`, `status-all.ps1`, and `validate-workspace.ps1` passed after
  the documented equivalence corrections: all three nested repos matched the
  lock and were clean; one tracked feature and ten snapshots passed workspace
  validation.
- Published the self-contained failure report and final state as
  `7b3d0a991fcf91bbc6d008d7b4ab361414e2aeb3` by normal fast-forward from
  evidence checkpoint `25bc3f55546de727fcdddfba0110b3d1d2b93614`.
  Post-push live `git ls-remote` returned `7b3d0a991fcf91bbc6d008d7b4ab361414e2aeb3`
  and `git rev-list --left-right --count` returned `0 0`. This metadata-only
  follow-up records the completed publication check; its own remote equality
  is verified independently after push.
- Published evidence commit `dfe99a1fa7c246f9d84320deac2f143033cec12b`
  and final report/state commit
  `2895913410272e4b93c8aadc20940959915f4039` by a normal fast-forward from
  control remote checkpoint `4b296c18472aec46bddeae9974bad24252fd44dc`.
  Post-push `git ls-remote` returned `2895913410272e4b93c8aadc20940959915f4039`
  and `git rev-list --left-right --count` returned `0 0`. This metadata-only
  follow-up records that completed publication check; its own remote equality
  is verified independently after push.

## 2026-08-03

- Reproduced the 2026-07-31 warm pair 2/3 defect on the unchanged image and
  Pod UIDs at `20/120` failed rounds. Every failure affected case 2 with the
  same marker-free continuation while Decode reported 25/25 block hits and
  3200 hit tokens.
- Temporary tagged probes proved scheduler block allocation, worker `ReqMeta`,
  ranged key/local-buffer rows, and attention block-table rows were aligned for
  failed requests. Experiments that split duplicate keys (`26/120` failed) or
  synchronized the NPU after each ranged get (`19/120` failed) were falsified
  and reverted.
- The accepted fix keeps Mooncake key-major batching inside each request and
  dispatches concurrent requests separately. Focused UT went red then green;
  row-local failure filtering is also covered. The complete AscendStore suite
  passed `478` tests, and two independent warm pair 2/3 runs passed `120/120`
  each. All temporary `[DEBUG-KVPAIR-20260803]` source and bytecode probes were
  removed.
- Committed and normally pushed source fix
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` (`fix(kv_pool): isolate
  concurrent Mooncake range loads`). Origin matched and left/right was `0 0`.
  The original 11 Mooncake integration commits remain linear and unmodified;
  this is a twelfth post-validation bugfix commit.
- Per explicit user direction, the next full validation reuses image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`
  without rebuilding. The run freezes image source `14beaf161` separately from
  final Python source `d28c52958`, permits only the two changed package files,
  and requires host/Prefill/Decode/UT checksums plus every source-dependent
  gate to rerun.
- The overlay validation tooling now fail-closes on the exact two-file package
  set, verifies host/Prefill/Decode checksums, disables Python bytecode writes
  in base and stress engines, and records image-source and final-source
  identities separately. Before the tooling freeze, the complete deployment
  collection passed `69` tests in the dedicated CPU-only UT Pod; Ruff
  lint/format, shell syntax, rendered ConfigMap Python/shell checks, all 10
  manifest client dry-runs, and source/control diff checks passed.
- Superseded tooling attempts were not treated as runtime failures: host Python
  lacked pytest; the first Pod fixture omitted `workspace.lock.json` and
  `Dockerfile.a2`; and the new bytecode assertion initially failed only Ruff
  formatting. The fixture layout and test formatting were corrected, then all
  affected gates were rerun to green. No production source changed during T0.
- The dedicated CPU-only UT Pod then passed the complete AscendStore collection
  (`478 passed`) and deployment collection (`69 passed`) with bytecode and
  pytest cache disabled. G0 proved the original imageID plus exact host,
  Prefill, Decode, and UT checksums for the two overlaid Python files. G1 passed
  3 keys across 4 layers with 40 API calls, 43 cases, and 24 negative cases.
- Lease validation passed two 31.5-second waits, exact stale-session result
  `-707`, fresh-session exact recovery, and empty cleanup. G4 passed all 27
  Prefill range saves, one ordered final commit, all 27 Decode range loads, and
  zero whole-key calls.
- The formal four-request smoke passed cold baseline 4/4, five warmups, direct
  concurrent loads 4/4, proxy concurrent loads 4/4, and all 12 response/hit
  correlations. This clears the exact hard gate that failed on 2026-07-31;
  marker ownership, token/usage, finish-reason, and foreign-marker oracles were
  unchanged.
- Stress ran on Prefill DP2/TP2 plus Decode DP1/TP2. S1 passed 4/4 at 508 keys,
  S2 passed 16/16 at 288 keys, and S3 passed its pinned probe plus 4/4 proxy
  cases at 348 keys. All `163/163` recorded runtime steps exited 0, all
  scenarios had zero whole-key events, and both Prefill DP ranks were active.
- Validation execution corrections were preserved in the tracker: an
  over-escaped UT checksum command; one lease post-rollout endpoint race; the
  G4 pre-request active-client oracle corrected before any request; the smoke
  offline warmup count corrected from four to five; and credential-safe
  capacity projection with a regression test. The final deployment collection
  passed `70` tests and capacity arithmetic remained unchanged.
- Evidence commit `03d13567659a30c2df42521f1a0d384c30d220c1` contains 616
  files. Root `SHA256SUMS` digest is
  `e66b4909df7a3bcf6e870c434f37590aad3927f800dfdfadc1f5c710fc7f4aa5`;
  complete `sha256sum -c` replay passed. Six dated family/umbrella reports pass
  the fail-closed report checker after placing each `Script SHA256` and digest
  on the same line.
- Final live audit confirmed the original retained Pod and node UIDs, imageID,
  overlay checksums, CPU-only UT contract, stopped Prefill/Decode child
  processes, and Master keys/bytes/clients `0/0/0`. The cluster was not
  reorganized. The six-NPU stress Pods, Master, proxy, and UT Pod remain
  retained; `deployment_yaml/` and `dockerfile.vllm23` remain untouched.
- A publication audit accidentally broadened Ruff to the entire historical
  deployment directory and exposed one existing unused checker read plus seven
  existing format differences. Those files were not changed because rewriting
  the frozen stress checker after runtime would invalidate its evidence. The
  formal scope was rerun instead: all three source-fix Python files and the
  credential-safe tooling test passed Ruff and format checks.
- Published the six self-contained reports, completed tracker, indices, lock,
  and repo state as `127e781277c21bb3a28de2a2a1d53aa0619c9d97` by a normal
  fast-forward from evidence commit
  `03d13567659a30c2df42521f1a0d384c30d220c1`. Post-push `git ls-remote`
  returned `127e781277c21bb3a28de2a2a1d53aa0619c9d97` and
  `git rev-list --left-right --count` returned `0 0`.

## 2026-08-04

- Created independent source branch `wip/mooncake-review-findings-d28c529` from
  `14beaf161cca6f1e044e20529ca96c6554dbbe50` without modifying either protected feature branch.
  Replayed the unsigned post-validation fix as signed commit `04cb824f6e8161e89547f220b92a0bc42ba0531a`.
- Implemented all seven review findings: multi-group Mooncake keys/sessions/transfers/failure
  handling in `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d`; request-local ranged failure isolation and
  immutable `LayerRangeRow` in `fdd0713e607ab919e08272e81f2925f191de678d`; shared audit emitters
  and corrected Client API documentation in `69819f6ea9a67944c14f749a66bffeba02d0db3f`; and the
  configurable real Mooncake/NPU nightly performance gate in
  `f97aed26f25a3427f20bdb7587b720dd6ef25bbf`.
- Final CPU/mock verification in the tar-synced CPU-only `liangjiahao/vllm-ascend-ut` Pod passed
  `534` tests with bytecode and pytest cache disabled. All 22 Python diff files passed Ruff and
  format checks, 12 source files passed `py_compile`, `git diff --check` passed, and the five WIP
  commits are signed with no merge commit. The benchmark collected one test and skipped as
  designed without external configuration; a real Mooncake/NPU performance run remains required.
- Protected local/origin refs remained unchanged:
  `feature/mooncake-layerwise-kv-pool` at `b5b65d9bbe325d009ad887fb87b8883b7ecee156` and
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` at
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`.
- Configured the control repo and all three nested repos to use the same workspace-only helper,
  `store --file=/root/.config/git/credentials-vllm-workspace`, with `credential.useHttpPath=false`
  and store mode `0600`. The stored token matches the existing global GitHub token, but a normal
  source WIP push returned HTTP 403 because it authenticates `swallowCXY`, which has no write
  permission to `jiahaoliang/vllm-ascend`; no source remote ref was created or modified.
- `pwsh` and `powershell` are unavailable. Linux equivalents of `lock-repos.ps1`,
  `status-all.ps1`, and `validate-workspace.ps1` passed: all three nested repos are clean and match
  the refreshed lock, workspace required paths and snapshot headers are valid, and the lock schema
  contains every required repository field. Control `git diff --check`, JSON parsing, source DCO,
  history, and protected-ref checks also passed.
- The control branch was a verified fast-forward from remote checkpoint
  `bc75cb6adf7aa3dd9bc0a2089e8ff6efa94c3a0f`, but its normal push was also rejected with HTTP 403
  for authenticated account `swallowCXY`. `origin/kv-pool-layerwise-reuse` remained at that
  checkpoint. Source and control publication both require a GitHub token with write permission to
  the `jiahaoliang` forks; repeated retries with the current token were stopped.
- After replacing the workspace-only credential with a token that has access to the `jiahaoliang`
  forks, normally pushed `wip/mooncake-review-findings-d28c529` to vLLM-Ascend origin. Live
  `git ls-remote` returned `f97aed26f25a3427f20bdb7587b720dd6ef25bbf`, and
  `git rev-list --left-right --count origin/wip/mooncake-review-findings-d28c529...HEAD` returned
  `0 0`. Both protected source refs remained unchanged.
- Committed the refreshed source publication state as
  `b22dff4080dcc7e89a191ad41882adb6c8eee2a5` and normally fast-forward pushed the control branch
  from remote checkpoint `bc75cb6adf7aa3dd9bc0a2089e8ff6efa94c3a0f`. Post-push
  `git ls-remote` returned `b22dff4080dcc7e89a191ad41882adb6c8eee2a5`, and
  `git rev-list --left-right --count origin/kv-pool-layerwise-reuse...HEAD` returned `0 0`.
- Decided to defer authoritative design §5.8 from the current merge target. The design snapshot now
  retains multi-group as future work and explicitly forbids claiming it as supported or validated
  on `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`.
- Switched the active vLLM-Ascend checkout from the clean, published WIP `f97aed26f` back to
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` at local/origin
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`; no source commit or worktree change was made.
- Classified WIP merge candidates without §5.8: exclude `0dad9ad94`; do not cherry-pick the empty
  signed replacement `04cb824f6`; selectively backport the single-group `SP2`/`ST4` parts of
  `fdd0713e6` and the `ST1`/`ST5` parts of `69819f6ea`; `f97aed26f` is an independent direct
  cherry-pick candidate. `git apply --check` confirmed only `f97aed26f` applies directly to
  `d28c52958`; no candidate was applied in this decision step.
- Applied the approved single-group content as signed commits `8d9897143`,
  `189dcdd2c`, and `6451f9010`. A two-axis review then found ranged-success,
  centralized-env, hot-path, magic-number, and limitation-documentation issues;
  signed correction `d5f0ea7f8` fixed them before source freeze. No §5.8 symbols
  entered the range.
- The CPU-only `liangjiahao/vllm-ascend-ut` Pod passed `490` source tests. Ruff,
  format, compile, DCO, no-merge, protected-ref, and diff gates passed. The
  target source branch was normally pushed from `d28c52958` to `d5f0ea7f8`;
  live left/right is `0 0`, while protected branch local/origin remains
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`.
- Full validation run `20260804T103209Z` passed G0/G1, lease, G4, smoke, and
  stress S1-S3. Physical NPU 1 was isolated before the passing stress run; the
  only post-freeze code change was validation tooling to support a clean start
  without retained engine Pods. The complete deployment suite passed `82`.
- Raw evidence and checksums remain local. Two external evidence-push attempts
  were rejected by the workspace safety gate, first for raw cluster/runtime
  logs and then for curated summaries/source-publication metadata. The control
  branch therefore publishes reports/tooling/state only; it does not upload
  this run's evidence payload.
- Published the report/state checkpoint as
  `2ecc56730cf29c0765460e66db3ad5fb09789b5b`. Live `git ls-remote` matched
  that control SHA and source `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`;
  both left/right counts were `0 0`. Protected source ref
  `feature/mooncake-layerwise-kv-pool` remained
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`.
- Audited the complete source range from pinned parent `a46a1dabb` through
  `d5f0ea7f8`: all 16 linear commits were authored and committed by
  `jiahaoliang <gzliangjiahao@gmail.com>`. The fetched moving collaborator ref
  had been force-updated to `e4f2dd3e6`; it was explicitly excluded because
  the requested result must preserve the `d5f0ea7f8` tree.
- Rewrote only
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` into eight
  functionally grouped DCO-signed commits: foundations `7b5e57d5b`, ranged
  transfers `309798210`, session orchestration `c429750b9`, audit introduction
  `a4e4c8787`, Mooncake API compatibility `0b4445773`, request failure
  isolation `e6391552c`, audit centralization `e1979b151`, and performance
  contract alignment `6bf3fb04c`.
- Every rewritten commit tree exactly matches its selected original group
  endpoint. Final old/new trees are both
  `ca363697034538b86626517066940315283ac8ad`; `git diff` is empty, merge-base
  is the pinned `a46a1dabb`, commit count is eight, merge count is zero, DCO is
  complete, and §5.8 prohibited symbols remain absent. A local recovery ref
  preserves old tip `d5f0ea7f8`.
- Re-synchronized the identical tree by tar into the CPU-only, no-hostPath
  `liangjiahao/vllm-ascend-ut` Pod and ran with bytecode and pytest cache
  disabled. AscendStore, env, and performance-contract tests passed
  `492 passed, 1 skipped`; the skip is the expected unconfigured real
  Mooncake/NPU benchmark. All 22 Python diff files passed Ruff lint/format,
  11 production files passed `py_compile`, and `git diff --check` passed.
- The source remote still pointed to exact old checkpoint `d5f0ea7f8` before
  publication. An explicit old-SHA `--force-with-lease` updated only the target
  ref to `6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7`; live `git ls-remote` matched,
  left/right is `0 0`, and protected local/origin
  `feature/mooncake-layerwise-kv-pool` remains `b5b65d9bb`.
- Added the recoverable execution plan and detailed Chinese committer report.
  Historical run `20260804T103209Z`, `validation-identity.json`, and checksummed
  evidence remain immutable at source identity `d5f0ea7f8`; exact tree identity
  supports the current code but is not represented as a newly executed full
  NPU validation or throughput benchmark.
- `pwsh` and `powershell` were unavailable. Linux equivalents of
  `lock-repos.ps1`, `status-all.ps1`, and `validate-workspace.ps1` passed:
  lock schema/remote contracts are valid; all three nested repos are clean and
  match branch/HEAD pins; required paths, workspace instruction text, the one
  tracked direct feature, and all snapshot headers passed. The first ad hoc
  feature check incorrectly treated nested README files as feature roots; it
  was corrected to the PowerShell script's direct-child enumeration and rerun
  without any repository file change.

## 2026-08-07

- Froze the rewritten Mooncake collaborator implementation at read-only detached
  `df3f74ed8ebdb0c935554beea6299a9f11c723e2`. The seven session/range API names
  remain unchanged; failed revoke now intentionally retains the local session.
- Added vLLM-Ascend ownership state for failed cleanup in DCO commit
  `45b2e785b10ca4604cd6314819ed15f3ff674781`. `_put_started_keys` contains only
  writable sessions, `_put_revoke_pending_keys` fails closed, cleanup retries
  only failed keys up to three attempts, and commit/revoke release tracker state
  only for result-zero keys.
- TDD red reproduced ten missing ownership/retry behaviors. The final tar-synced
  CPU-only `liangjiahao/vllm-ascend-ut` gate passed `495` AscendStore tests;
  `/workspace/tools/ruff`, `py_compile`, and `git diff --check` passed. The source
  commit was normally pushed and local/origin left-right is `0 0`.
- Tooling freeze `4b5e49900a9ea3cd50344cb053747dc9e5a5b07b` pins native image tag
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`,
  removes the formal Python overlay path, and marks FabricMem disabled/out of
  scope. Deployment tests passed `83`; shell, JSON, Ruff, and diff checks passed.
- Created validation run `20260807T100722Z`. At this checkpoint only source and
  tooling are frozen; native image construction and A2 full validation remain
  pending and are not yet claimed.
- Built the frozen native image with exit `0`. Containerd records manifest
  `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351`
  and config
  `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b`
  for `linux/arm64`; OCI labels and in-image Git HEADs match all three frozen
  commits. The dependency allowlist, Mooncake native module and seven static
  APIs, and vLLM-Ascend native modules passed.
- The live `default/buildkitd` Pod was Ready, privileged, restart-free, and
  scheduled on ARM64 node `m1` with the recorded BuildKit image digest. Corrected
  the earlier `builder_node: n1` metadata before any UT or A2 runtime family;
  runtime workloads remain pinned to `n1`. The image evidence preserves two
  superseded validation-command failures: an over-broad log match and missing
  host CNI bridge for default `nerdctl run`; exact regex and `--net=none`
  replacements passed.
- Recreated only `liangjiahao/vllm-ascend-ut` from the native image. The new Pod
  UID uses config ID
  `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b`,
  is Ready/restart-free, and has no NPU resource, driver/model/hostPath mount,
  or service-account token. Tar-synced clean source passed `495` AscendStore
  tests; a corrected cache-excluding control sync passed `83` deployment tests.
  Ruff lint, isolated `py_compile`, source `git diff --check`, exact package/Git
  metadata, and zero source cache pollution passed. The evidence retains a
  non-contract Ruff formatter result and the first cache-copying tar attempt as
  superseded execution checks; neither changed source or weakened a required
  gate.
- G0 replaced the retained historical 4+2 engine Pods with exact new-image 1+1
  base Pods after stopping their vLLM children. Live physical capacity was 7
  cards after replacement accounting. Both runtime checkers loaded the seven
  Mooncake APIs from the native image, the read-only no-overlay gate passed,
  NPU/model/ldd and Master 30000 ms TTL checks passed, both APIs became Ready,
  and proxy discovery was exactly 1P1D. Both child processes were then stopped;
  the reset Master reported keys/allocated bytes/active clients `0/0/0`.
  The evidence records the corrected `tokenizer.json` checker target and an
  early selector wait superseded by exact old-Pod deletion plus new UID/imageID
  assertions.
- Before G1, audit found that the direct ranged negative suite did not prove a
  same-key `PutStart` after successful revoke. TDD correction
  `3bda70d786db46310994afc689af4fc10da4858e` added result-zero restart and
  second-revoke cleanup gates. The cache-excluding tar-synced
  `liangjiahao/vllm-ascend-ut` run passed all `84` deployment tests, Ruff lint,
  isolated `py_compile`, host/Pod SHA256 equality, and cache-free checks. The
  earlier broad formatter result remains a non-contract extra check. An
  existing Ruff cache was recorded and removed before a `--no-cache` rerun.
  This direct-driver-only change does not invalidate G0; G1 had not started.
- Direct G1 on the stopped Prefill NPU Pod passed all `45` cases, including
  `26` negative cases and result-zero same-key restart/cleanup after revoke.
  Eight positive ranged calls covered three keys, four layers, and two
  fragments per key; all per-key byte results were `4096` and final source and
  destination SHA256 matched. Master metrics were `0/0/0` both before reset
  and after reset. The first preflight assertion incorrectly required
  container readiness after the intentional G0 engine stop; the replacement
  required Running Pods, `ready=false`, exact image/config ID, one physical NPU
  request each, zero restarts, and no vLLM PID.
- Lease validation used the live `30000ms` TTL and `1500ms` margin. The put and
  get waits were `31500.128ms` and `31500.090ms`; slow put committed, stale
  ranged read returned exact `-707`, and fresh get recovered exact two-layer
  bytes. All `13` recorded execution steps were green, cleanup returned Master
  to `0/0/0`, and the post-family reset was also empty.
- G4 attempt 1 completed a valid HTTP 200 runtime request and the stable
  27-layer checker passed, but an evidence-local assertion compared the whole
  response `usage` object and rejected the valid extra
  `prompt_tokens_details: null` field. The failure trap stopped both vLLM
  children and reset Master to `0/0/0`. A focused standalone validator changed
  only that check to exact prompt/completion/total fields and replayed the
  captured attempt successfully; the failed attempt remains checksummed.
- The complete G4 rerun then passed all `41` runtime steps. Prefill save and
  Decode load each covered layers `0..26`; for every layer and key,
  `147456 == 131072 + 16384 == result`. Final-layer commit `[0,0,0,0]`
  followed the last save, whole-key calls were zero, Decode logged `512/512`
  hit correlation, and post-request Master metrics were 4 keys, 15925248 bytes,
  and 2 active clients. Both engines were stopped and reset Master ended at
  `0/0/0`.
- The formal 1P1D smoke runner passed with exit `0`: four cold baseline, five
  warmup, four direct load, and four proxy concurrent cases all satisfied
  marker token/text prefixes, foreign-marker exclusion, prompt/completion
  usage, generated token count, and finish reason. All `12` request/role hit
  correlations passed at 25 blocks and 3200 tokens; the expected Master key
  count was 64. The wrapper's immediate metrics read raced the endpoint after
  a successful cleanup rollout; its failure trap reset Master again, and the
  replacement 60-second retry proved both engine PIDs absent and Master
  `0/0/0`. No smoke runtime gate was rerun because the nonzero step occurred
  only after the complete runner and independent hard-oracle assertion passed.
- Stress ran once on Prefill DP2/TP2 plus Decode DP1/TP2 with 7 physical cards
  available and 6 required. S1 passed `4/4` pinned 16K cases at 508 keys, S2
  passed `16/16` concurrent 8K cases at 288 keys, and S3 passed its pinned 32K
  proof plus `4/4` concurrent cases at 348 keys. Marker isolation was `4/4`,
  `16/16`, and `4/4`; both Prefill DP ranks were active, all 27-layer
  range/commit checks passed, and whole-key calls were zero.
- All `164/164` stress ledger steps exited zero. The runner stopped both vLLM
  children, confirmed PID-file absence and refused HTTP endpoints, and retained
  the six-NPU Pods. A final explicit Mooncake Master restart and rollout then
  returned key count, allocated bytes, and active clients to `0/0/0`.
- Stress `SHA256SUMS` covers 392 immutable files and replayed successfully; its
  manifest digest is
  `1fd99b15ad418508d0ff97b162fb563f33b3c097aeffbd9f3dc4d8ae3938c88c`.
  Six self-contained 2026-08-07 family/umbrella reports and final structured
  state were added. The long-running `liangjiahao/vllm-ascend-ut` Pod and
  `default/buildkitd` remain retained; `deployment_yaml/` and
  `dockerfile.vllm23` remain untouched.
- The evidence-root `SHA256SUMS` covers 797 files and replayed successfully;
  its manifest digest is
  `e5a13d163cfd98fe547c44ec22dc6c1c9688a07e42609d885f88935892a37f08`.
