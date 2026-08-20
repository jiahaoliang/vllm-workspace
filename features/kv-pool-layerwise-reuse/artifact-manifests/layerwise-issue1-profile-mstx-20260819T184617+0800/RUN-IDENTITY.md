# Test 2 Profiling + MSTX Run Identity

- Namespace: `liangjiahao`
- Node: `m1`
- Base image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
- Runtime image ID: `sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd`
- vLLM source: `baf481c7f0e84cd93705bcd4cdf42bcff03c3909`
- vLLM-Ascend source: `c97cef309713dcf6c86412efd9c882b8425e28ce`
- Mooncake native: `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Prefill: DP1/TP2 on physical NPU 2,3
- Decode: DP1/TP2 on physical NPU 4,5
- NPU0 reserve: `profile-mstx-reserve-1`; no model process used NPU0
- NPU6,7 remained outside this workload

## Workload

- Model: `vllm-ascend/DeepSeek-V2-Lite-W8A8`
- Input: 32,000 tokens
- Shared external prefix: 28,800 tokens / 225 keys
- Uncached suffix: 3,200 tokens / 25 Prefill chunks
- Output: 1 token
- c1 formal count: 1 request per variant
- c20 formal count: 20 concurrent requests per variant
- `max_num_seqs=40`
- `max_num_batched_tokens=32768`
- `long_prefill_token_threshold=128`
- `layerwise_prefetch_layers=3`
- REUSE3 `layerwise_num_shared_buffers=3`

Every formal response passed HTTP, prompt-token, and completion-token checks.
Every formal request had an initial Prefill lookup with exactly 28,800 external
hit tokens.

## Profiling

- Prefill only; Decode profiler disabled
- c1: stack on, delay 0, max 30, request-scoped copy ranges on
- Planned c20 pilot: stack off, delay 3, max 3, request scopes off
- Corrected stable c20: stack off, delay 6, max 3, request scopes off

The delay=3 pilot sampled ramp-up at approximately 5, 8, and 20 calls per layer.
It is excluded from the stable comparison. The accepted stable REUSE3 trace
covers step 485-487; both ranks contain 25 layer tasks per step and every task
has `request_call_count=20`.

## Diagnostic Overlay

The image was reused. Only the minimum Python files and launcher were copied to
the serving Pods. `overlay-sha256.txt` records their exact SHA256 values, and
`vllm-ascend-profile-mstx.patch` preserves the source changes. No Mooncake C++ or
native library was modified.

## Cleanup

- Mooncake final `master_key_count=0`, `master_allocated_bytes=0`, and
  `master_active_clients=0`.
- Prefill and Decode Deployment specs equal their pre-run snapshots at
  `replicas=0`.
- Temporary physical-device annotations and the NPU0 reserve Pod were removed.
- Final `liangjiahao` Pods request no `huawei.com/Ascend910` resource.
- The runtime ConfigMap has no diff from the pre-run snapshot.
