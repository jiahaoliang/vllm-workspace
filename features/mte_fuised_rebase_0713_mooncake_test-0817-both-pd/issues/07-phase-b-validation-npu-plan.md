# 07 — 完成 Phase B 验收与 NPU E2E 计划

**What to build:** 为完整 Blockwise DSA 实现建立可复核的 release evidence：在规定的 CPU-only UT Pod 中执行 contract-complete Phase B matrix，并发布一个以 `P TP8/DP2 -> D TP2/DP8` 为起点、包含 deployment preflight、correctness oracle 和 cleanup 的 NPU E2E 计划；未执行的 runtime case 始终明确标记为计划。

**Blocked by:** 06 — 完成 preemption 与 cancellation ownership recovery.

**Status:** ready-for-agent

- [ ] Phase B 覆盖 lifetime reservation、HOL admission、等待期间 ownership、release-once和多请求交错。
- [ ] Phase B 覆盖 transfer failure、exact TP terminal barrier、all-TP replay、preemption epoch rebind/Main reuse、cancellation drain-and-ack及 fused D2H validity/fail-fast。
- [ ] Phase B 覆盖 duplicate/conflict/stale/future/illegal/missing result，并验证无 outer retry、无 source TTL check、无 unquiesced completion 和无 connector-side positional compatibility claim等 negative contracts。
- [ ] DSA matrix完成后重新运行普通 V1 metadata、scheduler、transfer和 completion regression，证明 opt-in isolation。
- [ ] Phase A和 Phase B 都在 `liangjiahao` namespace 的专用长期运行 CPU-only UT Pod 中执行；使用 tar加显式 namespace的 `kubectl exec` 同步源码，不使用hostPath、serving Pod或NPU资源。
- [ ] 验证报告分别记录 Phase A/Phase B 的 source identity、显式命令、结果、修复和最终 rerun；仅在两阶段都通过后声明 `CPU/mock validated`。
- [ ] NPU plan定义 P/D immutable image digest、dependency revisions、model/configuration fingerprint、positional ABI、topology、leader replica、Host capacity和 registration preflight，任一不匹配时禁止发流量。
- [ ] NPU plan覆盖 happy path、partial/multi-block、并发/reservation pressure、ordering/failure injection、preemption、cancellation、default V1 isolation和 cleanup。
- [ ] 每个 NPU case包含 prerequisite、命令或 manifest、输入、baseline output与 cache checksum或等价 tensor oracle、成功条件、失败证据和显式资源 cleanup。
- [ ] 所有未真实执行的 NPU case标记 `planned / not run`；static、CPU/mock和 NPU runtime状态分别报告，不把计划或 mock结果提升为 `NPU runtime validated`。
