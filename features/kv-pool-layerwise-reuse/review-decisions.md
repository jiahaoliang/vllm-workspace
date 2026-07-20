# `support Mooncake chunked prefill sessions` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
a1e888b46dbaa3c76a9c0dd1060a3631148fe8af
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

临时 review 分支：`review/mooncake-chunked-prefill-sessions`

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

暂无。仅在用户明确采纳后添加。
