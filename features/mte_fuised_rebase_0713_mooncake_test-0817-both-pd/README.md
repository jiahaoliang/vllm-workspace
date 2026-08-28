# Blockwise DSA PD Offload

本 feature 为 `MooncakeConnectorV1` 增加显式 opt-in 的 Blockwise DSA PD offload mode：Prefill 保持 request-level block transfer，Decode 将 Indexer 放在 HBM、将 Main K/V 放在 per-TP local Swapped Main pool，并提供 lifetime reservation、exact TP lifecycle、failure replay、preemption、cancellation 与 fused D2H ownership contract。

当前 production tree 是已发布的 vLLM-Ascend commit `117637d205603b0c1e43aa0ea3e141de926ff3b1`。实现收敛为既有 `MooncakeConnectorV1`、一个 typed DSA metadata module 和 thin SFA scheduler extension，不包含旧 `60eb76e` 的 standalone DSA subsystem；`59fd10b0d` 追加了 glm-5.1/glm5.2 NPU E2E 中发现的 runtime fixes，后续提交补齐 E2E 分析。

2026-08-26 批准的 async scheduling delta 已实现并通过 GitCode reporter CPU/mock happy-path gate，目标 contract 见 [spec](spec.md) 与 ADR 0024-0030。完整 failure/lifecycle matrix仍为“未测试”。

既有sync replacement的static、focused DSA/SFA、完整connector/default V1和排除已知baseline-broken文件后的broad CPU/mock regression已通过。完整CPU/mock root为`241 passed / 5 pre-existing failures`；五项均来自未修改测试文件的缺失import。Origin 分支记录的 glm-5.1/glm5.2 NPU 冒烟、长请求和约 4k 输入并发 E2E 已通过；这不等于旧 8-case plan 全部完成，且本 workspace 未重跑 NPU。Graph-capture、完整 failure/lifecycle matrix 与未记录的 plan cases 仍未验证。

## 文档入口

- [Spec](spec.md)
- [Sync replacement historical design](blockwise-dsa-pd-offload-design.md)
- [Domain context](CONTEXT.md)
- [Issue map](map.md)
- [Current status](status.md)
- [CPU/mock validation report](cpu-mock-validation-report.md)
- [NPU E2E test plan](npu-e2e-test-plan.md)
- [Repo state](repo-state.md)
- [Replacement goal](reimplementation-goal.md)
- [Final ordering/budget gate](reimplementation-whitebox-ordering-budget-amendment.md)
- [Sync log](sync-log.md)

实现位于独立源码仓库的 `feature/blockwise-dsa-mooncake-v1-reimplementation` 分支；标准恢复路径仍为 `repos/vllm-ascend`，源码不提交到 control repo。跨 P/D positional ABI compatibility 是 deployment precondition，不是 connector 已证明的 semantic compatibility。
