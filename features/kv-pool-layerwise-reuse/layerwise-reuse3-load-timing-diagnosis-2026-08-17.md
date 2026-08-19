# Test 2 REUSE3 slowdown diagnosis

## Archive status and scope

This is the accepted diagnostic-only BULK/REUSE3 comparison from 2026-08-17.
It used `max_num_seqs=40` and `long_prefill_token_threshold=128`; it is
separate from the earlier symmetric threshold-0 attempt with
`max_num_seqs=6`, which failed before producing a formal result. That failed
attempt is preserved at
[`evidence/layerwise-issue1-threshold0-partial-20260817T095300Z/`](evidence/layerwise-issue1-threshold0-partial-20260817T095300Z/README.md).

The compact analysis products, instrumentation patch, analysis script, and
complete raw checksum inventory are under
[`artifact-manifests/layerwise-issue1-load-timing-20260817T181503+0800/`](artifact-manifests/layerwise-issue1-load-timing-20260817T181503+0800/README.md).
The 723 MiB raw logs remain transient `/tmp` artifacts and are not published
by Git; the report and compact analysis products are the durable archive.

## Executed commands and workload

This section records the accepted 2026-08-17 BULK and REUSE3 runs. The
services were started through `direct-start-vllm.sh`; the executable entrypoint
was `python3 -m vllm.entrypoints.openai.api_server`, not the `vllm serve` CLI.
The source-of-truth expanded argv files are:

- `load-timing-test2-bulk/prefill-argv.txt`
- `load-timing-test2-bulk/decode-argv.txt`
- `load-timing-test2-reuse3/prefill-argv.txt`
- `load-timing-test2-reuse3/decode-argv.txt`

The accepted launcher had SHA256
`69d191af71509ea8b6f1ebcb0611b40f1c4222e4559aef7b6f1a77641b0f161f`
and was invoked inside the serving Pods as follows:

```bash
bash /tmp/direct-start-vllm.sh prefill bulk 40 128
bash /tmp/direct-start-vllm.sh decode bulk 40 128
bash /tmp/direct-start-vllm.sh prefill reuse3 40 128
bash /tmp/direct-start-vllm.sh decode reuse3 40 128
```

All four processes used the following environment and common server argv. The
`VLLM_ASCEND_KVPOOL_LOAD_TIMING_DEBUG=1` flag enabled the temporary timing
instrumentation used by this diagnosis; range-debug logging remained disabled.

```bash
env VLLM_USE_V1=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \
  MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB \
  MC_TE_METRIC=1 MC_TE_METRIC_INTERVAL_SECONDS=1 \
  MC_STORE_CLIENT_METRIC=1 MC_STORE_CLIENT_METRIC_INTERVAL=1 \
  VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0 \
  VLLM_ASCEND_KVPOOL_LOAD_TIMING_DEBUG=1 \
python3 -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port PORT \
  --model /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --served-model-name vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --quantization ascend --trust-remote-code --enforce-eager \
  --distributed-executor-backend mp --data-parallel-size 1 \
  --data-parallel-backend mp --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 --prefill-context-parallel-size 1 \
  --decode-context-parallel-size 1 --block-size 128 \
  --enable-chunked-prefill --max-model-len 32768 \
  --max-num-batched-tokens 32768 --max-num-seqs 40 \
  --no-enable-prefix-caching --enable-logging-iteration-details \
  --gpu-memory-utilization 0.95 --kv-transfer-config 'KV_JSON' \
  --async-scheduling --seed 1024 \
  --long-prefill-token-threshold 128 --enable-per-request-metrics
```

`PORT` was `8100` for Prefill and `8200` for Decode. No
`max_num_partial_prefills` or `max_long_partial_prefills` option was passed.
The four exact `KV_JSON` values were:

### BULK Prefill

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":false},"kv_load_failure_policy":"fail","kv_role":"kv_producer"}
```

### BULK Decode

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":false,"consumer_is_to_load":true},"kv_load_failure_policy":"fail","kv_role":"kv_consumer"}
```

