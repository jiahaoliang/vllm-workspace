# 定义 preemption 与 late D2H progress contract

Type: grilling
Status: resolved
Blocked by: 08, 11, 12
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

preemption 发生在旧 batch 已 schedule/执行但 output 尚未回收时，execution epoch、issued-step ledger、late `D2H step progress`、Main preserved prefix、Indexer rebind 与 exact-TP `PREPARE_REPLAY -> REPLAY_READY` 应如何交互？如何保证 old-epoch completion 不扩大新 epoch validity，同时让 replay 安全覆盖未确认 suffix？

## Answer

Decision asset: [ADR 0026 - 使用 epoch cut 与 PREPARE_REPLAY barrier 恢复 preempted request](../docs/adr/0026-use-epoch-cut-and-prepare-replay-barrier.md).

### Epoch cut 与 preserved Main prefix

Scheduler 第一次在 active execution epoch 上观察到权威 `preempted_req_ids` 时立即形成 preemption cut：停止为旧 epoch 发布新的 Issued D2H step，封存旧 issued-step ledger，并把当时已经由 scheduler 消费的 `confirmed Main watermark` 快照为 immutable preserved prefix `P`。`issued Main watermark`、尚未回收的 worker output 与 scheduled token count 都不能扩大 `P`。

该次 preemption 只递增一次 execution epoch。Awaiting-rebind、`PREPARE_REPLAY` pending 或尚未重新开始 compute 时重复出现的同一次 preemption evidence 幂等忽略。只有 replay 已放行并形成新的 active execution 后再次发生真实 preemption，才创建下一 epoch，并以当时的 current-epoch confirmed boundary 重复本合同。

Cut 后返回的 old-epoch D2H progress 仍须通过 metadata schema、rank uniqueness 与 same-step aggregation检查；scheduler一旦按 execution epoch 将其分类为stale，只做bounded warning/metric后忽略，不重建或查询旧issued-step ledger，不推进validity，也不影响新epoch。旧operation可能在barrier前完成对未确认suffix的物理写入，但该suffix不属于`P`，随后由新epoch replay安全覆盖。

### 新 epoch ledger、Indexer rebind 与 replay barrier

新 epoch 使用空的 issued-step ledger 和新的 epoch-local D2H step sequence namespace；issued/confirmed Main watermark 都初始化为 `P`。Full-sequence compute replay 仍从 token 0 重建 Indexer，Main D2H只从`P`开始。Main reservation identity、Host block prefix/layout、capacity或request token boundary任一连续性无法证明时，`P`保守降为`0`，两条watermark同样从`0`开始。

Scheduler 等 core 为 resumed request 完成 Indexer allocation/rebind 后，携带新 execution epoch、stable Main reservation、new ownership snapshot 与 `P` 下发 `PREPARE_REPLAY`。Allocator 可以合法返回与旧 epoch 数值相同的 Indexer block IDs；新 epoch 加明确 rebind event 才是 ownership identity，不能要求 block ID tuple 必须变化。

对满足 per-worker step FIFO 的 executor，new-epoch `PREPARE_REPLAY` 是所有已发布 old-epoch work 之后的 preemption replay barrier。Worker必须允许它排在仍in-flight的旧operation之后，而不是按generic overlapping command立即fail closed；只有旧epoch的receive、replay、D2H save/event与background operation均不再访问destination、旧binding已清理且新Indexer ownership已安装后，才能返回`REPLAY_READY`。

`REPLAY_READY` 继续使用 `(request_id, execution_epoch, command_seq, tp_rank)` typed result identity与exact Decode TP rank coverage。缺失rank保持pending；相同完整result幂等；current identity的冲突、future或非法rank fail closed；stale result忽略。只有exact-TP coverage完整后，scheduler才建立replay state、将compute state重置到token 0并通过现有core transition hook放行请求。该transition不释放Main reservation，也不表示replay forward已执行或external KV有效。

### Terminal、failure 与无法完成 barrier

如果 awaiting-rebind 或 `PREPARE_REPLAY` pending期间出现normal finish、EOS、stop、length cap或abort，`Terminal-pending`主导：不再放行replay或发布D2H，也不等待Indexer rebind；scheduler通过latest epoch的metadata-only/no-forward batch下发`QUIESCE`。已经排队的`REPLAY_READY`仍按identity校验，但不能触发core replay。只有terminal ordinary all-worker completion才能release-once Main reservation与delayed NPU blocks。

Transfer-failure replay继续沿用既有same-epoch、all-TP terminal coverage与`P=0`规则。`PREPARE_REPLAY`只表达共同的Replay-ready安全边界，不新增replay-cause field、typed `PREEMPTED` result或upstream core channel。

如果`PREPARE_REPLAY`无法下发、任一旧operation不返回、缺失任一TP `REPLAY_READY`或worker无法证明barrier，继续遵守ADR 0016：请求、Main reservation与相关destination无限期保持pending/隔离，不增加watchdog、reliable native cancel、fatal latch或自动restart contract。非default executor是否满足FIFO与barrier delivery前提由[定义 async executor compatibility boundary](17-define-async-executor-compatibility-boundary.md)继续决定。

### Current replacement delta

Replacement `7401ae79c` 的scheduler已经在`_mark_preempted()`中递增execution epoch、等待Indexer rebind并把old result按stale忽略，但其D2H仍是single-active-command gate，worker收到`PREPARE_REPLAY`时可以立即产生`REPLAY_READY`，且generic overlap guard会拒绝与in-flight operation并存的newer non-`QUIESCE` command。Async实现必须把`PREPARE_REPLAY`强化为上述pending FIFO barrier，并按本决策接入epoch-local D2H ledger；本ticket未修改production source或运行source tests。
