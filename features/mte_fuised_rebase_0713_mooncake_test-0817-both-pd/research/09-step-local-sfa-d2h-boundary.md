# Step-local SFA D2H data-plane 与证据边界

Captured At: 2026-08-26 (Asia/Shanghai)

## Question

现有 layerwise / `SFAPDCpuOffloadScheduler` 如何计算 finalized tokens、把
`SFAReqMeta` 绑定到当前 `SchedulerOutput`、在 attention forward 中执行 fused
D2H 并传播 TP failure？哪些 data-plane primitive 可以由 Blockwise DSA 直接
复用，哪些 completion、speculative-token、graph-capture 或 lifecycle 事实不能
从该路径推断？

## Checkout identities

本结论只对应以下 live checkout：

| Checkout | Branch | Commit | Dirty state |
| --- | --- | --- | --- |
| control repo | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `772142bb7104ca3eb05c9e043c0f8025bd300d23` | 有预存文档与 untracked WIP；本研究未修改它们 |
| `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | clean |
| `repos/vllm-ascend` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `60eb76e46225e9aaec1493fb247313f8642486ad` | clean |
| `repos/vllm-ascend-blockwise-dsa-reimplementation` | `feature/blockwise-dsa-mooncake-v1-reimplementation` | `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` | clean |

本次只读源码并写本文；没有运行 static、CPU/mock 或 NPU 测试。因此本文是
source-backed design evidence，不是 runtime validation。

## Answer

**Confirmed**：当前 layerwise / puncture path 已经具备完整的 step-local D2H
data plane：scheduler 从当前 `SchedulerOutput` 计算 token range，把 Host Main
block table 与 range 放进 `SFAReqMeta`，vLLM core 将 metadata 与同一个
`SchedulerOutput` 一起送到 worker，SFA attention 在当前 forward 的每层写出
Main KV。eager / PIECEWISE 非 capture 路径还会在层内同步 D2H，并通过 TP
collective 把 owner rank 的异常扩散为该 forward 的异常。

**Not proven**：这条 path 没有提供 scheduler-side D2H completion ACK、durable
Main-valid ledger、speculative-token acceptance reconciliation、preemption/cancel
ownership barrier，也没有证明 FULL graph capture 与 eager 路径具有相同的
completion/failure 边界。因此可以复用 data-plane primitive，但不能把
layerwise 的乐观 tracker 更新直接当成 Blockwise DSA 的 lifecycle contract。

## Confirmed data-plane facts

### 1. `finalized` 是当前 step 的 non-draft scheduled count

`SFAPDCpuOffloadScheduler` 定义：

```text
finalized = max(num_scheduled_tokens - len(scheduled_spec_decode_tokens), 0)
```

它只从当前 step 的 scheduled count 中扣除当前 draft token 数量；函数本身不读
model output，也不读 draft acceptance 结果。

Source:
[finalized-token formula](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L55-L58)

### 2. scheduler 直接为当前 `SchedulerOutput` 构造 `SFAReqMeta`

`build_connector_meta()` 先从 `scheduled_cached_reqs` 建立 request 到
`num_computed_tokens`、新 Main HBM blocks 的映射，再为每个相关 request 构造
`ReqMeta`。fused range 使用：

```text
offload_token_start = num_computed
offload_num_tokens = finalized
num_tokens_after_step = num_computed + finalized
```

同一个 `ReqMeta` 还携带 Main Host block IDs、Indexer block IDs 与本 step 的
range。新 remote-prefill request 与 cached request 都走该 metadata family；
cached request 缺少 `scheduled_cached_reqs` snapshot 时会回退到 tracker 中的
`num_cpu_saved_tokens`。

Source:
[metadata construction and fields](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L403-L464),
[new-request same-step range](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L466-L501),
[cached-request fused range](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L503-L556),
[`ReqMeta` schema](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py#L39-L84)

`MooncakeToDramDecodeScheduler` 没有覆盖 `build_connector_meta()`，因此复用上述
parent implementation；它只覆盖 Host tracker 分配与 remote advertise。PD
request 以 prompt length 初始化 `num_cpu_saved_tokens`，Decode-only request 从
0 开始。

Source:
[`MooncakeToDramDecodeScheduler`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_to_dram_connector.py#L563-L608),
[Host tracker initialization](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_to_dram_connector.py#L656-L726)

### 3. metadata 与执行它的 worker step 使用现有 core binding

vLLM scheduler 先构造 `SchedulerOutput`，随后调用 connector
`build_connector_meta()`，并把结果写入该对象的 `kv_connector_metadata`。
worker 进入 forward 前 bind 这份 metadata，然后调用 `start_load_kv()`；forward
结束后才调用 `wait_for_save()`、收集 connector output 并 clear metadata。

Source:
[scheduler attaches connector metadata](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L932-L967),
[worker bind/start/wait/output order](../../../repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py#L78-L112)

这证明无需新增 vLLM core channel 就可以把 step-local D2H descriptor 送到执行
该 batch 的 worker。它不证明 scheduler 何时可以把该 range 标为 durable
Main-valid。

### 4. worker 每次 `start_load_kv()` 重建本 step 的 D2H view

SFA worker 在 `start_load_kv()` 中清空上一 step 的 fused request map，从本次
metadata 选择 `offload_num_tokens > 0` 的 request，经 TP broadcast 形成
`fused_step_has_offload`，再按当前 `req_ids` 顺序重建 CPU block table、
`offload_token_start` 和 `offload_num_tokens` buffer。

Source:
[per-step reset and request selection](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L958-L995),
[block-table binding](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1005-L1070)

因此 step-local 方案必须保证每个实际 worker step 都调用 SFA
`start_load_kv()`，包括“本 step 没有 D2H request”的情况；否则 worker 不能从
这段代码得知应清除上一 step 的 fused state。

### 5. D2H 使用当前 attention step 的 token/slot view

SFA attention 在 Main KV 已写入当前 `kv_cache` 后调用 connector 的
`save_current_kv_tokens()`。调用参数来自当前 attention metadata，包括
`slot_mapping`、`token_to_req`、`cum_query_lens`、`num_actual_tokens` 与
`num_reqs`。

Source:
[attention-side argument binding](../../../repos/vllm-ascend/vllm_ascend/attention/sfa_v1.py#L1282-L1315),
[MLAPO call site](../../../repos/vllm-ascend/vllm_ascend/attention/sfa_v1.py#L2379-L2385),
[native call site](../../../repos/vllm-ascend/vllm_ascend/attention/sfa_v1.py#L2453-L2460)

worker 的 token-pair iterator 只遍历当前 `num_actual_tokens`。对某个 request，
只有当前 batch 内 `local_offset < offload_num_tokens` 的 token 会被复制；Host
位置由 `offload_token_start + local_offset` 计算。它不会扫描历史 HBM range，
也不会仅因 `offload_num_tokens` 大于当前 request 的 actual token 数就自动回填
历史 token。

Source:
[current-step token-pair selection](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1598-L1640)

### 6. eager / PIECEWISE failure 是 forward failure，不是 scheduler ACK

非 capture 路径在 local Host owner 上执行 D2H。owner 异常被写入
`d2h_status_npu`；Mooncake Host allocation 使用 TP `all_reduce`，TP0-shared
Host 使用 `broadcast`。任一失败使所有参与 rank 抛出 `RuntimeError`；成功后
进入 TP barrier。

Source:
[TP failure convergence](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1565-L1596)

非 capture sparse-copy 路径还会记录并同步 `d2h_save_event`，因此该函数返回
前 Host write 已落地；`index_copy_` bypass 也在同一个同步函数调用内返回。

Source:
[eager index-copy path](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1706-L1739),
[eager sparse-copy event synchronization](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1782-L1834)

fused mode 的 `save_kv_layer()` 直接返回，不创建 legacy layer-save background
task；相应 `wait_for_save()` 在没有 pending layer IDs 时立即返回。也就是说，
eager fused D2H 的实质 fence 位于 `save_current_kv_tokens()` 内，而不是
`wait_for_save()`。

Source:
[fused `save_kv_layer` no-op](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1212-L1217),
[`wait_for_save` pending-task behavior](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1836-L1854)

### 7. current Blockwise DSA 已经复用相同 SFA data plane

replacement worker 收到 `FUSED_D2H` 后，把 lifecycle range 与 Main Host block
binding 转换为 `SFAReqMeta`，再调用相同 `sfa_worker.start_load_kv()`。attention
hook 和底层 D2H primitive 因此不是需要重新设计的部分。

Source:
[Blockwise-to-SFA adapter](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4425-L4455)

current Blockwise completion 与 layerwise 不同：worker 在 connector
`wait_for_save()` 返回后生成 local `D2H_COMPLETE`；scheduler 聚合 worker
metadata，只有 terminal rank set 精确等于 Decode TP rank set，才推进
`confirmed_main_tokens` 并清除 active action。

Source:
[local `D2H_COMPLETE` emission](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2850-L2877),
[exact-TP scheduler gate](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1927-L1989)

## Directly reusable primitives

以下结论只覆盖 data plane：

1. `SFAReqMeta` 的 Main Host block table、Indexer IDs、`offload_token_start`、
   `offload_num_tokens` 与 `num_tokens_after_step` 字段。
2. `SchedulerOutput.kv_connector_metadata` 到 paired worker forward 的现有传输与
   bind/start hook。
3. SFA worker 的 per-step fused-state reset、request-order CPU block table 和
   descriptor buffer 构造。
4. attention 内当前 step 的 `slot_mapping` / `token_to_req` 驱动方式。
5. eager / PIECEWISE 的 `index_copy_` 或 `sparse_copy` D2H primitive、event
   synchronize、TP error convergence。
6. Blockwise worker 现有的 DSA-to-`SFAReqMeta` field mapping；移除
   `FUSED_D2H` command 不要求改变这些字段的物理含义。

“可复用”不等于现有 code 可以原样搬动。尤其是每个 step 都必须 reset SFA
state，range 必须来自新的 Main-valid ledger，而不能继续由单一 active command
gate 驱动。

## Boundaries that cannot be inferred

### Lifecycle completion boundary

layerwise scheduler 在构造 metadata 时就把 `tracker.num_cpu_saved_tokens` 更新为
`num_tokens_after_step`。它没有等 worker output，也没有 D2H worker metadata。
因此该 tracker 表达的是已计划位置，不是 Blockwise replay 可以依赖的 durable
Main-valid 证明。

Source:
[new-request optimistic update](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L478-L497),
[cached-request optimistic update](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L522-L555)

不能据此推断：

- successful metadata build 等于 D2H complete；
- 一个 TP rank 返回等于 exact-TP completion；
- scheduler 可以在 worker output 前提升 `confirmed_main_tokens`；
- late output 属于哪个 execution epoch、preemption 或 terminal barrier。

### Speculative-token boundary

`finalized = scheduled - current draft count` 只说明当前 metadata 不选择当前
draft token。vLLM scheduler 会在 schedule 后立即把全部 scheduled tokens（含
draft）乐观计入 `request.num_computed_tokens`，等 model output 返回后才减去
rejected draft 数。

Source:
[optimistic computed-token advance](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1000-L1013),
[post-output speculative correction](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1414-L1431)

在 async queue 中，后继 `SchedulerOutput.scheduled_cached_reqs.num_computed_tokens`
因此可能包含前一未回收 step 的 optimistic draft positions。结合当前 SFA
只遍历本 step actual slots 的事实，现有源码不能证明
`[confirmed_main_tokens, computed + finalized)` 是已连续写入 Host 的 range。
特别是已接受的历史 draft token 是否、何时被回填，不能从 layerwise path
推断。

### Async completion/accounting boundary

step-local metadata binding 证明“descriptor 跟随哪个 worker step”，不证明
“scheduler 如何在多个未回收 batch 下确认该 descriptor”。connector
`update_connector_output()` 只收到 `KVConnectorOutput`，API 不直接传入 paired
`SchedulerOutput`。

Source:
[`update_connector_output` API](../../../repos/vllm/vllm/distributed/kv_transfer/kv_connector/v1/base.py#L532-L540)

因此本研究不决定 completion ledger 使用 FIFO step record、显式 step identity、
worker metadata 还是其他 oracle；也不证明 abort/preemption 发生时，已经执行但
尚未被 scheduler 回收的 D2H progress 应计入哪个 epoch。

### Graph-capture boundary

capture path 与 eager path 明确分叉：它通过 C++ host callback 生成 descriptors，
使用 non-blocking buffer copy，且不执行 eager path 的 `d2h_save_event.synchronize()`。
outer capture branch 也在 eager 的 try/status `all_reduce`/barrier 之前返回；
Mooncake Host allocation 在这条分支没有对应的 TP status `all_reduce`。

Source:
[capture branch and early return](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1538-L1553),
[capture descriptor callback](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1741-L1781),
[capture versus eager fence](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1814-L1834)

不能仅根据 eager evidence 声称 FULL capture 在 connector `wait_for_save()` 返回时
已经完成相同的 physical fence、TP failure convergence 或 Host visibility。
该边界需要独立 runtime/implementation contract；本次没有运行 graph-capture
实验。

### Preemption, cancellation and terminal ownership boundary

layerwise `request_finished_all_groups()` 直接移除 tracker 并归还 CPU blocks，
源码注释假设 request finish 后不再有 inference 或 KV transfer。它没有
Blockwise 的 lifetime reservation、execution epoch、late completion 或
Quiesced ownership contract。

Source:
[layerwise immediate free](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py#L595-L609)

因此不能从 layerwise path 推断：

- preemption 时哪些已执行但未回收 step 可以扩展 preserved Main；
- cancellation/normal finish 何时可以释放 Main reservation；
- late D2H failure 或 success 如何与 terminal barrier 竞争；
- `RECEIVE_REMOTE`、`PREPARE_REPLAY`、`QUIESCE` 的 exact-TP/ownership contract
  可以随 `FUSED_D2H` 一起删除。

### Failure contract boundary

当前 eager D2H error 会作为 worker model-step exception 向上传播；它不是
`TRANSFER_FAILED`，也不会产生 successful D2H completion metadata。replacement
unit test 只确认 fake SFA save/wait 抛错后没有 `D2H_COMPLETE`；它不是 NPU
runtime evidence。

Source:
[replacement failure unit contract](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/tests/ut/kv_offload/test_mooncake_connector.py#L2600-L2609)

是否继续 fail-fast、是否为 async terminal cleanup 增加独立 failure fact，属于
lifecycle decision，不是 SFA data-plane 已经回答的问题。

## Decision input

后续设计可以把以下内容作为已确认前提：

- sync/async 可以共用 step-local `SFAReqMeta` data plane；
- `RECEIVE_REMOTE` 与 D2H 的 completion 性质不同，前者仍需 remote-transfer
  lifecycle；
- Main validity 必须由独立 progress ledger 根据已完成 worker step 推进，不能
  复用 layerwise 的 metadata-build-time cursor；
- speculative-token 连续 prefix、preemption late progress、terminal ownership
  与 FULL capture completion 必须在 implementation 前分别作出显式决定或声明
  unsupported。

本文不选择具体 ledger schema，也不批准 production source 修改。