### REUSE3 Prefill

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":true,"layerwise_num_shared_buffers":3},"kv_load_failure_policy":"fail","kv_role":"kv_producer"}
```

### REUSE3 Decode

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":true,"consumer_is_to_load":true},"kv_load_failure_policy":"fail","kv_role":"kv_consumer"}
```

Only Prefill enabled `layerwise_num_shared_buffers=3`. Decode used layerwise
transfer for REUSE3 but did not enable compute-side shared buffers.

### Runtime and formal parameters

| Parameter | Accepted value |
| --- | --- |
| Namespace / node | `liangjiahao` / `m1` |
| Prefill physical NPUs | `2,3` |
| Decode physical NPUs | `4,5` |
| Topology | Prefill DP1/TP2, Decode DP1/TP2 |
| Model input length | exactly 32,000 tokens |
| Shared external prefix | exactly 28,800 tokens |
| Uncached suffix | exactly 3,200 tokens |
| Output | 1 token |
| Formal requests | 100 per variant |
| Client concurrency | 40 |
| Request rate | 0, closed-loop |
| AISBench workers / batch size | 40 / 40 |
| Streaming / retries | `stream=True` / one total attempt |
| Generation | `temperature=0`, `ignore_eos=True` |
| Formal dataset SHA256 | `085031e378bd6a9e5072b75245701fb9829cf23ee94ad1694bb4267efc1278c1` |
| Fixture manifest SHA256 | `af7f1910bbbd243f599e0e3f5b3e5fd7f19e66d60b1cf19836571e382a4a9d16` |

Both formal contracts are preserved at
`load-timing-test2-{bulk,reuse3}/aisbench-formal/attempt-contract.json`; their
generated AISBench configs are in the same directories. The formal client
command followed the existing native AISBench path:

```bash
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env \
  TORCH_DEVICE_BACKEND_AUTOLOAD=0 PYTHONDONTWRITEBYTECODE=1 \
  /client-tools/venv/bin/ais_bench -m perf --num-warmups 0 RUN_DIR/config.py
```

Each variant used this sequence against one server startup:

1. Run 8 warmup requests.
2. Clear all Mooncake keys.
3. Send one 28,800-token shared-prefix seed request.
4. Send one 40-request admission wave.
5. Clear all Mooncake keys again.
6. Send one fresh 28,800-token shared-prefix seed request.
7. Run the sole 100-request formal wave.

The full service logs therefore contain 150 client requests per variant
(`8 + 1 + 40 + 1 + 100`). The accepted result uses only the final formal wave;
the admission wave is retained as the server-side concurrency/capacity check.

## Conclusion

The primary problem is not low Mooncake transfer bandwidth. It is load amplification and serialization in the current REUSE3 multi-chunk orchestration:

1. The 3,200-token uncached suffix is split into 25 chunks by `long_prefill_token_threshold=128`.
2. For every formal request, shared layers 1-25 execute one load in every chunk: each layer recorded exactly 2,500 TP0 request calls (`100 requests x 25 chunks`).
3. `_handle_range_request()` issues those loads as request-scoped `batch_copy_get` calls. At concurrency 40, one layer executes 40 calls serially on the receive worker.
4. The receive worker cannot keep up with model execution. The model spends 814.071 seconds on the measured layer-load critical path, 70.0% of the 1,163.634 seconds of summed Prefill context iteration time.

Mooncake still matters because those repeated loads move real data, but its per-byte throughput is not the regression:

| Prefill TP0 | BULK | REUSE3 |
| --- | ---: | ---: |
| Load bytes | 95.253 GB | 2,190.828 GB |
| Transfer-call time | 30.052 s | 651.520 s |
| Effective bandwidth | 3.170 GB/s | 3.363 GB/s |
| Request-scoped calls | 106 | 62,700 |

REUSE3 therefore moved 23.00x as many Prefill bytes and issued 591.5x as many request-scoped calls, while effective bandwidth remained comparable to BULK.

