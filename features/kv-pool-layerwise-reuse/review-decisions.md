# `build Mooncake layer range batches` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
21bd87100c925eab72ab95bf8ac1fb14a0bb7b2d
feat(kv_pool): build Mooncake layer range batches
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
  `#fixup feat(kv_pool): build Mooncake layer range batches`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. `SharedBlockData` 是否明确区分 Memcache flat-GVA metadata 与 Mooncake
   key-major metadata，并保持原有 Memcache 路径行为。
2. `LayerBatchBuilder` 是否始终保持 object key、local block ID、buffer address、
   transfer size 和 object offset 对齐。
3. `None` key 的过滤是否同步作用于所有对齐字段，不会造成 key 与 block 错配。
4. K/V 等多段 cache buffer 是否使用正确的本地 stride、layer 内偏移和
   `layer_id * page_size` 对象偏移。
5. save batch 与 load batch 是否保留各自需要的重复 key 语义，不会错误丢失目标
   local block。
6. 新增测试是否覆盖 key-major batch 的结构、跨 layer offset、过滤与多 buffer
   对齐，而不是只验证理想的单 key、单 buffer 路径。

## 已采纳建议

### P2：补充同一 shared metadata 的跨层 range-batch 测试

- 检视结论：已采纳并实施，fixup commit 已折叠到原提交。
- 问题：implementation plan 要求 key-major metadata 与 offset 测试“至少覆盖
  两层”，但提交中的 `_build()` 将 `LayerTransferTask.layer_id` 固定为 `2`，新增的
  key-major 正常路径与 `None` key 过滤测试均只验证 layer 2。
- 影响：现有测试验证了非零 object offset，却没有证明同一份跨层不变的
  `SharedBlockData` 能在不同 `layer_id` 下生成对应层的 local buffer address、size 和
  object offset。若后续改动错误地复用某一层的 base address、stride 或 offset，当前
  测试不一定能发现。
- 设计依据：设计文档 §5.5 规定 `build_shared` 预计算跨层不变的 block metadata，
  `build_addrs(layer_id)` 再按层计算本地 address/size；Mooncake object offset 必须为
  `layer_id * page_size_bytes + layer_inner_offset[j]`。
- implementation plan：Task 3 步骤 1 明确要求两个 block、每层两个 cache segment，
  并至少覆盖两层；当前测试只覆盖其中的 layer 2，未完整满足该测试要求。
- 统一修改方案：构造一次 key-major `SharedBlockData`，至少分别调用
  `build_addrs(shared, 0)` 与 `build_addrs(shared, 2)`；断言两层保持相同的 key/block
  对齐和 `[2][2]` 嵌套 shape，同时分别得到各层正确的 local buffer address 和
  object offset（layer 0 为 `[0, 64]`，layer 2 为 `[192, 256]`）。保留现有
  `None` key 同步过滤测试。
- 实施归属：`21bd87100 feat(kv_pool): build Mooncake layer range batches`。
- 实施结果：原 fixup `6bb780019` 已折叠；新增同一份 `SharedBlockData` 分别构建
  layer 0 与 layer 2 range batch 的测试，验证两层 key/block/size 对齐，以及各自的
  local buffer address 和 object offset。
- rebase 结果：后续提交已重放，feature 分支最终 HEAD 为 `8cfd1e22f`，并已用精确
  `--force-with-lease` 推送到 `origin/feature/mooncake-layerwise-kv-pool`。
- 验证结果：完整 AscendStore CPU suite 为 `362 passed`；相关 Ruff check、Ruff
  format check、整段 `git diff --check` 和全部 6 个重写 commit 的
  `git show --check` 均通过；range-diff 证明后续 5 个 commit 内容未漂移。
