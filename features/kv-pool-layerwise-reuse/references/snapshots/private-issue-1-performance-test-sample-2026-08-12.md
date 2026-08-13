Source: https://github.com/jiahaoliang/vllm-private/issues/1
Captured At: 2026-08-12T23:59:00+08:00
Notes: User-provided full-text transcription. Embedded result images were represented only by the word `image`, so their numeric contents are unavailable in this snapshot.
# jiahaoliang/vllm-private Issue #1: performance test sample

## Requirement Identity

- Number: `1`
- State: `Open`
- Author: `jiahaoliang`
- Scope label in body: `layerwise测试集合`

This is distinct from the older
`jiahaoliang/vllm-workspace#1` requirement snapshot. The private issue is a
collection of concrete launch and AISBench samples rather than only a list of
comparison cases.

## Common Runtime Environment

The PDMix samples use the following common settings, with model-specific
differences called out below:

```bash
rm -rf /root/ascend/log/*
echo "/tmp/core.%p" | tee /proc/sys/kernel/core_pattern
export PYTHONPATH=$PYTHONPATH:/home/t00612968/vllm
export PYTHONPATH=$PYTHONPATH:/home/t00612968/vllm-ascend
export HCCL_OP_EXPANSION_MODE="AIV"
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=1
export VLLM_USE_V1=1
export HCCL_BUFFSIZE=200
export VLLM_ASCEND_ENABLE_MLAPO=1
export VLLM_RPC_TIMEOUT=3600000
export VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=3600000
export VLLM_ASCEND_ENABLE_FLASHCOMM1=0
export PYTORCH_NPU_ALLOC_CONF="expandable_segments:True"
export LD_LIBRARY_PATH=/usr/local/Ascend/ascend-toolkit/latest/python/site-packages/mooncake:$LD_LIBRARY_PATH
export ASCEND_CONNECT_TIMEOUT=10000
export ASCEND_TRANSFER_TIMEOUT=10000
export PYTHONHASHSEED=0
source /usr/local/memcache_hybrid/set_env.sh
source /usr/local/memfabric_hybrid/set_env.sh
```

The TP16 PDMix samples additionally set:

```bash
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
export DISABLE_L2_CACHE=1
export ASCEND_BUFFER_POOL=4:8
export TASK_QUEUE_ENABLE=1
```

## Sample Matrix

| Sample | Model | Topology | Input | Output | Data | Client concurrency | Prefix repeat | Server max seqs | Max model len | Batched-token budget | GPU memory |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM 8-concurrency | GLM-4.7 | PDMix TP16 | 32000 | 1 | 125 | 8 | 0.9 | 8 | 32769 | 32769 | 0.90 |
| GLM max-seqs-16 | GLM-4.7 | PDMix TP16 | 32000 | 1 | 125 | 8 | 0.9 | 16 | 32769 | 32769 | 0.90 |
| DeepSeek 40-concurrency | DeepSeek-V3.2-W8A8 | PDMix TP16 | 65000 | 1 | 100 | 40 | 0.9 | 8 | 65536 | 65536 | 0.95 |
| DeepSeek-V2-Lite PD | DeepSeek-V2-Lite-Chat | Prefill DP2/TP2 + Decode DP2/TP2 sample | 32000 | 1 | 125 | 8 | 0.9 | 8 | 32768 | 32768 | 0.95 |

All AISBench samples use `request_rate=0`, `dataset_type=prefix_cache`,
`prefix_test`, and an explicit seed. All vLLM launches enable chunked Prefill,
disable local prefix caching, use eager mode, and enable async scheduling.

## GLM-4.7 PDMix Samples

The first launch uses:

```text
model=/mnt/weight/GLM-4.7
served_model_name=glm4.7
tensor_parallel_size=16
max_num_seqs=8
max_model_len=32769
max_num_batched_tokens=32769
gpu_memory_utilization=0.90
backend=memcache
use_layerwise=true
kv_role=kv_both
```

The paired client command is:

```bash
python3 aisbench_test.py \
  --input_len 32000 \
  --output_len 1 \
  --data_num 125 \
  --concurrency 8 \
  --request_rate 0 \
  --dataset_type prefix_cache \
  --repeat_rate 0.9 \
  --prefix_test \
  --seed 1024
```

The second GLM launch changes `max_num_seqs` from 8 to 16. Its client still
uses concurrency 8 and changes the seed to 1023. Both samples compare
`use_layerwise=true` and `use_layerwise=false`; their result and HBM images are
not present in the text transcription.

## DeepSeek-V3.2 PDMix Sample

The server settings are:

