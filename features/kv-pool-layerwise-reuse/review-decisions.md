# Mooncake Layerwise KV Pool Feature Branch 检视决策

本文保留每轮 feature branch 检视必须遵守的通用规则。新的 findings、实施记录和旧 SHA
在开始新 review 时移除；只有用户明确采纳的结论才记录为本轮决策。

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

- CPU/mock UT 遵守 workspace `AGENTS.md`：使用 `liangjiahao` namespace 的 CPU-only
  专用 UT Pod，通过 tar + `kubectl exec` 同步源码，并区分真实依赖与 test stub。
- CPU mock UT、Ruff、`py_compile` 和 `git diff --check` 不能表述为真实 Mooncake wheel、
  memcache E2E 或 NPU E2E 已验证。
- NPU E2E、NPU benchmark 或真实 NPU 硬件验证只有在实际执行并保存证据后才能声明
  完成；未执行时必须持续标注 residual risk。

## 当前 Review 范围

- vLLM Ascend 原分支：`feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`
- 临时 review 分支：`review/mooncake-kv-offload-d28c529`（review 输入，已结束）
- WIP 实施分支：`wip/mooncake-review-findings-d28c529`
- review fixed point：`collaborator/kv_offload_0723`
- fixed point SHA：`a46a1dabbc260e8695002969f29528eb555eb583`
- review HEAD：`d28c52958a30cebdb7822d56e3dbb0dbe41499bc`
- WIP HEAD：`f97aed26f25a3427f20bdb7587b720dd6ef25bbf`
- review diff：`git diff collaborator/kv_offload_0723...d28c52958`
- WIP diff：`git diff 14beaf161...f97aed26f`
- 范围：11 个 Mooncake 线性集成 commit，以及其后的并发 ranged-load 隔离修复 commit。

本轮继续重点检查：

1. collaborator 的 group-aware/shared-buffer GVA 路径与 Mooncake key-major ranged 路径
   是否通过明确条件并存；
2. session owner、chunked-prefill、失败收尾和并发 request 隔离是否符合权威设计；
3. 是否保持 memcache、whole-key、Yuanrong 和既有 positional constructor contract；
4. 测试与 full-validation 证据是否覆盖新增行为，且没有越过验证边界。

## 本轮 Review 建议与实施状态

以下条目保留最初 review 证据，并记录独立 WIP 分支上的实施结果。`已实施` 只表示对应
改动已在 WIP 分支完成和通过所列验证，不表示已合入或已经完成未实际运行的 NPU gate。
Spec 与 Standards 两轴分别记录，不跨轴重排优先级。

### Spec

#### SP1：Mooncake multi-group contract 与当前实现不一致

- 状态：已实施于 WIP；owning commit `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d`。
- 严重级别：High。
- 判断性质：Spec 缺失/实现错误；兼容性风险。
- 设计依据：权威设计 §2.3、§5.8 要求 multi-group key 包含 `group_id`，每个 group
  使用独立的 `page_size[g] * num_layers[g]` object size、组内 layer offset 和独立
  commit：
  - `references/snapshots/design-mooncake-layerwise-gva-put.md:158-160`
  - `references/snapshots/design-mooncake-layerwise-gva-put.md:572-630`
- 代码证据：
  - Scheduler 在 `pool_scheduler.py:313-324` 为 multi-group 查询生成带 `group_id` 的 key；
  - Worker 在 `pool_worker.py:1354-1391`、`pool_worker.py:1439-1445` 仍生成不带
    `group_id` 的 key，并统一使用全局 `page_size_bytes * num_layers`；
  - `kv_transfer.py:336` 的 key-major builder 读取 group 0 `request.block_ids`；
  - `kv_transfer.py:1756-1757`、`kv_transfer.py:2154-2155` 拒绝同一物理层的多个
    group task，且 range build 使用 physical layer 而非 `layer_idx_in_group`；
  - 用户文档 `docs/source/user_guide/feature_guide/layerwise_kv_pool.md:309-311` 却声明
    未启用 buffer reuse 时保留 multi-group 支持。
- 影响：Scheduler 可能永远查询不到 Worker 写入的对象；不同 group 还可能出现 key、
  object size、本地 block 或 remote offset 错配。2026-08-03 full validation 覆盖了当前
  单 group runtime，不构成 multi-group runtime 证据。
- 历史边界：未完成的 Mooncake multi-group 实现曾被明确隔离到
  `wip/mooncake-multi-group-layerwise-optimization`，不应在未确认设计和范围时直接带入
  当前 review 分支。
- 实施结果：采用完整 group-local 路径，覆盖 key、metadata、session tracker、object size、
  组内 offset、逐组 completion/revoke 和 encoded invalid block IDs；保留 collaborator 的
  group-aware/shared-buffer GVA 路径以及单 group、Memcache、whole-key、Yuanrong 和 MTP 行为。
- 验证：覆盖 Scheduler/Worker key 一致性、不同 group block size、同一物理层多 group、
  组内 offset、逐组 commit/revoke、失败隔离和 session cleanup；最终 CPU/mock gate 包含在
  `534 passed` 中。真实 multi-group Mooncake/NPU E2E 尚未运行。