## Why Prefill reloads

The shared slot is reusable after layer `i` finishes the current chunk, but it is not dead for the whole request. When Prefill later computes layer `i` for the next chunk, attention again needs layer `i` KV for the preceding prefix. With only three shared slots and chunk-major execution, layer `i` has already been overwritten by later layers. The current implementation reloads that layer's range before each later chunk.

This matches the formal log exactly:

- Layers 1-25: 2,500 calls per layer, equal to 100 requests x 25 chunks.
- Layers 0 and 26: 100 calls per layer, equal to one call per request.
- Active load steps: 83, equal to the 83 Prefill context iterations in the formal interval.

The original intuition that Prefill no longer needs layer `i` is correct only after the request's final chunk. It does not hold between chunks of the same request.

## Timing breakdown

- TP0 `batch_copy_get`: 651.520 s total, 10.391 ms mean per request-scoped call.
- Worst-rank address construction: 360.788 s total.
- Critical `model_wait`: 814.071 s total.
- Worst-rank save gate: 13.439 s total; median per event is tens of microseconds.
- Worst-rank attention gate: 2.120 s total; median per event is also tens of microseconds.
- TP0 queue residence: 1.397 s median and 2.360 s p95 per layer task. This is receive-worker backlog, not an independent additive critical path.

The request-count scaling is nearly linear:

| Requests in step | Median bytes per TP step | Median transfer per TP step | Median critical model wait | Median iteration |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 31,907.8 MiB | 10.224 s | 12.815 s | 18.526 s |
| 20 | 15,939.8 MiB | 5.088 s | 6.391 s | 9.206 s |

This rules against a fixed layer gate as the main cost. It supports per-request serialized load volume and address preparation as the dominant mechanism.

Prefill NPU sampling corroborates the wait-heavy path: mean AICore utilization fell from BULK 80.0%/37.7% on NPUs 2/3 to REUSE3 32.3%/9.8%. Decode context iterations totaled only 14.744 seconds versus 1,163.634 seconds on Prefill, so Decode is not the Test 2 wall-time bottleneck.

## Run validity

- BULK: 100/100 successful, 0.2292 req/s, 436,371.9513 ms.
- REUSE3: 100/100 successful, 0.0855 req/s, 1,170,183.1656 ms.
- REUSE3/BULK: 0.3730x.
- Every variant had 100 unique `data_id` values, non-empty predictions, 32,000 input tokens, and one output token.
- First Prefill hit was exactly 28,800 tokens for 100/100 requests in both variants.
- REUSE3 admission reached 40 running, zero waiting, and zero preemption. BULK admission reached 20 running and 20 capacity-waiting.
- No formal `Traceback`, `ERROR`, OOM, or `507018` line was found.

The accepted REUSE3 throughput is 1.7% below the earlier uninstrumented replay (`0.0855` versus `0.0870 req/s`), while BULK reproduced `0.2292 req/s` exactly. Logging overhead may account for a small part of the REUSE3 delta, but it cannot explain the 23x byte amplification or exact per-layer/per-chunk call counts.

## Recommended implementation order

1. Remove or amortize the layers 1-25 reload on every chunk. This likely requires changing slot residency or chunk/layer scheduling, not just increasing prefetch depth.
2. Batch or parallelize safe cross-request Mooncake copies. The current request-scoped loop serializes 40 calls per layer because mixed destinations previously had correctness risk.
3. Reuse prepared range/address metadata across chunks where identities and destinations remain valid; address construction alone consumed up to 360.788 seconds.
4. Do not optimize save/attention gates first. Their measured contribution is too small.
5. Increasing `layerwise_prefetch_layers` alone is unlikely to solve the issue: the receive queue is already backlogged and the model still waits for the worker.

A profiler is not needed to distinguish the two original hypotheses. It would only be useful after a concrete orchestration change, to optimize the remaining address-build or copy-call CPU cost.
