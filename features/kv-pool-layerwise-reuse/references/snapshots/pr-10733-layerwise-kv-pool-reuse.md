Source: https://github.com/vllm-project/vllm-ascend/pull/10733
Captured At: 2026-07-09T19:21:19+08:00
Notes: Coordination target from ader47's branch; captures the layerwise KV pool reuse and Mooncake PD-transfer synchronization work that the Mooncake KVPool implementation must coexist with.

# vllm-project/vllm-ascend PR #10733

Title: `[Feature][Worker] Layerwise KV cache pool with prefill layer reuse support (Prefill offload)`

Status at capture: open, not draft, mergeable_state=`dirty`

Author: `ader47`

Head: `ader47/vllm-ascend` branch `feature/layerwise-kv-pool-with-reuse` at `8dfc5ee3c7f03e5d0f0bb52f497e04938433a0e6`

Base: `vllm-project/vllm-ascend` branch `main` at `36f7e7c1d78e5aed00515787d4958b49aac9b5cf`

Created: 2026-06-18T19:13:03Z

Updated: 2026-07-02T11:26:44Z

Diff size: 4 commits, 15 files, +2820 / -736

Patch archive: `../patches/pr-10733-layerwise-kv-pool-reuse.patch`

## Why It Matters Here

This PR is the integration surface the user's work must coordinate with. It implements layerwise KV cache pool reuse on the prefill node and explicitly coordinates `AscendStoreConnector` buffer reuse with the existing `MooncakeLayerwiseConnector` PD transfer path, so reused HBM buffers are not overwritten before per-layer Mooncake P2P transfer completes.

The user's note says this is also an `ader47` branch with earlier references updated. Treat it as the branch to align with for shared-buffer lifecycle, layerwise config, model runner storage sharing, and per-layer PD handshakes.

## PR Body Highlights

- Target deployment is PD disaggregation where long-context prefill is slow and HBM-heavy.
- Layers time-share a small number of shared HBM buffers instead of each layer owning a full KV buffer.
- Before each layer runs, KV can be loaded from the pool into a shared buffer while previous compute is progressing.
- After a layer computes, KV is saved back to the pool so the buffer can be reused.
- In chunked prefill, prior-layer KV may need to be loaded again because its shared buffer slot has been overwritten.
- The feature is designed to run alongside the existing layerwise Mooncake connector that streams each layer's KV to decode nodes.
- A per-layer handshake prevents `AscendStoreConnector` reuse from overwriting buffers before Mooncake PD transfer finishes.
- Layer reuse is configured with `layerwise_num_shared_buffers`, `layerwise_prefetch_layers`, and `layerwise_independent_layers`.
- vLLM available-memory reporting is inflated by `total_layers / reuse_layers` so block accounting still reflects full layer count.
- `model_runner_v1.py` merges per-layer `KVCacheTensor` entries into shared buffers and rejects unsupported hybrid reuse.

## Changed Files

| File | Status | + | - |
| --- | --- | ---: | ---: |
| `tests/ut/distributed/ascend_store/test_layerwise_config.py` | added | 165 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_connector.py` | modified | 19 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py` | modified | 11 | 11 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/__init__.py` | modified | 29 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/backend.py` | modified | 18 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/memcache_backend.py` | modified | 50 | 11 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py` | modified | 17 | 8 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py` | modified | 177 | 12 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py` | modified | 823 | 229 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py` | added | 191 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py` | modified | 607 | 166 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py` | modified | 522 | 298 |
| `vllm_ascend/memcache_comm_fence.py` | added | 91 | 0 |
| `vllm_ascend/worker/model_runner_v1.py` | modified | 74 | 0 |
| `vllm_ascend/worker/worker.py` | modified | 26 | 1 |

## Commits Captured

- `aefbb22bdf05e654b29dfb779490d40e8c859900` - `feat(ascend): add layerwise KV cache reuse support`
- `7968b8009bf9ea4601bdde003482791b5317527d` - `fix(kv_pool): free blocks immediately on request finish in layerwise mode`
- `fd6cee275c19a57ab3954fa0ddff5c435a5a30d8` - `feat(kv_pool): sync ascend_store save with mooncake PD transfer per layer`
- `8dfc5ee3c7f03e5d0f0bb52f497e04938433a0e6` - `fix(kv_pool): re-land #10077 base modules for layerwise-with-reuse`
