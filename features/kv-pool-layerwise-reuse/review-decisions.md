# Mooncake Layerwise Metadata 检视记录

本文只记录对以下提交已明确采纳的检视建议：

```text
a0f00eec47a28c393d629c4c2122595726f058b6
feat(kv_pool): add Mooncake layerwise metadata
```

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
