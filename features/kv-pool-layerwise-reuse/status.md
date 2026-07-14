# kv-pool-layerwise-reuse Status

Current Phase: Mooncake session API WIP integrated

## Baseline

- `repos/vllm`: `v0.20.2` (`bc150f50299199599673614f80d12a196f377655`)
- `repos/vllm-ascend`: `feature/new-memcache-layerwise` (`b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`)
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` (WIP)

## Next Steps

- Resolve the `batch_put_end` idempotency and ranged-put `config` signature mismatches between the frozen contract and Mooncake PR #2881.
- Build a wheel from the recorded PR head and run the session/range contract gate before NPU integration.
- Start the vLLM Ascend implementation from the baseline and milestones in `implementation-plan.md`.
