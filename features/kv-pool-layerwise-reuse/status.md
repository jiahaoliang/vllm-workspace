# kv-pool-layerwise-reuse Status

Current Phase: source implementation complete

## Baseline

- `repos/vllm`: `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`)
- `repos/vllm-ascend`: `feature/mooncake-layerwise-kv-pool` (`631b893e91821f32f0613a7aeb7e169de4b9203e`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Integrate the Mooncake wheel and run contract/NPU gates.
