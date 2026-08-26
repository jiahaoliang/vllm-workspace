# 盘点移除 FUSED_D2H command/result 的 lifecycle delta

Type: research
Status: resolved
Blocked by: None
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

若 sync/async 共用 step-local D2H，并从 typed lifecycle 删除 `FUSED_D2H` / `D2H_COMPLETE`，current production symbols、worker request state、Main block binding、preemption/replay/cancellation ownership、tests、`CONTEXT.md`、spec、ADRs 与 approved amendments 分别需要改变什么？哪些 exact-TP contracts 必须保留，哪些 correctness gaps 必须在 implementation 前作出新决策？

## Answer

完整 source evidence 见 [移除 FUSED_D2H command/result 的 lifecycle delta research](../research/10-fused-d2h-lifecycle-delta.md)。

`FUSED_D2H` enum/result、scheduler gate、worker pending/in-flight state 可以移除，但 D2H range、Main bound block table 与 completed-step validity proof 必须迁入独立 step-local contract。`RECEIVE_REMOTE`、mixed transfer-failure drain 与 `PREPARE_REPLAY -> REPLAY_READY` 仍保留 exact-TP coverage；cancellation/terminal cleanup 继续使用 ordinary all-worker completion。

需要部分 supersede ADR 0017、0019、0020、0021，以及 Stage 3 closure 和 white-box ordering amendments 中依赖 sync-only causality 的部分；ADR 0016 no-watchdog 与 ADR 0022 positional ABI 不重开。
