# kv-pool-layerwise-reuse Status

Current Phase: source implementation complete

## Baseline

- `repos/vllm`: `v0.24.0` (`ee0da84ab9e04ac7610e28580af62c365e898389`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`6a825ca54761131c9b73c8871a886381c49513d8`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Run the real vLLM v0.24.0 integration gate, then integrate the Mooncake wheel and run contract/NPU gates.

## Latest Validation

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
