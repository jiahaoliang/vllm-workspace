# kv-pool-layerwise-reuse Status

Current Phase: source implementation complete

## Baseline

- `repos/vllm`: `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`86049166111583446f1949941b48ad7c134cb68d`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Integrate the Mooncake wheel and run contract/NPU gates.

## Latest Validation

- Rebasing onto `ader47/feature/new-memcache-layerwise` at `5875ff0b366690c64324d71b47f9409f8cd762da` completed on 2026-07-15.
- The CPU AscendStore suite passed with `347 passed`; focused Ruff and `git diff --check` also passed.
- The source history is split into six review-sized commits with a final tree identical to the pre-split rebase tip `89b87ee2a1be466939579c165cba9df6b3824643`.
