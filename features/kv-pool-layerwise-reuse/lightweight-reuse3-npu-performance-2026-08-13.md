# REUSE3 NPU Direct Reproduction Commands And Results

## Identity

- Namespace: `liangjiahao`.
- Node: `m1`; physical NPU 0 and 7 are reserved and all service Pods use only
  physical devices 1-6.
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`.
- Manifest digest: `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`.
- Config digest: `sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd`.
- vLLM: `baf481c7f0e84cd93705bcd4cdf42bcff03c3909`; copy only
  `repos/vllm/vllm/engine/arg_utils.py` into each service Pod.
- vLLM-Ascend: `c97cef309`; its tree equals base commit `57d3c214e`, so no
  vLLM-Ascend file is copied.
- Do not rebuild the image while Mooncake/native dependencies are unchanged.

## Matrix

| Group | Variant | Output | Client concurrency | Server max seqs | Threshold |
| --- | --- | ---: | ---: | ---: | --- |
| Test 2 | BULK | 1 | 40 | 40 | 128 |
| Test 2 | REUSE3 | 1 | 40 | 40 | 128 |
| Test 1 | BULK | 128 | 8 | 8 | 1024, unchanged |
| Test 1 | LAYERWISE | 128 | 8 | 8 | 1024, unchanged |

All points use input 32,000, one 28,800-token shared seed, request rate zero,
`max_model_len=32768`, `max_num_batched_tokens=32768`,
`gpu_memory_utilization=0.95`, chunked Prefill and async scheduling. Neither
partial-prefill option is passed. Test 2 uses one configuration for both
capacity and performance: the same formal wave must provide the throughput
result and prove the observed server-side running/waiting boundary. Execute
both Test 2 variants first, then rerun both unchanged Test 1 variants.

## Deployments

Use the existing CPU-only client and sleep-style service manifests:

```bash
kubectl apply -n liangjiahao \
  -f features/kv-pool-layerwise-reuse/deployment/performance/00-aisbench-client.yaml
kubectl apply -n liangjiahao \
  -f features/kv-pool-layerwise-reuse/deployment/30-mooncake-master.yaml
kubectl apply -n liangjiahao \
  -f features/kv-pool-layerwise-reuse/deployment/20-proxy-server.yaml
kubectl apply -n liangjiahao \
  -f features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml
kubectl apply -n liangjiahao \
  -f features/kv-pool-layerwise-reuse/deployment/50-decode-engine.yaml
kubectl patch deployment/prefill-engine-deployment -n liangjiahao \
  --type strategic \
  --patch-file features/kv-pool-layerwise-reuse/deployment/performance/direct-issue1-prefill-patch.yaml
kubectl patch deployment/decode-engine-deployment -n liangjiahao \
  --type strategic \
  --patch-file features/kv-pool-layerwise-reuse/deployment/performance/direct-issue1-decode-patch.yaml
```

The final patch fixes the service image, `nodeName: m1`, TP2 resources
(`huawei.com/Ascend910: "2"`), `sleep infinity`, and the
`layerwise-runtime-config` volume. After the Pods are Running, resolve exact
non-deleting Pod names and verify the device IDs:

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o json |
  jq -r '.items[] | select(.status.phase=="Running" and
    (.metadata.deletionTimestamp == null)) |
    [.metadata.name,.metadata.labels.app,
     .metadata.annotations["ascend.kubectl.kubernetes.io/ascend-910-configuration"]]
    | @tsv'
```

Copy only the vLLM overlay, substituting the exact Pod names:

```bash
kubectl cp -n liangjiahao -c prefill-engine \
  repos/vllm/vllm/engine/arg_utils.py \
  PREFILL_POD:/vllm-workspace/vllm/vllm/engine/arg_utils.py
kubectl cp -n liangjiahao -c decode-engine \
  repos/vllm/vllm/engine/arg_utils.py \
  DECODE_POD:/vllm-workspace/vllm/vllm/engine/arg_utils.py
```

