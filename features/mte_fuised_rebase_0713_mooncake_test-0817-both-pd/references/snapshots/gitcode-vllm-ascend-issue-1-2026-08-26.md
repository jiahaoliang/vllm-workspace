Source: https://gitcode.com/shichangzhang064/vllm-ascend/issues/1 ; https://api.gitcode.com/api/v5/repos/shichangzhang064/vllm-ascend/issues/1 ; https://api.gitcode.com/api/v5/repos/shichangzhang064/vllm-ascend/issues/1/comments?per_page=100&page=1
Captured At: 2026-08-26T17:54:00+08:00
Notes: Markdown snapshot from GitCode first-party public REST API. Both GET requests succeeded without an Authorization header, login, or stored cookie jar. The issue endpoint reported `comments: 1`; the comments endpoint returned one item. Technical assertions in the issue body and comment are reporter content, not independently verified by this snapshot.

# GitCode Issue #1: [Usage]: decode mooncakeconnectorV1 cannot open async scheduling

Canonical URL: <https://gitcode.com/shichangzhang064/vllm-ascend/issues/1>

## Confirmed metadata

| Field | Value |
| --- | --- |
| Repository | `shichangzhang064/vllm-ascend` (repository ID `7474741`) |
| Issue API ID / number | `4280622` / `1` |
| Title | `[Usage]: decode mooncakeconnectorV1 cannot open async scheduling` |
| State | `open` |
| GitCode workflow state | `待办的` (`serial: 0`) |
| Visibility | `public` |
| Created at | `2026-08-25T23:55:14+08:00` |
| Updated at | `2026-08-26T10:50:03+08:00` |
| Closed / finished at | `null` / empty |
| Author | `shichangzhang064` (<https://gitcode.com/shichangzhang064>) |
| Assignee(s) | None (`assignee: null`, `assignees: []`) |
| Labels | None (`labels: []`) |
| Priority | `0` |
| Comment count | `1` |

## Issue body

#### Before submitting an issue, please make sure the issue hasn't been already addressed by searching through [the existing and past issues](https://github.com/vllm-project/vllm-ascend/issues?q=is%3Aissue+sort%3Acreated-desc+).

### Your current environment

```text
The output of above commands
```

### How would you like to use vllm on ascend

# 【KV Transfer】Blockwise DSA MooncakeConnectorV1 不应禁止 Decode async scheduling

- **类型**：缺陷
- **模块**：`kv_transfer` / MooncakeConnectorV1 / Blockwise DSA
- **分支**：`feature/blockwise-dsa-mooncake-v1-reimplementation`
- **对照分支**：`mte_fuised_rebase_0713_mooncake_test-0817-both-pd`（`MooncakeLayerwiseToDramConnector`）

---

### 环境信息 / Environment

- 分支：`feature/blockwise-dsa-mooncake-v1-reimplementation`
- Decode 开启 `--async-scheduling`
- `kv_connector=MooncakeConnector`，`kv_role=kv_consumer`
- `kv_connector_extra_config.dsa_pd_offload=true`（Indexer D2D + Main KV D2RH）

---

### 问题简述 / Brief Description

Decode 侧开启 async scheduling 拉起服务时，Blockwise DSA 路径在 `MooncakeConnector.__init__` 直接抛错，拒绝与 async scheduling 同时开启。

原 `MooncakeConnectorV1`（非 DSA）和 `MooncakeLayerwiseToDramConnector` 都没有这条限制。这不是 D2RH / block 粒度 PD 传输的固有限制，而是本版把 decode 期 D2H 做成了跨 step 命令机（`FUSED_D2H` + 精确 TP ACK + in-flight 互斥），调度器必须和 worker 锁步，因而和 async scheduling 冲突。

---

### 问题详情&复现步骤 / Details & Reproduction Steps

#### 1. 复现

Decode 按现网习惯开启 `--async-scheduling`，并打开 Blockwise DSA：

```text
--async-scheduling
--kv-transfer-config '{
  "kv_connector": "MooncakeConnector",
  "kv_role": "kv_consumer",
  "kv_connector_extra_config": {
    "dsa_pd_offload": true,
    ...
  }
}'
```

启动即失败。

#### 2. 实际报错

```text
ValueError: Blockwise DSA Decode does not support async_scheduling.
```

对应代码：

```python
# vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py
if (
    self._dsa_pd_offload
    and vllm_config.kv_transfer_config.kv_role == "kv_consumer"
    and vllm_config.scheduler_config.async_scheduling
):
    raise ValueError(
        "Blockwise DSA Decode does not support async_scheduling."
    )
```

引入 commit：`9612b18d9 feat(kv_transfer): add MooncakeV1 Blockwise DSA lifecycle`
UT 也按「必须拒绝」写死：`tests/ut/kv_offload/test_mooncake_connector.py`

仅 Decode + `dsa_pd_offload=true` 会被拒；Prefill、以及未开 `dsa_pd_offload` 的 MooncakeConnectorV1 不受影响。

#### 3. 对照：原路径没有这条限制

| 路径 | 是否禁止 Decode `async_scheduling` |
|---|---|
| 原 MooncakeConnectorV1（HBM block 传输） | 否。PD 接收本身就是 async load |
| `MooncakeLayerwiseToDramConnector`（Indexer D2D + Main D2RH） | 否。kv_transfer 中无 `async_scheduling` 检查 |
| 当前分支未开 `dsa_pd_offload` 的 MooncakeConnector | 否 |
| 当前分支 Decode + `dsa_pd_offload=true` | **是，启动硬拒绝** |

#### 4. 根因

D2RH（Prefill HBM → Decode DRAM）走的仍是标准 PD 接收：

- `get_num_new_matched_tokens(..., async=True)`
- 请求进入 `WAITING_FOR_REMOTE_KVS`
- worker 后台收完，`finished_recving` 后再进 decode

这和原 MooncakeConnectorV1 一样，**与 async scheduling 兼容**。

真正冲突的是本版额外做的 **decode 期 `FUSED_D2H` 生命周期**：

1. `_queue_scheduled_d2h()` 用当前 `num_scheduled_tokens` 算出 D2H 区间，设 `active_action = FUSED_D2H`
2. worker 要求同一 request 同时只能有一条 in-flight 命令，重叠直接抛错
3. 必须等所有 Decode TP 回 `D2H_COMPLETE`，`update_connector_output()` 才清掉 `active_action`，并推进 `confirmed_main_tokens`
4. 若 `active_action` 还在，下一步 **直接跳过 D2H**

Async scheduling 的时序：

```text
同步调度（当前实现能工作）:
  排 step N → worker 跑 N（含 D2H）→ 回 ACK → 清 active_action → 排 step N+1

异步调度（当前实现会坏）:
  排 step N（发出 FUSED_D2H）
  → 立刻排 step N+1（ACK 还没回来，active_action 仍在）
  → 要么跳过 N+1 的 D2H（新 token KV 不落 DRAM）
  → 要么再发一条（worker 报 in-flight overlap）
```

启动时 ban 掉 async scheduling，是为了避免静默丢 D2H 或运行时崩溃，不是 D2RH 做不了 async。

#### 5. 为什么 layerwise-to-DRAM 没有这个问题

`MooncakeToDramDecodeScheduler` / `SFAPDCpuOffloadScheduler` 同样按 step 计算 `offload_token_start / offload_num_tokens`，但：

- D2H 元数据绑在**这一 step** 的 `scheduler_output` 上，随这一 step 发给 worker
- worker 在**同一步 forward** 里做 fused D2H，调度器不必等 ACK 才能发下一步
- 没有 `in_flight` 互斥，也没有「精确 TP 回包后才能发下一条」

Async scheduling 只让 **scheduler 超前**；**同一 worker 仍按 step 顺序执行**。N 的 D2H 跟着 N 的 forward 走完，再执行 N+1。

当前分支其实已经在用同一套 SFA fused D2H：`FUSED_D2H` 最后仍拼成 `SFAReqMeta(offload_token_start/offload_num_tokens)` 交给 `sfa_worker.start_load_kv`。缺的不是传输能力，是外面多包了一层「命令 + 等齐 TP ACK」。

Layerwise 和 blockwise 的差别在 PD 接收（按层重叠 vs 整段 block 一次拉完），不在 decode 期 D2H。D2RH 只决定 prompt Main KV 如何落到 Decode DRAM，不改变「本 step 新写 KV 再 D2H」的协议。

---

### 期望结果 / Expected Results

1. Decode 开启 `--async-scheduling` 时，Blockwise DSA MooncakeConnectorV1 可以正常拉起，不再因这条检查失败。
2. Decode 期 D2H 对齐 `MooncakeLayerwiseToDramConnector`：
   - `build_connector_meta(scheduler_output)` 只为本 step 真正要算的 token 填写 D2H 区间（对齐 layerwise 的 `_num_finalized_scheduled_tokens`，扣掉 spec / placeholder）
   - 该 meta 跟随这一 step 发给 worker，worker 按 step 顺序在 forward 内完成 D2H
   - 不再走 `DsaAction.FUSED_D2H` / `D2H_COMPLETE` / `in_flight` 互斥
3. `RECEIVE_REMOTE`（真正的 D2RH PD 接收）继续走 `WAITING_FOR_REMOTE_KVS` 异步 load，与原 MooncakeConnectorV1 一致。请求还在等 KV 时不会进 decode，不会和本 step D2H 重叠。
4. 删除 Decode 启动时对 `async_scheduling` 的硬拒绝，以及对应「必须拒绝」的 UT；补上 step-local D2H + async scheduling 的回归。

实现注意：CPU block 表、`get_num_cpu_blocks` 从 request 的 DRAM 预留读取，不要再依赖 in-flight 的 `FUSED_D2H` 命令。preempt / replay / cancel 可以保留，但不要绑在每 step D2H 的跨 step ACK 上。

---

### 实际结果 / Actual Results

Decode + `dsa_pd_offload=true` + `--async-scheduling` 在 connector 初始化阶段直接 `ValueError: Blockwise DSA Decode does not support async_scheduling.`，服务无法拉起。

---

### 建议改法 / Proposed Fix

把 `FUSED_D2H` 改回 **step-local meta**，而不是把 async scheduling 关掉或把这条 ban 当成物理限制：

- D2H：随 `scheduler_output` 走，worker 顺序执行（对齐 layerwise-to-DRAM）
- D2RH / `RECEIVE_REMOTE`：维持现有异步 PD 接收
- 启动检查：删除 Decode 对 `async_scheduling` 的拒绝



Thanks for contributing 🎉!

## Comments

### Comment 1

| Field | Value |
| --- | --- |
| Comment ID | `186579976` |
| Author | `shichangzhang064` (<https://gitcode.com/shichangzhang064>) |
| Created / updated at | `2026-08-26T10:50:03+08:00` / `2026-08-26T10:50:03+08:00` |

# vLLM Ascend PD 分离推理服务启动规格（Block Connector / Mooncake）

> 本文档基于 `vllm-serve-block-connector` 启动脚本整理，供 Issue 说明服务拓扑与参数规格。
> 敏感信息（Pod IP、工作目录、账号路径等）已做占位符脱敏。

---

## 1. 部署拓扑

| 角色 | 节点（示例名） | 卡数 | 并行规格 | HTTP 端口 |
|------|----------------|------|----------|-----------|
| Prefill | `<PREFILL_POD>` | 16 | DP=2, TP=8, `dp-size-local=2` | `6700`, `6701` |
| Decode | `<DECODE_POD>` | 16 | DP=2, TP=8, `dp-size-local=2` | `6721`, `6722` |
| Proxy | 与 Prefill 同机 | - | Load-balance proxy（layerwise） | `8099` |

- 模型：`glm-5.1-w8a8`（served name: `glm-51`）
- KV 传输：`MooncakeConnector`（`use_ascend_direct` + `dsa_pd_offload`）
- 网络约束：**DP / HCCL / ZMQ 必须绑定 Pod IP**，不能绑宿主机 `NODE_IP`（否则会出现 `Cannot assign requested address`）

```
Client
  │
  ▼
Proxy (:8099)  ──on──  <PREFILL_POD>
  │
  ├── Prefill engines:  <PREFILL_POD_IP>:6700 / :6701
  └── Decode  engines:  <DECODE_POD_IP>:6721 / :6722
```

---

## 2. 启动方式概览

| 步骤 | 脚本 | 运行位置 |
|------|------|----------|
| 1. Prefill | `start_prefill.sh` | `<PREFILL_POD>` |
| 2. Decode | `start_decode.sh` | `<DECODE_POD>` |
| 3. Proxy | `start_proxy.sh` | `<PREFILL_POD>`（与 Prefill 同机） |
| 停止 | `stop_vllm.sh [prefill\|decode\|proxy\|all]` | 对应节点 |

Prefill / Decode 通过 `launch_online_dp.py` 按本地 DP 拉起多个 `vllm serve` 进程；实际 `vllm serve` 参数分别在：

- Prefill：`prefill_run_dp_template.sh`
- Decode：`decode_run_dp_template.sh`

---

## 3. Launcher 参数（`launch_online_dp.py`）

### 3.1 Prefill

```bash
python launch_online_dp.py \
  --role p \
  --dp-size 2 \
  --tp-size 8 \
  --dp-size-local 2 \
  --dp-rank-start 0 \
  --dp-address <PREFILL_POD_IP> \
  --dp-rpc-port 10521 \
  --vllm-start-port 6700
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `--role` | `p` | 使用 `prefill_run_dp_template.sh` |
| `--dp-size` | `2` | 全局 DP size |
| `--tp-size` | `8` | 每 DP rank 的 TP |
| `--dp-size-local` | `2` | 本机启动 2 个 engine（卡 `0-7` / `8-15`） |
| `--dp-rank-start` | `0` | 本机 rank 从 0 开始 |
| `--dp-address` | `<PREFILL_POD_IP>` | DP master 地址（Pod IP） |
| `--dp-rpc-port` | `10521` | DP RPC 端口 |
| `--vllm-start-port` | `6700` | engine HTTP 起始端口 → `6700/6701` |

### 3.2 Decode

```bash
python launch_online_dp.py \
  --role d \
  --dp-size 2 \
  --tp-size 8 \
  --dp-size-local 2 \
  --dp-rank-start 0 \
  --dp-address <DECODE_POD_IP> \
  --dp-rpc-port 10523 \
  --vllm-start-port 6721
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `--role` | `d` | 使用 `decode_run_dp_template.sh` |
| `--dp-rpc-port` | `10523` | 与 Prefill 区分 |
| `--vllm-start-port` | `6721` | engine HTTP 起始端口 → `6721/6722` |
| 其余并行参数 | 同 Prefill | DP=2 / TP=8 / local=2 |

---

## 4. Prefill `vllm serve` 关键参数

| 类别 | 参数 | 值 |
|------|------|-----|
| 模型 | `--served-model-name` | `glm-51` |
| 长度 / batch | `--max-model-len` | `16384` |
| | `--max-num-batched-tokens` | `1024` |
| | `--max-num-seqs` | `64` |
| 并行 | `--data-parallel-size` | `2` |
| | `--tensor-parallel-size` | `8` |
| | `--enable-expert-parallel` | 开启 |
| 量化 / 显存 | `--quantization` | `ascend` |
| | `--gpu-memory-utilization` | `0.94` |
| 其它 | `--enable-chunked-prefill` | 开启 |
| | `--enforce-eager` | 开启 |
| | `--enable-auto-tool-choice` | 开启 |
| | `--tool-call-parser` | `glm47` |
| | `--reasoning-parser` | `glm45` |
| additional-config | | `enable_dsa_cp=false`, `use_offload=false` |

### KV Transfer（Prefill = producer）

```json
{
  "kv_connector": "MooncakeConnector",
  "kv_buffer_device": "npu",
  "kv_role": "kv_producer",
  "kv_parallel_size": 1,
  "kv_port": 20020,
  "kv_rank": 0,
  "engine_id": "0",
  "kv_connector_module_path": "vllm_ascend.distributed.kv_transfer.kv_p2p.mooncake_connector",
  "kv_connector_extra_config": {
    "use_ascend_direct": true,
    "dsa_pd_offload": true,
    "prefill": {"dp_size": 2, "tp_size": 8},
    "decode": {"dp_size": 2, "tp_size": 8}
  }
}
```

---

## 5. Decode `vllm serve` 关键参数

| 类别 | 参数 | 值 |
|------|------|-----|
| 模型 | `--served-model-name` | `glm-51` |
| 长度 / batch | `--max-model-len` | `16384` |
| | `--max-num-batched-tokens` | `1024` |
| | `--max-num-seqs` | `4` |
| 并行 | `--data-parallel-size` | `2` |
| | `--tensor-parallel-size` | `8` |
| | `--enable-expert-parallel` | 开启 |
| 量化 / 显存 | `--quantization` | `ascend` |
| | `--gpu-memory-utilization` | `0.93` |
| 其它 | `--enable-chunked-prefill` | 开启 |
| | `--enforce-eager` | 开启 |
| | tool / reasoning parser | 同 Prefill（`glm47` / `glm45`） |
| compilation | `--compilation-config` | `cudagraph_mode=FULL_DECODE_ONLY`，capture sizes 含 `1..256` |

> 注意：Blockwise DSA Decode **不支持** `async_scheduling`。

### additional-config（Decode 侧 offload）

```json
{
  "enable_flashcomm1": false,
  "enable_dsa_cp": false,
  "use_offload": true,
  "kv_offload_mode": "fused_overlap",
  "lru_resident_cache_config": {
    "enabled": true,
    "buffer_size": 2048,
    "topk": 2048
  }
}
```

### KV Transfer（Decode = consumer）

```json
{
  "kv_connector": "MooncakeConnector",
  "kv_buffer_device": "npu",
  "kv_role": "kv_consumer",
  "kv_parallel_size": 1,
  "kv_port": 10010,
  "kv_rank": 1,
  "engine_id": "1",
  "kv_connector_module_path": "vllm_ascend.distributed.kv_transfer.kv_p2p.mooncake_connector",
  "kv_connector_extra_config": {
    "use_ascend_direct": true,
    "dsa_pd_offload": true,
    "sfa_kv_offload_backend": "mooncake",
    "prefill": {"dp_size": 2, "tp_size": 8},
    "decode": {"dp_size": 2, "tp_size": 8}
  }
}
```

---

## 6. Proxy 参数

```bash
python <proxy_script> \
  --port 8099 \
  --host 0.0.0.0 \
  --prefiller-hosts <PREFILL_POD_IP> <PREFILL_POD_IP> \
  --prefiller-ports 6700 6701 \
  --decoder-hosts  <DECODE_POD_IP> <DECODE_POD_IP> \
  --decoder-ports 6721 6722
```

| 项 | 值 |
|------|-----|
| 脚本优先 | `load_balance_proxy_layerwise_server_example.py`（不存在则回退非 layerwise 版本） |
| Listen | `0.0.0.0:8099` |
| Prefill backends | `<PREFILL_POD_IP>:6700`, `<PREFILL_POD_IP>:6701` |
| Decode backends | `<DECODE_POD_IP>:6721`, `<DECODE_POD_IP>:6722` |

---

## 7. 关键环境变量

| 变量 | 典型值 | 说明 |
|------|--------|------|
| `LOCAL_IP` / `VLLM_HOST_IP` / `HCCL_IF_IP` | `<POD_IP>` | 必须为 Pod IP |
| `GLOO/TP/HCCL_SOCKET_IFNAME` | `eth0` | 网卡名 |
| `HCCL_OP_EXPANSION_MODE` | `AIV` | |
| `HCCL_BUFFSIZE` | `256` | |
| `HCCL_INTRA_ROCE_ENABLE` | `1` | |
| `HCCL_INTRA_PCIE_ENABLE` | `0` | |
| `ASCEND_BUFFER_POOL` | `8:16` | ADXL buffer（layerwise D2D / D2RH） |
| `ASCEND_CONNECT_TIMEOUT` / `ASCEND_TRANSFER_TIMEOUT` | `30000` | |
| `VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT` | `480` | Prefill KV 自动释放超时（秒） |
| `VLLM_ASCEND_TRANSFER_SYNC_TIMEOUT_S` | `60` | `batch_transfer_sync_write` 软超时 |
| `VLLM_ASCEND_ENABLE_FUSED_MC2` | `1` | |
| `VLLM_ASCEND_ENABLE_FLASHCOMM1` | `0` | |
| `VLLM_ASCEND_SFA_DEBUG` | `1` | 调试日志 |
| `PYTORCH_NPU_ALLOC_CONF` | `expandable_segments:True` | |

---

## 8. Prefill vs Decode 差异速查

| 项 | Prefill | Decode |
|----|---------|--------|
| `max-num-seqs` | 64 | 4 |
| `gpu-memory-utilization` | 0.94 | 0.93 |
| `use_offload` | false | true（`fused_overlap` + LRU resident cache） |
| CUDA Graph | 无（eager） | `FULL_DECODE_ONLY` |
| `kv_role` | `kv_producer` | `kv_consumer` |
| `kv_port` | `20020` | `10010` |
| DP RPC port | `10521` | `10523` |
| HTTP ports | `6700/6701` | `6721/6722` |
