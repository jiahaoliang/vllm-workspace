# kv-pool-layerwise-reuse Sources

## Bundle Baseline

- vLLM: <https://github.com/vllm-project/vllm/releases/tag/v0.20.2>
- vLLM Ascend: <https://github.com/vllm-project/vllm-ascend/releases/tag/v0.20.2rc1>
- Mooncake: <https://github.com/kvcache-ai/Mooncake/releases/tag/v0.3.8.post1>

## Reference Code

- ader47 vLLM Ascend commit: <https://github.com/ader47/vllm-ascend/commit/674594c51d6f22c12136e5130ce4c677c9f913ec>
- Collaborator branch: `collaborator/feature/new-memcache-layerwise` from <https://github.com/ader47/vllm-ascend/tree/feature/new-memcache-layerwise>
  - Local reference: `reference/ader47-new-memcache-layerwise`
  - Personal fork mirror: `origin/feature/new-memcache-layerwise`
- vLLM Ascend PR #11444, memcache layerwise KV pooling reference: <https://github.com/vllm-project/vllm-ascend/pull/11444>
- vLLM Ascend PR #10733, layerwise KV pool reuse coordination target: <https://github.com/vllm-project/vllm-ascend/pull/10733>

## RFC

- vLLM issue #33398: <https://github.com/vllm-project/vllm/issues/33398>
- vLLM issue #33980: <https://github.com/vllm-project/vllm/issues/33980>

## Design Notes

- Mooncake Layerwise KVPool Put design: <https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/HJGESQG4ze>
  - Local snapshot: `features/kv-pool-layerwise-reuse/references/snapshots/design-mooncake-layerwise-gva-put.md`

## Local Snapshots

- `snapshots/rfc-33398-layerwise-kv-offload.md`
- `snapshots/rfc-33980-sparse-attention-kv-offload.md`
- `snapshots/ader47-vllm-ascend-674594c5-kv-pool-layerwise-reuse.md`
- `snapshots/design-mooncake-layerwise-gva-put.md`
- `snapshots/pr-11444-layerwise-kv-pooling-memcache.md`
- `snapshots/pr-10733-layerwise-kv-pool-reuse.md`

## Local Patch Archives

- `patches/pr-11444-layerwise-kv-pooling-memcache.patch`
- `patches/pr-10733-layerwise-kv-pool-reuse.patch`

