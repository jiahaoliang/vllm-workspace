# Blockwise DSA NPU Happy Path Runbook

状态：`planned / not run`

本文用于在具备 32 张可用 Ascend NPU 的外部环境中，手工验证 Blockwise DSA PD
offload 的 Happy Path。本文没有在当前 workspace 执行任何 NPU 命令。

## 1. 测试边界

### 1.1 被测对象

- vLLM-Ascend commit：`7401ae79c11d6ec0033ea3ac39085379a0bb81ef`
- Connector：`MooncakeConnectorV1`
- Feature switch：`dsa_pd_offload=true`
- 模型：GLM W4A8，实际路径由执行者填写
- 拓扑：`P TP8/DP2 -> D TP2/DP8`
- Decode：`use_offload=true`、`kv_offload_mode=fused_overlap`
- 传输：Mooncake Transfer Engine P2P，Indexer D2D、Main D2RH

### 1.2 本轮通过意味着什么

本轮只比较 baseline 与 P/D 回答的语义是否一致，并确认请求、服务和 Mooncake transfer
没有报错。全部通过后，结论只能写成：

```text
Happy Path smoke passed
```

它不证明 token IDs 一致、KV tensor 一致、性能达标或 Lifecycle 异常路径正确。

### 1.3 不需要单独启动 Mooncake Master

`MooncakeConnectorV1` 的 worker 会在 vLLM 进程内创建 Mooncake Transfer Engine，并以
`P2PHANDSHAKE`、Ascend backend 初始化。本文不使用 Mooncake Store，因此没有
Mooncake Master、metadata server 或独立 Mooncake 配置进程。

PD proxy 内置 `/v1/metaserver` HTTP endpoint。Decode 用它把当前请求的
`kv_transfer_params` 交给 proxy，proxy 再把请求转给 Prefill。KV payload 不经过 proxy，
仍由 P/D worker 的 Transfer Engine 直接 P2P 传输。

## 2. 执行前约定

在一台能 SSH 到所有 P/D 节点的协调节点执行本文命令。命令假设：

- 协调节点安装 Bash 4+、OpenSSH、curl、jq、Python 3 和 `rg`；
- 所有 P/D 节点使用相同的 vLLM-Ascend 路径、模型路径和 runtime env 文件路径；
- runtime env 文件负责设置 CANN、torch_npu、Mooncake、Python 和 `vllm` 的运行环境；
- SSH 已配置免交互认证；
- `PROXY_HOST` 是所有 Decode 节点都能访问的具体 IP，不是 `0.0.0.0` 或 loopback；
- 同一 host 上的 replica 使用不同 NPU、HTTP port、KV port 和 DP RPC port；
- 本轮没有其他进程占用配置中的 NPU 和端口。

本文不提供独立 preflight。启动命令会拒绝空配置，启动后用 health endpoint 判断是否
继续。

## 3. 创建并填写 `happy-path.env`

在协调节点创建工作目录：

```bash
mkdir -p blockwise-dsa-happy-path
cd blockwise-dsa-happy-path
```

创建环境文件：

```bash
cat > happy-path.env <<'EOF'
# 所有节点都使用的路径
RUN_ROOT=/absolute/path/to/dsa-test-runs
MODEL_PATH=/absolute/path/to/GLM-W4A8
SERVED_MODEL_NAME=glm-w4a8-dsa-happy
VLLM_ASCEND_ROOT=/absolute/path/to/vllm-ascend
REMOTE_ENV_FILE=/absolute/path/to/runtime.env

# SSH 与通信网卡
SSH_USER=root
NET_IFACE=eth0

# Proxy 进程所在节点和源码文件
PROXY_SSH_HOST=10.0.0.10
PROXY_HOST=10.0.0.10
PROXY_PORT=8000
PROXY_SCRIPT=/absolute/path/to/vllm-ascend/examples/disaggregated_prefill_v1/load_balance_proxy_layerwise_server_example.py

# Baseline 使用第一个 Prefill host 和第一组 8 张 NPU
BASELINE_PORT=8090

# Prefill external-DP coordinator。两个 P rank 使用同一组值。
P_DP_ADDRESS=10.0.0.11
P_DP_RPC_PORT=19001

# 两个 Prefill DP replica；每个列表严格按 DP_RANK=0,1 对齐。
P_HOSTS="10.0.0.11 10.0.0.12"
P_DEVICES="0,1,2,3,4,5,6,7 0,1,2,3,4,5,6,7"
P_HTTP_PORTS="8100 8100"
P_KV_PORTS="20000 20100"
P_ENGINE_IDS="p0 p1"

# Decode external-DP coordinator。八个 D rank 使用同一组值。
D_DP_ADDRESS=10.0.0.21
D_DP_RPC_PORT=19002

# 八个 Decode DP replica；每个列表严格按 DP_RANK=0..7 对齐。
D_HOSTS="10.0.0.21 10.0.0.22 10.0.0.23 10.0.0.24 10.0.0.25 10.0.0.26 10.0.0.27 10.0.0.28"
D_DEVICES="0,1 0,1 0,1 0,1 0,1 0,1 0,1 0,1"
D_HTTP_PORTS="8200 8200 8200 8200 8200 8200 8200 8200"
D_KV_PORTS="21000 21100 21200 21300 21400 21500 21600 21700"
D_ENGINE_IDS="d0 d1 d2 d3 d4 d5 d6 d7"

# 公共模型和调度参数
MAX_MODEL_LEN=32768
MAX_NUM_SEQS=32
P_MAX_NUM_BATCHED_TOKENS=8192
D_MAX_NUM_BATCHED_TOKENS=128
SEED=1024
GPU_MEMORY_UTILIZATION_P=0.80
GPU_MEMORY_UTILIZATION_D=0.85
EOF
```

