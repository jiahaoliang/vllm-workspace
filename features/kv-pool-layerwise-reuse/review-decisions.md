# Mooncake Layerwise KV Pool Feature Branch 检视决策

本文只记录 2026-07-20 整体 feature branch 检视中用户作出的当前决策。完整 findings、
证据和验证结果见：

`features/kv-pool-layerwise-reuse/feature-branch-review-2026-07-20.md`

## 新 Review 准备流程

每次开始新的 commit review，必须先依次完成：

1. 将本文还原为只保留通用规则、当前 review 范围和本轮决策的干净状态，移除上一轮
   review 的 findings、实施记录和旧 SHA。
2. 在源码仓库中，从目标 commit 建立并切换到独立临时分支；分支名使用
   `review/<commit-topic>`。
3. 先阅读权威设计，再检视目标 diff，逐部分向用户说明行为、影响和设计来源。
4. 只有用户明确表示“采纳”或“纳入”后，才把建议写入“本轮已采纳决策”。
5. 只有收到明确实施命令后才修改源码；fixup 保持独立，只有收到明确 rebase 命令后
   才折叠。

临时 review 分支不更新 `workspace.lock.json`。不得因为 review 执行无关格式化、重构、
状态文件刷新或源码 push。

## 检视依据

优先级从高到低：

1. `features/kv-pool-layerwise-reuse/references/snapshots/design-mooncake-layerwise-gva-put.md`
2. `features/kv-pool-layerwise-reuse/implementation-plan.md`
3. vLLM Ascend `AGENTS.md`、`CONTRIBUTING.md` 和现有源码 contract

当设计文档与 implementation plan 冲突时，以设计文档为准。每个 finding 必须说明
代码证据、影响、严重级别和判断性质；无法由设计文档直接推出的建议，必须标为代码
正确性、兼容性、测试充分性或 Standards 判断。

## 验证边界

- CPU UT 使用专用隔离 venv，并区分真实依赖与 test stub。
- CPU mock UT、Ruff、`py_compile` 和 `git diff --check` 不能表述为真实 Mooncake wheel、
  memcache E2E 或 NPU E2E 已验证。
- 当前没有 NPU 测试环境；本轮明确不把 NPU E2E、NPU benchmark 或真实 NPU 硬件
  验证纳入本地实施/验收范围，但报告必须持续标注该 residual risk。

## 本轮检视范围

- vLLM Ascend branch：`feature/mooncake-layerwise-kv-pool`
- feature HEAD：`1c75b507fe268b91a6f4183da0ae6221ffd05568`
- review fixed point：`upstream/main`
- review 时 `upstream/main`：`bb474a6a94a999d54a5a6c54663bce70502d7aad`
- feature merge-base：`9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384`
- Mooncake collaborator branch：`feature/layerwise-kv-session`
- Mooncake collaborator HEAD：`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`

重点：

1. 是否对原有 memcache 路径造成 breaking change；
2. 是否符合权威设计文档；
3. chunked-prefill session owner、last-owner cleanup 和失败收尾是否正确；
4. 真实 wheel、CPU UT 与 NPU E2E 的证据等级是否被准确区分。

## 本轮已采纳决策

### MC2：Layer load timeout 保留 drain barrier，并提供有界终止策略

- 用户决定：采纳。
- 问题：`wait_for_layer_load()` 第一次等待 10 秒超时后，会执行无 timeout 的第二次
  `event.wait()`。第二次等待用于让 RecvingThread 退出正在进行的 ranged read，避免
  backend 仍使用 Client session 时调用 `batch_get_end`；如果 backend 永久不返回，
  forward 也会永久阻塞。
- 设计约束：不能为了消除无限等待而提前 `batch_get_end`。Mooncake session cleanup
  必须晚于 in-flight ranged read，并继续由 Worker 按最后 active owner 统一执行。
- 采纳方案：
  - 保留 drain barrier；
  - 增加有界终止、backend cancel 或进程级失败策略；
  - 将 Mooncake session cleanup 竞态处理与 memcache fault-path 分开；
  - 不得无意改变 memcache 的正常路径行为。
- 测试要求：覆盖正常 completion、backend exception、首次 timeout 后最终 completion、
  backend 永久不 completion 的有界退出，以及 memcache/Mooncake 两条路径；in-flight
  ranged read 完成前不得调用 `batch_get_end`。

### D3：Put-start 异常 revoke 不得阻塞 Worker forward 主线程

- 用户决定：采纳。
- 问题：`batch_put_start` 抛异常或返回 malformed result 时，Worker 主线程同步执行
  `_best_effort_revoke_layerwise_keys(new_keys)`；该 Master RPC 可能阻塞 chunk setup。
- 设计依据：权威设计 §1.4 要求 ranges、`batch_put_end`、`batch_put_revoke` 在传输线程
  执行，使 offload control/data work 不阻塞 forward 热路径。
- 采纳方案：Worker 只完成本地 metadata filtering 与 pending-state transition，将需要
  revoke 的 keys 交给 SendingThread/control queue；异步 cleanup 保留
  `_put_started_keys`、pending owners 和 Master-timeout fallback 的既有不变量。
- 测试要求：覆盖 put-start exception、shape error、partial failure、queue handler
  exception 和 revoke failure；Worker preparation 不得同步调用 revoke，失败 keys 不得
  进入 ranged save，异步 cleanup 最终准确更新 tracker。

## 本轮明确不纳入

- `MC1`：不采纳。memcache block-key layerwise 的 TP-only breaking boundary 是
  intentional correctness boundary。
- `MC3/D4`：不采纳并忽略。失败 GVA 进入 transfer 是继承的 memcache 既有问题，
  不是本 feature 引入，也不直接影响 Mooncake。
- `D1/D2`：先前的采纳决定被用户最新实施边界覆盖。本轮不得修改 `repos/Mooncake`；
  不在 vLLM-Ascend 内伪造 Mooncake Client contract。`MooncakeBackend` 继续适配当前
  collaborator wheel：`batch_put_start(keys, sizes)`，ranged put 使用四参数调用。
  `batch_put_end` 幂等与 ranged put 可选 `ReplicateConfig` 仍是设计和 collaborator
  实现之间的已知差异，但不属于本轮代码改动。
- `D5b/ST1`：不采纳为当前本地实施/验收项。当前没有 NPU 环境，不要求完成 NPU E2E、
  NPU benchmark 或真实 NPU 硬件验证；仍须明确标注“未经 NPU 验证”。

## 当前实施状态

- vLLM-Ascend MC2/D3 fixup：
  `cfe97c8de2cce781750be05e34ac7d0030fd9c0b`，归属
  `feat(kv_pool): orchestrate Mooncake layerwise sessions`。
- vLLM-Ascend Mooncake contract 适配回退：
  `f5ab64a1f`；最终源码不依赖 D2 的新 signature。
- vLLM-Ascend feature HEAD：`f5ab64a1f`，已推送
  `origin/feature/mooncake-layerwise-kv-pool`；fixup 未 rebase。
- Mooncake 已恢复到未修改的 collaborator HEAD
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`，没有 Mooncake commit 或 push。
- 隔离 AscendStore CPU suite：`402 passed`；Ruff、`py_compile`、
  `git diff --check` 和 fixup commit checks 通过。
- 未运行真实 Mooncake wheel、memcache E2E 或 NPU E2E；本轮不声称经过 NPU 验证。
