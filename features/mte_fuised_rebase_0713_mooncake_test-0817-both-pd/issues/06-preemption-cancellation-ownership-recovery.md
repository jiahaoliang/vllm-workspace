# 06 — 完成 preemption 与 cancellation ownership recovery

**What to build:** 让已经 admission 的 Blockwise DSA 请求在 preemption 或 cancellation 下保持可证明的 destination ownership：preemption 使用新 execution epoch 重建 Indexer并尽可能复用有效 Main，cancellation 则在 worker 全部 quiesced 前禁止复用任何 reservation 地址。

**Blocked by:** 05 — 完成全 TP transfer-failure recovery.

**Status:** ready-for-agent

- [ ] Request tracker 区分跨 preemption 保留的 Main reservation state 与绑定当前运行的 execution epoch state。
- [ ] Preemption retire 旧 epoch、清除旧 Indexer/temporary Main binding与 pending result，并在 resume 时绑定 core 新分配的 Indexer HBM IDs，不重新从 Prefill pull。
- [ ] Resume 从 token 0 执行 Decode full-sequence compute replay以重建 Indexer；Main reservation跨 epoch 保持，已确认且 ownership/layout 连续的 Main prefix不重复 D2H。
- [ ] 无法证明 Main ownership、layout或 validity 连续时，preserved boundary保守降为0并在 replay 中重写完整 Main。
- [ ] Preemption evidence记录 replay token数、复用 Main token数、跳过的 D2H bytes和恢复耗时，不与正常 PD transfer指标混淆。
- [ ] Admission 前 cancellation 可立即结束；admission 后进入 cancel-pending、禁止新的 receive/replay/D2H并继续隔离 Main reservation与 delayed NPU blocks。
- [ ] Worker drain 当前 Indexer D2D、Main D2RH或 fused D2H，清理 request/epoch binding后产生 `QUIESCED`；调用 cancel API 本身不能视为 quiesced。
- [ ] Scheduler 只在 exact TP `QUIESCED` 后 release-once Main reservation，并按现有 completion顺序释放 delayed NPU blocks；重复 cancel/ack和 late completion均为 no-op。
- [ ] 无法产生 quiesced ack的 operation无限期保持 ownership隔离，不增加 watchdog、可靠 native cancel或 timeout后强制释放。
- [ ] Focused tests覆盖 preemption rebind/Main reuse/fallback、各 lifecycle cancellation时点、in-flight drain、exact TP quiesce、release ordering与 idempotency。