编辑所有 `/absolute/path/...` 和示例 IP。不要在该文件中保存密码或 access token。

## 4. 初始化本次运行

后续命令应在同一个协调节点 Bash session 中执行。加载配置并定义公共 helper：

```bash
set -euo pipefail
source happy-path.env

for command in ssh scp curl jq python3 rg; do
  command -v "$command" >/dev/null || {
    echo "missing command: $command" >&2
    exit 1
  }
done

for name in RUN_ROOT MODEL_PATH SERVED_MODEL_NAME VLLM_ASCEND_ROOT \
  REMOTE_ENV_FILE SSH_USER NET_IFACE PROXY_SSH_HOST PROXY_HOST PROXY_PORT \
  PROXY_SCRIPT BASELINE_PORT P_DP_ADDRESS P_DP_RPC_PORT \
  D_DP_ADDRESS D_DP_RPC_PORT; do
  value="${!name:-}"
  test -n "$value" || {
    echo "$name is empty" >&2
    exit 1
  }
  case "$value" in
    *REPLACE_ME*|/absolute/path/*)
      echo "$name is not resolved: $value" >&2
      exit 1
      ;;
  esac
done

read -r -a P_HOST_A <<<"$P_HOSTS"
read -r -a P_DEVICE_A <<<"$P_DEVICES"
read -r -a P_HTTP_A <<<"$P_HTTP_PORTS"
read -r -a P_KV_A <<<"$P_KV_PORTS"
read -r -a P_ENGINE_A <<<"$P_ENGINE_IDS"
read -r -a D_HOST_A <<<"$D_HOSTS"
read -r -a D_DEVICE_A <<<"$D_DEVICES"
read -r -a D_HTTP_A <<<"$D_HTTP_PORTS"
read -r -a D_KV_A <<<"$D_KV_PORTS"
read -r -a D_ENGINE_A <<<"$D_ENGINE_IDS"

for count in "${#P_HOST_A[@]}" "${#P_DEVICE_A[@]}" \
  "${#P_HTTP_A[@]}" "${#P_KV_A[@]}" "${#P_ENGINE_A[@]}"; do
  test "$count" -eq 2 || {
    echo "every P_* list must contain exactly 2 values" >&2
    exit 1
  }
done
for count in "${#D_HOST_A[@]}" "${#D_DEVICE_A[@]}" \
  "${#D_HTTP_A[@]}" "${#D_KV_A[@]}" "${#D_ENGINE_A[@]}"; do
  test "$count" -eq 8 || {
    echo "every D_* list must contain exactly 8 values" >&2
    exit 1
  }
done

RUN_ID="dsa-happy-$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_RUN_DIR="$RUN_ROOT/$RUN_ID/coordinator"
mkdir -p "$LOCAL_RUN_DIR"/{requests,responses,logs,review}
cp happy-path.env "$LOCAL_RUN_DIR/resolved.env"
printf '%s\n' "$RUN_ID" | tee "$LOCAL_RUN_DIR/RUN_ID"

wait_http() {
  local url=$1
  local name=$2
  local deadline=$((SECONDS + 3600))
  until curl --silent --show-error --fail "$url" >/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "$name did not become healthy: $url" >&2
      return 1
    fi
    sleep 10
  done
  echo "$name is healthy: $url"
}

stop_remote_pid() {
  local host=$1
  local pid_file=$2
  local expected=$3
  ssh -o BatchMode=yes "$SSH_USER@$host" bash -s -- \
    "$pid_file" "$expected" <<'REMOTE'
set -euo pipefail
pid_file=$1
expected=$2
test -s "$pid_file" || {
  echo "missing PID file: $pid_file" >&2
  exit 1
}
pid=$(cat "$pid_file")
if ! kill -0 "$pid" 2>/dev/null; then
  echo "process already exited: $pid"
  exit 0
fi
cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline")
case "$cmdline" in
  *"$expected"*) ;;
  *)
    echo "refusing to stop unexpected process $pid: $cmdline" >&2
    exit 1
    ;;
esac
kill -TERM "$pid"
for _ in $(seq 1 60); do
  kill -0 "$pid" 2>/dev/null || exit 0
  sleep 2
done
echo "SIGTERM timeout for $pid; sending SIGKILL" >&2
kill -KILL "$pid"
REMOTE
}
```

