# 定义 step-local D2H metadata 与 worker binding

Type: grilling
Status: resolved
Blocked by: 09, 10, 11, 13
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

Blockwise DSA scheduler 怎样为每个 `SchedulerOutput` 生成独立的 D2H range 与 Main bound block table，使 worker 不再从 active `FUSED_D2H` command 推导 `get_num_cpu_blocks()` 或 SFA binding？Step-local value object 应携带哪些 identity、range、reservation 与 bound-prefix fields，worker state 应保留什么，speculative decoding fail-closed 与 default V1 isolation 应在哪一层验证？

## Answer

Decision assets: [ADR 0027 - 使用 step-local D2H plan 与 worker Main binding](../docs/adr/0027-use-step-local-d2h-plans-and-worker-main-bindings.md)、[ADR 0028 - 允许 speculative 配置启动但暂不承诺 Blockwise DSA correctness](../docs/adr/0028-allow-unvalidated-speculative-blockwise-dsa-startup.md)。

### Metadata shape 与 exact fields

`DsaConnectorMetadata` 增加独立的 `d2h_plans` tuple，与只承载 `RECEIVE_REMOTE`、`PREPARE_REPLAY` 和 `QUIESCE` 的 lifecycle `requests` 并列。D2H plan 不属于 `DsaStepRequest`，也不复用 lifecycle `command_seq` 或普通 `SFAKVOffloadConnectorMetadata`。同一 request 在一个 `SchedulerOutput` 中最多有一个 plan，且不能同时携带 lifecycle command；同一 batch 可以分别为不同 request 携带两类对象。

每个非空 plan 使用以下 immutable、process-independent schema：

```text
DsaD2HStepPlan
  request_id
  execution_epoch
  d2h_step_seq
  main_reservation_id
  main_reservation_block_count
  main_bound_host_block_ids
  token_start
  token_end
```

Plan 不携带 lifecycle `command_seq`、Indexer IDs、remote source、global scheduler step、`num_computed_tokens` 或冗余的 `num_tokens_after_step`。`D2HStepProgress` 回显 request、epoch、D2H step sequence、reservation identity 与 token range，再增加 local `tp_rank`；progress 不回传 Main block table。

### Scheduler issuance

对本版明确验收的 non-speculative path，scheduler 从当前 `SchedulerOutput` 的 pre-step `num_computed_tokens` 与 `num_scheduled_tokens` 计算 `model_step_end`，并以 current-epoch `issued Main watermark` 作为下一段 D2H 起点：

- `model_step_end <= issued Main watermark` 时不生成 plan；这覆盖 full-sequence replay 尚未追上 preserved prefix `P` 的步骤；
- `model_step_end > issued Main watermark` 时生成 `[issued Main watermark, model_step_end)`；跨过 `P` 的第一个 replay step 只发布超过 `P` 的 suffix；
- pre-step boundary 已大于 issued watermark 表示出现无法解释的 gap，必须 fail fast；
- Main bound table 精确取 lifetime reservation 的前 `ceil(model_step_end / main_block_size)` 个 block，同一 epoch 内只能保持或追加，不能超过 reservation capacity。

Metadata 构造成功后，scheduler立即写入 immutable issued-step ledger并推进issued watermark，但不推进confirmed watermark。每个request每个`SchedulerOutput`最多发布一个nonempty plan；没有range就不分配`d2h_step_seq`。

### Worker binding 与 current-step view

Worker 为每个 live request 持久保存 Main reservation identity/capacity、active execution epoch、latest Main bound prefix、next D2H sequence、last accepted plan、用于验证连续性的 `expected_d2h_token_start`，以及既有 Indexer/lifecycle/Quiesce state。该 cursor 只验证 scheduler 下发顺序，不表示 confirmed Main validity；完整 issued/confirmed ledger 与 reservation release authority仍只属于scheduler。

Lifecycle command可以建立binding；`PREPARE_REPLAY` barrier完成后可以切换epoch，并把可访问Main prefix与expected D2H boundary重置到`P`。同一epoch的D2H plan只能扩展现有binding。每个worker step另外建立ephemeral current-step view：

- 每次`start_load_kv()`先清空上一step的SFA view；
- 根据实际batch `req_ids`，从persistent binding为所有Blockwise DSA request重建Main CPU block table；
- 有plan的request附加nonzero D2H range；无plan的request仍获得bound table，但range为零；
- `get_num_cpu_blocks()`读取该step对应的latest binding，不再查询active lifecycle command；
- 即使本step没有任何D2H plan，也调用SFA `start_load_kv()`清除旧fused state。

### Worker validation 与 progress

D2H plan不能创建request binding，必须命中已有live reservation和当前实际model batch。每个epoch的首个非空plan使用`d2h_step_seq=0`；后续plan必须同时满足sequence连续、`token_start == expected_d2h_token_start`、reservation identity/capacity稳定、bound table是同epoch有序prefix extension且覆盖`token_end`。相同identity与完整内容的duplicate幂等；冲突内容、sequence/range gap、非法block table或未经过lifecycle rebind的future epoch必须fail fast。

对满足FIFO前提的worker，preemption cut后已排队的old-epoch plan仍在`PREPARE_REPLAY` barrier前正常执行并返回progress，由scheduler按stale规则忽略。Barrier完成后才到达的old-epoch plan不得触碰SFA或destination，也不产生progress，只做bounded warning后忽略。

Worker只在对应step的SFA `wait_for_save()`成功返回后，为每个accepted plan产生一条rank-aware `D2HStepProgress`。Worker metadata分别携带lifecycle results与D2H progress；same-step aggregation对相同完整identity幂等，对冲突内容fail fast。没有plan、被忽略的stale plan或尚未完成的D2H不产生progress。SFA save/wait或TP failure继续抛出model-step exception，不伪造progress、`TRANSFER_FAILED`或`finished_recving`。Current-step pending plan在completion metadata形成后才清除；已完成历史不阻止reservation retirement，未完成plan仍属于outstanding work。

### Speculative 与 default isolation boundary

按本票确认的scope变化，`dsa_pd_offload=true`与speculative config的组合不在startup或metadata boundary拒绝，也不增加validation或completion-gate test。该组合可以启动，但本版不定义D2H range reconciliation，不承诺Main validity、preemption replay或cache correctness，也不能标记为supported或validated；后续实现再决定其配合方式。这一选择取代map先前的“首版fail closed”约束。

`dsa_pd_offload=false`继续使用普通`MooncakeConnectorMetadata`、`ReqMeta`和default V1 worker state，不增加DSA optional fields。Mode/type validation只维持DSA metadata与default V1 metadata互不混用，不对speculative config做gate。

### Current replacement delta

Replacement `7401ae79c`仍由active `FUSED_D2H` lifecycle command携带range和Main bound table，`get_num_cpu_blocks()`读取`_dsa_active_commands`，worker通过`_dsa_pending_fused`在`wait_for_save()`后生成`D2H_COMPLETE`。目标实现需要删除这条single-active-command gate，把SFA adapter改为上述step-local plan、persistent Main binding与rank-aware progress；本ticket未修改production source或运行source tests。
