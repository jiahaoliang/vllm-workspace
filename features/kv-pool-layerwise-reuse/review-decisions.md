# Mooncake Layerwise Metadata 检视记录

本文只记录对以下提交已明确采纳的检视建议：

```text
a0f00eec47a28c393d629c4c2122595726f058b6
feat(kv_pool): add Mooncake layerwise metadata
```

## 检视依据与优先级

每一项代码检视必须按以下顺序查证：

1. 首先参考
   `features/kv-pool-layerwise-reuse/references/snapshots/design-mooncake-layerwise-gva-put.md`。
   该设计文档是功能语义、架构边界和生命周期要求的最高优先级依据。
2. 其次参考
   `features/kv-pool-layerwise-reuse/implementation-plan.md`，用于核对实施步骤、
   测试要求和已记录的落地决策。
3. 当设计文档与 implementation plan 存在冲突时，以设计文档为准。不得仅因实现
   符合 implementation plan，就忽略它与设计文档的偏差。
4. 记录已采纳建议时，应注明对应的设计文档依据；如果涉及冲突，还应同时注明
   implementation plan 中的冲突内容及最终采用设计文档的原因。

## 检视处理规则

- 检视过程中先分析代码和验证事实；只有用户明确表示“采纳”或“纳入”后，才把
  对应建议记录到本文。
- 检视期间只记录已采纳建议，不逐条修改源码。
- 只有收到用户明确的“统一修改”或“执行”命令后，才集中实现本文中的建议。
- 修改按所属原提交创建独立 fixup commit，提交标题严格使用
  `#fixup feat(kv_pool): add Mooncake layerwise metadata`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`
- `tests/ut/distributed/ascend_store/test_config_data.py`
- `tests/ut/distributed/ascend_store/test_ascend_store_connector.py`
- `tests/ut/distributed/ascend_store/test_pool_scheduler.py`

重点检视：

1. Mooncake key 是否稳定规范化为 `model@block_hash@tp_rank`。
2. Mooncake layerwise 模式是否拒绝 `PP`、`PCP`、`DCP` 大于 1，同时保留
   `TP` 支持。
3. scheduler 是否只有在同一 block 的全部保存 `TP rank` key 均存在时才判定命中。
4. 新增 metadata 是否保持 Memcache、Yuanrong 和非 layerwise 路径的原有行为。
5. 测试是否覆盖边界条件和失败路径，而非只复述实现细节。

## 已采纳建议

当前没有已采纳建议。