记录本次执行时间和源码身份。以下命令只读取远端信息：

```bash
{
  echo "run_id=$RUN_ID"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "expected_vllm_ascend=7401ae79c11d6ec0033ea3ac39085379a0bb81ef"
  for host in "${P_HOST_A[@]}" "${D_HOST_A[@]}"; do
    printf '%s ' "$host"
    ssh -o BatchMode=yes "$SSH_USER@$host" \
      git -C "$VLLM_ASCEND_ROOT" rev-parse HEAD
  done
} | tee "$LOCAL_RUN_DIR/source-identity.txt"
```

若任一节点不是目标 commit，停止本次运行；不要在测试过程中修改源码。

## 5. 生成固定请求

用同一组请求分别调用 baseline 和 P/D proxy：

```bash
python3 - "$LOCAL_RUN_DIR/requests" "$SERVED_MODEL_NAME" "$SEED" <<'PY'
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
model = sys.argv[2]
seed = int(sys.argv[3])

def payload(prompt: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "seed": seed,
        "max_tokens": max_tokens,
        "stream": False,
    }

short = "用三句话解释为什么海水是咸的。"
paragraph = (
    "请在阅读本段背景后总结关键因果关系。某城市同时推进可再生能源、公共交通、"
    "建筑节能和电网储能，并要求兼顾可靠性、成本、公平性与长期维护。"
)
long_prompt = "\n".join([paragraph for _ in range(100)]) + "\n请给出结构化总结。"
long_output = "系统说明从需求分析到上线运维，如何建设一个可靠的城市应急响应平台。"

(out / "hp01-short.json").write_text(
    json.dumps(payload(short, 96), ensure_ascii=False, indent=2) + "\n"
)
(out / "hp02-long-prompt.json").write_text(
    json.dumps(payload(long_prompt, 192), ensure_ascii=False, indent=2) + "\n"
)
(out / "hp03-long-output.json").write_text(
    json.dumps(payload(long_output, 512), ensure_ascii=False, indent=2) + "\n"
)

questions = [
    "解释光合作用的基本过程。",
    "说明供需关系如何影响价格。",
    "比较 TCP 和 UDP 的主要差异。",
    "解释为什么需要数据库索引。",
    "概述水循环的主要阶段。",
    "说明什么是幂等操作。",
    "解释缓存命中率的含义。",
    "概述机器学习训练与推理的区别。",
    "说明分布式系统为何需要超时。",
    "解释太阳能电池的基本原理。",
    "比较进程与线程。",
    "说明日志分级的作用。",
    "解释什么是负载均衡。",
    "概述软件回归测试的目的。",
    "说明数据备份为何需要恢复演练。",
    "解释 API 版本管理的意义。",
]
with (out / "hp04-low-concurrency.jsonl").open("w") as stream:
    for index, question in enumerate(questions, start=1):
        item = payload(question, 128)
        item["request_id"] = f"hp04-{index:02d}"
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
PY

sha256sum "$LOCAL_RUN_DIR"/requests/* \
  | tee "$LOCAL_RUN_DIR/requests/SHA256SUMS"
```

定义请求执行 helper。它保存原始 JSON，不做语义判断：

