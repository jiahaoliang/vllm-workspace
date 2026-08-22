# 在 handshake 中发布 semantic tensor map

状态：已被 ADR 0022 取代

后续决策改为沿用穿刺 positional ABI，并把 P/D image、配置和 tuple layout 一致性记录为文档化部署前置条件；本 feature 不实现 deployment gate，见 [ADR 0022](0022-use-the-puncture-positional-handshake-abi.md)。本 ADR 保留为被否决方案的历史记录。

Blockwise DSA PD offload 在 P/D handshake 中显式发布 Main K、Main V、Indexer 和可选 Indexer scale 的 semantic tensor map，并在 ready 前严格校验双方的 role、layer coverage、tensor layout 和 memory kind。Cache tuple 下标只作为 worker 内部适配细节，不构成跨端协议，从而避免 `model_runner_v1` layout 或 P/D 配置差异把正确下标静默解释为错误 tensor。

## 考虑过的方案

- 固定 SFA cache tuple 下标，并校验 tuple 长度、shape 和 dtype。该方案改动较小，但把 connector protocol 绑定到当前隐式 layout，且不同 sparse/C8/offload 组合的 tuple 顺序并不统一。
- 显式 semantic tensor map。该方案增加 handshake metadata 和测试工作，但使协议可自描述，并能在首个请求前拒绝不兼容 layout。

## 结果

- 每个 tensor entry 必须携带足以识别语义、layer、内存位置和 block layout 的 metadata。
- 缺失、重复、未知或不兼容的 semantic role 均导致 handshake fail closed。
- `indexer_scale` 是由模型 layout 决定的可选 role，但 P/D 对其需求必须一致。
- 按 ADR 0017，semantic tensor map 使用独立、versioned 的 Blockwise DSA handshake metadata，与普通 `MooncakeAgentMetadata` 和 scheduler/worker lifecycle metadata 分离。具体 Python class 名和 entry 字段全集仍需后续子决策，但不得退回固定 tuple 下标的跨端 contract。
