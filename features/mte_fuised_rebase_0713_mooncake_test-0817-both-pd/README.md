# Blockwise DSA PD Offload

本 feature 为 `MooncakeConnectorV1` 增加显式 opt-in 的 Blockwise DSA PD offload mode：Prefill 保持 request-level block transfer，Decode 将 Indexer 放在 HBM、将 Main K/V 放在 per-TP local Swapped Main pool，并提供 lifetime reservation、exact TP lifecycle、failure replay、preemption、cancellation 与 fused D2H ownership contract。

当前 production tree 是 vLLM-Ascend commit `f826ea3f354f87cdf95895addbdaaad6ca92dd7c`。Static、Phase A、Phase B 和 default V1 regression 已通过，状态为 `CPU/mock validated`。NPU runtime 未执行，所有 mandatory case 保持 `planned / not run`。

## 文档入口

- [Spec](spec.md)
- [Design](blockwise-dsa-pd-offload-design.md)
- [Domain context](CONTEXT.md)
- [Issue map](map.md)
- [Current status](status.md)
- [CPU/mock validation report](cpu-mock-validation-report.md)
- [NPU E2E test plan](npu-e2e-test-plan.md)
- [Repo state](repo-state.md)
- [Sync log](sync-log.md)

实现位于独立源码仓库 `repos/vllm-ascend`，不提交到 control repo。跨 P/D positional ABI compatibility 是 deployment precondition，不是 connector 已证明的 semantic compatibility。
