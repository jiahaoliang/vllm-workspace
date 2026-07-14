# kv-pool-layerwise-reuse Status

Current Phase: workspace setup

## Baseline

- `repos/vllm`: `v0.20.2` (`bc150f50299199599673614f80d12a196f377655`)
- `repos/vllm-ascend`: `feature/new-memcache-layerwise` (`b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`)
- `repos/Mooncake`: `v0.3.8.post1` (`5738f80752d889123a6cfb44a9444da837210b00`)

## Next Steps

- Study RFC #33398 and RFC #33980 against the checked-out vLLM Ascend collaborator branch.
- Compare the ader47 memcache-based reference implementation with the bundled Mooncake backend.
- Draft the implementation design for Mooncake-backed layerwise reuse before changing source code.
