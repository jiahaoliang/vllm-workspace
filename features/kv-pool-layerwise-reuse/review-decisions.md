# `add Mooncake ranged layer save` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
a3611520dfd204ab6349637680fb43235513bc03
feat(kv_pool): add Mooncake ranged layer save
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
  `#fixup feat(kv_pool): add Mooncake ranged layer save`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. ranged save 是否只对 active key 调用 `batch_copy_put`，并保持 key、buffer、size、
   offset 和返回结果严格对齐。
2. 单 key ranged write 失败是否只 revoke 对应 key，并在后续 layer 中稳定过滤该 key。
3. 最终 layer 是否只 commit 仍 active 的 key；commit 失败与 malformed result 是否
   完成本地 tracker 清理及 best-effort revoke。
4. 重复 save key 是否只写入和收尾一次，同时不改变 load batch、Memcache、Yuanrong
   和非 layerwise 路径的既有行为。
5. 测试是否覆盖正常多层保存、部分失败、返回 shape/type 错误、commit/revoke 失败、
   重复 key，以及异常安全的 layer completion。

## 已采纳建议

### P2：验证 active subset 的 key-major 数据数组仍严格对齐

- 检视结论：已采纳并实施，fixup 已折叠到原提交。
- 问题：`_handle_range_request()` 使用同一组 `active_indices` 过滤 keys、buffers、
  sizes 和 offsets，当前实现正确；但两层部分失败测试只断言第二层发送的 key 是
  `key-1`，没有断言该调用中的 `all_buffers`、`all_sizes` 和 `all_offsets` 同样来自
  `key-1` 的原始 index。
- 风险：将来若 key 与三组嵌套数组的过滤索引发生错位，测试仍可能通过，却会向正确的
  key 写入另一个 block 的 K/V 数据。
- 设计依据：设计文档 §5.5 定义 key-major 的逐项对应关系：`keys[i]`、
  `all_buffers[i][j]`、`all_sizes[i][j]` 和 `all_dst_offsets[i][j]` 必须来自同一个
  logical block。implementation plan Task 4 步骤 1 也要求 put-start 部分失败后仍保持
  key/block/buffer 对齐。
- 统一修改方案：扩展两层部分 ranged-write 失败测试，断言第二层
  `batch_copy_put` 的 key、buffer、size 和 offset 均是原始 `key-1` 的同一 index；
  不只断言过滤后的 key 列表。

### P2：覆盖 commit/revoke 的异常及 malformed result 收尾

- 检视结论：已采纳并实施，fixup 已折叠到原提交。
- 问题：现有测试覆盖了 `batch_copy_put` 的过短、过长和非整数 result，以及 commit
  返回单项失败；但没有覆盖 `batch_commit` 或 `batch_revoke` 抛异常、返回过短/过长或
  非整数 result 的路径。
- 风险：这些分支依赖 `_revoke_range_keys()` 的 `finally` 清理
  `_put_started_keys`。没有测试时，修改异常处理或 result-shape guard 很容易重新造成
  tracker 残留，永久抑制同一 key 的后续 `batch_put_start`。
- 设计依据：设计文档 §3 要求 `end`/`revoke` 后从进程级 `_put_started_keys` 移除；
  implementation plan Task 4 步骤 1、4 明确要求所有 `list[int]` API 的 shape error
  中止并清理受影响 batch，且 commit/revoke shape error 不得对未经验证的结果使用
  `zip`。
- 统一修改方案：为 commit result 的异常与三类 malformed result 添加参数化测试，
  断言全部 active key 被 best-effort revoke 且 tracker 清空；为 revoke 的异常与三类
  malformed result 添加参数化测试，断言请求完成、layer event 释放、无异常传播，并且
  已尝试 key 从 tracker 移除。

### P3：为 `_handle_range_request()` 的状态机补充必要注释

- 检视结论：已采纳并实施，fixup 已折叠到原提交。
- 问题：该方法包含跨层 active-set 初始化、按层过滤、单 key revoke、最终 commit 和
  tracker 清理五个阶段，但没有解释 `_active_put_keys` 与 `_put_started_keys` 的不同
  生命周期，也没有说明异常时仍移除本地 tracker 的原因。
- 风险：维护者可能将 `_active_put_keys` 误当作进程级 put-start 去重表，或将 revoke
  失败时的本地移除改为“仅远端成功后移除”，导致后续 save 永久跳过 key。
- 设计依据：设计文档 §3 明确区分本批 `active_keys` 与跨 step 的
  `_put_started_keys`；implementation plan D09 和 Task 4 步骤 4 定义了它们的状态机及
  tracker invariant。
- 统一修改方案：在 active set 初始化、负数 ranged-write 处理、最终 commit 和
  `_revoke_range_keys()` 的本地清理处加入简短注释，说明本批生命周期、后续 layer
  过滤，以及“尝试收尾后即清 tracker、未关闭远端 session 交由 Master timeout”的理由。

## 实施结果

- 原 fixup：`d53c64768 #fixup feat(kv_pool): add Mooncake ranged layer save`，
  已折叠为 `a3611520d feat(kv_pool): add Mooncake ranged layer save`。
- 新增 active subset payload 对齐断言，以及 commit/revoke 抛异常、过短、过长和
  非整数 result 的回归测试；为 ranged save 状态机补充生命周期注释。
- `py_compile`、Ruff 和 `git diff --check` 通过。
- 精确 pytest 仍无法在此 Windows CPU 环境中完成 collection：正常 conftest 依赖
  Ascend build 生成的 `_build_info`，隔离 conftest 后又暴露既有 `_mock_deps.py` 的
  `zmq` stub 缺少 vLLM v0.24.0 所需 `zmq.asyncio`。此问题与本 fixup 无关，未对
  mock 基线作无关修复。
- rebase 后后续提交依次重写为：`29c5f2cfa feat(kv_pool): add Mooncake ranged
  layer load`、`54e6684f1 feat(kv_pool): orchestrate Mooncake layerwise sessions`、
  `8bf9ac9c3 docs(kv_pool): document Mooncake layerwise backend`。最终源码 HEAD 为
  `8bf9ac9c3`，临时 `review/mooncake-ranged-layer-save` 分支已删除。
- 最终源码 HEAD `8bf9ac9c34397b2fd4ab1c21c1e6965b5a55eb0b` 已使用针对旧远端
  `1d56db71e19130ddb4c22e23f21f76756c3d6295` 的精确 `--force-with-lease`
  推送到 `origin/feature/mooncake-layerwise-kv-pool`。