#### SP2：并发 ranged-load 的异常边界仍扩大到其他 request

- 状态：已实施于 WIP；owning commit `fdd0713e607ab919e08272e81f2925f191de678d`。
- 严重级别：Medium。
- 判断性质：代码正确性；测试充分性。
- 设计依据：`implementation-plan.md:91-96` 和 `implementation-plan.md:792-797`
  要求 ranged-read failure 映射到准确的本地 block，并只中止受影响 batch。
- 代码证据：`kv_transfer.py:2073-2091` 已按 `req_id` 分别调用 `batch_copy_get`；但任一
  request 子调用抛异常或返回 malformed result 后，`kv_transfer.py:2245-2255` 会把整个
  `transfer_tasks` 的 blocks 标为 invalid、清空全部 active rows 并 abort。
- 影响：单个 request 的 Mooncake/协议故障会使同批其他 request 无谓重算；当前新增测试
  只覆盖负返回码的 row-local failure，没有覆盖 subgroup exception 或 shape error。
- 实施结果：request-local API exception 和 result-shape failure 只移除该 request 的 active
  rows，其他 request 继续；无法归属的 shared metadata/invariant 错误仍 abort 整个 task。
- 验证：覆盖第一个/中间/最后一个 request 抛异常，以及 short、long、non-integer result；
  focused gate `150 passed`，并包含在最终 `534 passed` 中。

### Standards

#### ST1：用户文档发布了错误的 Mooncake Client API 名称

- 状态：已实施于 WIP；owning commit `69819f6ea9a67944c14f749a66bffeba02d0db3f`。
- 严重级别：P1。
- 判断性质：Documented-standard hard violation。
- 规范依据：vLLM Ascend `AGENTS.md:367-371` 要求 public API 与用户可见行为被准确记录。
- 代码证据：`docs/source/user_guide/feature_guide/layerwise_kv_pool.md:50-56` 声称 Client
  wheel 提供 `batch_put_start`、`batch_put_end` 等 API；实际 capability contract 是
  `backend/mooncake_backend.py:29-37` 的 `batch_*_session_*` API。
- 影响：用户可能按错误 contract 选择 wheel，随后在 startup capability validation 失败。
- 实施结果：文档已明确区分内部 `Backend` method 与 Mooncake Client method，列出五个
  `batch_*_session_*` 和两个 ranged Client API，并同步 chunked-prefill 调用名称。

#### ST2：最新 source fix commit 缺少 DCO sign-off

- 状态：已实施于独立 WIP history；owning commit
  `04cb824f6e8161e89547f220b92a0bc42ba0531a`。
- 严重级别：P2。
- 判断性质：Documented-standard hard violation。
- 规范依据：vLLM Ascend `AGENTS.md:271-279` 要求每个 commit 必须包含 `Signed-off-by`。
- 代码证据：`d28c52958 fix(kv_pool): isolate concurrent Mooncake range loads` 只有 subject，
  没有 `Signed-off-by`；其余 11 个 review commit 均包含 sign-off。
- 影响：DCO/提交规范检查会拒绝该 commit。
- 实施结果：从 `14beaf161` 建立 WIP 分支并将 `d28c52958` 的 patch 重放为 signed commit
  `04cb824f6`；原 `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` local/origin
  继续保持 `d28c52958`，未改写、未 force-push。

#### ST3：NPU ranged-transfer 热路径缺少持续性能回归 gate

- 状态：性能 gate 已实施于 WIP；owning commit
  `f97aed26f25a3427f20bdb7587b720dd6ef25bbf`；真实 NPU benchmark 未运行。
- 严重级别：P2。
- 判断性质：Documented-standard hard violation；测试充分性。
- 规范依据：vLLM Ascend `AGENTS.md:78-90` 要求 NPU-specific code path 提供 nightly
  benchmark，performance-critical code 提供 performance regression test。
- 代码证据：`kv_transfer.py:2047-2100` 新增 ranged-load batching/dispatch 热路径及 mock UT，
  但当前 diff 没有新增 `tests/e2e/nightly` benchmark 或可持续的性能阈值检查。
- 影响：现有 full validation 证明一次功能和压力运行通过，但不能防止后续吞吐或延迟回归。
- 实施结果：新增真实 Mooncake/NPU ranged save/load nightly benchmark，固定记录 batch size、
  并发 request 数、layer 数、吞吐和 p50/p95，并通过环境变量设置最小 GB/s 和最大 p95
  阈值。CPU-only Pod 完成单测试 collection 和未配置环境的预期 skip；真实 benchmark
  仍是 nightly runner residual gate。

#### ST4：Ranged row 使用多组位置对齐 list

