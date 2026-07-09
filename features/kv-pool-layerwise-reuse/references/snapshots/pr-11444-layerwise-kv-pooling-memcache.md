Source: https://github.com/vllm-project/vllm-ascend/pull/11444
Captured At: 2026-07-09T19:21:19+08:00
Notes: Reference implementation for layerwise KV pooling using memcache; this workspace should port the relevant scheduling/backend shape to Mooncake, not copy memcache-specific lifecycle assumptions blindly.

# vllm-project/vllm-ascend PR #11444

Title: `[KV Cache][Feature] Support Layerwise KV Pooling with Memcache Backend`

Status at capture: open, not draft, mergeable_state=`unstable`

Author: `tyy0829`

Head: `ader47/vllm-ascend` branch `feature/new-memcache-layerwise` at `b1c4ab5e0959f7c37e4d1c4ae930dfd48dfecd4d`

Base: `vllm-project/vllm-ascend` branch `main` at `2eaff29567f79c17c4f9d53411a79104c17349d6`

Created: 2026-07-04T13:29:19Z

Updated: 2026-07-07T13:06:55Z

Diff size: 1 commit, 29 files, +4599 / -860

Patch archive: `../patches/pr-11444-layerwise-kv-pooling-memcache.patch`

## Why It Matters Here

This PR is the closest code reference for the user's Mooncake implementation target. It implements layerwise KVPool save/load over the memcache backend, including address-based `batch_copy`, per-rank key choices, hit checks via `batch_get_key_info`, lease lifecycle handling, save/load GVA separation, and failure handling that avoids crashing the inference path.

The Mooncake design in this workspace intentionally differs in object lifecycle: Mooncake needs explicit `batch_alloc`, descriptor passing, `batch_copy`, `batch_commit`, and `batch_revoke` semantics, while preserving the useful vLLM-Ascend scheduling and `kv_transfer` integration shape.

## PR Body Highlights

- Previous layerwise design had per-layer keys, frequent metadata lookups, and Python-list HBM address computation overhead.
- The optimized design resolves addresses once and uses base address plus layer offset for runtime access.
- Memcache adds a new address-based `batch_copy` interface.
- HBM address computation moves to NumPy vectorized operations.
- Transfer overlap with attention is controlled to reduce runtime contention.
- Memcache keys are per block and per rank group: `{model}@{block_hash}@{head_or_tp_rank}`.
- `batch_alloc` is moved from Scheduler to Worker because memcache `gvaBlobTracker` is process-local.
- Save behavior is controlled by `put_step`; MLA can save only once per rank group.
- Full k+v writes are used to avoid memcache partial-blob errors.
- Hit blocks are skipped during save because loaded blobs become READABLE and cannot be re-saved directly.
- Separate save/load GVA fields avoid overwriting address state between alloc-for-save and prepare-load.
- `batch_get_key_info` is used instead of `batch_is_exist` to avoid false hits before save completion.
- `batch_add_lease` / `batch_remove_lease` bound the load lifecycle.
- Memcache API failures are logged and treated as pool miss/skip rather than fatal errors.

## Changed Files

| File | Status | + | - |
| --- | --- | ---: | ---: |
| `.github/workflows/scripts/test_config.yaml` | modified | 1 | 0 |
| `docs/source/user_guide/feature_guide/index.md` | modified | 33 | 0 |
| `docs/source/user_guide/feature_guide/layerwise_kv_pool.md` | added | 241 | 0 |
| `tests/ut/attention/a2/test_mla_v1.py` | modified | 0 | 1 |
| `tests/ut/conftest.py` | modified | 20 | 0 |
| `tests/ut/distributed/ascend_store/_mock_deps.py` | modified | 28 | 0 |
| `tests/ut/distributed/ascend_store/test_ascend_store_connector.py` | modified | 96 | 6 |
| `tests/ut/distributed/ascend_store/test_config_data.py` | modified | 9 | 1 |
| `tests/ut/distributed/ascend_store/test_kv_transfer.py` | modified | 15 | 5 |
| `tests/ut/distributed/ascend_store/test_pool_scheduler.py` | modified | 812 | 9 |
| `tests/ut/distributed/ascend_store/test_pool_worker.py` | modified | 690 | 86 |
| `tests/ut/distributed/mooncake/test_mooncake_kv_transfer.py` | modified | 3 | 37 |
| `vllm_ascend/attention/attention_v1.py` | modified | 5 | 8 |
| `vllm_ascend/attention/context_parallel/attention_cp.py` | modified | 8 | 4 |
| `vllm_ascend/attention/context_parallel/mla_cp.py` | modified | 2 | 5 |
| `vllm_ascend/attention/mla_v1.py` | modified | 9 | 14 |
| `vllm_ascend/attention/sfa_v1.py` | modified | 6 | 3 |
| `vllm_ascend/attention/utils.py` | modified | 20 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_connector.py` | modified | 13 | 7 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py` | modified | 11 | 11 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/__init__.py` | modified | 29 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/backend.py` | modified | 24 | 0 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/memcache_backend.py` | modified | 58 | 11 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py` | modified | 15 | 7 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py` | modified | 183 | 12 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py` | modified | 857 | 208 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py` | modified | 570 | 161 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py` | modified | 750 | 264 |
| `vllm_ascend/memcache_comm_fence.py` | added | 91 | 0 |

## Commit Captured

- `b1c4ab5e0959f7c37e4d1c4ae930dfd48dfecd4d` - `feat(kv_pool): layerwise KV pool with per-rank key and dynamic save by put_step`
