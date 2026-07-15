# kv-pool-layerwise-reuse Status

Current Phase: source implementation complete

## Baseline

- `repos/vllm`: `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`1143c6470624e8e7d820a841c88117f9df36aebc`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Integrate the Mooncake wheel and run contract/NPU gates.

## Latest Validation

- Rebasing onto `ader47/feature/new-memcache-layerwise` at `5875ff0b366690c64324d71b47f9409f8cd762da` completed on 2026-07-15.
- The accepted metadata review findings were implemented and folded into the six review-sized commits. The rewritten history was pushed with `--force-with-lease`; its final HEAD is `1143c6470624e8e7d820a841c88117f9df36aebc`.
- On the final rebased HEAD, the CPU AscendStore suite passed with `353 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all six commits also passed.
