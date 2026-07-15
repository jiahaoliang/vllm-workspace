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

### P1：保持 `SharedBlockData` 对现有 memcache 构造点兼容

- 检视结论：采纳。
- 问题：`a0f00eec4` 为 `SharedBlockData` 新增无默认值的必填字段
  `block_keys`，但同一提交中 `LayerBatchBuilder.build_shared()` 的既有 memcache
  构造点没有传入该字段。该提交单独运行时会抛出：

  ```text
  TypeError: SharedBlockData.__init__() missing 1 required positional argument: 'block_keys'
  ```

- 影响：现有 memcache block-key layerwise 路径在构建 shared metadata 时失败；后续
  `517d796f2` 虽然显式补入 `block_keys=None`，但不能消除 `a0f00eec4` 本身引入的
  提交级回归。
- 设计依据：设计文档 §5.5 明确要求 `SharedBlockData` 保持双轨：memcache 使用
  `block_gvas_arr`，Mooncake 使用 `block_keys`。新增 Mooncake metadata 不应破坏
  memcache flat-GVA 路径。
- implementation plan：Task 3 要求扩展 `SharedBlockData`，但没有要求同步更新已有
  memcache 构造点，也没有覆盖该兼容性回归；这是计划覆盖缺口，不是与设计冲突。
- 统一修改方案：在 `a0f00eec4` 中让 `block_keys` 默认取 `None`，保持既有构造调用
  兼容；后续 range commit 仍可为 Mooncake 显式传入 key list。补充调用真实
  `LayerBatchBuilder.build_shared()` 的 memcache 回归测试，避免只测试 dataclass 字段。
- 验证证据：在 `a0f00eec4` detached worktree 中，相关四个测试文件为
  `178 passed`，但上述最小构造复现稳定失败，证明现有测试没有覆盖生产构造点。

### P2：区分 Mooncake `batch_is_exist` 的 miss 与错误状态

- 检视结论：采纳。
- 问题：`_get_block_key_layerwise_hit_tokens()` 只判断结果是否为 `1`，并把其他所有
  状态都作为 prefix miss 截断。Mooncake Python API 的 contract 是
  `1=exists`、`0=not exists`、`-1=error`，因此 `-1` 会被静默吞成普通 miss。
- 影响：Master RPC 或 Client 故障被隐藏，scheduler 无法区分正常 cache miss 与后端
  错误；同文件旧的 store lookup 路径则会对既不是 `1` 也不是 `0` 的状态抛错。
- 设计依据：设计文档 §5.6 要求 Mooncake scheduler 通过 `batch_is_exist` 判定 hit，
  PROCESSING object 不可见；§5.4 同时要求 Backend 透传负错误码。因此只有 `0` 应
  作为不可见或 miss，负错误码不能被当作正常 miss。
- implementation plan：Task 2 仅要求覆盖 COMPLETE、PROCESSING/miss 和 result
  length mismatch，没有覆盖 Mooncake `batch_is_exist=-1`；这是计划测试矩阵的缺口，
  不改变设计优先级。
- 统一修改方案：Mooncake 分支只把 `0` 当作 miss；任何负数或其他非法状态均抛出包含
  request 和状态值的明确错误。将现有使用未定义状态 `2` 的测试改为真实语义，并新增
  `-1` 回归测试。
- 验证证据：Mooncake 本地 Python API 文档明确声明
  `List[int]` 返回值为 `1=exists, 0=not exists, -1=error`。
