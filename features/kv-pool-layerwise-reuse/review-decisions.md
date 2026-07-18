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
- 本 commit 新增或显著改写的连续逻辑超过 40 行时，必须保留原有有效注释，并在
  阶段边界补充必要注释，说明状态不变量、失败处理和 ownership；不添加逐行复述
  代码的无效注释。
- 重构、改名或 backend 泛化不得无故删除原源码中仍然有效的注释。若代码结构或职责
  已改变，应把原注释迁移到新的对应分支并按当前语义改写，保留其设计理由和风险说明；
  只有注释已经失效时才可删除，并应以新的准确注释替代。

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

### P1：只有 saving TP rank 才能打开 Mooncake put session

- 问题：`_prepare_mooncake_layerwise_sessions()` 当前在每个 TP rank 上调用
  `_prepare_mooncake_put_session()`，而 `_process_save_for_layer_batch()` 只允许
  `tp_rank % put_step == 0` 的 saving rank 建立 save task。
- 风险：MLA 中同一 `put_step` group 的多个 rank 共享相同
  `model@block_hash@head_or_tp_rank` key。非 saving rank 可能先成功执行
  `batch_put_start`，使真正负责 ranged write 的 saving rank 得到 duplicate/conflict；
  该对象随后没有数据写入并停留在 PROCESSING。
- 设计依据：设计文档 §2.3 明确规定 MLA 只有
  `tp_rank % put_step == 0` 的 rank 保存；§3 将 `batch_put_start` 和逐层 ranged write
  归属于同一个 saving rank。implementation plan Task 4 步骤 3 也要求 put-session
  preparation 与 LayerSendingThread 的 save ownership 一致。
- 统一修改方案：只对 put-session preparation 增加与 save task 相同的 saving-rank
  及 KV role 门控；不能跳过整个 session preparation，因为每个需要读取 KV 的 TP rank
  仍须用自己的 Mooncake Client 打开 get session。复用同一判断，避免 put preparation
  与 layer task selection 再次漂移。
- 测试要求：增加 TP=4、MLA `put_step=4` 测试；rank 0 调用一次
  `batch_put_start` 并建立 save metadata，rank 1/2/3 不调用 `batch_put_start`，但有 load
  需求时仍调用 `batch_get_start`。

### P1：只能在 ranged read 完成或 Receiver abort finalization 后关闭 get session

- 问题：`wait_for_layer_load()` 的 layer event 等待超时后，即使 `is_finish=False`，
  final layer 仍会调用 `_close_load_sessions_once()`。
- 风险：Receiver 可能仍在执行 `batch_copy_get`；此时 `batch_get_end` 删除 Client
  get-session，会与在途 ranged read 竞态。Worker 同时继续 forward，可能使用未完成的
  KV 数据。
- 设计依据：设计文档 §3 的时序要求 final ranged read 完成后才执行
  `batch_get_end`；§5.5 将 session cleanup 归 Worker 所有。implementation plan Task 4
  步骤 5 明确要求正常最终 layer **完成**或 Receiver 已完成异常 abort 后 exactly once
  收尾，而不是仅凭 wait 超时收尾。
- 统一修改方案：关闭条件必须以 Receiver 已完成 transfer handler/finalization 为准。
  timeout 不能直接调用 `batch_get_end`；timeout 路径必须先进入明确的失败处理，等待在途
  handler 完成并标记受影响 block invalid，再由 Worker 的 exactly-once helper 关闭
  session。Receiver 仍只通知 completion/abort，不直接拥有 `batch_get_end`。
- 测试要求：覆盖 final layer 正常完成、Receiver abort 和 wait timeout 三条路径；断言
  timeout 时不会提前调用 `batch_get_end`，handler finalization 后只调用一次，并验证
  invalid-block fallback、layer event 和 queue completion 都已完成。

### P2：为超过 40 行的连续编排逻辑补充阶段和状态注释

- 要求：本 commit 新增或显著改写的连续逻辑超过 40 行时，必须增加必要注释，并保留
  原有仍然有效的注释。
- 重点范围：`_get_block_key_layerwise_hit_tokens()`、
  `_prepare_mooncake_put_session()`、`_open_mooncake_get_sessions()`，以及修改后仍超过
  40 行的其他连续 session-orchestration 逻辑。
- 注释内容：说明 key construction、backend query、per-block prefix decision、
  put tracker ownership、get-key deduplication、result fan-out、invalid-block mapping 和
  exactly-once cleanup 等阶段及不变量。避免对显而易见的赋值、循环和列表推导逐行复述。
- 恢复或迁移本 commit 在 scheduler 泛化过程中删除、弱化的原有设计说明：
  `_get_block_key_layerwise_hit_tokens()` 从 block 0 **查询** remote contiguous prefix 的
  理由；Memcache 必须使用 `batch_get_key_info` 而不是 `batch_is_exist`，以避免只完成
  alloc、尚未完成全部 layer save 的对象形成 false hit；以及同一 block 的全部 saving
  rank 都必须返回有效 GVA 才算完整。原注释中把“查询”描述为“加载”的部分应改为准确
  表述，但不能连同其设计理由一起删除。
- 校验要求：源码修改后人工复查所有本 commit 新增长逻辑；Ruff、format 和 UT 通过，
  且不得为了加注释进行无关重构。
