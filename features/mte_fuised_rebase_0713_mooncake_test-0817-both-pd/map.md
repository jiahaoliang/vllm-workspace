# Blockwise DSA PD Offload Map

## Notes

- Delivery contract: [spec.md](spec.md)
- Architecture: [blockwise-dsa-pd-offload-design.md](blockwise-dsa-pd-offload-design.md) and [accepted ADRs](docs/adr/)
- Source commit: vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` on `feature/blockwise-dsa-mooncake-v1-reimplementation`
- Validation: [replacement CPU/mock evidence](cpu-mock-validation-report.md); NPU `planned / not run`
- Replacement history: [durable goal](reimplementation-goal.md) and its approved design/closure/white-box amendments

## Decisions-so-far

- [01](issues/01-blockwise-dsa-opt-in-control-plane.md): opt-in control plane、typed lifecycle contract 与 default V1 isolation 已完成。
- [02](issues/02-positional-data-plane-main-reservation.md): positional data plane、per-TP Host Main registration、lifetime reservation 与 HOL admission 已完成。
- [03](issues/03-phase-a-request-lifecycle.md): fixed-leader Indexer D2D -> Main D2RH、basic failure replay 与 Phase A 已完成。
- [04](issues/04-exact-tp-lifecycle-fused-d2h.md): exact TP aggregation、typed result boundaries 与 fused D2H validity 已完成。
- [05](issues/05-all-tp-transfer-failure-recovery.md): mixed TP failure barrier、all-TP validity reset 与 full replay 已完成。
- [06](issues/06-preemption-cancellation-ownership-recovery.md): preemption evidence、Main reuse/fallback 与 cancellation drain-and-ack 已完成。
- [07](issues/07-phase-b-validation-npu-plan.md): Phase B、default V1 regression、CPU/mock report 与 8-case NPU plan 已完成。

## Fog

- GitCode replacement branch 已发布并实时核对为 `7401ae79c`；`workspace.lock.json` 已改为该 fetchable identity。
- Replacement source 位于独立 worktree，而 lock 的标准恢复路径为 `repos/vllm-ascend`；本轮手工刷新 lock，未移动旧 behavior-reference checkout，也未修改公共脚本。
- Positional ABI 不提供跨 P/D semantic compatibility proof；image/configuration/layout/leader replica 必须由 deployment preflight 保证。
- NPU correctness、真实 transfer、fused D2H 和 performance 均未运行，不从 CPU/mock 结果推断。
