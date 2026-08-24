# Blockwise DSA NPU Happy Path Runbook 设计

状态：设计已批准；Runbook 尚未编写；NPU runtime `planned / not run`

## 1. 目标与结论边界

本设计定义一份供人类执行的真实 Ascend NPU E2E Runbook。Runbook 聚焦
Blockwise DSA PD offload 的 correctness Happy Path，不在当前阶段实现自动化
harness，也不执行 NPU 测试。

被测对象固定为：

- vLLM-Ascend replacement commit
  `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`；
- `MooncakeConnectorV1`，并设置 `dsa_pd_offload=true`；
- GLM W4A8，实际 `MODEL_PATH` 由执行者填写；
- `P TP8/DP2 -> D TP2/DP8`；
- Mooncake Transfer Engine P2P 数据传输；不使用旧
  `MooncakeLayerwiseToDramConnector`。

本轮 oracle 是人工比较同模型 baseline 与 P/D 回答的语义一致性，并确认服务和
Mooncake transfer 无报错。即使全部通过，也只能声明
`Happy Path smoke passed`，不能声明 token-level correctness、性能或完整 Lifecycle
已经验证。

## 2. 交付形式

交付物是一份 feature-local、按时间顺序执行的 Markdown Runbook。所有命令以可直接
复制的代码块提供，但本轮不创建独立启动脚本、schema、runner 或测试框架。

Runbook 的主流程是：

1. 填写并加载一个 `happy-path.env`。
2. 运行非 PD baseline 并保存四组回答。
3. 停止 baseline。
4. 启动 8 个 Decode replica，并等待全部健康。
5. 启动 2 个 Prefill replica，并等待全部健康。
6. 启动 PD proxy，并等待健康。
7. 执行四组 Happy Path 请求。
8. 人工比较 baseline 与 P/D 回答。
9. 检查全部服务和 transfer 日志。
10. 按精确 PID 停止本次启动的进程并汇总证据。

Runbook 不设置独立的全节点 preflight 阶段。每个命令仍须在使用变量前拒绝空值，服务
启动后仍须检查 health endpoint；这些是命令自身的失败保护，不构成单独测试阶段。

## 3. Mooncake 与控制面边界

本路径不启动 Mooncake Master 或 Mooncake Store。每个 vLLM worker 在进程内初始化
Mooncake Transfer Engine，使用 `P2PHANDSHAKE` 和 Ascend backend 做 P2P 数据传输。

PD proxy 同时提供 OpenAI-compatible API 和 `/v1/metaserver` endpoint。这里的
metaserver 不是独立进程，也不是 Mooncake Master。Decode 用它把当前请求的
`remote_block_ids`、`remote_host`、`remote_port` 等 `kv_transfer_params` 回传给 proxy，
proxy 再把这些参数交给 Prefill。KV payload 不经过 proxy，仍由 P/D worker 内的
Mooncake Transfer Engine 直接传输。

因此 Runbook 只包含：

- `MooncakeConnectorV1` 的 P/D 配置；
- Transfer Engine 所需的网卡、host、KV port 和 `engine_id`；
- P/D topology 与 SFA offload 配置；
- Transfer Engine initialize、register 和 transfer 日志检查；
- PD proxy 的启动与 endpoint 列表。

## 4. 单一环境文件

Runbook 提供一个可被 Bash `source` 的 `happy-path.env` 模板。它不是 Docker Compose
或通用 dotenv parser 的输入。

模板至少包含：

```bash
RUN_ROOT=/absolute/path/to/test-runs
MODEL_PATH=/absolute/path/to/GLM-W4A8
VLLM_ASCEND_ROOT=/absolute/path/to/vllm-ascend
NET_IFACE=eth0
SSH_USER=root

PROXY_HOST=10.0.0.10
PROXY_PORT=8000

P_HOSTS="10.0.0.11 10.0.0.12"
P_DEVICES="0,1,2,3,4,5,6,7 0,1,2,3,4,5,6,7"
P_HTTP_PORTS="8100 8100"
P_KV_PORTS="20000 20100"

D_HOSTS="10.0.0.21 10.0.0.22 10.0.0.23 10.0.0.24 10.0.0.25 10.0.0.26 10.0.0.27 10.0.0.28"
D_DEVICES="0,1 0,1 0,1 0,1 0,1 0,1 0,1 0,1"
D_HTTP_PORTS="8200 8200 8200 8200 8200 8200 8200 8200"
D_KV_PORTS="21000 21100 21200 21300 21400 21500 21600 21700"

MAX_MODEL_LEN=32768
MAX_NUM_SEQS=4
SEED=1024
GPU_MEMORY_UTILIZATION_P=0.80
GPU_MEMORY_UTILIZATION_D=0.85
```

`P_*` 列表按 `DP_RANK=0,1` 对齐，且必须正好有两项。`D_*` 列表按
`DP_RANK=0..7` 对齐，且必须正好有八项。host 可以重复，以支持一台物理机承载多个
replica；设备和端口不能冲突。Runbook 提供短命令检查列表长度。

## 5. 服务启动设计

### 5.1 Baseline

