# Mooncake Layer Range Transfer 检视记录

本文只记录对以下提交已明确采纳的检视建议：

```text
87c31d1e8926911ea8dae92d8e0ba5f6b47ef9f1
feat(kv_pool): add Mooncake layer range transfer
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
- 修改创建独立 fixup commit，提交标题严格使用
  `#fixup feat(kv_pool): add Mooncake layer range transfer`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 执行状态

- 2026-07-16：两项建议已采纳，尚未实施；等待用户统一修改命令。
- 当前源码 HEAD 为 `a018212f32b057f1bdd75b4cbaccd2b132d2e30b`，已推送到
  `origin/feature/mooncake-layerwise-kv-pool`。
- 采纳前验证：`test_kv_transfer.py` 为 `36 passed`；Ruff 和
  `git show --check 87c31d1e8` 通过。
- Mooncake wheel contract 与 NPU E2E 尚未验证；CPU 单测不能替代真实 ranged
  transfer 集成测试。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. key-major metadata 是否始终保持 key、block ID、buffer、size 和 object offset 对齐。
2. ranged write/read 的非负成功码、负错误码和 result shape 是否按 contract 处理。
3. save 失败是否只 revoke 对应 active key，并确保后续 layer 不再传输失败 key。
4. 最终 layer 是否只 commit active key，并正确清理本地 session tracker。
5. load 失败是否映射到准确的本地 block ID，并保证 layer event 与 queue accounting 收尾。
6. 新增路径是否保持 Memcache flat-GVA 行为，并避免把 save-only 规则误用于 load。

## 已采纳建议

### P1：range save 异常路径必须平衡 request 完成计数

- 检视结论：已采纳，尚未实施。
- 问题：`KVCacheStoreLayerSendingThread._handle_range_request()` 只在正常路径调用
  `dec_stored_request()` 和 `try_finish_and_delete_stored_request()`。当
  `build_addrs()`、同步 event、`batch_copy_put()` 或 batch result shape validation
  抛出异常时，异常分支会 revoke active key，但不会平衡此前由 `save_kv_layer()`
  增加的 `stored_requests` 计数。
- 影响：queue item 虽已调用 `task_done()`，layer finished event 也已设置，但 request
  永远不会进入 sending finished 集合。依赖 `done_sending` 的 delayed-free 路径可能
  因而无法释放对应 KV block；同一 request ID 的 tracker 也会长期残留。
- 设计依据：设计文档 §1.4 要求 KVPool offload 不得阻塞 HBM forward 热路径；§5.5
  将 SendingThread 定义为逐层传输和最终收尾的责任方。异常传输已经结束时，线程必须
  完成本地 request accounting，不能把失败转化为永不完成的本地状态。
- implementation plan：Task 4 步骤 6 明确要求每个出队 item 恰好调用一次
  `task_done()` 并在 `finally` 中设置 layer event，但没有明确写出
  `stored_requests` 必须同样成对收尾；这是计划覆盖缺口，不是与设计冲突。
- 统一修改方案：把每层 request accounting 移到 guaranteed-finalization 路径，并从
  原始 `LayerTransferTask.block_ranges` 获取 request ID，确保 probe 尚未生成
  `LayerRangeReqMeta` 时也能收尾。每次 `add_stored_request()` 必须恰好对应一次
  decrement；失败只表示传输工作结束，不得因此发布成功的 `BlockStored` 事件。
- 新增测试：分别注入 `build_addrs` exception、`batch_copy_put` exception、过短、过长和
  非整数 result；断言 `task_done()` 与 layer event 各完成一次、`stored_requests` 不残留、
  request 进入 transfer-finished 集合，并确认没有发布成功的 `BlockStored` 事件。
- 验证证据：malformed `batch_copy_put` 动态复现后得到
  `stored_requests={'r1': 1}`、`finished_requests=set()`、`unfinished_tasks=0`。

### P2：save key-major batch 必须按 object key 稳定去重

- 检视结论：已采纳，尚未实施。
- 问题：`LayerBatchBuilder._build_key_major_shared()` 会直接累计同一 batch 内所有
  request 的 save key；SendingThread 虽用 `set` 跟踪 active key，随后仍按原始
  `req_meta.keys` 构造 `active_indices`，因此重复 key 会继续进入 ranged write 和最终
  commit。
- 影响：共享 prefix 的多个 request 会对同一 Mooncake object 重复传输，并在同一个
  `batch_commit` 中重复提交相同 key。当前 Mooncake Client/Master 实现可能容忍同 batch
  的重复 `PutEnd`，但 Backend contract 没有承诺重复 key 语义；这还会造成冗余数据传输，
  并使 per-key 失败处理和返回码对齐变得含糊。
- 设计依据：设计文档 §1.2、§2.3 和 §5.5 定义“每个 logical block 对应一个 key”，
  `SharedBlockData.block_keys` 与 `block_ids_arr` 一一对应，SendingThread 末层只 commit
  本批 active key。相同 object key 在 save batch 中应只有一个 writer entry。
- implementation plan：Task 3 规定 key-major 对齐和失败项过滤，Task 4 要求 commit
  全部 active key，但没有覆盖多个 request 共享同一 prefix key 的 batch；这是测试矩阵
  缺口。
- 统一修改方案：仅对 save shared batch 按 object key 保持首次出现顺序去重，并保留与
  所选 key 对应的 block ID。load 侧不得按 key 简单去重，因为同一远端 object 可能需要
  复制到多个不同的本地 block ID。
- 新增测试：构造两个 request 共享同一 full-block key，断言 save 的
  `SharedBlockData`、`batch_copy_put` 和 `batch_commit` 均只包含一次该 key；另加 load
  对照测试，确认相同远端 key 仍能复制到两个本地 block，避免误把 save 去重扩展到 load。
- 验证证据：当前实现动态复现得到
  `shared_keys=['key-1', 'key-1']`，且 `batch_copy_put`、`batch_commit` 收到相同重复列表。
