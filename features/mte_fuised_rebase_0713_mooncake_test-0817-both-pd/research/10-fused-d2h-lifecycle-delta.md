# 移除 FUSED_D2H command/result 的 lifecycle delta

Research ticket: [盘点移除 FUSED_D2H command/result 的 lifecycle delta](../issues/10-research-fused-d2h-lifecycle-delta.md)

## 研究问题

若 sync/async 共用 step-local D2H，并从 typed lifecycle 删除 `FUSED_D2H` / `D2H_COMPLETE`，current production symbols、worker request state、Main block binding、preemption/replay/cancellation ownership、tests、`CONTEXT.md`、spec、ADRs 与 approved amendments 分别需要改变什么？哪些 exact-TP contracts 必须保留，哪些 correctness gaps 必须在 implementation 前作出新决策？

## 证据范围

- Replacement source：`feature/blockwise-dsa-mooncake-v1-reimplementation`，commit `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`，审计时 source worktree clean。
- 配套 vLLM core：`feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd`，commit `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`，审计时 worktree clean。
- Contract source：本 feature 的 `CONTEXT.md`、spec、design、accepted ADRs 和 approved amendments。
- GitCode Issue #1 的 body 是问题输入，不作为实现事实；本结论只把 production source、core source 和 accepted feature contract 当作 primary evidence。
- 本研究没有运行测试，也不提供 NPU、graph capture、真实 Mooncake transfer 或 cache-content runtime evidence。

## 结论

把 decode 期 D2H 改成随 `SchedulerOutput` 下发的 step-local metadata，可以删除当前跨 step 的 `FUSED_D2H -> exact-TP D2H_COMPLETE -> 下一 step` scheduling gate。当前 worker 最终仍把 `FUSED_D2H` 转成 `SFAReqMeta(offload_token_start, offload_num_tokens)`，真正 copy 在同一步 model execution 的 attention hook 中发生；command/result 是外层 lifecycle 包装，不是 D2H data plane 本身。[worker adapter](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4425-L4455) [SFA step metadata consumption](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L960-L1070)

但删除 enum 和 ACK 不是完整修复。实现前还必须决定：completed worker step 如何与 scheduler-issued D2H plan 关联并推进 `confirmed_main_tokens`；normal finish/abort 如何等待已经 issued 的 async batches Quiesced 后才释放 reservation；preemption 如何隔离 old-epoch late progress；speculative decoding 如何定义可写和可确认 token range；worker 如何在没有 active FUSED command 时取得最新 Main bound block table。没有这些决定，单独删除 startup rejection 会把显式 fail-closed 变成潜在的 silent Main validity 或 address-reuse corruption。

## 当前同步 gate 为什么与 async scheduling 冲突

当前 `_DsaSchedulerRequest` 同时保存 lifecycle command 状态和 Main validity：`active_action`、`command_emitted`、`command_seq`、`confirmed_main_tokens`、`d2h_token_start`、`d2h_token_count`、`terminal_results`。[scheduler tracker](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1693-L1712)

`build_connector_meta()` 先调用 `_queue_scheduled_d2h()`。该函数只有在 `active_action is None` 时才创建下一条 `FUSED_D2H`，并把 range 固定为 `[confirmed_main_tokens, target_tokens)`；在 `D2H_COMPLETE` exact TP coverage 到齐前，`active_action` 不会清空。[D2H issue](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1830-L1875) [D2H queue](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1895-L1925) [D2H result consumption](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1979-L1989)

Worker 又把 `RECEIVE_REMOTE` 和 `FUSED_D2H` 都放入单 request `in_flight`，遇到 newer non-`QUIESCE` command 时 fail closed。`FUSED_D2H` 要等 `wait_for_save()` 后才从 `_dsa_pending_fused` 生成 `D2H_COMPLETE`。[worker overlap guard](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4379-L4400) [pending fused dispatch](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4425-L4455) [D2H result publication](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2855-L2877)

