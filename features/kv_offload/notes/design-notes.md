# kv_offload Design Notes

## 初始设计关注点

- `vllm` 侧：KV cache manager、scheduler、KVConnector、attention metadata。
- `vllm-ascend` 侧：Mooncake PD、SFA offload、Ascend attention backend、GLM sparse 路径。
- `Mooncake` 侧：传输后端与 KV cache 传输语义，默认只读。

本文件记录本地设计推演；外部资料原文快照放在 `references/snapshots/`。
