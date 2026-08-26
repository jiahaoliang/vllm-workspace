# 使用 QUIESCE tail marker 建立统一 terminal ownership barrier

状态：已接受

Async scheduling 允许请求在 step `N` 的 output 触发 EOS、stop、length cap 或 abort 时，step `N+1` 仍已进入 worker queue。Blockwise DSA 因此把所有 finish reason 统一映射到 reason-agnostic `Terminal-pending`，停止发布新的 receive、replay 和 Issued D2H step，并通过后续 metadata-only/no-forward batch 下发 `QUIESCE` tail marker。只要 executor 保证 per-worker step FIFO，该 marker 就排在所有已发布 work 之后；worker 达到 Quiesced 并上报 ordinary `finished_recving`，all-worker completion 到达后才 release-once Main reservation 与 delayed NPU blocks。

只有尚未取得 Main lifetime reservation 的请求可以立即结束。只要 reservation 已建立，即使 scheduler 认为它可能尚未暴露给 worker，也必须进入 terminal ownership barrier，避免新增一套不完整的 worker-visibility proof。

进入 Terminal-pending 时冻结 issued/confirmed Main watermarks。Queued batch 返回的 current-epoch D2H step progress 仍须匹配 immutable issued-step ledger；conflict、future identity 或内容不一致继续 fail fast，但合法 progress 只用于退休对应记录，不推进可复用 validity，也不阻塞 terminal release。永久 progress gap 不替代、也不阻塞 `QUIESCE` 对 destination ownership 的证明。

Worker 只有在以下条件全部满足时才是 Quiesced：该 reservation 的 `QUIESCE` tail marker 已到达；current 或 old execution epoch 的 receive、replay、D2H save/event 与 background operation 都不会再访问 Indexer/Main destination；request/epoch binding 已清理；并已对实际读取且尚未通知完成的 Prefill source 尝试一次 best-effort `DONE_RECVING_MSG`。随后每个 worker只上报一次 ordinary `finished_recving`，并保留最小 completion-once state，直到 scheduler 的 reservation snapshot 明确退休该 reservation。

本决策复用 ADR 0010 的 drain-and-ack、ADR 0020 的 ordinary completion channel 和 vLLM delayed-free ordering，并将其从 abort/cancellation 扩展到所有 finish reason；不增加 typed `QUIESCED` result或upstream vLLM completion channel。非 default executor 是否满足 FIFO 与 metadata-only/no-forward delivery 由 [定义 async executor compatibility boundary](../../issues/17-define-async-executor-compatibility-boundary.md) 决定，不能从 default `MultiprocExecutor` 外推。

无法下发或完成 `QUIESCE`、background operation 不返回、或 worker 无法证明 Quiesced 时，按 ADR 0016 不产生 ordinary completion，不释放或复用 Main reservation 与 delayed NPU blocks，不增加 watchdog、reliable cancel、fatal latch 或自动 restart contract。完整决议与 source evidence 入口见 [定义 async terminal ownership barrier](../../issues/12-define-async-terminal-ownership-barrier.md)。
