# 使用 epoch cut 与 PREPARE_REPLAY barrier 恢复 preempted request

状态：已接受

Async scheduling 允许请求被 preempt 时仍有 old-epoch D2H batch 已发布但尚未回收。Blockwise DSA 因此在 scheduler 第一次观察到 active epoch 的 preemption 时立即形成 validity cut：封存旧 issued-step ledger，以当时已经消费的 confirmed Main watermark 快照 immutable preserved prefix `P`，并只递增一次 execution epoch。Cut 后的 old-epoch progress 在基础 metadata/aggregation 校验后按 stale 观察并忽略，不能扩大 `P`；新 epoch 以 issued/confirmed watermark `P`、空 ledger 和新的 epoch-local D2H sequence namespace开始，连续性无法证明时 `P=0`。

Core 完成 resumed request 的 Indexer allocation/rebind 后，scheduler下发new-epoch `PREPARE_REPLAY`。对满足per-worker step FIFO的executor，该command是所有已发布old-epoch work之后的preemption replay barrier：worker只有在旧operation均不再访问destination、旧binding已清理并安装新Indexer ownership后才能返回`REPLAY_READY`。Allocator可以返回与旧epoch相同的block ID数值；execution epoch与明确rebind event共同标识新ownership，不能以ID数值变化作为安全前提。

Scheduler继续按typed identity累积exact-TP `REPLAY_READY`，完整coverage后才建立token-0 full-sequence replay state并使用现有core transition hook。Replay重建完整Indexer，但Main D2H跳过`[0, P)`，覆盖全部未确认suffix；该transition不释放Main reservation，也不表示replay已经执行。Transfer-failure replay仍使用same-epoch `PREPARE_REPLAY`与`P=0`，不新增replay-cause field或typed `PREEMPTED` result。

重复的同一次preemption evidence在awaiting-rebind/barrier阶段幂等；只有新epoch compute已经开始后的真实再次preemption才创建下一epoch。Preemption-pending期间出现terminal intent时，`Terminal-pending`主导并改走latest-epoch `QUIESCE` tail marker，late `REPLAY_READY`不能重新放行replay。Barrier无法完成时按ADR 0016无限期隔离ownership，不增加watchdog、reliable cancel、fatal latch或自动restart。非default executor的FIFO compatibility仍由独立决策处理。

完整contract与replacement delta见[定义 preemption 与 late D2H progress contract](../../issues/13-define-preemption-late-progress-contract.md)。
