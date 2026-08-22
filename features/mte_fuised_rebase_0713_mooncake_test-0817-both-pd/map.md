# Blockwise DSA PD Offload Map

## Notes

- Delivery contract: [spec.md](spec.md)
- Architecture: [blockwise-dsa-pd-offload-design.md](blockwise-dsa-pd-offload-design.md) and [accepted ADRs](docs/adr/)
- Source commit: vLLM-Ascend `f826ea3f354f87cdf95895addbdaaad6ca92dd7c`
- Validation: [CPU/mock validated](cpu-mock-validation-report.md); NPU `planned / not run`

## Decisions-so-far

- [01](issues/01-blockwise-dsa-opt-in-control-plane.md): opt-in control plane、typed lifecycle contract 与 default V1 isolation 已完成。
- [02](issues/02-positional-data-plane-main-reservation.md): positional data plane、per-TP Host Main registration、lifetime reservation 与 HOL admission 已完成。
- [03](issues/03-phase-a-request-lifecycle.md): fixed-leader Indexer D2D -> Main D2RH、basic failure replay 与 Phase A 已完成。
- [04](issues/04-exact-tp-lifecycle-fused-d2h.md): exact TP aggregation、typed result boundaries 与 fused D2H validity 已完成。
- [05](issues/05-all-tp-transfer-failure-recovery.md): mixed TP failure barrier、all-TP validity reset 与 full replay 已完成。
- [06](issues/06-preemption-cancellation-ownership-recovery.md): preemption evidence、Main reuse/fallback 与 cancellation drain-and-ack 已完成。
- [07](issues/07-phase-b-validation-npu-plan.md): Phase B、default V1 regression、CPU/mock report 与 8-case NPU plan 已完成。

## Fog

- GitCode HTTPS credential 不可用，vLLM-Ascend commit 尚未 push；新 lock 暂不可跨机器 restore。
- `./scripts/lock-repos.sh` 当前不能把 control branch `feature/<name>` 映射到 `features/<name>`；本轮只记录失败并手工刷新 lock，未在 feature branch 修改公共脚本。
- Positional ABI 不提供跨 P/D semantic compatibility proof；image/configuration/layout/leader replica 必须由 deployment preflight 保证。
- NPU correctness、真实 transfer、fused D2H 和 performance 均未运行，不从 CPU/mock 结果推断。