Async EngineCore 会在 batch queue 未满时连续 `schedule()` 和 `execute_model()`，优先填满 queue，然后按 FIFO 取回最老的 `(future, scheduler_output)` 并调用 `update_from_output()`。默认 PP=1 的 async queue depth 是 2。[async batch queue](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/engine/core.py#L484-L598) [queue depth](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/config/vllm.py#L496-L507)

因此 step N 的 ACK 尚未回到 scheduler 时，step N+1 已经可以构造。当前实现要么因为 `active_action` 跳过 N+1 D2H，要么在绕过 scheduler guard 后被 worker overlap check 拒绝。Startup 的 `async_scheduling` rejection 正是这条同步 causality 的显式保护。[startup rejection](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2076-L2083)

## Affected production symbols

| Area | Current symbol/state | Required delta |
| --- | --- | --- |
| Typed enum | `DsaAction.FUSED_D2H` | 删除 enum member；`RECEIVE_REMOTE`、`PREPARE_REPLAY`、`QUIESCE` 保留。 [enum](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py#L20-L31) |
| Typed result | `DsaLocalResultKind.D2H_COMPLETE` | 删除 result member及 action/result matrix 分支；receive/failure/replay result identity 保留。 [matrix](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py#L293-L310) |
| Lifecycle fields | `LifecycleCommand.d2h_token_start/count` | 不应简单消失；range 必须移入独立 step-local D2H value object或等价 channel，使 D2H plan 不占用 lifecycle action/command sequence。 [fields](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py#L141-L164) |
| Request validator | `DsaStepRequest.__post_init__()` | 删除 FUSED-only/source/range组合；为新的 step-local object验证 nonempty range、reservation identity、bound prefix和capacity。 [validator](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py#L168-L212) |
| Scheduler tracker | `active_action`, `command_emitted`, `command_seq` | 只管理 receive/replay/quiesce lifecycle；不能继续用一条 active command gate 每一步 D2H。 |
| Scheduler tracker | `confirmed_main_tokens` | 保留，但后续来源改成 current-epoch completed-step progress；initial receive 仍可直接建立 prompt validity。 [initial receive transition](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2019-L2034) |
| Scheduler tracker | `d2h_token_start/count` | 从 request-global active command state删除；改为 per-issued-step immutable plan/ledger entry。 |
| Scheduler result state | `terminal_results` | 继续用于 receive和replay exact-TP accumulation；不再用于 D2H。 |
| Scheduler builder | `_queue_scheduled_d2h()` | 改为每个 `SchedulerOutput` 独立生成 step-local D2H metadata，不因 receive/replay以外的旧 D2H ACK 阻塞后续 step。 |
| Scheduler output | `update_connector_output()` FUSED branch | 删除 exact-TP `D2H_COMPLETE` branch；改由已决定的 completed-step progress contract推进 watermark。 |
| Startup | async rejection | 只有在 progress、terminal、preemption和spec contracts都闭环后才能删除。 |
| Worker state | `_DsaWorkerRequestState.in_flight` | 继续保护异步 `RECEIVE_REMOTE` 和允许 overlap 的 `QUIESCE` terminal intent；不再把 step-local D2H建模为跨 batch command。 [state](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2676-L2682) |
| Worker state | `_dsa_pending_fused` | 删除；reservation snapshot retirement 必须改用新的 outstanding-step/terminal ownership证明，不能只删 pending check。 [snapshot retirement](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4280-L4318) |
| Worker dispatch | `_dispatch_dsa_commands()` FUSED branch | 从 lifecycle dispatch删除；每个 engine step仍要把 step-local D2H plan适配成 `SFAKVOffloadConnectorMetadata`。 |
| Worker completion | `wait_for_save()` synthetic result | 保留 SFA drain调用，但删除 synthetic `D2H_COMPLETE` publication。 |
| Main binding | `get_num_cpu_blocks()` | 不能再从 `_dsa_active_commands` 取 block table；worker需要独立保存最新 live reservation的 current bound Host prefix。 [current dependency](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2842-L2848) |

## confirmed Main validity 可以从哪里获得

### 已证实的两个 current source

1. Initial remote receive：scheduler 收到 exact TP `RECEIVE_COMPLETE` 后，把 `num_computed_tokens + num_external_tokens` 写入 `confirmed_main_tokens`。这条 prompt Main validity source保留。[receive transition](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2019-L2034)
2. Decode D2H：当前由 exact TP `D2H_COMPLETE` 把 `d2h_token_start + d2h_token_count` 写入 watermark；该 source随 command/result删除而被替代。[D2H transition](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1982-L1989)

### Worker step output 是可用 completion carrier，但 contract 尚未完成

vLLM worker 的 connector context 在构造 `KVConnectorOutput` 前调用 `wait_for_save()`，并随后收集 worker metadata；这使“该 worker step 已经越过 connector save barrier”与其 `ModelRunnerOutput` 同寿命。[worker connector output ordering](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/worker/kv_connector_model_runner_mixin.py#L78-L112)

Multiprocess `KVOutputAggregator` 又在同一个 returned step 内遍历所有 worker outputs并合并 `kv_connector_worker_meta`；scheduler 只收到聚合后的 `ModelRunnerOutput`。[worker aggregation](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/distributed/kv_transfer/kv_connector/utils.py#L50-L70) [metadata aggregation](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/distributed/kv_transfer/kv_connector/utils.py#L87-L168)

这说明 completed worker step output可以承载 non-gating D2H progress，但不能直接得出具体 watermark，原因有三项：

- Connector `update_connector_output()` 只收到 `KVConnectorOutput`，没有对应 `SchedulerOutput`；若不增加 step identity或严格 FIFO issued-plan ledger，无法证明 returned output对应哪条 D2H range。[core connector call](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L1595-L1607) [connector dispatch](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L2221-L2248)
- Core 在 `schedule()` 结束时乐观增加 `request.num_computed_tokens`；async 下一 batch可以在上一 output返回前再次增加它。因此 returned step处理时读取 current request counter可能包含尚未完成的 future batch。[optimistic update](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L997-L1027)
- Spec rejection 只在 `update_from_output()` 中按 generated tokens修正，且修正在 connector output consumption之前发生；step plan必须区分 scheduled、copied、accepted和confirmed boundary，不能用一个 current token count混写四种事实。[spec adjustment](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L1414-L1438)

因此 [定义 non-gating D2H progress 与 confirmed Main validity ledger](../issues/11-define-d2h-progress-main-validity-ledger.md) 必须在 implementation 前选择最小的 step identity、same-step aggregation、range-continuity与 epoch validation contract；本 research 不替它作设计决定。

## 哪些 exact-TP contracts 必须保留

1. `RECEIVE_REMOTE` success：只有 current routed Decode DP replica 的 exact TP rank set全部返回 `RECEIVE_COMPLETE`，才能建立 Indexer/Main validity和产生 `finished_recving`。
2. Initial transfer failure：第一个 `TRANSFER_FAILED` 不能立即启动 replay；仍要等当前 receive command 的 exact TP terminal coverage，证明其他 TP 不再访问 destination。
3. `PREPARE_REPLAY`：只有 exact TP `REPLAY_READY` 后，scheduler 才能把 request token state置零并恢复 local full-sequence replay。
4. Result validation：`(request_id, execution_epoch, command_seq, tp_rank)` identity、missing pending、identical duplicate idempotent、conflict/future fail closed、stale ignore继续适用于 receive/failure/replay。
5. Cancellation 是保留的窄例外：每个 worker在 local Quiesced 后上报 ordinary `finished_recving`，由 vLLM expected-worker-count aggregation形成 all-worker completion；不新增 typed `QUIESCED`。

这些边界当前集中在 scheduler result loop和 ADR 0021。[scheduler exact-TP loop](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1941-L2034) [ADR 0021](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)

独立 `D2H_COMPLETE` exact-TP ACK可以删除的依据不是“D2H 只需一个 TP成功”，而是 model execution本身要等待每个 worker返回；SFA Mooncake eager path在每层 D2H后还执行 TP `all_reduce` status、失败 fail-fast和 barrier。[SFA D2H TP status](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1525-L1596) 这项 source evidence不能替代 graph-capture/NPU runtime validation；capture path与真实 stream completion继续属于 [定义 async validation、failure 与 compatibility matrix](../issues/15-define-async-validation-failure-matrix.md) 的未验证范围。

## Ownership 与 correctness gaps

### Normal finish 不是现有 cancellation barrier

`request_finished()` 只对 `FINISHED_ABORTED` 建立 `cancel_pending -> QUIESCE -> delay_free_blocks=True`。Normal EOS/length/stop 直接删除 tracker并归还 Main blocks。[current finish path](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2036-L2057)

Core 在处理当前 step sampled output时，可能先 `_free_request()` 并调用 connector finish，再到整个 request loop之后消费同一步 `kv_connector_output`。Async queue中还可能有同 request的后继 batch已 issued。[stop/free ordering](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L1519-L1529) [connector output after request loop](https://github.com/jiahaoliang/vllm/blob/0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665/vllm/v1/core/sched/scheduler.py#L1574-L1607)

所以 async support必须把 normal finish、EOS、stop与abort都纳入明确 terminal barrier，或提供等价 outstanding-batch proof；否则 Main reservation可能在旧 worker D2H前被重新分配。该决定属于 [定义 async terminal ownership barrier](../issues/12-define-async-terminal-ownership-barrier.md)。

### Preemption 必须冻结 preserved boundary

Current preemption立即增加 execution epoch、清空 Indexer binding和pending results，但保留 `confirmed_main_tokens`。[preemption transition](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1879-L1893)

Async 下 old-epoch batch可能已经 schedule/execute、但 output尚未回收。实现必须决定这些 late progress是忽略、仅写但不扩大 validity，还是可以在某个 freeze barrier前纳入；无论哪种，都不能在 `PREPARE_REPLAY` 已携带 preserved boundary后再扩大新 epoch的有效 prefix。该决定属于 [定义 preemption 与 late D2H progress contract](../issues/13-define-preemption-late-progress-contract.md)。Exact-TP `PREPARE_REPLAY -> REPLAY_READY` 本身继续保留。

### Step-local Main binding 需要独立 source of truth

SFA worker每一步用 metadata 中的 `block_ids_cpu` 重建 `cpu_block_table`，并用同一步 `offload_token_start/offload_num_tokens`选择 D2H descriptor。[SFA block table](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L981-L1070)

当前 DSA `get_num_cpu_blocks()` 从 `_dsa_active_commands` 取 bound blocks；FUSED command不断替换 active command，所以 block table会随 D2H range增长。删除 FUSED command后，如果不新增 independent latest destination binding，worker可能一直看到 initial prompt bound prefix。[current block lookup](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2842-L2848) 该 schema和worker state决定属于 [定义 step-local D2H metadata 与 worker binding](../issues/14-define-step-local-d2h-metadata-worker-binding.md)。

### Speculative decoding 不能只照搬现有 helper

当前 DSA和SFA scheduler都用 `num_scheduled_tokens - len(scheduled_spec_decode_tokens)` 作为“finalized scheduled tokens”。[DSA calculation](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1901-L1911) [SFA helper](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_scheduler.py#L29-L32)

这段 arithmetic证明了现有 prior art，不证明 accepted draft KV如何补写、rejected positions如何覆盖、async placeholder下 range start如何与worker实际 slot一致。现有 DSA real Scheduler test显式关闭 async，且没有 scheduled spec case。[DSA test config](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/a2/test_remote_prefill_lifecycle.py#L45-L84) 因此 implementation必须选择经过 test的 spec contract；不能把“layerwise也这样做”当作 correctness oracle。

### Reservation snapshot retirement 需要新的 outstanding-work定义

Worker snapshot当前拒绝 retire 含 `in_flight`、`pending_quiesce` 或 `_dsa_pending_fused` 的 request。[snapshot guard](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4297-L4311) 删除 `_dsa_pending_fused` 后必须由 terminal/output ledger或worker顺序证明取代；否则 snapshot可能把仍会写 Main Host的request误判为 Quiesced。

## Test impact

### 需要改写或删除的现有断言

- `test_mooncake_dsa_metadata.py`：删除 FUSED request field matrix、D2H action/result matrix和 `D2H_COMPLETE` duplicate conflict；把 capacity/range negative cases迁移到新的 step-local D2H type。[current metadata tests](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/test_mooncake_dsa_metadata.py#L28-L85) [capacity tests](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/test_mooncake_dsa_metadata.py#L137-L153)
- `test_mooncake_connector.py`：把 startup “必须拒绝 async”改成支持 matrix；删除 scheduler D2H exact-TP transition和worker synthetic result/overlap assertions；保留 receive/replay/cancellation ordering negative tests。[startup test](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/test_mooncake_connector.py#L1600-L1610) [worker fused test](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/test_mooncake_connector.py#L2539-L2622)
- `a2/test_remote_prefill_lifecycle.py`：删除 `_d2h_results()` ACK helper，重写 transfer-failure full rewrite和preemption suffix-only assertions，使其通过 completed-step progress推进 validity，而不是手工注入 `D2H_COMPLETE`。[helper](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/a2/test_remote_prefill_lifecycle.py#L87-L115) [replay/preemption tests](https://gitcode.com/gzliangjiahao/vllm-ascend/blob/7401ae79c11d6ec0033ea3ac39085379a0bb81ef/tests/ut/kv_offload/a2/test_remote_prefill_lifecycle.py#L209-L334)

### 必须保留的 regression evidence

- Receive exact TP partial/missing/duplicate/conflict/stale/future/illegal-rank/action mismatch。
- Mixed TP transfer failure等待完整 terminal coverage，再进入 full replay。
- Exact TP replay-ready、token-0 public Scheduler replay和new Indexer binding。
- Cancellation receive-in-flight drain、DONE-before-finished、ordinary all-worker completion、release-once、late completion no-op。
- Reservation snapshot monotonicity、no resurrection、non-Quiesced retirement fail closed、request-ID reuse only after retirement。
- `dsa_pd_offload=false` ordinary `MooncakeConnectorV1` isolation。

### 新 completion gate 需要的 evidence

- sync与async走同一 step-local D2H schema和worker adapter。
- Real EngineCore-style queue depth大于1：连续 N/N+1 metadata都包含各自range，N未返回不阻塞N+1 issue。
- Returned step progress只能推进对应 current-epoch contiguous range；duplicate idempotent，gap/conflict/future fail closed，stale不扩大validity。
- Normal EOS/stop、length cap和abort在存在queued steps时都不提前释放Main/NPU ownership。
- Preemption发生在old-epoch output pending时，preserved boundary冻结，late progress不扩大new epoch，replay覆盖未确认suffix。
- Spec accepted/rejected/zero-draft/placeholder cases，或若首版无法证明则在startup/configuration fail closed。
- Eager D2H failure继续engine fail-fast，不伪造progress、`TRANSFER_FAILED`或`finished_recving`。
- `P TP8 -> D TP8` 与 `P TP8 -> D TP2` CPU/mock topology；reporter `P DP2/TP8 -> D DP2/TP8` 保留为后续NPU target，不硬编码产品唯一拓扑。
- NPU、graph capture、real transfer、cache content和performance继续标为 `planned / not run`。

完整 matrix由 [定义 async validation、failure 与 compatibility matrix](../issues/15-define-async-validation-failure-matrix.md) 决定。

## Domain docs、spec 与 ADR impact

### 需要部分 supersede

- [ADR 0017](../docs/adr/0017-use-a-separate-typed-dsa-metadata-family.md)：保留独立 scheduler-to-worker step metadata与worker-to-scheduler typed result family，但把 fused-D2H evidence从 command-scoped result family移出；新增的 step-progress是否仍属于 `KVConnectorWorkerMetadata` 由 progress ticket决定。
- [ADR 0019](../docs/adr/0019-use-minimal-complete-dsa-step-fields.md)：`LifecycleCommand` 不再携带 FUSED action专属 range，`command_seq` 不再为每个normal decode step充当gate；Main bound prefix和range validation迁移到step-local D2H schema。
- [ADR 0020](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)：action集合删除 `FUSED_D2H`，result集合删除 `D2H_COMPLETE`，matrix和scheduler consumption rules删除D2H exact-TP transition；D2H failure fail-fast边界保留。
- [ADR 0021](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)：exact TP继续管receive/failure/replay，不再把normal D2H建模为command-scoped cross-step accumulation；cancellation例外保持。

### 需要补充，但核心决定不应重开

- [ADR 0009](../docs/adr/0009-replay-preempted-requests-locally-on-decode.md)：保留full compute replay、new Indexer binding和可证明Main prefix复用；把“上一执行步D2H已完成”的证明来源改成accepted progress/terminal contract。
- [ADR 0010](../docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)：保留Quiesced、ordinary all-worker ack、release-once；把“drain current FUSED command”扩展为drain所有issued但未回收的step-local D2H，并覆盖normal terminal。
- [ADR 0016](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)：保持不变。不得借async support加入watchdog、reliable cancel、timeout后复用或automatic restart contract。
- [ADR 0022](../docs/adr/0022-use-the-puncture-positional-handshake-abi.md)：保持不变。Positional ABI、fixed leader mapping与deployment compatibility preconditions不受D2H lifecycle改造影响。
- [ADR 0023](../docs/adr/0023-use-staged-phase-a-then-phase-b-validation.md)：Phase A/Phase B和NPU证据分层保持；Phase B matrix需替换D2H ACK case并增加async queue/terminal/preemption/spec cases。

### Approved amendments

- [Stage 3 closure amendment](../reimplementation-stage3-closure-amendment.md) 的 async startup fail-closed和“normal finish只在single synchronous batch后retire”依据需要显式部分 supersede；reservation snapshot本身保留。
- [White-box ordering amendment](../reimplementation-whitebox-ordering-amendment.md) 的 single-command invariant继续适用于 `RECEIVE_REMOTE`、`PREPARE_REPLAY` 和 `QUIESCE`，但“拒绝async”和“FUSED_D2H在同步step内回ACK形成causality”不再成立；新的step-local D2H不应被归入newer non-`QUIESCE` lifecycle command overlap。

### CONTEXT、spec 与 design

- `CONTEXT.md`：更新 `DSA command sequence`、`DSA lifecycle action`、`DSA local result`、`DSA TP result coverage`、Main valid prefix和preemption术语；增加step-local D2H plan、D2H progress/confirmed watermark、issued/completed step和async terminal barrier的最终定义。[current terms](../CONTEXT.md)
- `spec.md`：更新summary、user stories 33-49、Implementation Decisions 22-39和Testing Decisions 4-15；删除D2H exact-TP ACK requirement，保留receive/replay exact TP、failure barrier、preemption/cancellation ownership及default isolation。[current spec](../spec.md)
- `blockwise-dsa-pd-offload-design.md`：重写preemption、cancellation、metadata boundaries、action/result matrix、fused D2H validity与validation sections；保留data plane、reservation、positional ABI、receive ordering和no-watchdog boundary。[current design](../blockwise-dsa-pd-offload-design.md)
- 已resolved的 [完成 exact TP lifecycle 与 fused D2H validity](../issues/04-exact-tp-lifecycle-fused-d2h.md) 和 [完成 preemption 与 cancellation ownership recovery](../issues/06-preemption-cancellation-ownership-recovery.md) 是旧contract的实现历史，不应静默改写成新contract；新implementation chain应通过supersession链接说明哪些结论被替换。

最终更新顺序与implementation vertical slices由 [定义 ADR/spec supersession 与 implementation ticket chain](../issues/16-define-doc-supersession-implementation-chain.md) 决定。

## 实现前必须回答的决策

1. [定义 non-gating D2H progress 与 confirmed Main validity ledger](../issues/11-define-d2h-progress-main-validity-ledger.md)：step identity、same-step aggregation、watermark continuity、duplicate/conflict/gap/future/stale规则。
2. [定义 async terminal ownership barrier](../issues/12-define-async-terminal-ownership-barrier.md)：normal finish/abort如何停止issue、drain queued batches、Quiesce并release-once。
3. [定义 preemption 与 late D2H progress contract](../issues/13-define-preemption-late-progress-contract.md)：epoch切换时冻结boundary及处理old-epoch late output。
4. [定义 step-local D2H metadata 与 worker binding](../issues/14-define-step-local-d2h-metadata-worker-binding.md)：range/reservation/bound-prefix schema、worker latest binding和spec fail-closed位置。
5. [定义 async validation、failure 与 compatibility matrix](../issues/15-define-async-validation-failure-matrix.md)：queue depth、sync/async、terminal/preemption/spec/topology/default regression及NPU边界。
6. [定义 ADR/spec supersession 与 implementation ticket chain](../issues/16-define-doc-supersession-implementation-chain.md)：在上述决定闭环后统一更新contract并拆implementation tickets。

在这些问题解决前，删除 `ValueError: Blockwise DSA Decode does not support async_scheduling` 不是安全的独立 implementation slice。
