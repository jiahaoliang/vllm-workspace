Source: https://github.com/vllm-project/vllm/issues/33398
Captured At: 2026-07-03T11:54:56+08:00
Notes: Reference RFC for layerwise KV offload behavior and design context.

# RFC #33398: Layerwise KV Offload

This snapshot records the RFC link for the `kv-pool-layerwise-reuse` workspace setup. Use the upstream issue as the authoritative source during design review.

Local interpretation for this feature:

- The feature should preserve the RFC's layerwise KV movement intent.
- The implementation target is Mooncake-backed reuse in vLLM Ascend, not a memcache backend.
- Follow the bundled versions recorded in `workspace.lock.json` when comparing code paths.
