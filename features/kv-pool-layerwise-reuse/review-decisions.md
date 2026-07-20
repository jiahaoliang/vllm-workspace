# `support Mooncake chunked prefill sessions` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
e5989049e9cb27f218b52b8e03af8e5dc841ac74
feat(kv_pool): support Mooncake chunked prefill sessions
```

## 新 commit 检视准备流程

每次开始检视一个新的 commit，必须先依次完成：

1. 将本文还原为只保留通用规则、当前 commit 信息、当前检视范围和空白
   “已采纳建议”的干净状态，移除上一 commit 的范围、结论和实施记录。
2. 在源码仓库中，从目标 commit 建立并切换到独立的临时 review 分支；分支名使用
   `review/<commit-topic>`，便于隔离和定位本轮检视。
3. 依据下述优先级自行完成第一轮代码检视，逐部分向用户详细说明每个变更的作用、
   行为影响及其设计来源，并单独列出 findings；只有用户明确表示“采纳”或“纳入”后，
   才将对应建议写入本文。

临时 review 分支只用于检视和后续显式要求的 fixup，不更新
`workspace.lock.json`；结束本轮检视或切换到下一 commit 时，按用户指令清理。

## 检视依据与优先级

每一项代码检视必须按以下顺序查证：

1. 首先参考
   `features/kv-pool-layerwise-reuse/references/snapshots/design-mooncake-layerwise-gva-put.md`。
   该设计文档是功能语义、架构边界和生命周期要求的最高优先级依据。
2. 其次参考 `features/kv-pool-layerwise-reuse/implementation-plan.md`，用于核对实施
   步骤、测试要求和已记录的落地决策。
3. 当两者冲突时，以设计文档为准。不得仅因实现符合 implementation plan，就忽略
   它与设计文档的偏差。
4. finding 必须说明代码证据、影响、严重级别和设计依据；无法由设计文档直接推出的
   建议，应明确标为代码正确性、兼容性或测试充分性判断。

## UT 环境规则

- CPU UT 必须使用专用 venv
  `C:\Users\l30034596\.venvs\vllm-ascend-cpu-tests-py314`，不得使用系统 `python`。
- 检视报告必须区分 venv UT、静态检查以及未执行的 NPU/E2E 验证。
- Windows CPU 环境需要测试 bootstrap 时，应复用已验证的真实 `torch`、`zmq` 和
  `zmq.asyncio` 导入，只对缺失的 Ascend 运行时依赖做最小 stub。
- 不得把环境依赖缺失记为源码测试失败，也不得把 CPU mock UT 通过描述为真实
  Mooncake wheel 或 NPU E2E 已验证。

## 检视处理规则

- 本轮先分析代码和验证事实，不逐条修改源码。
- 只有用户明确表示“采纳”或“纳入”后，才把对应建议记录到本文。
- 只有收到用户明确的“统一修改”或“执行”命令后，才集中实现全部已采纳建议。
- 修改创建独立 GitExtensions-style fixup commit，提交标题严格使用
  `#fixup feat(kv_pool): support Mooncake chunked prefill sessions`。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。
- 本 commit 新增或显著改写的连续逻辑超过 40 行时，必须保留原有有效注释，并在
  阶段边界补充必要注释，说明状态不变量、失败处理和 ownership；不添加逐行复述
  代码的无效注释。
- 重构、改名或 backend 泛化不得无故删除原源码中仍然有效的注释。若代码结构或职责
  已改变，应迁移并准确改写注释；只有注释已经失效时才可删除，并以当前语义说明替代。
- 不因本轮 review 执行无关的整文件格式化或重构。

## 检视范围

临时 review 分支（rebase 后已删除）：`review/mooncake-chunked-prefill-sessions`

- `docs/source/user_guide/feature_guide/layerwise_kv_pool.md`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py`
- `tests/ut/distributed/ascend_store/test_pool_worker.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. Worker 是否正确维护 `req_id -> accumulated load keys`、pending put ownership 和
   `key -> active request owners`，且状态转换具有单一、明确的 owner。
2. 每个 chunk 是否只对累计且仍需要的 keys 调用 `batch_get_start` 续租，并将失败精确
   映射回对应 block，避免加载已失效数据。
