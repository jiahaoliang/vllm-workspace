# Test 2 load-timing run identity

- Namespace: `liangjiahao`
- Base image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
- vLLM source: `baf481c7f0e84cd93705bcd4cdf42bcff03c3909`
- vLLM-Ascend source: `c97cef309713dcf6c86412efd9c882b8425e28ce`
- Prefill physical NPUs: 2, 3
- Decode physical NPUs: 4, 5
- Test 2 server arguments: `max_num_seqs=40`, `long_prefill_token_threshold=128`
- Client: 32,000 input tokens, 28,800-token shared seed, output 1, concurrency 40
- Formal request count: 100 per variant
- Debug flags: `VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0`, `VLLM_ASCEND_KVPOOL_LOAD_TIMING_DEBUG=1`

## Runtime Python overlays

The following corrected instrumentation files were copied to both serving Pods before the accepted BULK and REUSE3 runs:

```text
8686eec0066335e73cfa609c57a74b7620497083f37b306fd8754ccf5f85d09d  range_debug.py
5999cab2965fae360feb7ecc5e62aed27dcd2db9aacd376538bd976c794eea3a  pool_worker.py
7be13f36b827edd8566f799b333fb117f0312a2e9675f5beb0f95dac7008d274  kv_transfer.py
69d191af71509ea8b6f1ebcb0611b40f1c4222e4559aef7b6f1a77641b0f161f  direct-start-vllm.sh
```

The earlier `identity/overlay.sha256` records the first probe version. Its BULK warmup failed because `requested_bytes` treated a nested `list[list[int]]` as scalar sizes. That failed warmup is isolated under `failed-warmup/`; it is not part of either accepted formal point.

## Fixture identity

```text
793b16c968b22bb8ad99eb0db93ad613885f86715f0c50d0f08c8de14625e4ce  warmup.jsonl
49bae33c6656ddddaee4725ea9beaddf297d9932d75829d781036302e8752a87  seed.jsonl
20cec5cabafe048f8a603b1ba3204ee585806d717bf144495d5553dd03459856  admission.jsonl
085031e378bd6a9e5072b75245701fb9829cf23ee94ad1694bb4267efc1278c1  formal-1.jsonl
af7f1910bbbd243f599e0e3f5b3e5fd7f19e66d60b1cf19836571e382a4a9d16  manifest.json
```

## Cleanup

- Prefill and Decode Deployments restored to 0 replicas.
- Temporary NPU reserve Pods deleted.
- Remaining `liangjiahao` Pods request no `huawei.com/Ascend910` or `huawei.com/vnpu-number`.
- Mooncake final `master_key_count=0`, `master_allocated_bytes=0`, and `master_active_clients=0`.
