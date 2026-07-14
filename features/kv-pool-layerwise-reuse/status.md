# kv-pool-layerwise-reuse Status

Current Phase: implementation baseline

## Baseline

- `repos/vllm`: `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Implement the Mooncake layerwise Backend contract.
