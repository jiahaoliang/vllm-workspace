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
- 临时 review 分支：`review/mooncake-kv-offload-d28c529`
- review fixed point：`collaborator/kv_offload_0723`
- fixed point SHA：`a46a1dabbc260e8695002969f29528eb555eb583`
- review HEAD：`d28c52958a30cebdb7822d56e3dbb0dbe41499bc`
- diff：`git diff collaborator/kv_offload_0723...HEAD`
- 范围：11 个 Mooncake 线性集成 commit，以及其后的并发 ranged-load 隔离修复 commit。

本轮继续重点检查：

1. collaborator 的 group-aware/shared-buffer GVA 路径与 Mooncake key-major ranged 路径
   是否通过明确条件并存；
2. session owner、chunked-prefill、失败收尾和并发 request 隔离是否符合权威设计；
3. 是否保持 memcache、whole-key、Yuanrong 和既有 positional constructor contract；
4. 测试与 full-validation 证据是否覆盖新增行为，且没有越过验证边界。

## 本轮待用户 Review 建议

以下条目均为 `待决策`，不代表已经采纳。Spec 与 Standards 两轴分别记录，不跨轴
重排优先级。用户明确回复“采纳”“纳入”“不采纳”或“延后”后，再更新对应状态。

### Spec

#### SP1：Mooncake multi-group contract 与当前实现不一致

- 状态：待决策。
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
- 待决定方案：
  1. 纳入：按权威设计完整实现 group-local key、metadata、session tracker、object size、
     offset、completion 和 failure state；或
  2. 不纳入当前分支：初始化时对 Mooncake block-key layerwise multi-group 明确 fail-fast，
     修正文档的支持声明，并把 §5.8 标为后续 WIP，而不是让不完整路径继续可达。
- 若纳入的测试要求：覆盖 Scheduler/Worker key 一致性、不同 group block size、同一物理层
  多 group、组内 offset、逐组 commit/revoke、失败隔离和 `batch_get_end` owner cleanup。

#### SP2：并发 ranged-load 的异常边界仍扩大到其他 request

- 状态：待决策。
- 严重级别：Medium。
- 判断性质：代码正确性；测试充分性。
- 设计依据：`implementation-plan.md:91-96` 和 `implementation-plan.md:792-797`
  要求 ranged-read failure 映射到准确的本地 block，并只中止受影响 batch。
- 代码证据：`kv_transfer.py:2073-2091` 已按 `req_id` 分别调用 `batch_copy_get`；但任一
  request 子调用抛异常或返回 malformed result 后，`kv_transfer.py:2245-2255` 会把整个
  `transfer_tasks` 的 blocks 标为 invalid、清空全部 active rows 并 abort。
- 影响：单个 request 的 Mooncake/协议故障会使同批其他 request 无谓重算；当前新增测试
  只覆盖负返回码的 row-local failure，没有覆盖 subgroup exception 或 shape error。
- 建议：将 request-local API exception/shape failure 映射到该 request 的 active indices，
  继续处理其他 request；只有 shared metadata/invariant 失配等无法归属的错误才 abort
  整个 transfer task。
- 测试要求：覆盖第一个/中间/最后一个 request 抛异常，以及 short、long、non-integer
  result；验证其他 request 仍执行、只有受影响 block invalid，session cleanup 仍 exactly-once。

### Standards

#### ST1：用户文档发布了错误的 Mooncake Client API 名称

- 状态：待决策。
- 严重级别：P1。
- 判断性质：Documented-standard hard violation。
- 规范依据：vLLM Ascend `AGENTS.md:367-371` 要求 public API 与用户可见行为被准确记录。
- 代码证据：`docs/source/user_guide/feature_guide/layerwise_kv_pool.md:50-56` 声称 Client
  wheel 提供 `batch_put_start`、`batch_put_end` 等 API；实际 capability contract 是
  `backend/mooncake_backend.py:29-37` 的 `batch_*_session_*` API。
- 影响：用户可能按错误 contract 选择 wheel，随后在 startup capability validation 失败。
- 建议：文档明确区分 vLLM Ascend 内部 `Backend` method 与 Mooncake Client method，列出
  当前七个 `batch_*_session_*`/ranged API，并同步 chunked-prefill 段落中的调用名称。

#### ST2：最新 source fix commit 缺少 DCO sign-off

- 状态：待决策。
- 严重级别：P2。
- 判断性质：Documented-standard hard violation。
- 规范依据：vLLM Ascend `AGENTS.md:271-279` 要求每个 commit 必须包含 `Signed-off-by`。
- 代码证据：`d28c52958 fix(kv_pool): isolate concurrent Mooncake range loads` 只有 subject，
  没有 `Signed-off-by`；其余 11 个 review commit 均包含 sign-off。
- 影响：DCO/提交规范检查会拒绝该 commit。
- 建议：仅在用户明确授权 history rewrite 后，为 `d28c52958` 补签并使用精确
  `--force-with-lease` 更新目标 source branch；不得改写受保护的原始 feature branch。

#### ST3：NPU ranged-transfer 热路径缺少持续性能回归 gate

- 状态：待决策。
- 严重级别：P2。
- 判断性质：Documented-standard hard violation；测试充分性。
- 规范依据：vLLM Ascend `AGENTS.md:78-90` 要求 NPU-specific code path 提供 nightly
  benchmark，performance-critical code 提供 performance regression test。
- 代码证据：`kv_transfer.py:2047-2100` 新增 ranged-load batching/dispatch 热路径及 mock UT，
  但当前 diff 没有新增 `tests/e2e/nightly` benchmark 或可持续的性能阈值检查。
- 影响：现有 full validation 证明一次功能和压力运行通过，但不能防止后续吞吐或延迟回归。
- 建议：纳入 nightly ranged save/load benchmark，至少记录 batch size、并发 request 数、
  layer 数、吞吐和延迟阈值；若本分支暂不纳入，明确记录为合入前 residual gate。

#### ST4：Ranged row 使用多组位置对齐 list

- 状态：待决策。
- 严重级别：P2。
- 判断性质：Standards judgement call；Data Clumps smell。
- 代码证据：`config_data.py:1093-1103` 以 `keys`、`block_ids`、`all_buffers`、
  `all_sizes`、`all_offsets`、`row_req_ids` 等平行 list 表示一行；`kv_transfer.py:2069-2092`
  依赖长度检查和重复 index 维持关联。此前并发串扰正与 ownership 未进入 row model 有关。
- 影响：以后新增 row 属性或过滤逻辑时仍容易出现静默错位。
- 建议：考虑引入不可变 `LayerRangeRow` 值对象，使 key、destination、sizes、offsets 和
  owner 结构性绑定。该项不是当前 correctness fix 的必要条件，可由用户决定延后。

#### ST5：Ranged audit emitter 存在重复逻辑

- 状态：待决策。
- 严重级别：P3。
- 判断性质：Standards judgement call；Duplicated Code smell。
- 代码证据：`kv_transfer.py:55-117` 与 `backend/mooncake_backend.py:41-62` 重复实现
  feature gate、JSON logging 和 instrumentation exception isolation。
- 影响：未来修改 payload 或失败策略时，两处审计事件可能产生不一致行为。
- 建议：仅在能保持模块依赖方向清晰时提取共享 emitter；否则保留现状并补充一致性测试。

## 本轮已采纳决策

- 无。等待用户逐项确认上述 `SP1`、`SP2`、`ST1`、`ST2`、`ST3`、`ST4`、`ST5`。
