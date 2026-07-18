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

暂无。仅在用户明确采纳后添加。
