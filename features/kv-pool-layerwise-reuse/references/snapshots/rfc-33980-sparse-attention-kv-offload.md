Source: https://github.com/vllm-project/vllm/issues/33980
Captured At: 2026-07-03T11:54:56+08:00
Notes: Reference RFC for sparse attention KV offload context and related constraints.

# RFC #33980: Sparse Attention KV Offload

This snapshot records the RFC link for the `kv-pool-layerwise-reuse` workspace setup. Use the upstream issue as the authoritative source during design review.

Local interpretation for this feature:

- Treat sparse-attention KV offload requirements as compatibility context.
- Avoid designing a memcache-specific path into the final Mooncake-backed implementation.
- Check interaction with vLLM Ascend attention and KV pool scheduling paths before source changes.
