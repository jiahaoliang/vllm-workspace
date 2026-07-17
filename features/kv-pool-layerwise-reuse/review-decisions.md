# `make layer transfer completion exception-safe` 检视记录

本文只记录以下提交中经用户明确采纳的检视建议：

```text
bfdc0984544b27a79d26fb3f84e0f181f02b2424
refactor(kv_pool): make layer transfer completion exception-safe
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
  `#fixup refactor(kv_pool): make layer transfer completion exception-safe`
  （GitExtensions style）。
- fixup commit 创建后保持独立；只有收到用户明确的 rebase 命令后，才将其折叠到
  原提交。
- 未采纳、仍有争议或仅用于讨论的建议不写入本文。

## 检视范围

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- `tests/ut/distributed/ascend_store/test_kv_transfer.py`

重点检视：

1. transfer completion 是否在成功、返回失败码和抛出异常三条路径上都完成统一的
   状态收敛。
2. 异常清理是否保留原始异常，不因 cleanup/finalization 的次生异常改变根因。
3. save 与 load 的完成语义是否保持对称，并保持 Memcache、Yuanrong 和非
   layerwise 路径的既有行为。
4. completion hook 的调用次数、调用顺序及 batch 对齐约束是否明确且可测试。
5. 新增测试是否覆盖同步异常、异步结果异常、失败结果和正常完成，而不只覆盖理想
   路径。

## 已采纳建议

### P2：保留原有传输语义注释，并为异常收尾补充必要注释

- 检视结论：已采纳，尚未修改源码。
- 问题：本提交将 save/load handler 包入 `try/except/finally` 时，删除了原代码中
  关于 `put_step` 保存 rank、完整 K/V blob、所有 rank 完整读取，以及最终 layer
  释放 read lease 的注释；新增的 exception finalization helper 和 invalid-block
  标记顺序也没有注释说明。
- 影响：重构后的控制流明显变长，但关键的 rank 读写职责和 lease 生命周期依据反而
  消失。后续维护者难以判断 full K/V copy 是有意设计还是遗漏切片，也可能把
  invalid-block 标记、layer event、`task_done()` 的顺序当作普通清理代码调整，重新引入
  错误命中或等待死锁。
- 设计依据：设计文档 §5.5 将 `kv_transfer` 定义为按层执行 copy、在最终 layer 完成
  write/read 生命周期，并要求各层传输保持正确的本地 buffer 语义；§7 要求 load 失败
  由 vLLM fallback 重算。implementation plan D02 和 Task 4 步骤 6 进一步明确：发生
  load exception 时必须先标记失败 block，并且无论异常与否都必须设置 layer event、
  恰好调用一次 `request_queue.task_done()`。
- 统一修改方案：
  1. 在 save copy 前恢复 `tp_rank % put_step == 0` 的保存职责，以及保存 rank 写入完整
     K/V blob 的说明。
  2. 在 load copy 前恢复所有 rank 读取完整 K/V blob、不做 rank slicing 的说明。
  3. 在最终 layer 的 lease release 前保留 lease 覆盖整个 layerwise load 生命周期的
     说明，但将原注释中硬编码的 “27 layers” 改为与模型无关的 “all layers”。
  4. 在异常路径或 finalization helper 附近添加简短注释，说明 load 必须在释放 layer
     event 前标记 invalid block，且 `task_done()` 与 finished event 必须在所有退出路径
     执行，以避免错误命中、`queue.join()` 或 layer wait 永久阻塞。
- 实施归属：
  `bfdc09845 refactor(kv_pool): make layer transfer completion exception-safe`。
