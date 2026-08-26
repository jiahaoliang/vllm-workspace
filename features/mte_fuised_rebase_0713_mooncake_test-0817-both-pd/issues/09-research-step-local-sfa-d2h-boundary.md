# 验证 step-local SFA D2H completion 与 failure boundary

Type: research
Status: resolved
Blocked by: None
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

现有 layerwise / `SFAPDCpuOffloadScheduler` 如何计算 finalized tokens、把 `SFAReqMeta` 绑定到当前 `SchedulerOutput`、在 attention forward 中执行 fused D2H 并传播 TP failure？哪些 data-plane primitive 可以由 Blockwise DSA 直接复用，哪些 completion、speculative-token、graph-capture 或 lifecycle 事实不能从该路径推断？

## Answer

完整 source evidence 见 [step-local SFA D2H data-plane 与证据边界 research](../research/09-step-local-sfa-d2h-boundary.md)。

现有 SFA path 已提供可复用的 step-local `SFAReqMeta`、Main block table、attention 内逐层 D2H、eager path synchronization 与 TP failure convergence。它没有提供 durable Main-valid ledger、speculative-token reconciliation、preemption/cancel ownership barrier，也没有证明 FULL graph capture 与 eager path 具有相同 completion/failure 边界。

因此 Blockwise DSA 可以复用 data-plane primitive，但不能沿用 layerwise 在 metadata build 时乐观推进 cursor 的 lifecycle 语义。
