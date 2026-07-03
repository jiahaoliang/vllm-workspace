# kv-pool-layerwise-reuse Status

Current Phase: workspace setup

## Baseline

- `repos/vllm`: `v0.20.2` (`bc150f50299199599673614f80d12a196f377655`)
- `repos/vllm-ascend`: `v0.20.2rc1` (`367b8e62da799870a7476ce34f5f7658589a8aad`)
- `repos/Mooncake`: `v0.3.8.post1` (`5738f80752d889123a6cfb44a9444da837210b00`)

## Next Steps

- Study RFC #33398 and RFC #33980 against the vLLM Ascend KV pool code in this baseline.
- Compare the ader47 memcache-based reference implementation with the bundled Mooncake backend.
- Draft the implementation design for Mooncake-backed layerwise reuse before changing source code.