Mooncake Master itself runs:

```bash
mooncake_master --rpc_port=50001 --metrics_port=9003 \
  --default_kv_lease_ttl=30s --enable_offload=false --logtostderr=true
```

Clear keys without restarting Master or breaking existing vLLM clients:

```bash
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs /client-tools/venv/bin/python -c '
from urllib.request import Request, urlopen
r = Request("http://mooncake-master-service:9003/api/v1/remove_all?force=true",
            data=b"", method="POST")
print(urlopen(r, timeout=30).read().decode())'
```

## vLLM Commands

The common Prefill command is below. Decode changes port to 8200,
`kv_role` to `kv_consumer`, and adds `consumer_is_to_load:true`.

```bash
env VLLM_USE_V1=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \
  MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB \
  MC_TE_METRIC=1 MC_TE_METRIC_INTERVAL_SECONDS=1 \
  MC_STORE_CLIENT_METRIC=1 MC_STORE_CLIENT_METRIC_INTERVAL=1 \
  VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0 \
python3 -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8100 \
  --model /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --served-model-name vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --quantization ascend --trust-remote-code --enforce-eager \
  --distributed-executor-backend mp --data-parallel-size 1 \
  --data-parallel-backend mp --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 --prefill-context-parallel-size 1 \
  --decode-context-parallel-size 1 --block-size 128 \
  --enable-chunked-prefill --max-model-len 32768 \
  --max-num-batched-tokens 32768 --max-num-seqs MAX_NUM_SEQS \
  --no-enable-prefix-caching --enable-logging-iteration-details \
  --gpu-memory-utilization 0.95 --kv-transfer-config 'KV_JSON' \
  --async-scheduling --seed 1024 --enable-per-request-metrics
```

Test 1 additionally passes `--long-prefill-token-threshold 1024`. Test 2 passes
`--long-prefill-token-threshold 128`. The Prefill `KV_JSON` values are:

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":false},"kv_load_failure_policy":"fail","kv_role":"kv_producer"}
```

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":true},"kv_load_failure_policy":"fail","kv_role":"kv_producer"}
```

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":true,"layerwise_num_shared_buffers":3},"kv_load_failure_policy":"fail","kv_role":"kv_producer"}
```

They correspond to BULK, LAYERWISE and REUSE3. Decode removes
`layerwise_num_shared_buffers`, uses the same `use_layerwise` value, adds
`consumer_is_to_load:true`, and uses `kv_consumer`.

The complete Decode command has the same common arguments and is started as:

```bash
env VLLM_USE_V1=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \
  MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB \
  MC_TE_METRIC=1 MC_TE_METRIC_INTERVAL_SECONDS=1 \
  MC_STORE_CLIENT_METRIC=1 MC_STORE_CLIENT_METRIC_INTERVAL=1 \
  VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0 \
python3 -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8200 \
  --model /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --served-model-name vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --quantization ascend --trust-remote-code --enforce-eager \
  --distributed-executor-backend mp --data-parallel-size 1 \
  --data-parallel-backend mp --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 --prefill-context-parallel-size 1 \
  --decode-context-parallel-size 1 --block-size 128 \
  --enable-chunked-prefill --max-model-len 32768 \
  --max-num-batched-tokens 32768 --max-num-seqs MAX_NUM_SEQS \
  --no-enable-prefix-caching --enable-logging-iteration-details \
  --gpu-memory-utilization 0.95 --kv-transfer-config 'DECODE_KV_JSON' \
  --async-scheduling --seed 1024 --enable-per-request-metrics
