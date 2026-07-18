# `add Mooncake ranged layer load` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
29c5f2cfa9089f584d6502fe9daa153cee0f36fc
feat(kv_pool): add Mooncake ranged layer load
```

## 新 commit 检视准备流程

每次开始检视一个新的 commit，必须先依次完成：

1. 将本文还原为只保留通用规则、当前 commit 信息、当前检视范围和空白
   “已采纳建议”的干净状态，移除上一 commit 的范围、结论和实施记录。
2. 在源码仓库中，从当前 feature branch 的目标 commit 建立并切换到独立的临时
   review 分支；分支名使用 `review/<commit-topic>`，便于隔离和定位本轮检视。
3. 依据下述优先级自行完成第一轮代码检视，逐部分向用户详细说明每个变更的作用、
   行为影响及其设计来源，并单独列出发现；只有用户明确表示“采纳”或“纳入”后，
   才将对应建议写入本文。

临时 review 分支只用于检视和后续显式要求的 fixup，不更新
`workspace.lock.json`；结束本轮检视或切换到下一 commit 时，按用户指令清理。

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
- 修改创建独立 fixup commit，提交标题严格使用
  `#fixup feat(kv_pool): add Mooncake ranged layer load`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. ranged load 是否按每个 layer 只读取该层 K/V range，并保持 key、buffer、size、
   source offset 严格对齐。
2. 单 key load 失败、返回 shape/type 错误和 backend 异常是否按设计更新 invalid block，
   同时保证 layer completion 不会阻塞后续计算。
3. 多层 load 是否复用同一份 shared metadata，且每层地址与 offset 均正确。
4. session 收尾是否与 ranged save、worker 共享 invalid-block 状态和 exception-safe
   completion 约定一致。
5. 新路径是否不改变 Memcache、Yuanrong 和非 layerwise 路径的既有行为。

## 已采纳建议

### P1：按 transfer row 而不是 remote key 跟踪 ranged-load active 状态

- 检视结论：已采纳，尚未修改源码。
- 问题：`KVCacheStoreLayerRecvingThread` 当前使用 `_active_load_keys: set[str]`
  和 `_active_load_blocks: dict[str, set[int]]` 跨层跟踪 load 状态。同一个 remote
  key 被读取到多个本地 block 时，任一 entry 返回负数都会将该 key 对应的全部本地
  block 标记为 invalid，并停止这些 block 的后续 layer read。
- 实际 contract：Mooncake `Client::BatchTransferReadRanges` 按 batch entry 分别提交和
  等待 transfer，返回 per-entry bytes 或 `ErrorCode`；`RealClient` 将普通 transfer
  error 只写回原始 input index，并不删除 `get_sessions_[key]`。只有 lease expiry 等
  明确路径删除整个 key session。因此负返回值本身只证明当前 destination entry 失败，
  不能统一解释为整个 key/session 失效。
- 风险：例如 `keys=["shared-key", "shared-key"]`、`block_ids=[3, 4]`、
  `results=[96, TRANSFER_FAIL]` 时，block 3 已成功且 session 仍有效，当前实现却会把
  block 3、4 都加入 `_invalid_block_ids`，造成不必要的重计算并跳过 block 3 的后续层。
- 设计依据：设计文档 §4.3 要求 `keys[i]`、buffers、sizes、offsets 和返回结果按
  index 一一对应；§5.5 要求 `SharedBlockData.block_keys` 与 `block_ids_arr` 对齐。
  implementation plan D02 和 Task 4 步骤 5 进一步要求 ranged-read 失败映射到准确的
  本地 block ID。Mooncake 最新 PR #2881 head `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`
  的实际实现消除了 duplicate-key 失败粒度的歧义。
- 统一修改方案：用 `_active_load_indices: set[int] | None` 维护 shared key-major
  metadata 中仍 active 的 row；每层使用同一组 index 过滤 keys、buffers、sizes 和
  offsets。返回负数时，通过 filtered result index 映射回原始 row，只标记对应
  `req_meta.block_ids[index]` 并移除该 row。最终 layer 或整批 abort 后清理 row 状态。
  不根据 Mooncake error code 主动执行 key-wide fan-out；若 session 确实失效，Mooncake
  会让该 key 的其他 entries 自然返回负数。
- 测试要求：增加两层 duplicate-key 部分失败测试，第一层返回 `[96, -1]`，断言只
  标记第二个 block invalid，第二层仍传输第一个 row，并校验其 key、buffer、size、
  offset 全部对齐；再覆盖两个 entries 均失败时两个 block 都被过滤。现有 malformed
  result 和 backend exception 仍按整批 abort，不改变 session cleanup ownership、
  Memcache GVA 路径或非 layerwise 行为。