```bash
run_suite() {
  local base_url=$1
  local label=$2
  local output_dir="$LOCAL_RUN_DIR/responses/$label"
  mkdir -p "$output_dir"

  for case_id in hp01-short hp02-long-prompt hp03-long-output; do
    curl --silent --show-error --fail-with-body \
      --connect-timeout 30 --max-time 1800 \
      -H 'Content-Type: application/json' \
      --data-binary "@$LOCAL_RUN_DIR/requests/$case_id.json" \
      "$base_url/v1/chat/completions" \
      > "$output_dir/$case_id.json"
  done

  seq 1 16 | xargs -P 8 -I '{}' sh -c '
    line=$1
    request_file=$2
    output_dir=$3
    base_url=$4
    sed -n "${line}p" "$request_file" \
      | jq "del(.request_id)" \
      | curl --silent --show-error --fail-with-body \
          --connect-timeout 30 --max-time 1800 \
          -H "Content-Type: application/json" \
          --data-binary @- \
          "$base_url/v1/chat/completions" \
      > "$output_dir/hp04-$(printf "%02d" "$line").json"
  ' _ '{}' "$LOCAL_RUN_DIR/requests/hp04-low-concurrency.jsonl" \
    "$output_dir" "$base_url"

  for response in "$output_dir"/*.json; do
    jq -e '.choices[0].message.content | type == "string" and length > 0' \
      "$response" >/dev/null
  done
  sha256sum "$output_dir"/*.json > "$output_dir/SHA256SUMS"
}
```

## 6. 运行 baseline

Baseline 使用第一个 Prefill replica 的 8 张 NPU，TP=8、DP=1，不配置 KV connector。

```bash
BASELINE_HOST=${P_HOST_A[0]}
BASELINE_DEVICES=${P_DEVICE_A[0]}

ssh -o BatchMode=yes "$SSH_USER@$BASELINE_HOST" bash -s -- \
  "$RUN_ROOT" "$RUN_ID" "$REMOTE_ENV_FILE" "$VLLM_ASCEND_ROOT" \
  "$MODEL_PATH" "$SERVED_MODEL_NAME" "$BASELINE_DEVICES" "$BASELINE_PORT" \
  "$NET_IFACE" "$MAX_MODEL_LEN" "$MAX_NUM_SEQS" \
  "$P_MAX_NUM_BATCHED_TOKENS" "$SEED" "$GPU_MEMORY_UTILIZATION_P" <<'REMOTE'
set -euo pipefail
run_root=$1; run_id=$2; runtime_env=$3; source_root=$4
model=$5; served_model=$6; devices=$7; port=$8; nic=$9
max_model_len=${10}; max_num_seqs=${11}; max_batched=${12}; seed=${13}; gpu_util=${14}
source "$runtime_env"
cd "$source_root"
run_dir="$run_root/$run_id/baseline"
mkdir -p "$run_dir"
nohup env \
  ASCEND_RT_VISIBLE_DEVICES="$devices" \
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
  GLOO_SOCKET_IFNAME="$nic" TP_SOCKET_IFNAME="$nic" HCCL_SOCKET_IFNAME="$nic" \
  vllm serve "$model" \
    --served-model-name "$served_model" \
    --host 0.0.0.0 --port "$port" \
    --tensor-parallel-size 8 --data-parallel-size 1 \
    --seed "$seed" --max-model-len "$max_model_len" \
    --max-num-seqs "$max_num_seqs" \
    --max-num-batched-tokens "$max_batched" \
    --trust-remote-code --enforce-eager --quantization ascend \
    --gpu-memory-utilization "$gpu_util" \
    --additional-config '{"use_offload":false}' \
    > "$run_dir/baseline.log" 2>&1 < /dev/null &
echo $! > "$run_dir/baseline.pid"
REMOTE

wait_http "http://$BASELINE_HOST:$BASELINE_PORT/health" baseline
run_suite "http://$BASELINE_HOST:$BASELINE_PORT" baseline
```

停止 baseline 后再占用 P/D 的 32 张 NPU：

```bash
stop_remote_pid "$BASELINE_HOST" \
  "$RUN_ROOT/$RUN_ID/baseline/baseline.pid" \
  "vllm serve $MODEL_PATH"
```

## 7. 启动 8 个 Decode replica

Decode 必须先启动。下面的 `kv_connector_extra_config` 是本次 Mooncake P2P 配置；没有
单独的 Mooncake Master 配置文件。

