Source: https://github.com/ader47/vllm-ascend/commit/674594c51d6f22c12136e5130ce4c677c9f913ec
Captured At: 2026-07-03T11:54:56+08:00
Notes: Reference implementation uses memcache; this workspace targets equivalent behavior with Mooncake.

# ader47 vLLM Ascend Reference Commit

Commit: `674594c51d6f22c12136e5130ce4c677c9f913ec`

Title: `feat(kv_pool): add kv-pool-layerwise with layer reuse support`

Discovered branch: `kv-pool-layerwise-reuse`

## Summary

The reference commit implements per-layer KV cache transfer with HBM buffer reuse for the AscendStore KV pool connector. It adds layer reuse behavior using a smaller set of HBM buffers and remote storage movement. This workspace uses the commit as a reference, but should avoid carrying over memcache-specific design unless it is needed only for comparison.

## Changed Areas

- `tests/ut/device_allocator/test_cpu_binding.py`
- `vllm_ascend/attention/attention_v1.py`
- `vllm_ascend/attention/context_parallel/attention_cp.py`
- `vllm_ascend/attention/mla_v1.py`
- `vllm_ascend/attention/sfa_v1.py`
- `vllm_ascend/cpu_binding.py`
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/memcache_utils.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- `vllm_ascend/memcache_comm_fence.py`
- `vllm_ascend/patch/platform/patch_layerwise_kv_cache_reuse.py`
- `vllm_ascend/worker/model_runner_v1.py`
- `vllm_ascend/worker/worker.py`

## Design Reminder

Use this commit to identify required integration points and state transitions. Rework backend-specific operations around the bundled Mooncake version `v0.3.8.post1`.
