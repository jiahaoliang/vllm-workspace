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
