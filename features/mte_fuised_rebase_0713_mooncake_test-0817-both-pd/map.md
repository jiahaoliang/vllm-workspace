# Blockwise DSA Async Scheduling Wayfinder Map

## Destination

形成一套已批准、可直接交给 implementation agent 的 async-compatible Blockwise DSA spec、ADR delta 与 implementation/test ticket chain，使 `MooncakeConnectorV1` 的 Decode `dsa_pd_offload=true` 同时支持 sync 和 async scheduling。该 map 在生产源码修改前结束。

## Notes

- Delivery scope includes feature-local `CONTEXT.md`、spec、ADR 与 implementation/test ticket planning；不包含 `repos/*` 生产源码修改。
- 每次处理 decision ticket 时使用 `grilling` 与 `domain-modeling`；research ticket 使用 `research`，并把 current checkout facts 与 proposal 分开。
- External report: [GitCode issue 1 snapshot](references/snapshots/gitcode-vllm-ascend-issue-1-2026-08-26.md).
- Source baseline: vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` on `feature/blockwise-dsa-mooncake-v1-reimplementation`; vLLM `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`.
- Decode D2H 使用 sync/async 共用的 step-local metadata；typed lifecycle 删除 `FUSED_D2H` / `D2H_COMPLETE`，但 `RECEIVE_REMOTE` 与 `PREPARE_REPLAY` 继续使用 exact-TP result coverage。
- 不修改 upstream vLLM core。产品 topology 保持现有 `P_TP >= D_TP` 且 `P_TP % D_TP == 0` 的通用边界；reporter 的 `P DP2/TP8 -> D DP2/TP8` 是明确回归目标，不是唯一 topology。
- `D2H step progress` 是 `wait_for_save()` 后随本 step worker output 返回、不会阻塞后续 schedule 的 completion fact。`confirmed Main watermark` 只能由已回收的 current-epoch progress 推进，不能由 issued/scheduled range 推测。
- normal finish、EOS、stop 与 abort 共用 terminal ownership barrier：禁止新 D2H，drain 已发 async batch，ordinary all-worker `finished_recving` 后 release-once。
- Preemption 只保留 preemption 前已确认的 current-epoch Main prefix；晚到 old-epoch progress 不扩大 preserved prefix。Fused D2H failure 继续 model-step fail-fast。
- Blockwise DSA与speculative config的组合不拒绝启动，但本版不validation、不测试，也不承诺D2H/Main/replay correctness；async output placeholders仍属于支持范围。
- 初版 async implementation acceptance只要求GitCode reporter `P DP2/TP8 -> D DP2/TP8`单请求happy path的static与CPU/mock gate，包括真实`AsyncScheduler`/EngineCore queue depth 2；完整failure/lifecycle matrix标记“未测试”，NPU/graph-capture继续标记`planned / not run`。

## Decisions so far

- [建立 Blockwise DSA opt-in control plane](issues/01-blockwise-dsa-opt-in-control-plane.md): 已完成 opt-in control plane、typed lifecycle contract 与 default V1 isolation。
- [建立 positional data plane 与 Main lifetime reservation](issues/02-positional-data-plane-main-reservation.md): 已完成 positional data plane、per-TP Host Main registration、lifetime reservation 与 HOL admission。
- [打通并验证 Phase A request lifecycle](issues/03-phase-a-request-lifecycle.md): 已完成 fixed-leader Indexer D2D -> Main D2RH、basic failure replay 与 Phase A。
- [完成 exact TP lifecycle 与 fused D2H validity](issues/04-exact-tp-lifecycle-fused-d2h.md): 已完成 replacement 的 exact-TP aggregation 与 fused D2H validity；其中 fused D2H command/result 部分将由本 map 重新决策。
- [完成全 TP transfer-failure recovery](issues/05-all-tp-transfer-failure-recovery.md): 已完成 mixed-TP failure barrier、all-TP validity reset 与 full replay。
- [完成 preemption、cancellation 与 ownership recovery](issues/06-preemption-cancellation-ownership-recovery.md): 已完成 replacement 的 preemption evidence、Main reuse/fallback 与 cancellation drain-and-ack；async terminal barrier 由本 map 继续收敛。
- [完成 Phase B validation 与 NPU plan](issues/07-phase-b-validation-npu-plan.md): 已完成 Phase B、default V1 regression、CPU/mock report 与 NPU plan；NPU runtime 仍为 `planned / not run`。
- [验证 async batch completion 与 executor ordering](issues/08-research-async-batch-completion-ordering.md): Default `MultiprocExecutor` 的 worker/output FIFO 可作为 narrow completion boundary，但 schedule 会领先 output，terminal/preemption 可与旧 batch 交错，其他 executor 尚未验证。
- [验证 step-local SFA D2H completion 与 failure boundary](issues/09-research-step-local-sfa-d2h-boundary.md): Step-local `SFAReqMeta`、attention D2H 与 TP failure convergence 可复用；durable validity、spec reconciliation、terminal ownership 与 graph-capture completion 不能从 layerwise path 推断。
- [盘点移除 FUSED_D2H command/result 的 lifecycle delta](issues/10-research-fused-d2h-lifecycle-delta.md): D2H command/result gate 可移除，但必须新增 completed-step validity 与 async terminal barrier；receive/failure/replay exact-TP contracts 继续保留。
- [定义 non-gating D2H progress 与 confirmed Main validity ledger](issues/11-define-d2h-progress-main-validity-ledger.md): 每个request/epoch使用独立D2H step sequence、issued/confirmed双watermark与immutable ledger；same-step exact-TP progress推进连续validity，但不形成跨-step scheduling gate。
- [定义 async terminal ownership barrier](issues/12-define-async-terminal-ownership-barrier.md): 所有finish reason统一进入Terminal-pending，并以FIFO `QUIESCE` tail marker、ordinary all-worker completion和release-once建立终态ownership边界。
- [定义 preemption 与 late D2H progress contract](issues/13-define-preemption-late-progress-contract.md): Preemption在confirmed boundary形成epoch cut，并以FIFO `PREPARE_REPLAY` barrier、exact-TP `REPLAY_READY`和new-epoch ledger安全覆盖未确认suffix。
- [定义 step-local D2H metadata 与 worker binding](issues/14-define-step-local-d2h-metadata-worker-binding.md): D2H使用独立step-local plan、persistent worker Main binding与`wait_for_save()`后rank-aware progress；speculative组合允许启动但保持unverified。
- [定义 async executor compatibility boundary](issues/17-define-async-executor-compatibility-boundary.md): 只验证default `MultiprocExecutor` + default `AsyncScheduler`；其他组合允许启动、warning为未测试，且不由topology或upstream capability自动升级。
- [定义 async validation、failure 与 compatibility matrix](issues/15-define-async-validation-failure-matrix.md): 初版只以GitCode reporter的default-executor、depth-2单请求happy path作为CPU/mock gate；完整failure/lifecycle、其他topology与非默认组合保持未测试。
- [定义 ADR/spec supersession 与 implementation ticket chain](issues/16-define-doc-supersession-implementation-chain.md): Canonical spec已升级并保留sync历史evidence；旧ADR/amendment使用forward pointer记录async supersession，后续拆为五张需独立授权的implementation/test tickets。
- [实现 non-gating D2H plan/progress vertical slice](issues/18-implement-non-gating-d2h-plan-progress.md): 已发布step-local plan/progress、issued/confirmed ledger与persistent worker Main binding；focused static和CPU/mock通过，terminal/preemption与真实runtime evidence未扩大。
- [实现 async terminal ownership barrier](issues/19-implement-async-terminal-ownership-barrier.md): 已发布normal-finish `QUIESCE` tail marker、ordinary all-worker completion与release-once；preemption交错留给ticket 20，abort与真实runtime未测试。
- [实现 async preemption replay barrier](issues/20-implement-async-preemption-replay-barrier.md): 已发布cut-time confirmed prefix、old-D2H drain/rebind barrier与terminal dominance；focused CPU/mock通过但Preemption runtime claim仍为未测试。

## Not yet specified

## Out of scope

- 修改或提交 vLLM-Ascend production source、运行 source tests、刷新 `workspace.lock.json` 或发布新 replacement commit。
- 修改 upstream vLLM core，或新增 core-level running-request D2H failure/completion channel。
- Blockwise DSA与speculative decoding的配合实现、correctness validation和support claim；配置组合允许启动，但本版保持out of scope / unverified。
- Fused D2H request-local recovery、feature watchdog、reliable native cancel、fatal latch 或自动 restart contract。
- NPU runtime、performance threshold、完整 Lifecycle runtime validation、GitCode 回帖或关闭 external issue。
- 改变 positional tensor ABI、TP leader mapping、Main reservation policy或 default `MooncakeConnectorV1` behavior。
