# 定义 async terminal ownership barrier

Type: grilling
Status: resolved
Blocked by: 08, 10, 11
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

normal finish、EOS、stop 与 abort 到达时，connector 如何停止发布新 step-local D2H、识别和 drain 已发但未回收的 async batch、令每个 worker 达到 Quiesced，并只在 ordinary all-worker `finished_recving` 后 release-once Main reservation 和 delayed NPU blocks？现有 `QUIESCE`、no-forward metadata 与 delayed-free hooks 是否足够，无法 quiesce 时如何继续遵守 ADR 0016？

## Answer

Decision asset: [ADR 0025 - 使用 QUIESCE tail marker 建立统一 terminal ownership barrier](../docs/adr/0025-use-quiesce-tail-marker-for-terminal-ownership.md).

### 统一 terminal state 与发布边界

Normal finish、EOS、stop、length cap 和 abort 都进入 reason-agnostic `Terminal-pending`。进入时冻结 issued/confirmed Main watermarks，停止发布新的 receive、replay 与 Issued D2H step，并为当前 execution epoch 分配新的 lifecycle `command_seq` 以发布 `QUIESCE`。只有尚未取得 Main lifetime reservation 的请求可以立即结束；只要 reservation 已建立，就不根据“可能尚未暴露给 worker”推测安全释放。

### FIFO tail marker 与 late progress

`QUIESCE` 通过 terminal 后的 metadata-only/no-forward batch 下发。对满足 per-worker step FIFO 的 executor，它是所有已发布 async batch 的 tail marker；worker output 与 EngineCore output consumption 同样按 step FIFO，因此 all-worker terminal completion 不会越过更早的 queued D2H output。

Terminal 后到达的 current-epoch D2H step progress 仍匹配 immutable issued-step ledger并执行 duplicate/conflict/future validation，但合法 progress只退休对应记录，不推进 frozen confirmed Main watermark，也不成为 terminal gate。永久 progress gap不阻止随后 `QUIESCE` 证明 Quiesced。非 default executor是否满足 FIFO 与metadata-only/no-forward delivery由 [定义 async executor compatibility boundary](17-define-async-executor-compatibility-boundary.md)继续决定。

### Worker Quiesced 与 release-once

Worker 仅在 `QUIESCE` 到达，current/old execution epoch 的 receive、replay、D2H save/event 与 background operation 均不再访问 destination，并清理 request/epoch binding 后达到 Quiesced。它先对实际读取且尚未通知完成的 Prefill source 尝试一次best-effort `DONE_RECVING_MSG`，再通过completion-once guard上报一次ordinary `finished_recving`；最小worker state保留到后续reservation snapshot明确退休该reservation。

`KVOutputAggregator` 形成all-worker completion后，scheduler connector在core处理ordinary completion之前release-once完整Main reservation，随后core释放delayed NPU blocks。现有 `QUIESCE`、no-forward metadata、ordinary `finished_recving` 与 delayed-free hooks 在上述 FIFO 前提下足够，不新增 typed `QUIESCED` result或upstream vLLM completion channel。

### Unquiesced boundary

无法下发或完成 `QUIESCE`、operation不返回或worker无法证明Quiesced时，继续遵守ADR 0016：不伪造 `finished_recving`，不释放或复用Main reservation与delayed NPU blocks，不增加watchdog、reliable native cancel、fatal latch或自动restart contract。恢复只依赖operation最终返回、已有process failure行为或外部重启。
