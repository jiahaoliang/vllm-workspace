# Mooncake Layerwise Metadata 检视记录

本文记录对以下提交已明确采纳并完成实施的检视建议：

```text
6cff8ea86158c69ee32715815af833572922e214
feat(kv_pool): add Mooncake layerwise metadata
```

该提交由检视时的 `a0f00eec47a28c393d629c4c2122595726f058b6`
经 fixup rebase 重写而来。

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

## 执行状态

- 2026-07-15：本文三项建议均已实施。
- metadata 兼容性调整已折叠到 `6cff8ea86`。
- scheduler/worker 同步激活及错误状态处理已折叠到 `0a9b787f5`。
- 最终源码 HEAD 为 `1143c6470624e8e7d820a841c88117f9df36aebc`，已使用
  `--force-with-lease` 推送到 `origin/feature/mooncake-layerwise-kv-pool`。
- 最终 HEAD 验证：AscendStore CPU 单测 `353 passed`；Ruff、整段
  `git diff --check` 以及六个提交的 `git show --check` 均通过。

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

- 检视结论：已采纳并实施。
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

- 检视结论：已采纳并实施。
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

### P1：Mooncake block-key 路径必须在 scheduler 与 worker 同步激活

- 检视结论：已采纳并实施。
- 问题：`a0f00eec4` 已让 connector 和 scheduler 将 Mooncake 识别为
  `use_block_key_layerwise`，scheduler 因而改用带 rank 后缀的 per-block key 查询；
  但该提交没有修改 `pool_worker.py`。同一历史点的 worker 仍只在 memcache 下设置
  `use_gva_layerwise`，Mooncake 继续选择旧的 `KVCacheStoreKeyLayer*Thread`。
- 影响：scheduler 按每个 logical block 一个 key 判定命中，worker 却按每个 block 的
  每一层一个 key 传输，双方使用不同对象模型。后续 `532fbc76a` 已补齐 worker 和
  session 编排，但不能使 `a0f00eec4` 成为可独立运行的提交。
- 设计依据：设计文档 §5.1 明确要求 connector、scheduler、worker 三处同步使用
  `use_block_key_layerwise`；§2.3 要求 scheduler 与 saving worker 使用相同的
  `head_or_tp_rank` key schema。
- implementation plan：Task 2 将 `pool_worker.py` 列入修改范围，并要求
  `make_layerwise_block_key` 与 `use_block_key_layerwise` 贯穿 connector、scheduler、
  worker。实际拆分遗漏了 worker，属于实施偏离计划；与设计文档不存在冲突。
- 统一修改方案：`a0f00eec4` 只保留规范 key helper 和纯 metadata 定义；将 Mooncake
  block-key scheduler 分支、topology gate 的实际激活及其行为测试移动到 worker 的
  session/range 路径已经同时可用的原提交。不要仅把 thread 选择提前，因为缺少 session
  preparation 和 ranged transfer 时仍不可运行。
- fixup 归属：移出 `a0f00eec4` 的部分使用
  `#fixup feat(kv_pool): add Mooncake layerwise metadata`；移入 worker 编排提交的部分使用
  `#fixup feat(kv_pool): orchestrate Mooncake layerwise sessions`。两者保持独立，等待用户
  明确要求 rebase 后再分别折叠。
- 测试要求：新增同一配置下 scheduler/worker gate 一致性测试，并覆盖
  Mooncake MLA、Mooncake GQA、memcache、Yuanrong 和 `use_layerwise=false` 的 thread
  family/path matrix。
- 验证证据：在 `a0f00eec4` detached worktree 上，三个直接相关测试文件为
  `143 passed`，额外 key/gate/topology/MLA 矩阵通过；静态调用链仍确认 Mooncake
  scheduler 使用 block-key，而 worker 使用 KeyLayer thread，现有测试未覆盖该跨组件
  不一致。
