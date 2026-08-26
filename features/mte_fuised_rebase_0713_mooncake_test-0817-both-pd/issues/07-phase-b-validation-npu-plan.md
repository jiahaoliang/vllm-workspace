# 07 — 完成 Phase B 验收与 NPU E2E 计划

**What to build:** 为完整 Blockwise DSA 实现建立可复核的 release evidence：在规定的 CPU-only UT Pod 中执行 contract-complete Phase B matrix，并发布一个以 `P TP8/DP2 -> D TP2/DP8` 为起点、包含文档化 deployment preflight、correctness oracle 和 cleanup 的 NPU E2E 计划；未执行的 runtime case 始终明确标记为计划。本票不实现 production deployment system。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0001 — 使用 per-Decode-TP local Swapped Main pool](../docs/adr/0001-use-per-decode-tp-local-swapped-main-pools.md)、[ADR 0004 — 使用固定 TP leader 作为完整 replica source](../docs/adr/0004-use-fixed-tp-leaders-as-complete-replica-sources.md)、[ADR 0015 — Transfer 前不检查 Prefill source TTL](../docs/adr/0015-do-not-check-prefill-source-ttl-before-transfer.md)、[ADR 0016 — 不为 Unquiesced operation 增加 watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)、[ADR 0022 — 沿用穿刺 positional handshake ABI](../docs/adr/0022-use-the-puncture-positional-handshake-abi.md)、[ADR 0023 — 使用 Phase A 后 Phase B 的分阶段验证](../docs/adr/0023-use-staged-phase-a-then-phase-b-validation.md)

**Blocked by:** 06 — 完成 preemption 与 cancellation ownership recovery.

**Status:** resolved

- [x] Phase B 覆盖 lifetime reservation、HOL admission、等待期间 ownership、release-once和多请求交错。
- [x] Phase B 覆盖 transfer failure、exact TP typed terminal barrier、all-TP replay、preemption epoch rebind/Main reuse、cancellation drain-and-ack、`DONE_RECVING_MSG` ordering、ordinary all-worker completion及 fused D2H validity/fail-fast。
- [x] Phase B 覆盖 duplicate/conflict/stale/future/illegal/missing typed result和cancellation duplicate/stale ordinary ack，并验证无 outer retry、无 source TTL check、无 unquiesced completion/Prefill notification 和无 connector-side positional compatibility claim等 negative contracts。
- [x] DSA matrix完成后重新运行普通 V1 metadata、scheduler、transfer和 completion regression，证明 opt-in isolation。
- [x] Phase A和 Phase B 都在 `liangjiahao` namespace 的专用长期运行 CPU-only UT Pod 中执行；使用 tar加显式 namespace的 `kubectl exec` 同步源码，不使用hostPath、serving Pod或NPU资源。
- [x] 验证报告分别记录 Phase A/Phase B 的 source identity、显式命令、结果、修复和最终 rerun；仅在两阶段都通过后声明 `CPU/mock validated`。
- [x] NPU plan把 P/D immutable image digest、dependency revisions、model/configuration fingerprint、positional ABI、topology、leader replica、Host capacity和 registration写成可执行preflight及证据要求，任一不匹配时对应case禁止发流量；该计划不声称已实现production admission gate。
- [x] NPU plan覆盖 happy path、partial/multi-block、并发/reservation pressure、ordering/failure injection、preemption、cancellation、default V1 isolation和 cleanup。
- [x] 每个 NPU case包含 prerequisite、命令或 manifest、输入、baseline output与 cache checksum或等价 tensor oracle、成功条件、失败证据和显式资源 cleanup。
- [x] 所有未真实执行的 NPU case标记 `planned / not run`；static、CPU/mock和 NPU runtime状态分别报告，不把计划或 mock结果提升为 `NPU runtime validated`。

## Answer

Replacement checkout已在`liangjiahao/vllm-ascend-ut` CPU-only Pod完成focused与broad regression：DSA/SFA group `47 passed`，完整connector/default-V1 target `111 passed`，排除一个已知baseline-broken测试文件后的broad root `221 passed`。完整root为`241 passed / 5 failed`；五项均是未修改`test_mooncake_to_dram_asymmetric_push.py`缺少import的pre-existing defect。Static compile与`git diff --check`通过，当前delta没有新增ruff failure。证据与边界见 [CPU/mock validation report](../cpu-mock-validation-report.md)。

[NPU E2E test plan](../npu-e2e-test-plan.md) 与 [repository-local harness](../npu-e2e/README.md) 提供 versioned config/fixture/case schema、manifest render、fail-closed preflight、单 case runner、oracle contract 和 cleanup。仅完成 static/offline synthetic validation，未执行 NPU workload；8 个 case 全部保持 `planned / not run`，不得据此声明 `NPU runtime validated`。
