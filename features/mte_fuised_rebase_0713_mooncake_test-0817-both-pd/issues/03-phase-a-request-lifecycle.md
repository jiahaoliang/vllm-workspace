# 03 — 打通并验证 Phase A request lifecycle

**What to build:** 打通一个可观察的 Blockwise DSA request tracer：从 matched-token/admission、destination allocation 和 metadata 发布开始，经 fixed leader source、Indexer D2D、Main D2RH、worker result 与 scheduler output consumption，最终进入 receive-complete；基本 transfer failure 能安全进入 Decode replay，terminal cleanup 能 release-once。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0004 — 使用固定 TP leader 作为完整 replica source](../docs/adr/0004-use-fixed-tp-leaders-as-complete-replica-sources.md)、[ADR 0005 — 将 partial block 按完整物理 block 传输](../docs/adr/0005-transfer-partial-blocks-as-full-physical-blocks.md)、[ADR 0011 — Indexer 传输失败时不启动 Main](../docs/adr/0011-stop-before-main-when-indexer-transfer-fails.md)、[ADR 0012 — Transfer 最终失败后由 Decode replay](../docs/adr/0012-retry-transfer-then-replay-on-decode.md)、[ADR 0014 — 仅依赖 Mooncake 内部 retry](../docs/adr/0014-rely-only-on-mooncake-internal-retry.md)、[ADR 0020 — 使用 lifecycle action 和 terminal local result](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)、[ADR 0023 — 使用 Phase A 后 Phase B 的分阶段验证](../docs/adr/0023-use-staged-phase-a-then-phase-b-validation.md)

**Blocked by:** 02 — 建立 positional data plane 与 Main lifetime reservation.

**Status:** ready-for-agent

- [ ] Decode TP 使用其连续 Prefill TP group 的首个 rank 作为 Main、Indexer 和可选 scale 的唯一 payload source，并只使用实际处理请求的 Prefill DP replica。
- [ ] Source/destination block mapping 使用现有 token state；最后一个 partial Main block 和 Indexer page按完整物理长度传输，不新增第二套 valid-token 事实来源。
- [ ] 一个 `RECEIVE_REMOTE` command 在每个 worker 内只调用一次同步 Indexer D2D；仅成功后才调用一次同步 Main D2RH，两者成功后才产生 `RECEIVE_COMPLETE`。
- [ ] Indexer final failure 不启动 Main，并产生 `TRANSFER_FAILED(INDEXER_D2D)`；Main final failure 产生 `TRANSFER_FAILED(MAIN_D2RH)`，任何 failure 都不能伪装成 cache hit。
- [ ] 基本 failure path 保留 Main reservation、令 `preserved_main_tokens=0`，通过 `PREPARE_REPLAY` 让请求从 token 0 执行 Decode full-sequence replay。
- [ ] Python connector 不增加 outer retry、attempt/backoff 配置或 source TTL check，只消费 Mooncake 同步调用的最终结果。
- [ ] 主 lifecycle harness 同时覆盖 opt-in path 与 default V1 isolation，并从 public connector hooks 验证 ownership transition，而不是把 private helper 调用顺序作为主要 oracle。
- [ ] Phase A static 和 CPU/mock tests 在 `liangjiahao` namespace 的专用 CPU-only UT Pod 中执行；记录 source branch、commit、dirty 状态、显式 targets、结果、修复和最终 rerun。
- [ ] Phase A 通过后的状态只声明 `Phase A passed`，不声明 `CPU/mock validated` 或任何 NPU runtime 结论。