3. SendingThread 是否只把成功 `batch_put_end` 的 keys 提升为后续 chunk 的 load keys，
   失败、异常和 revoke 路径是否清理 pending ownership。
4. 中间 chunk 是否保留 active owner；last chunk、preempt、finished 和 abort 是否统一
   释放 request owner；共享 key 是否只在最后一个 owner 完成后调用 `batch_get_end`。
5. receiver abort 后是否释放 active owner但保留 desired keys 供后续 chunk 重试，并
   保证 repeated cleanup、并发完成和异常路径不会泄漏或过早结束 session。
6. Memcache、Yuanrong、非 block-key layerwise 和非 Chunked Prefill 路径是否保持原行为。
7. UT 是否覆盖共享 key mixed-lastness、多 chunk lease renewal、put promotion、失败重试、
   preempt/finished/abort 和 cleanup 幂等；文档是否准确区分 CPU UT 与真实 NPU E2E 边界。

## 已采纳建议

### P1：get-start 协议失败不得绕过共享 key 的最后 owner

- 问题：`_open_mooncake_get_sessions()` 在 `batch_get_start` 抛异常或返回结果
  shape/type 不合法时，直接对本批全部 keys 调用 `batch_get_end`，随后通过
  `invalidate_get_sessions()` 删除这些 keys 的全部 active owners。
- 已验证影响：当 `model@0a@0` 已由另一个 request 持有时，新 request 的 malformed
  get-start 结果仍会立即触发 `batch_get_end(["model@0a@0"])`；旧 owner 随后 release
  返回空，说明其 session 已在 owner 完成前被关闭。现有
  `test_get_start_shape_error_ends_all_keys_and_marks_all_blocks_invalid` 只覆盖单 owner，且把
  这一行为固化为预期。
- 设计依据：implementation plan D13 要求 Worker 维护
  `key -> active request owners`，只有最后 owner 被移除时才调用 `batch_get_end`；Task 6
  步骤 4 同样要求 shared key 的其他 owner 存在时不得 end。设计文档 §5.7 规定
  `batch_get_end` 只在 request 的 last chunk 最终 onload 后释放。
- 统一修改方案：把 get-start 异常/shape failure 的 cleanup 交给 tracker。tracker 应只
  释放本次尝试涉及的 request owners，保留未参与本次失败的其他 active owners；仅将
  owner 集合变空的 keys 返回给 Worker 执行 `batch_get_end`。当前 request 的 desired
  entries 必须保留供后续 chunk 重试，本批对应 local blocks 全部标记 invalid。不得直接
  对原始 `keys` 列表做无条件 get-end 或全局 owner invalidation。
- 测试要求：增加“旧 request 已持有 shared key，新 request 的 get-start 抛异常、返回过短、
  过长或非整数结果”测试；断言新 request blocks 全部 invalid、旧 owner 仍存在且不调用
  get-end，旧 owner 最终 release 后恰好调用一次。另覆盖没有其他 owner 时协议失败仍
  best-effort get-end，以及当前 request desired entries 在 retry 时仍可重建。
- fixup 归属：
  `#fixup feat(kv_pool): support Mooncake chunked prefill sessions`。

### P2：Chunk preparation 必须先 get-start 再 put-start

- 问题：`_prepare_mooncake_layerwise_sessions()` 当前逐 request 先调用
  `_prepare_mooncake_put_session()`，全部 put-start 完成后才统一调用
  `_open_mooncake_get_sessions()`。实际 backend 调用顺序为
  `batch_put_start -> batch_get_start`。
- 设计依据：设计文档 §5.7 的 API 表和伪代码均明确规定每个 chunk 进入 layer pipeline
  前先执行 `batch_get_start`，随后 saving rank 执行 `batch_put_start`。这是直接设计偏差，
  不是 implementation plan 推断。该顺序虽来自父 commit，但本 commit 纳入 §5.7 后仍未
  校正，因此属于本能力的缺失要求。
- 统一修改方案：将 preparation 改成两个明确阶段。第一阶段为所有 requests 合并累计
  load entries、去重并完成一次 `batch_get_start` 及结果 fan-out；第二阶段才逐 request
  准备本 chunk save metadata 并调用 `batch_put_start`。保留 non-saving TP rank 只做
  get-start、partial failure 对齐和 get-start 失败后仍可进入 recompute/save 的现有语义。
