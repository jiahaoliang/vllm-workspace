# kv-pool-layerwise-reuse Status

Current Phase: source implementation complete

## Baseline

- `repos/vllm`: `v0.24.0` (`ee0da84ab9e04ac7610e28580af62c365e898389`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`f5ab64a1f`),
  rebased onto `upstream/main` (`9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` (WIP)

## Next Steps

- In an environment with the Mooncake C++ toolchain, validate the unchanged collaborator wheel contract and run the real vLLM v0.24.0 integration gate. NPU E2E is not a local acceptance item.

## Latest Validation

- Implemented the accepted MC2/D3 review decisions in vLLM-Ascend fixup
  `cfe97c8de`: Mooncake load timeout now has a bounded fatal drain path without
  early `batch_get_end`, while memcache retains its original drain behavior;
  put-start exception revoke runs on the layer SendingThread control queue.
- The latest scope decision forbids Mooncake source changes. Mooncake remains
  exactly at collaborator HEAD `74b0acf15`; vLLM-Ascend adapter rollback
  `f5ab64a1f` preserves its current two-argument put-start and four-argument
  ranged-put calls.
- The complete isolated AscendStore CPU suite passed `402` tests. Focused Ruff,
  `py_compile`, `git diff --check`, and fixup commit checks passed. Real
  Mooncake wheel, memcache E2E, and NPU E2E were not run.

- Rebased the feature onto latest `vllm-ascend` `upstream/main`
  `9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384`; the rewritten signed feature HEAD is
  `1c75b507fe268b91a6f4183da0ae6221ffd05568`. The rebase preserved chunk-spanning
  Mooncake session ownership: Worker retains
  `req_id -> keys` and `key -> active request owners`, renews accumulated keys
  on every chunk, promotes only successful PutEnd keys, and calls
  `batch_get_end` only after the final owner releases a shared key.
- The accepted review fixes are folded into that commit: malformed get-start
  cleanup preserves unrelated owners, chunk preparation runs get-start before
  put-start, retry/terminal cleanup uses separate named lifecycle APIs, and a
  request retains ownership of an already-started shared put key when a new
  key's put-start fails.
- The complete isolated AscendStore CPU suite passed `398` tests. Focused Ruff
  lint, `py_compile`, and `git diff --check` passed. New tracker/test files pass
  Ruff format check; no unrelated whole-file formatting was applied to the four
  legacy files with existing format deltas.
- The rebase had semantic conflicts in `kv_transfer.py`, `pool_scheduler.py`, and
  `pool_worker.py`. Resolutions preserve upstream multi-group layer indexing and
  the feature's Mooncake key-major ranges, exception-safe finalization, and
  last-owner session cleanup.
- Real Mooncake wheel contract validation and NPU chunked-prefill E2E remain
  pending; this checkpoint does not claim runtime/NPU validation.
- Folded the accepted cross-layer range-batch test fixup into rewritten builder commit `21bd87100`, then replayed the five later commits without conflicts. Range-diff showed all five later patches unchanged.
- Force-pushed final source HEAD `8cfd1e22f92ee1a40139ea40b487fa5001d1c81f` with an exact `--force-with-lease` against prior remote `6a825ca54761131c9b73c8871a886381c49513d8`.
- On the rewritten HEAD, the complete isolated AscendStore CPU suite passed `362` tests; focused Ruff, format check, full-range `git diff --check`, and all six rewritten commit checks passed.
- Split the former `87c31d1e8` range-transfer commit into four review-sized commits: range batch builder `2b2ae920e`, exception-safe finalization `29f2a8e69`, ranged save `ff2557f74`, and ranged load `89b1a88ea`. The accepted request-accounting and save-key deduplication findings are folded into those commits.
- Replayed session orchestration as `552541f94` and documentation as `6a825ca54`, then force-pushed the rewritten source history with an exact `--force-with-lease` against `a018212f3`.
- On final HEAD `6a825ca54761131c9b73c8871a886381c49513d8`, the isolated AscendStore suite passed `361` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all 8 feature commits passed.
- Rebasing onto `ader47/feature/new-memcache-layerwise` at `5875ff0b366690c64324d71b47f9409f8cd762da` completed on 2026-07-15.
- The accepted metadata review findings were implemented and folded into the six review-sized commits. The rewritten history was pushed with `--force-with-lease`; its final HEAD is `1143c6470624e8e7d820a841c88117f9df36aebc`.
- On the final rebased HEAD, the CPU AscendStore suite passed with `353 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all six commits also passed.
- Rebasing onto the force-updated `ader47/feature/new-memcache-layerwise` at `6d0b2b70c33f70ca8d708870668514afafd1cb7e` completed on 2026-07-16. The collaborator's `d7affe61e` already contains the TP-mismatch initialization fix, so the duplicate local commit was dropped and the review history now contains five commits.
- The Backend contract was adapted to the collaborator's public `ensure_initialized()` API. On the new final HEAD, the CPU AscendStore suite passed with `354 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
- Updated `repos/vllm` to the official v0.24.0 tag `ee0da84ab9e04ac7610e28580af62c365e898389` and re-reviewed the pending Memcache TP-only plan against that source plus vLLM Ascend `bfe697450`. The plan remains applicable with a stricter direct-field validation and Mooncake/Memcache documentation alignment.
- The Windows CPU venv cannot import the real vLLM v0.24.0 package because `vllm._C_stable_libtorch` is unavailable. The baseline review is source-backed, while real cross-repo integration remains pending.
- After switching the checkout, the isolated mock-based AscendStore suite still passed `354` tests.
- Implemented the accepted Memcache TP-only decision and folded the metadata, orchestration, and documentation fixups into the five review commits. Mooncake and Memcache block-key layerwise now reject PP/PCP/DCP greater than one, while TP and non-block-key paths retain their prior behavior.
- On final rewritten HEAD `7ba9937d77189e9bb5703d0bc86727f63d0fd9a9`, the isolated AscendStore suite passed `360` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
- Replaced the topology error labels `PP`/`PCP`/`DCP` with the full `ParallelConfig` field names, folded the test and implementation fixups into the metadata and orchestration commits, and rebased onto the latest fetched collaborator head `6d0b2b70c33f70ca8d708870668514afafd1cb7e`.
- On final rewritten HEAD `a018212f32b057f1bdd75b4cbaccd2b132d2e30b`, the isolated AscendStore suite passed `360` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
