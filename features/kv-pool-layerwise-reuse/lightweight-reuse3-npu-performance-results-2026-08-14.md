# REUSE3 NPU Lightweight Four-Point Results

## Scope

This document records the direct four-point run completed on 2026-08-14. The
execution followed
[`lightweight-reuse3-npu-performance-2026-08-13.md`](lightweight-reuse3-npu-performance-2026-08-13.md)
and used the existing AISBench fixtures and native `ais_bench -m perf` path.
The points ran in this order:

1. Test 2 BULK.
2. Test 2 REUSE3.
3. Test 1 BULK.
4. Test 1 LAYERWISE.

The plan commit `6dc686a0d757f9a85ab40fd98dae199ca35ec9d6` was
committed and pushed before the first Test 2 warmup started.

## Runtime Identity

- Namespace: `liangjiahao`.
- Node: `m1`.
- Image:
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`.
- Image manifest digest:
  `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`.
- vLLM: `baf481c7f0e84cd93705bcd4cdf42bcff03c3909`.
- The only copied source file was `vllm/engine/arg_utils.py`, with SHA256
  `6edd591fef62f5ea3a31a5fdb2b27bee06ff49f8df00f70b4a24756b4f3408af`.
- vLLM-Ascend: `c97cef309713dcf6c86412efd9c882b8425e28ce`.
  Its tree `0bd032828e6e8f409962eeae7019e7c37251ff18` is identical to
  `57d3c214e642cdbb529400f0742d1a98a8d38708`; no vLLM-Ascend file was
  copied.
- Prefill used physical NPUs 2 and 3. Decode used physical NPUs 4 and 6.
  Serving did not use physical NPUs 0 or 7.
- All formal runs used `VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0`.

## Fixed Matrix

| Test | Variant | Input | Output | Client concurrency | `max_num_seqs` | Threshold | Formal |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Test 2 | BULK | 32,000 | 1 | 40 | 40 | 128 | 100 |
| Test 2 | REUSE3 | 32,000 | 1 | 40 | 40 | 128 | 100 |
| Test 1 | BULK | 32,000 | 128 | 8 | 8 | 1024 | 125 |
| Test 1 | LAYERWISE | 32,000 | 128 | 8 | 8 | 1024 | 125 |

All points also used `max_model_len=32768`,
`max_num_batched_tokens=32768`, `gpu_memory_utilization=0.95`, chunked
Prefill, async scheduling, and one 28,800-token shared-prefix seed. Neither
`max_num_partial_prefills` nor `max_long_partial_prefills` was passed.

## Commands

The run used one-shot helper scripts under `/tmp`. Their byte-identical
snapshots are now archived under
[`deployment/performance/direct/`](deployment/performance/direct/README.md).
The commands below use the archived host paths. Before launching a point, copy
the Pod-side vLLM entry script into both serving Pods:

```bash
DIRECT_DIR=features/kv-pool-layerwise-reuse/deployment/performance/direct
PREFILL_POD=$(kubectl get pod -n liangjiahao -l app=prefill \
  --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
DECODE_POD=$(kubectl get pod -n liangjiahao -l app=decode \
  --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

kubectl cp -n liangjiahao -c prefill-engine \
  "${DIRECT_DIR}/direct-start-vllm.sh" \
  "${PREFILL_POD}:/tmp/direct-start-vllm.sh"
kubectl cp -n liangjiahao -c decode-engine \
  "${DIRECT_DIR}/direct-start-vllm.sh" \
  "${DECODE_POD}:/tmp/direct-start-vllm.sh"

bash "${DIRECT_DIR}/direct-stop-vllm.sh"
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
bash "${DIRECT_DIR}/direct-launch-point.sh" \
  VARIANT MAX_NUM_SEQS THRESHOLD
bash "${DIRECT_DIR}/direct-wait-ready.sh"
bash "${DIRECT_DIR}/direct-start-samplers.sh"
```

`direct-launch-point.sh` started both Prefill and Decode with the common vLLM
arguments from the plan. It changed only the point's KV JSON,
`max_num_seqs`, and `long_prefill_token_threshold`. Prefill used
`kv_producer`; Decode used `kv_consumer` plus `consumer_is_to_load:true`.

Each AISBench phase was generated and executed by:

```bash
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/client-tools/tooling /client-tools/venv/bin/python \
  -m performance.fixtures config --topology dp1 --input-tokens 32000 \
  --output-tokens OUTPUT --variant VARIANT --concurrency CONCURRENCY \
  --dataset RUN_DIR/dataset.jsonl --request-count REQUESTS --phase PHASE \
  --fixture-manifest FIXTURE_DIR/manifest.json --output RUN_DIR/config.py

kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
  PYTHONDONTWRITEBYTECODE=1 /client-tools/venv/bin/ais_bench \
  -m perf --num-warmups 0 RUN_DIR/config.py
```

The exact phase wrapper form was:

```bash
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  POINT VARIANT CONCURRENCY OUTPUT PHASE REQUESTS FIXTURE_CONCURRENCY
```

Test 2 BULK used:

```bash
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test2-bulk bulk 40 1 warmup 8 40
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test2-bulk bulk 40 1 seed 1 40
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test2-bulk bulk 40 1 admission 40 40
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test2-bulk bulk 40 1 seed 1 40
bash "${DIRECT_DIR}/direct-capture-before.sh" rerun-test2-bulk
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test2-bulk bulk 40 1 formal-1 100 40
```

Test 2 REUSE3 used the same sequence and parameters, replacing point and
variant with `rerun-test2-reuse3 reuse3`.

Test 1 BULK used:

```bash
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test1-bulk bulk 8 128 warmup 8 8
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test1-bulk bulk 8 128 seed 1 8
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test1-bulk bulk 8 128 admission 8 8
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test1-bulk bulk 8 128 seed 1 8
bash "${DIRECT_DIR}/direct-capture-before.sh" rerun-test1-bulk
bash "${DIRECT_DIR}/direct-aisbench-phase.sh" \
  rerun-test1-bulk bulk 8 128 formal-1 125 8
```

Test 1 LAYERWISE used the same sequence and parameters, replacing point and
variant with `rerun-test1-layerwise layerwise`.

After each formal run, sampling stopped and the artifacts were copied out:

```bash
bash "${DIRECT_DIR}/direct-stop-samplers.sh"
DIRECT_EVIDENCE_ROOT=/tmp/layerwise-issue1-direct-20260814-rerun \
  bash "${DIRECT_DIR}/direct-capture-after.sh" POINT
```

## Formal Results

| Test | Variant | Result | Throughput | Avg TTFT | Avg TPOT | Avg ITL | Avg E2E | Ratio to BULK |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Test 2 | BULK | 100/100 | 0.2292 req/s | 156.012 s | N/A | 0.1 ms | 156.012 s | 1.0000 |
| Test 2 | REUSE3 | 100/100 | 0.0870 req/s | 413.351 s | N/A | 0.1 ms | 413.351 s | 0.3796 |
| Test 1 | BULK | 125/125 | 0.2718 req/s | 10.494 s | 146.0 ms | 144.9 ms | 29.041 s | 1.0000 |
| Test 1 | LAYERWISE | 125/125 | 0.3606 req/s | 4.560 s | 134.4 ms | 133.4 ms | 21.633 s | 1.3267 |

Test 1 LAYERWISE was 32.67% faster than Test 1 BULK by request throughput.
Test 2 REUSE3 was 62.04% slower than Test 2 BULK by request throughput.
These are direct single-run characterization results, not a statistical
significance claim.

## Validity And Capacity

Every point completed 8 warmup requests, a Mooncake clear, one seed, one
admission wave, a second clear and seed, and exactly one formal run.

- All formal detail rows succeeded.
- Formal `data_id` values were unique and complete.
- All predictions were non-empty.
- Input token counts were exactly 32,000.
- Output token counts were exactly 1 for Test 2 and 128 for Test 1.
- The first KVPool hit for every formal request was exactly 28,800 tokens.
- No formal point logged OOM or `507018`.
- Test 1 admission reached 8 running requests for both variants.
- Test 2 BULK admission reached at most 21 running requests and had capacity
  waiting requests.
- Test 2 REUSE3 admission reached 40 running requests with no waiting.

The Test 2 startup therefore proved
`BULK capacity < 40 <= REUSE3 capacity`. REUSE3 provided the intended
capacity increase, but it did not convert that increase into higher
throughput.

## Slow-Point Localization

Only Test 2 triggered slowdown localization because `REUSE3/BULK=0.3796`.
The formal evidence localizes the direct bottleneck to Prefill context
iterations:

| Observation | BULK | REUSE3 |
| --- | ---: | ---: |
| Context iterations | 146 | 83 |
| Context tokens | 320,000 | 320,000 |
| Aggregate iteration time | 424.99 s | 1,142.94 s |
| Context throughput | 753 tokens/s | 280 tokens/s |
| Dominant full iteration | 21 requests, 3.45 s average | 40 requests, 18.27 s average |
| Prefill NPU 2 average AICore | 72.2% | 40.3% |
| Prefill NPU 3 average AICore | 38.5% | 15.2% |

REUSE3 had no scheduler waiting or preemption during formal, and Decode was
nearly idle because Test 2 generated one token. Mooncake Master recorded the
same formal object and byte deltas for both variants, without a Master failure
counter increase. The proven direct mechanism is therefore the much slower
40-request Prefill iteration shape after REUSE3 admits all contexts, rather
than scheduler waiting, Decode, or Mooncake capacity.

The current range-debug events record layer ranges, byte sizes and results but
do not record boundary timings. The evidence cannot distinguish layer-load
synchronization from NPU efficiency for the 40-request shape. That lower-level
cause remains `unresolved`; the four formal points are not replaced by this
diagnostic conclusion.

## Artifacts And Cleanup

The local evidence root is:

```text
/tmp/layerwise-issue1-direct-20260814-rerun/
```

Each point contains AISBench config/raw/details/summary, full Prefill and
Decode logs, formal log offsets, Prefill and Decode Prometheus samples,
Mooncake before/after and time-series metrics, NPU time series, before/after
HBM state, and actual server argv. The machine-readable committed summary is
[`lightweight-reuse3-npu-performance-results-2026-08-14.csv`](lightweight-reuse3-npu-performance-results-2026-08-14.csv).

The raw staging root contains 107 files and 721,923,136 payload bytes. Its
complete checksum manifest replayed successfully. The committed manifest,
manifest digest and archive status are under
[`artifact-manifests/layerwise-issue1-direct-20260814-rerun-archive-metadata/`](artifact-manifests/layerwise-issue1-direct-20260814-rerun-archive-metadata/README.md).
The large payload is not in Git. Its persistent external copy is still pending
selection of a workspace-external destination.

Cleanup used:

```bash
bash "${DIRECT_DIR}/direct-stop-vllm.sh"
bash "${DIRECT_DIR}/direct-clear-mooncake.sh"
kubectl scale deployment -n liangjiahao \
  prefill-engine-deployment decode-engine-deployment --replicas=0
kubectl delete pod -n liangjiahao \
  issue1-npu-reserve-1 issue1-npu-reserve-4 \
  issue1-npu-reserve-6 issue1-npu-reserve-7 --wait=true
```

The final live checks showed both serving Deployments at zero replicas,
Mooncake `master_allocated_bytes=0`, and zero non-terminal
`huawei.com/Ascend910` requests in `liangjiahao`. AISBench, Mooncake Master,
proxy and the CPU-only UT Pod were retained.
