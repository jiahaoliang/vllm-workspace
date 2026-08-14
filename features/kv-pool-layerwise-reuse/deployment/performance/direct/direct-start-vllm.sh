#!/usr/bin/env bash
set -euo pipefail
role=$1
variant=$2
max_num_seqs=$3
long_prefill_token_threshold=$4

if [[ ${role} == prefill ]]; then
  port=8100
  kv_role=kv_producer
  consumer=''
else
  port=8200
  kv_role=kv_consumer
  consumer=',"consumer_is_to_load":true'
fi

case ${variant} in
  bulk) variant_json='"use_layerwise":false' ;;
  layerwise) variant_json='"use_layerwise":true' ;;
  reuse3)
    if [[ ${role} == prefill ]]; then
      variant_json='"use_layerwise":true,"layerwise_num_shared_buffers":3'
    else
      variant_json='"use_layerwise":true'
    fi
    ;;
  *) echo "unknown variant: ${variant}" >&2; exit 2 ;;
esac

kv_config='{"kv_connector":"AscendStoreConnector","kv_connector_extra_config":{"backend":"mooncake","layerwise_prefetch_layers":3,"lookup_rpc_port":0,'"${variant_json}${consumer}"'},"kv_load_failure_policy":"fail","kv_role":"'"${kv_role}"'"}'

exec env VLLM_USE_V1=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \
  MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB \
  MC_TE_METRIC=1 MC_TE_METRIC_INTERVAL_SECONDS=1 \
  MC_STORE_CLIENT_METRIC=1 MC_STORE_CLIENT_METRIC_INTERVAL=1 \
  VLLM_ASCEND_KVPOOL_RANGE_DEBUG=0 \
  python3 -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port "${port}" \
  --model /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --served-model-name vllm-ascend/DeepSeek-V2-Lite-W8A8 \
  --quantization ascend --trust-remote-code --enforce-eager \
  --distributed-executor-backend mp --data-parallel-size 1 \
  --data-parallel-backend mp --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 --prefill-context-parallel-size 1 \
  --decode-context-parallel-size 1 --block-size 128 \
  --enable-chunked-prefill --max-model-len 32768 \
  --max-num-batched-tokens 32768 --max-num-seqs "${max_num_seqs}" \
  --no-enable-prefix-caching --enable-logging-iteration-details \
  --gpu-memory-utilization 0.95 --kv-transfer-config "${kv_config}" \
  --async-scheduling --seed 1024 \
  --long-prefill-token-threshold "${long_prefill_token_threshold}" \
  --enable-per-request-metrics