- 测试要求：使用 backend call sequence 断言单 request 和多 request 均为所有
  get-start 先于任何 put-start；覆盖 saving rank、non-saving rank、shared load key、
  get-start 部分失败以及无 load keys 但有 save keys 的 chunk。
- fixup 归属：
  `#fixup feat(kv_pool): support Mooncake chunked prefill sessions`。

### P3：用具名生命周期操作替代 `drop_state` 布尔参数

- 问题：`MooncakeSessionTracker.release_requests(..., drop_state: bool)` 同时编码两种语义：
  retryable abort 只释放 active owner并保留 desired/pending 状态；last、preempt、finished
  的 terminal cleanup 还要删除完整 request 状态。调用方只看到布尔值，传反不会产生
  类型或即时错误，却会导致重试数据被误删或 terminal request 状态泄漏。
- 判断性质：这是 Standards 轴的 Primitive Obsession / 可维护性判断，不是已经复现的
  运行时 bug。D13 和 Task 6 步骤 4 明确区分 abort 与 terminal cleanup，为两个具名领域
  操作提供了语义依据。
- 统一修改方案：对外暴露具名方法，例如 `release_for_retry(req_ids)` 与
  `release_terminal(req_ids)`；两者可复用一个私有实现，但业务调用点不得继续传裸布尔值。
  Worker 的 wrapper 和 `_finish_current_mooncake_load_sessions()` 也应使用相同的具名语义，
  让 abort、last、preempt 和 finished 分支可直接从方法名审查。
- 测试要求：分别验证 retry release 保留 desired entries、terminal release 删除 desired
  和 pending put ownership；两种方法均只对最后 active owner 返回 get-end key，并保持
  repeated release 幂等。
- fixup 归属：
  `#fixup feat(kv_pool): support Mooncake chunked prefill sessions`。

## 实施结果

- 原独立 fixup
  `78d84d7e0ee382a3869836f533fd208118055e9f #fixup feat(kv_pool): support Mooncake chunked prefill sessions`
  已折叠为 `e5989049e9cb27f218b52b8e03af8e5dc841ac74 feat(kv_pool): support Mooncake chunked prefill sessions`。
  最终 tree 与 rebase 前 review HEAD 相同；源码已用 exact `--force-with-lease` 从远端旧
  SHA `a1e888b46dbaa3c76a9c0dd1060a3631148fe8af` 更新到新 SHA，临时 review 分支已在
  本地和远端删除。
- P1：`MooncakeSessionTracker.release_failed_get_attempts()` 只释放失败调用涉及的 request
  owners；有其他 owner 的 shared key 不再提前 get-end，无 owner 的 key 仍由 Worker
  best-effort cleanup。当前 request 的 desired entries 保留供下一 chunk 重试。
- P2：`_prepare_mooncake_layerwise_sessions()` 改为两阶段 preparation，先汇总、去重并
  完成全部 `batch_get_start`，再逐 request 执行 `batch_put_start`。
- P3：公开 lifecycle API 改为 `release_for_retry()` 和 `release_terminal()`；Worker 的
  retry、last、preempt 和 finished 调用点不再传递 `drop_state` 裸布尔值。
- TDD 证据：实现前目标范围 `8 failed, 17 passed`，失败覆盖缺失的具名 API、shared-owner
  提前 get-end 和反向 API 顺序；实现后目标范围 `25 passed`。
- 使用专用 CPU venv 和隔离 bootstrap 运行完整
  `tests/ut/distributed/ascend_store`：`397 passed`。相关文件 Ruff check、`py_compile`、
  新 tracker/测试 Ruff format check、`git diff --check` 和重写 commit
  `git show --check` 均通过。
- S1 未纳入本轮源码修改；真实 Mooncake wheel / NPU Chunked Prefill E2E 仍按
  implementation plan Task 6 保持 pending。
- `workspace.lock.json` 和 `repo-state.md` 已刷新到最终 feature HEAD
  `e5989049e9cb27f218b52b8e03af8e5dc841ac74`。
