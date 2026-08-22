# 06 — 完成 preemption 与 cancellation ownership recovery

**What to build:** 让已经 admission 的 Blockwise DSA 请求在 preemption 或 cancellation 下保持可证明的 destination ownership：preemption 使用新 execution epoch 重建 Indexer并尽可能复用有效 Main；cancellation 在 worker 全部 Quiesced 前禁止复用任何 reservation 地址，并复用普通 `finished_recving` 与现有 `DONE_RECVING_MSG` 完成本地 ack 和 Prefill source release。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0006 — 为请求完整生命周期预留 Main capacity](../docs/adr/0006-reserve-main-capacity-for-the-request-lifetime.md)、[ADR 0009 — Preemption 后 full compute replay 并复用 Main](../docs/adr/0009-replay-preempted-requests-locally-on-decode.md)、[ADR 0010 — Cancellation 使用两阶段 drain-and-ack](../docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)、[ADR 0013 — Transfer-failure replay 统一失效所有 TP 的 Main](../docs/adr/0013-invalidate-main-on-all-tps-for-transfer-failure-replay.md)、[ADR 0016 — 不为 Unquiesced operation 增加 watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)、[ADR 0019 — 使用显式最小完备的 DSA step fields](../docs/adr/0019-use-minimal-complete-dsa-step-fields.md)、[ADR 0020 — 使用 lifecycle action 和 terminal local result](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)、[ADR 0021 — 使用精确 TP coverage 和跨 step result 累积](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)

**Blocked by:** 05 — 完成全 TP transfer-failure recovery.

**Status:** resolved

- [x] Request tracker 区分跨 preemption 保留的 Main reservation state 与绑定当前运行的 execution epoch state。
- [x] Preemption retire 旧 epoch、清除旧 Indexer/temporary Main binding与 pending result，并在 resume 时绑定 core 新分配的 Indexer HBM IDs，不重新从 Prefill pull。
- [x] Resume 从 token 0 执行 Decode full-sequence compute replay以重建 Indexer；Main reservation跨 epoch 保持，已确认且 ownership/layout 连续的 Main prefix不重复 D2H。
- [x] 无法证明 Main ownership、layout或 validity 连续时，preserved boundary保守降为0并在 replay 中重写完整 Main。
- [x] Preemption evidence记录 replay token数、复用 Main token数、跳过的 D2H bytes和恢复耗时，不与正常 PD transfer指标混淆。
- [x] Admission 前 cancellation 可立即结束；admission 后进入 cancel-pending、禁止新的 receive/replay/D2H并继续隔离 Main reservation与 delayed NPU blocks。
- [x] Worker drain 当前 Indexer D2D、Main D2RH或 fused D2H，按 active `(request_id, execution_epoch)` 拒绝 stale/duplicate completion并清理 request/epoch binding；调用 cancel API 本身不能视为 Quiesced，且不产生 typed `QUIESCED` result。
- [x] 每个 worker 达到 Quiesced 后，先向自己实际读取且尚未通知完成的 Prefill leader endpoint best-effort 发送一次现有 `DONE_RECVING_MSG`，再把 request ID 放入普通 `finished_recving` set一次；普通 receive 已通知的 endpoint不重发，通知失败由 Prefill hard TTL兜底。
- [x] Scheduler 只在 vLLM expected-worker-count aggregation 产生 ordinary all-worker completion 后 release-once Main reservation，并按现有 completion顺序释放 delayed NPU blocks；重复 cancel/ack和 late completion均为 no-op。
- [x] 无法产生 quiesced ack的 operation无限期保持 ownership隔离，不增加 watchdog、可靠 native cancel或 timeout后强制释放。
- [x] Admission 前或尚未向 worker 绑定 Prefill endpoint的 cancellation不保证主动source-release notification，由hard TTL回收；unquiesced operation不发送伪`DONE_RECVING_MSG`或普通completion。
- [x] Focused tests覆盖 preemption rebind/Main reuse/fallback、各 lifecycle cancellation时点、in-flight drain、worker-local once guard、Prefill notification ordering/failure、ordinary all-worker aggregation、release ordering与 idempotency。

## Answer

`mooncake_dsa_scheduler.py` 分离 lifetime reservation 与 execution epoch，支持 preemption rebind、Main reuse proof/fallback、cancel-pending 和 ordinary all-worker ack 后 release-once。只读 `DsaPreemptionEvidence` 记录 full replay token 数、复用 Main token 数、按真实 Main `page_size_bytes` 计算的 skipped D2H bytes，以及从 preemption 到 exact `REPLAY_READY` 的 monotonic recovery duration。`mooncake_dsa_worker.py`、`mooncake_dsa_worker_adapter.py` 与 `mooncake_dsa_decode_runtime.py` 实现 drain、stale/duplicate guard、DONE-before-finished ordering 和 worker-local once guard；`QUIESCE` 不产生 typed result。

Preemption/cancellation 的所有 lifecycle timing、notification failure、aggregation、release ordering 与幂等性均在 Phase B 中通过，详见 [验证报告](../cpu-mock-validation-report.md)。NPU 恢复耗时等 runtime 指标仍待 NPU case 实测，不由 CPU/mock 结果推断。