```

For example, the REUSE3 Decode JSON is explicit and does not contain the
Prefill-only shared-buffer option:

```json
{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","consumer_is_to_load":true,"layerwise_prefetch_layers":3,"lookup_rpc_port":0,"use_layerwise":true},"kv_load_failure_policy":"fail","kv_role":"kv_consumer"}
```

## AISBench Commands

Keep the current AISBench execution path. Fixtures already exist under
`/client-tools/fixtures/tokens-32000-c8` and `tokens-32000-c40` in the client
chroot. For each phase, copy `warmup.jsonl`, `seed.jsonl`, `admission.jsonl` or
`formal-1.jsonl` to a fresh run directory, generate the standard AISBench
config, then execute:

```bash
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/client-tools/tooling /client-tools/venv/bin/python \
  -m performance.fixtures config --topology dp1 --input-tokens 32000 \
  --output-tokens OUTPUT --variant VARIANT --concurrency CLIENT_CONCURRENCY \
  --dataset RUN_DIR/dataset.jsonl --request-count REQUESTS --phase PHASE \
  --fixture-manifest FIXTURE_DIR/manifest.json --output RUN_DIR/config.py

kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
  PYTHONDONTWRITEBYTECODE=1 /client-tools/venv/bin/ais_bench \
  -m perf --num-warmups 0 RUN_DIR/config.py
```

For seed, generate the config against the 32k fixture contract first, then
replace `RUN_DIR/dataset.jsonl` with `seed.jsonl`; this preserves the 28,800
token seed used by the formal requests. Wait for the phase's final
`*_details.jsonl` to contain exactly the requested row count and for its
AISBench process to exit before starting the next phase.

The sequence per point is: 8 warmup; `remove_all`; one seed; one admission wave
(8 for Test 1, 40 for Test 2); `remove_all`; one seed; one formal (125 for Test
1, 100 for Test 2). Stop a point at admission if the service OOMs or times out;
do not change one variant's parameters.

For Test 2, sample `running`, `waiting`, KV usage and preemption throughout the
same formal wave. It is one performance-and-capacity point, not separate
`max_num_seqs=8` and `max_num_seqs=40` runs. Accept the capacity claim only if
the observations prove `BULK capacity < 40 <= REUSE3 capacity`; request success
or client concurrency alone is insufficient.

## 2026-08-14 Direct Results

| Group | Variant | Result | Request throughput | Direct evidence |
| --- | --- | --- | ---: | --- |
| Test 1 | BULK | 125/125 success | 0.2721 req/s | max concurrency 8 |
| Test 1 | LAYERWISE | 125/125 success | 0.3589 req/s | max concurrency 8 |
| Superseded Test 2, max seqs 8, threshold 0 | BULK | admission OOM | N/A | 8 running, 31 waiting; 158 MiB allocation failed |
| Superseded Test 2, max seqs 8, threshold 0 | REUSE3 | admission OOM | N/A | 8 running, 9 waiting; 158 MiB allocation failed |
| Superseded Test 2, max seqs 40, threshold 0 | BULK | admission OOM | N/A | at most 6 observed running; 146 MiB allocation failed |
| Superseded Test 2, max seqs 40, threshold 0 | REUSE3 | admission OOM | N/A | at most 5 observed running; 66/256 MiB allocations failed |

`LAYERWISE/BULK = 0.3589 / 0.2721 = 1.3190`. These Test 2 attempts do not apply
to the revised Test 2 configuration: they used threshold 0 and two different
`max_num_seqs` values. Rerun BULK and REUSE3 with the unified settings and the
current AISBench path before calculating a Test 2 ratio or making a capacity
claim.

Raw artifacts are under `/tmp/layerwise-issue1-direct-20260814/`. Test 1
directories contain AISBench raw/detail, full Prefill/Decode logs, actual argv,
formal offsets, Mooncake metrics and before/after NPU snapshots. Test 2
directories retain the complete failure logs and client detail rows.

## Cleanup

```bash
kubectl scale deployment/prefill-engine-deployment -n liangjiahao --replicas=0
kubectl scale deployment/decode-engine-deployment -n liangjiahao --replicas=0
kubectl delete pod -n liangjiahao issue1-npu-reserve-1 issue1-npu-reserve-4
```

Then call the `remove_all` command above and verify
`huawei.com/Ascend910` requests are zero. Do not delete the namespace.
