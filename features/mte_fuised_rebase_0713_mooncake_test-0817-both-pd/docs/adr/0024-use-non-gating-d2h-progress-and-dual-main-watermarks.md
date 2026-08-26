# 使用 non-gating D2H progress 与 dual Main watermarks

状态：已接受

Blockwise DSA 的 decode-time Main D2H 使用独立、request-local、epoch-local 的 Issued D2H step，而不是 lifecycle `FUSED_D2H` command。Scheduler 分别维护 issued Main watermark 与 confirmed Main watermark，并只在消费 `wait_for_save()` 后形成的 rank-aware D2H step progress 时推进 confirmed boundary，从而允许 async scheduler 提前发布下一 step，又不把 scheduled range误当作有效 Main prefix。

每个非空 plan 使用独立 `d2h_step_seq`，并以 request、execution epoch、reservation 和 token range 形成 immutable issued-step ledger。当前 model step 的 progress 必须覆盖精确 Decode TP rank set；later step可以先标记 completed，但 confirmed watermark不能跨越缺口。Active plan的duplicate/conflict/future validation保持严格，old-epoch、已confirmed或released progress只观察后忽略；永久缺口不增加timeout、watchdog或推测性completion。

完整 contract 与 rejected alternatives 记录在 [定义 non-gating D2H progress 与 confirmed Main validity ledger](../../issues/11-define-d2h-progress-main-validity-ledger.md)。本 ADR 只取代 ADR 0017、0019、0020、0021 中把 decode-time D2H 表达为 `FUSED_D2H` / `D2H_COMPLETE` lifecycle command/result及其跨-step gate的部分；receive、transfer failure、replay exact-TP coverage和ordinary terminal completion边界继续有效。