```bash
for rank in $(seq 0 7); do
  host=${D_HOST_A[$rank]}
  devices=${D_DEVICE_A[$rank]}
  http_port=${D_HTTP_A[$rank]}
  kv_port=${D_KV_A[$rank]}
  engine_id=${D_ENGINE_A[$rank]}

  ssh -o BatchMode=yes "$SSH_USER@$host" bash -s -- \
    "$RUN_ROOT" "$RUN_ID" "$REMOTE_ENV_FILE" "$VLLM_ASCEND_ROOT" \
    "$MODEL_PATH" "$SERVED_MODEL_NAME" "$devices" "$http_port" "$kv_port" \
    "$engine_id" "$rank" "$D_DP_ADDRESS" "$D_DP_RPC_PORT" "$NET_IFACE" \
    "$MAX_MODEL_LEN" "$MAX_NUM_SEQS" "$D_MAX_NUM_BATCHED_TOKENS" \
    "$SEED" "$GPU_MEMORY_UTILIZATION_D" <<'REMOTE'
set -euo pipefail
run_root=$1; run_id=$2; runtime_env=$3; source_root=$4
model=$5; served_model=$6; devices=$7; http_port=$8; kv_port=$9
engine_id=${10}; dp_rank=${11}; dp_address=${12}; dp_rpc_port=${13}; nic=${14}
max_model_len=${15}; max_num_seqs=${16}; max_batched=${17}; seed=${18}; gpu_util=${19}
source "$runtime_env"
cd "$source_root"
run_dir="$run_root/$run_id/decode-$dp_rank"
mkdir -p "$run_dir"
kv_config=$(printf '%s' "{
  \"kv_connector\": \"MooncakeConnectorV1\",
  \"kv_buffer_device\": \"npu\",
  \"kv_role\": \"kv_consumer\",
  \"kv_parallel_size\": 1,
  \"kv_port\": \"$kv_port\",
  \"engine_id\": \"$engine_id\",
  \"kv_connector_extra_config\": {
    \"dsa_pd_offload\": true,
    \"sfa_kv_offload_backend\": \"mooncake\",
    \"prefill\": {\"dp_size\": 2, \"tp_size\": 8, \"pp_size\": 1},
    \"decode\": {\"dp_size\": 8, \"tp_size\": 2, \"pp_size\": 1}
  }
}")
nohup env \
  ASCEND_RT_VISIBLE_DEVICES="$devices" \
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
  VLLM_ASCEND_KV_TRANSFER_BACKEND=mooncake \
  GLOO_SOCKET_IFNAME="$nic" TP_SOCKET_IFNAME="$nic" HCCL_SOCKET_IFNAME="$nic" \
  vllm serve "$model" \
    --served-model-name "$served_model" \
    --host 0.0.0.0 --port "$http_port" \
    --tensor-parallel-size 2 \
    --data-parallel-size 8 --data-parallel-rank "$dp_rank" \
    --data-parallel-address "$dp_address" \
    --data-parallel-rpc-port "$dp_rpc_port" \
    --seed "$seed" --max-model-len "$max_model_len" \
    --max-num-seqs "$max_num_seqs" \
    --max-num-batched-tokens "$max_batched" \
    --trust-remote-code --enforce-eager --quantization ascend \
    --gpu-memory-utilization "$gpu_util" \
    --additional-config '{"use_offload":true,"kv_offload_mode":"fused_overlap","lru_resident_cache_config":{"enabled":true,"buffer_size":2048,"topk":2048}}' \
    --kv-transfer-config "$kv_config" \
    > "$run_dir/decode-$dp_rank.log" 2>&1 < /dev/null &
echo $! > "$run_dir/decode-$dp_rank.pid"
REMOTE
done

for rank in $(seq 0 7); do
  wait_http "http://${D_HOST_A[$rank]}:${D_HTTP_A[$rank]}/health" \
    "decode-$rank"
done
```

若任一 Decode health 失败，不启动 Prefill。先执行第 13 节收集日志，再执行清理。

## 8. 启动 2 个 Prefill replica

