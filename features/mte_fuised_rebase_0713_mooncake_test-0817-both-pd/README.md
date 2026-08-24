# Blockwise DSA PD Offload

本 feature 为 `MooncakeConnectorV1` 增加显式 opt-in 的 Blockwise DSA PD offload mode：Prefill 保持 request-level block transfer，Decode 将 Indexer 放在 HBM、将 Main K/V 放在 per-TP local Swapped Main pool，并提供 lifetime reservation、exact TP lifecycle、failure replay、preemption、cancellation 与 fused D2H ownership contract。

当前 production tree 是已发布的 vLLM-Ascend replacement commit `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`。实现收敛为既有 `MooncakeConnectorV1`、一个 typed DSA metadata module 和 thin SFA scheduler extension，不包含旧 `60eb76e` 的 standalone DSA subsystem。

Static、focused DSA/SFA、完整 connector/default V1 和排除已知 baseline-broken 文件后的 broad CPU/mock regression 已通过。完整 CPU/mock root 为 `241 passed / 5 pre-existing failures`；五项均来自未修改测试文件的缺失 import。NPU runtime 未执行，所有 mandatory case 保持 `planned / not run`。

## 文档入口

- [Spec](spec.md)
- [Design](blockwise-dsa-pd-offload-design.md)
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
