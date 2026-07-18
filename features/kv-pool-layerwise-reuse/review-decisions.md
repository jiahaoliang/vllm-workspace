# `orchestrate Mooncake layerwise sessions` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
67ef431aed0c427ad51d6f46ec7b4afb4e35c76e
feat(kv_pool): orchestrate Mooncake layerwise sessions
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

## UT 环境规则

- 本 feature 的 CPU UT 必须使用专用 venv
  `C:\Users\l30034596\.venvs\vllm-ascend-cpu-tests-py314` 运行。
- PowerShell 中直接调用
  `C:\Users\l30034596\.venvs\vllm-ascend-cpu-tests-py314\Scripts\python.exe -m pytest ...`，
  不使用系统 `python`，避免因系统环境未安装 `torch` 产生无效失败。
- 检视报告必须区分 venv UT 结果、静态检查结果和未执行的 NPU/E2E 验证，不得把
  系统 Python 的依赖缺失记为源码测试失败。

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
  `#fixup feat(kv_pool): orchestrate Mooncake layerwise sessions`（GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- `tests/ut/distributed/ascend_store/test_ascend_store_connector.py`
- `tests/ut/distributed/ascend_store/test_pool_scheduler.py`
- `tests/ut/distributed/ascend_store/test_pool_worker.py`

重点检视：

1. connector、scheduler 和 worker 是否只在 Mooncake block-key layerwise 模式启用
   session/ranges 编排，并保持 Memcache、Yuanrong 和非 layerwise 路径不变。
2. save 侧 `batch_put_start`、逐层 ranged write、`batch_commit` / `batch_revoke` 的
   ownership、幂等状态和失败清理是否符合设计。
3. load 侧 `batch_get_start`、逐层 ranged read、exactly-once `batch_get_end` 和
   invalid-block fallback 是否符合设计。
4. scheduler 是否使用带 `tp_rank` 的稳定 block key，并且只有全部 TP rank key
   均存在时才判定 block 命中。
5. metadata 在 scheduler、worker 与 transfer thread 之间是否保持 key、block ID、
   range payload 严格对齐。
6. 测试是否覆盖正常、多层、部分失败、异常和既有 backend 回归路径。

## 已采纳建议

暂无。等待用户确认第一轮检视结论。