```text
model=/mnt/weight/DeepSeek-V3.2-W8A8
served_model_name=ds3.2
tensor_parallel_size=16
max_num_seqs=8
max_model_len=65536
max_num_batched_tokens=65536
gpu_memory_utilization=0.95
quantization=ascend
backend=memcache
use_layerwise=false in the shown command
kv_role=kv_both
```

The paired client command is:

```bash
python3 aisbench_test.py \
  --input_len 65000 \
  --output_len 1 \
  --data_num 100 \
  --concurrency 40 \
  --request_rate 0 \
  --dataset_type prefix_cache \
  --repeat_rate 0.9 \
  --prefix_test \
  --seed 1024
```

The issue compares layerwise enabled/disabled and HBM consumption. The numeric
contents of the three images are unavailable.

## DeepSeek-V2-Lite PD-Separated Sample

The issue comment labels this sample `A3 PD分离 DeepSeek-V2-Lite-Chat 输入32k
性能基线-开layerwise+offload`. It sets:

```bash
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
export MMC_LOCAL_CONFIG_PATH=/usr/local/memcache_hybrid/latest/config/mmc-local.conf
export NUM_REUSE_LAYERS=27
export NUM_LAYERS=27
export VLLM_VERSION=0.19.0
```

Both roles use:

```text
model=/home/weight/DeepSeek-V2-Lite-Chat
tensor_parallel_size=2
data_parallel_size=2
enforce_eager=true
seed=1024
served_model_name=ds2
enable_expert_parallel=true
max_num_seqs=8
max_model_len=32768
max_num_batched_tokens=32768
enable_chunked_prefill=true
enable_prefix_caching=false
gpu_memory_utilization=0.95
async_scheduling=true
additional_config.fuse_muls_add=true
additional_config.multistream_overlap_shared_expert=true
additional_config.ascend_compilation_config.enable_npugraph_ex=true
compilation_config.cudagraph_mode=FULL_DECODE_ONLY
```

The Prefill role listens on port 8005, uses `kv_producer`, `engine_id=2`, and a
`MultiConnector` containing:

```json
{
  "connectors": [
    {
      "kv_connector": "MooncakeLayerwiseConnector",
      "kv_role": "kv_producer",
      "kv_buffer_device": "npu",
      "kv_rank": 0,
      "kv_port": "20001",
      "kv_connector_extra_config": {
        "use_ascend_direct": true,
        "prefill": {"dp_size": 1, "tp_size": 2},
        "decode": {"dp_size": 1, "tp_size": 2}
      }
    },
    {
      "kv_connector": "AscendStoreConnector",
      "kv_role": "kv_producer",
      "kv_connector_extra_config": {
        "backend": "memcache",
        "mooncake_rpc_port": "0",
        "use_layerwise": true
      }
    }
  ]
}
```

The Decode role listens on port 8006 and uses the corresponding
`kv_consumer`, `kv_rank=1`, `kv_port=20002`, and `mooncake_rpc_port=1`
configuration. The issue text assigns visible devices 8-15 to Decode.

The paired client command is:

```bash
python3 aisbench_test.py \
  --input_len 32000 \
  --output_len 1 \
  --data_num 125 \
  --concurrency 8 \
  --request_rate 0 \
  --dataset_type prefix_cache \
  --repeat_rate 0.9 \
  --prefix_test \
  --seed 1023
```

## Parameters Adopted For The Mooncake Validation Lane

The current validation lane cannot reproduce A3, TP16, GLM-4.7,
DeepSeek-V3.2, memcache, or the historical `MooncakeLayerwiseConnector`
topology. Those would answer a different compatibility question. The following
workload and scheduling principles are adopted directly:

- DeepSeek-V2-Lite, PD separation, TP2, and Prefill DP when capacity permits.
- Exact 32,000-token input, 90-percent shared external prefix, closed-loop
  request rate zero, deterministic seed, and local prefix caching disabled.
- `max_model_len=32768`, `max_num_batched_tokens=32768`, chunked Prefill, eager
  execution, async scheduling, and GPU memory utilization 0.95, subject to a
  new startup capacity capture.
- Test 1 compares BULK and LAYERWISE at output 128 as separately required.
- Test 2 compares BULK and REUSE3 at output 1 at one capacity-bound concurrency
  point rather than scanning a concurrency staircase.
- Client concurrency is not accepted as server concurrency. Iteration and
  scheduler metrics must prove multiple context requests were admitted.

The connector remains the frozen Mooncake-backed `AscendStoreConnector`, and
the candidate source/model/image remain those accepted by the feature handoff.
