# 使用固定 TP leader 作为完整 replica source

状态：部分被 [ADR 0031](0031-use-exact-prefill-dcp-shards-for-main.md) 取代

Blockwise DSA PD offload 最初沿用穿刺 connector 的 TP coverage：要求 `P_TP % D_TP == 0`，将 Prefill TP 连续分组，并由每组首个 rank 作为对应 Decode TP 的唯一 payload source。Indexer、可选 Indexer scale、Main K 和 Main V 共用该 leader；其他组内 rank 不发送 payload。这个选择避免首版实现多 P shard 拼装和多 writer destination，但要求 leader 持有完整 replica，并比普通 `MooncakeConnectorV1` 增加更严格的整除约束。

ADR 0031 保留 Indexer 的 fixed replica leader，但在 Prefill `DCP>1` 时用 exact Prefill DCP source group 拼装 Main；本 ADR 对 Main 完整 leader replica 与禁止 multi-P shard assembly 的决定不再适用。`DCP=1` 仍完全沿用本 ADR。

## 结果

- `ratio = P_TP / D_TP`，`source(D_j) = P_(j * ratio)`。
- 按 [ADR 0022](0022-use-the-puncture-positional-handshake-abi.md)，connector handshake 不再验证 leader coverage 和完整 replica placement；该 placement 是文档化部署前置条件，执行它的 deployment system 不在本 feature 范围内。不支持的 sharded layout 属于可能 silent corruption 的 unsupported configuration。
- 不使用普通 Mooncake 的 request-hash replica selection，source leader 对同一拓扑是确定的。
- 每个 request 只使用实际处理它的 P DP replica，不跨 P DP 混合 tensor。
- 多P shard拼装已由ADR 0031重新决策；非整除拓扑或dynamic replica selection仍需新的ADR。