```bash
for rank in $(seq 0 1); do
  host=${P_HOST_A[$rank]}
  devices=${P_DEVICE_A[$rank]}
  http_port=${P_HTTP_A[$rank]}
  kv_port=${P_KV_A[$rank]}
  engine_id=${P_ENGINE_A[$rank]}

  ssh -o BatchMode=yes "$SSH_USER@$host" bash -s -- \
    "$RUN_ROOT" "$RUN_ID" "$REMOTE_ENV_FILE" "$VLLM_ASCEND_ROOT" \
    "$MODEL_PATH" "$SERVED_MODEL_NAME" "$devices" "$http_port" "$kv_port" \
    "$engine_id" "$rank" "$P_DP_ADDRESS" "$P_DP_RPC_PORT" "$NET_IFACE" \
    "$MAX_MODEL_LEN" "$MAX_NUM_SEQS" "$P_MAX_NUM_BATCHED_TOKENS" \
    "$SEED" "$GPU_MEMORY_UTILIZATION_P" <<'REMOTE'
set -euo pipefail
run_root=$1; run_id=$2; runtime_env=$3; source_root=$4
model=$5; served_model=$6; devices=$7; http_port=$8; kv_port=$9
engine_id=${10}; dp_rank=${11}; dp_address=${12}; dp_rpc_port=${13}; nic=${14}
max_model_len=${15}; max_num_seqs=${16}; max_batched=${17}; seed=${18}; gpu_util=${19}
source "$runtime_env"
cd "$source_root"
run_dir="$run_root/$run_id/prefill-$dp_rank"
mkdir -p "$run_dir"
kv_config=$(printf '%s' "{
  \"kv_connector\": \"MooncakeConnectorV1\",
  \"kv_buffer_device\": \"npu\",
  \"kv_role\": \"kv_producer\",
  \"kv_parallel_size\": 1,
  \"kv_port\": \"$kv_port\",
  \"engine_id\": \"$engine_id\",
  \"kv_connector_extra_config\": {
    \"dsa_pd_offload\": true,
    \"prefill\": {\"dp_size\": 2, \"tp_size\": 8, \"pp_size\": 1},
    \"decode\": {\"dp_size\": 8, \"tp_size\": 2, \"pp_size\": 1}
  }
}")
nohup env \
  ASCEND_RT_VISIBLE_DEVICES="$devices" \
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
  VLLM_ASCEND_KV_TRANSFER_BACKEND=mooncake \
  GLOO_SOCKET_IFNAME="$nic" TP_SOCKET_IFNAME="$nic" HCCL_SOCKET_IFNAME="$nic" \
  vllm serve "$model" \
    --served-model-name "$served_model" \
    --host 0.0.0.0 --port "$http_port" \
    --tensor-parallel-size 8 \
    --data-parallel-size 2 --data-parallel-rank "$dp_rank" \
    --data-parallel-address "$dp_address" \
    --data-parallel-rpc-port "$dp_rpc_port" \
    --seed "$seed" --max-model-len "$max_model_len" \
    --max-num-seqs "$max_num_seqs" \
    --max-num-batched-tokens "$max_batched" \
    --trust-remote-code --enforce-eager --quantization ascend \
    --gpu-memory-utilization "$gpu_util" \
    --additional-config '{"use_offload":false}' \
    --kv-transfer-config "$kv_config" \
    > "$run_dir/prefill-$dp_rank.log" 2>&1 < /dev/null &
echo $! > "$run_dir/prefill-$dp_rank.pid"
REMOTE
done

for rank in $(seq 0 1); do
  wait_http "http://${P_HOST_A[$rank]}:${P_HTTP_A[$rank]}/health" \
    "prefill-$rank"
done
```

## 9. 启动 PD proxy 和内置 metaserver

```bash
P_HOST_ARGS=$(printf '%q ' "${P_HOST_A[@]}")
P_PORT_ARGS=$(printf '%q ' "${P_HTTP_A[@]}")
D_HOST_ARGS=$(printf '%q ' "${D_HOST_A[@]}")
D_PORT_ARGS=$(printf '%q ' "${D_HTTP_A[@]}")

ssh -o BatchMode=yes "$SSH_USER@$PROXY_SSH_HOST" bash -s -- \
  "$RUN_ROOT" "$RUN_ID" "$REMOTE_ENV_FILE" "$PROXY_SCRIPT" \
  "$PROXY_HOST" "$PROXY_PORT" "$P_HOST_ARGS" "$P_PORT_ARGS" \
  "$D_HOST_ARGS" "$D_PORT_ARGS" <<'REMOTE'
set -euo pipefail
run_root=$1; run_id=$2; runtime_env=$3; proxy_script=$4
proxy_host=$5; proxy_port=$6; p_hosts=$7; p_ports=$8; d_hosts=$9; d_ports=${10}
source "$runtime_env"
run_dir="$run_root/$run_id/proxy"
mkdir -p "$run_dir"
command="python3 $(printf '%q' "$proxy_script") \
  --host $(printf '%q' "$proxy_host") --port $(printf '%q' "$proxy_port") \
  --prefiller-hosts $p_hosts --prefiller-ports $p_ports \
  --decoder-hosts $d_hosts --decoder-ports $d_ports"
nohup bash -lc "exec $command" > "$run_dir/proxy.log" 2>&1 < /dev/null &
echo $! > "$run_dir/proxy.pid"
printf '%s\n' "$command" > "$run_dir/proxy.command"
REMOTE

wait_http "http://$PROXY_HOST:$PROXY_PORT/healthcheck" proxy
curl --silent --show-error --fail \
  "http://$PROXY_HOST:$PROXY_PORT/healthcheck" \
  | tee "$LOCAL_RUN_DIR/proxy-health.json" \
  | jq -e '.status == "ok" and .prefill_instances == 2 and .decode_instances == 8'
```