Baseline 使用第一个 Prefill host 和该 replica 的 8 张 NPU，运行普通非 PD 服务：

- TP=8，DP=1；
- 不设置 `kv-transfer-config`；
- `use_offload=false`；
- 与 P/D 使用相同 `MODEL_PATH`、seed、模型参数和 sampling 参数。

采集 baseline 回答后先停止 baseline，再启动 P/D，避免额外占用 NPU。

### 5.2 Decode

每个 Decode replica 使用以下固定语义：

```text
TP_SIZE=2
DP_SIZE=8
DP_RANK=0..7
kv_role=kv_consumer
dsa_pd_offload=true
sfa_kv_offload_backend=mooncake
use_offload=true
kv_offload_mode=fused_overlap
```

每个 replica 从 `D_*` 对齐列表取得 host、两张可见 NPU、HTTP port 和 KV base port。
所有 Decode replica 健康后才能启动 Prefill。

### 5.3 Prefill

每个 Prefill replica 使用以下固定语义：

```text
TP_SIZE=8
DP_SIZE=2
DP_RANK=0..1
kv_role=kv_producer
dsa_pd_offload=true
use_offload=false
```

每个 replica 从 `P_*` 对齐列表取得 host、八张可见 NPU、HTTP port 和 KV base port。
所有 Prefill replica 健康后才能启动 proxy。

### 5.4 Proxy

Proxy 使用具体、可被全部 Decode replica 访问的 `PROXY_HOST`，不能用只在 proxy
本机可达的 loopback address。启动命令显式列出两个 Prefill endpoint 和八个 Decode
endpoint，并保证 host 与 port 一一对应。

## 6. Happy Path case

全部请求固定 `temperature=0`、seed 和 `max_tokens`。请求和原始 JSON 响应分别保存，
不得只保存终端截图。

| Case | 目的 |
|---|---|
| `HP-01 short` | 短 prompt、短输出，验证基本 P/D 链路 |
| `HP-02 long-prompt` | prompt 跨多个 KV block，验证多 block P2P transfer 后正常出词 |
| `HP-03 long-output` | 较长生成，验证持续 Decode 和 `fused_overlap` 正常 |
| `HP-04 low-concurrency` | 至少 16 条固定问题低并发提交，使 2 个 P DP 和 8 个 D DP 都有机会被调度 |

本轮不把 capacity pressure、HOL、fault injection、preemption 或 cancellation 混入 Happy
Path。

## 7. Oracle 与失败处理

人工验收表按请求记录：

```text
请求 ID | baseline 摘要 | P/D 摘要 | 语义一致 PASS/FAIL | 备注
```

自动或命令行检查只判断客观事实：

- HTTP 请求全部成功并返回非空文本；
- baseline 和 P/D 回答数量一致；
- vLLM 与 proxy 没有 traceback 或 process crash；
- Mooncake 没有 initialize、register、transfer 或非法地址错误；
- 日志能够证明请求实际走过 remote prefill 和 Mooncake transfer。

错误处理采用 fail-fast：

- 服务启动失败时不启动下游组件；
- case 出现服务 crash、transfer error 或请求丢失时停止后续 case并保留现场；
- 人工发现回答语义不一致时，完成当前 case 的证据收集后停止；
- 不自动重试失败请求，以免覆盖首次失败证据。

四个 case 全部满足人工与客观检查后，才记录 `Happy Path smoke passed`。

## 8. 证据与清理

每次执行生成唯一 `RUN_ID`。协调节点和远端节点使用相同 `RUN_ID`，但不假设共享文件
系统。每台节点在 `$RUN_ROOT/$RUN_ID/` 下保存 resolved environment、PID、日志、请求和
响应；最后通过明确的 `scp` 命令汇总。

启动命令将 stdout/stderr 写入角色和 rank 专属日志，并立即保存 PID。清理顺序为：

```text
停止发请求 -> 停止 proxy -> 停止 Prefill -> 停止 Decode
```

停止前核对 `/proc/<pid>/cmdline` 与预期角色。先发送 `SIGTERM` 并等待；只有超时后才对
该精确 PID 使用 `SIGKILL`。禁止 `pkill vllm`、`killall python` 或删除共享目录。

清理完成后检查本次 PID 已退出、本次端口不再监听、NPU 上没有本次 worker。Mooncake
Transfer Engine 随 vLLM worker 退出，不执行 Mooncake Master/Store cleanup。

最终证据至少包含全部服务日志、四组请求与原始响应、人工验收表、实际启动命令、PID
记录和 `summary.md`。

## 9. 后续阶段占位

以下部分保留为独立章节，但本轮不提供命令或 pass/fail 标准：

- 基础性能：TTFT、TPOT、吞吐、资源占用、baseline 和门槛；
- Lifecycle / Boundary：容量边界、partial block、并发与 HOL；
- Lifecycle / Failure：fault injection、transfer failure、exact-TP barrier 与 replay；
- Lifecycle / Control：preemption、cancellation、quiesce 与资源 release。

这些章节统一标记 `待后续设计`。它们不能由 Happy Path 结果推断为已验证。