- 状态：已实施于 WIP；owning commit `fdd0713e607ab919e08272e81f2925f191de678d`。
- 严重级别：P2。
- 判断性质：Standards judgement call；Data Clumps smell。
- 代码证据：`config_data.py:1093-1103` 以 `keys`、`block_ids`、`all_buffers`、
  `all_sizes`、`all_offsets`、`row_req_ids` 等平行 list 表示一行；`kv_transfer.py:2069-2092`
  依赖长度检查和重复 index 维持关联。此前并发串扰正与 ownership 未进入 row model 有关。
- 影响：以后新增 row 属性或过滤逻辑时仍容易出现静默错位。
- 实施结果：引入 immutable `LayerRangeRow`，结构性绑定 key、block、buffers、sizes、
  offsets 和 owner；`LayerRangeReqMeta` 保留并验证 legacy positional constructor contract。

#### ST5：Ranged audit emitter 存在重复逻辑

- 状态：已实施于 WIP；owning commit `69819f6ea9a67944c14f749a66bffeba02d0db3f`。
- 严重级别：P3。
- 判断性质：Standards judgement call；Duplicated Code smell。
- 代码证据：`kv_transfer.py:55-117` 与 `backend/mooncake_backend.py:41-62` 重复实现
  feature gate、JSON logging 和 instrumentation exception isolation。
- 影响：未来修改 payload 或失败策略时，两处审计事件可能产生不一致行为。
- 实施结果：新增依赖方向单一的 `range_debug.py`，集中 range、commit、whole-key 三类
  best-effort emitter；disabled、payload coercion 和 logger failure 均有 focused coverage。

## 本轮 WIP 实施记录

- `SP1`、`SP2`、`ST1`、`ST2`、`ST3`、`ST4`、`ST5` 均已在独立 WIP 分支实施。
- 最终 source verification：AscendStore、patch 与 env CPU/mock tests `534 passed`；22 个
  Python diff 文件 Ruff/format 通过；12 个 source 文件 `py_compile` 通过；
  `git diff --check` 通过；5 个 WIP commits 均有 DCO sign-off 且无 merge commit。
- 验证边界：真实 Mooncake/NPU ranged performance benchmark 未运行，不能声明性能 gate
  已通过；原受保护 feature 分支未被修改。

## 2026-08-04 合回范围决策

- 当前合回目标是
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` at
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`。
- 暂不实现权威设计 §5.8；`SP1` owning commit `0dad9ad94` 不进入当前合回范围，完整
  multi-group 实现继续只保存在 `wip/mooncake-review-findings-d28c529`。
- `04cb824f6` 与目标分支现有 `d28c52958` tree 完全相同，不能通过普通 cherry-pick
  替换已有 unsigned commit；当前不改写受保护分支历史。DCO 问题只能在明确授权的
  history rewrite 或后续 squash 边界处理。
- `SP2` 与 `ST4`（`fdd0713e6`）在语义上不依赖 multi-group，可以按单 group 基线定向
  backport：保留 immutable `LayerRangeRow`、legacy positional constructor 和
  request-local exception/result-shape failure 隔离；不得带入 `group_id`、group-local
  active rows 或 encoded group/block failure。该 commit 依赖 `0dad9ad94` 的上下文，不能
  整笔直接 cherry-pick。
- `ST1` 与 `ST5`（`69819f6ea`）在语义上不依赖 multi-group，可以定向 backport Client API
  文档修正、共享 `range_debug.py` 和对应测试；该 commit 的 `kv_transfer.py` hunk 基于
  WIP row/group 上下文，不能整笔直接 cherry-pick。
- `ST3`（`f97aed26f`）不依赖 multi-group，当前 patch 对 `d28c52958` 通过
  `git apply --check`，可作为独立 cherry-pick 候选。它只新增 nightly performance gate
  和文档；真实 Mooncake/NPU benchmark 仍未运行。
- 已按上述边界回合为目标分支上的独立 signed commits：
  - `8d9897143`：`fdd0713e6` 的 single-group row/failure isolation；
  - `189dcdd2c`：`69819f6ea` 的共享 ranged audit emitter 与 Client API 文档修正；
  - `6451f9010`：`f97aed26f` 的 opt-in nightly performance gate。
- 合回后的第二轮 Standards/Spec 复核发现 `6451f9010` 不能原样发布：测试错误要求
  ranged data API 必须返回精确字节数，而权威 contract 允许任意非负成功码；nightly
  环境变量没有集中注册；用户文档仍错误暗示 Mooncake multi-group 可用；immutable row
  的兼容 property 还在 save 热路径重复物化。
- 上述问题修复于 `d5f0ea7f8`：接受长度对齐的非负 ranged 结果并保留最终数据一致性
  oracle；集中注册 nightly env；save 热路径直接消费 `LayerRangeRow`；明确 memcache
  既有 multi-group 路径与当前不支持的 Mooncake multi-group 边界。该修复没有引入
  `group_id`、group-local key/session/offset/completion 或 encoded failure。
- 修复后 gate：nightly contract `2 passed, 1 skipped`，env `3 passed`，AscendStore + env
  `490 passed`，Ruff/format/compile/`git diff --check` 通过。真实 Mooncake/NPU performance
  benchmark 仍是 nightly residual gate，不得声明已通过。