## 10. 运行 P/D Happy Path 请求

```bash
run_suite "http://$PROXY_HOST:$PROXY_PORT" pd
```

客观响应检查：

```bash
test "$(find "$LOCAL_RUN_DIR/responses/baseline" -name '*.json' | wc -l)" -eq 19
test "$(find "$LOCAL_RUN_DIR/responses/pd" -name '*.json' | wc -l)" -eq 19

for label in baseline pd; do
  for response in "$LOCAL_RUN_DIR/responses/$label"/*.json; do
    jq -e '.choices[0].message.content | type == "string" and length > 0' \
      "$response" >/dev/null
  done
done
```

## 11. 人工语义对比

先生成便于阅读的文本：

```bash
for label in baseline pd; do
  output="$LOCAL_RUN_DIR/review/$label.txt"
  : > "$output"
  for response in "$LOCAL_RUN_DIR/responses/$label"/*.json; do
    {
      echo "===== $(basename "$response") ====="
      jq -r '.choices[0].message.content' "$response"
      echo
    } >> "$output"
  done
done
```

逐条阅读 `review/baseline.txt` 与 `review/pd.txt`，填写：

| 请求 ID | Baseline 摘要 | P/D 摘要 | 语义一致 | 备注 |
|---|---|---|---|---|
| `hp01-short` | | | PASS / FAIL | |
| `hp02-long-prompt` | | | PASS / FAIL | |
| `hp03-long-output` | | | PASS / FAIL | |
| `hp04-01` ... `hp04-16` | | | PASS / FAIL | |

将完成后的表保存为 `$LOCAL_RUN_DIR/review/manual-review.md`。任何一项 FAIL 都使本次
Happy Path 失败；不自动重试该请求。

## 12. 收集远端日志

在停止服务前收集日志：

```bash
mkdir -p "$LOCAL_RUN_DIR/logs/remote"

scp -r "$SSH_USER@$PROXY_SSH_HOST:$RUN_ROOT/$RUN_ID/proxy" \
  "$LOCAL_RUN_DIR/logs/remote/"

for rank in $(seq 0 1); do
  scp -r "$SSH_USER@${P_HOST_A[$rank]}:$RUN_ROOT/$RUN_ID/prefill-$rank" \
    "$LOCAL_RUN_DIR/logs/remote/"
done

for rank in $(seq 0 7); do
  scp -r "$SSH_USER@${D_HOST_A[$rank]}:$RUN_ROOT/$RUN_ID/decode-$rank" \
    "$LOCAL_RUN_DIR/logs/remote/"
done

scp -r "$SSH_USER@$BASELINE_HOST:$RUN_ROOT/$RUN_ID/baseline" \
  "$LOCAL_RUN_DIR/logs/remote/"

find "$LOCAL_RUN_DIR/logs" -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > "$LOCAL_RUN_DIR/logs/SHA256SUMS"
```

## 13. 日志验收

先搜索明确失败信号：

```bash
rg -n -i \
  'Traceback|segmentation fault|process.*crash|illegal address|invalid handle|TransferEngine initialization failed|register.*fail|transfer.*fail|batch_transfer_sync_read.*fail|ACL.*error' \
  "$LOCAL_RUN_DIR/logs/remote" \
  | tee "$LOCAL_RUN_DIR/review/error-scan.txt" || true
```

逐条人工判断 `error-scan.txt`。任何真实 traceback、process crash、Transfer Engine
initialize/register/transfer failure 或非法地址错误均为 FAIL。不要仅因日志包含描述性
单词 `error` 就判失败，也不要删除失败日志后重跑。

再搜索正向路径证据：

```bash
rg -n -i \
  'KV transfer backend = mooncake|P2PHANDSHAKE|dsa_pd_offload|RECEIVE_REMOTE|RECEIVE_COMPLETE|fused_overlap|D2H_COMPLETE|finished_recving' \
  "$LOCAL_RUN_DIR/logs/remote" \
  | tee "$LOCAL_RUN_DIR/review/path-evidence.txt" || true
```

人工确认至少存在：

- Decode 与 Prefill 的 Mooncake backend 初始化证据；
- Decode 侧 fused overlap Host Main allocation/registration 证据；
- 请求 remote prefill 与 Mooncake receive 完成证据；
- Decode 持续生成期间 fused D2H/`fused_overlap` 路径证据；
- 没有请求丢失或 worker/rank 提前退出。

只有 HTTP 200 或 proxy 日志不足以证明 P2P Happy Path。

## 14. 精确停止本次 P/D 服务

停止顺序与启动相反。先停止 proxy：

```bash
stop_remote_pid "$PROXY_SSH_HOST" \
  "$RUN_ROOT/$RUN_ID/proxy/proxy.pid" \
  "$PROXY_SCRIPT"
```

停止 Prefill：

```bash
for rank in $(seq 0 1); do
  stop_remote_pid "${P_HOST_A[$rank]}" \
    "$RUN_ROOT/$RUN_ID/prefill-$rank/prefill-$rank.pid" \
    "vllm serve $MODEL_PATH"
done
```

停止 Decode：

```bash
for rank in $(seq 0 7); do
  stop_remote_pid "${D_HOST_A[$rank]}" \
    "$RUN_ROOT/$RUN_ID/decode-$rank/decode-$rank.pid" \
    "vllm serve $MODEL_PATH"
done
```

禁止使用 `pkill`、`killall` 或按进程名批量终止。Mooncake Transfer Engine 随各 vLLM
worker 退出，不需要清理 Mooncake Master 或 Store session。

检查本次端口已释放：

```bash
for rank in $(seq 0 1); do
  p_base=${P_KV_A[$rank]}
  p_ports=${P_HTTP_A[$rank]}
  for offset in $(seq 0 7); do
    p_ports="$p_ports|$((p_base + offset))"
  done
  if ssh -o BatchMode=yes "$SSH_USER@${P_HOST_A[$rank]}" ss -lntp \
    | rg ":($p_ports)\\b"; then
    echo "Prefill $rank still owns a configured port" >&2
    exit 1
  fi
done
for rank in $(seq 0 7); do
  d_base=${D_KV_A[$rank]}
  d_ports="${D_HTTP_A[$rank]}|$d_base|$((d_base + 1))"
  if ssh -o BatchMode=yes "$SSH_USER@${D_HOST_A[$rank]}" ss -lntp \
    | rg ":($d_ports)\\b"; then
    echo "Decode $rank still owns a configured port" >&2
    exit 1
  fi
done
if ssh -o BatchMode=yes "$SSH_USER@$PROXY_SSH_HOST" ss -lntp \
  | rg ":${PROXY_PORT}\\b"; then
  echo "Proxy still owns port $PROXY_PORT" >&2
  exit 1
fi
```

如果端口仍被监听，先核对 PID 与 command line；不要终止无法证明属于本次 RUN_ID 的
进程。

## 15. 结果汇总

在 `$LOCAL_RUN_DIR/summary.md` 记录：

```markdown
# Blockwise DSA NPU Happy Path Result

- Run ID: `<RUN_ID>`
- Status: PASS / FAIL / BLOCKED
- vLLM-Ascend: `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`
- Model: GLM W4A8，实际路径与 identity 见 `resolved.env`
- Topology: `P TP8/DP2 -> D TP2/DP8`
- Runtime evidence: `executed` 或 `planned / not run`

## Case Results

| Case | HTTP/response | Human semantic review | Logs | Result |
|---|---|---|---|---|
| HP-01 short | | | | |
| HP-02 long-prompt | | | | |
| HP-03 long-output | | | | |
| HP-04 low-concurrency | | | | |

## Conclusion

只有全部 case 均 PASS 时填写：`Happy Path smoke passed`。
不得填写 token-level correctness、performance validated 或 Lifecycle validated。

## Failures And Evidence

记录首个失败时间、请求 ID、服务/rank、原始错误和对应 artifact 路径。
```

执行前，`Runtime evidence` 必须保持 `planned / not run`。只有真实执行后才能改为
`executed`，并附上本次 run directory 的完整证据。

## 16. 后续计划边界

### 16.1 基础性能

后续单独定义 TTFT、TPOT、E2EL、吞吐、NPU/Host 内存、采样方法、baseline 和阈值。
Happy Path 不采纳性能 pass/fail 结论。

### 16.2 Lifecycle / Boundary

后续单独定义 partial physical block、容量边界、并发 reservation、HOL admission 和资源
release 条件。

### 16.3 Lifecycle / Failure

后续单独定义 fault injection、Indexer/Main 分 phase failure、exact-TP terminal barrier、
all-TP replay 和 stale/duplicate result。

### 16.4 Lifecycle / Control

后续单独定义 preemption、epoch rebind、cancellation、Quiesced、`DONE_RECVING_MSG`、
`finished_recving` 和 release-once。

这些章节当前没有执行命令或验收阈值，不能由本次 Happy Path 结果推断为已验证。
