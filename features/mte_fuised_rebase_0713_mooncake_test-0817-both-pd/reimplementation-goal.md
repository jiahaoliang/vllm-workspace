# Blockwise DSA PD Offload 重实现 Goal

状态：sync replacement source已实现并发布；async delta已批准、implementation pending；旧source/test授权与stop lines不自动延伸到async delta

## Async follow-up boundary

本文件及其Stage 1/Stage 3/white-box amendments记录已发布sync replacement `7401ae79c`的实现与授权历史。Async-compatible contract现以[spec.md](spec.md)、ADR 0024-0030和[implementation ticket chain](issues/16-define-doc-supersession-implementation-chain.md)为准；旧文档中的async fail-closed、single-active `FUSED_D2H` / `D2H_COMPLETE`与Phase B completion gate已按各自supersession pointer收窄为历史baseline。

创建async implementation tickets不授权修改`repos/*`。后续session必须单独取得source修改授权，并按新ticket的文件范围与stop-and-review条件执行；旧replacement的`1770/1500`行数stop lines、TDD allowlist和Pod验证授权不能直接复用。

## 使用方式与优先级

本文件是已发布sync replacement历史的持久入口。处理该历史或开始async follow-up前仍须完整读取本文件；async follow-up还必须读取当前spec、ADR 0024-0030和被认领的implementation ticket，不得用conversation summary代替这些artifact。

进入或继续 Stage 2 时，还必须完整读取已批准的
[`reimplementation-stage1-design-gate.md`](./reimplementation-stage1-design-gate.md)。该文件是本 goal 的 normative companion，不需要在 `/goal` prompt 中另行摘要。

当前 Stage 2 审计发现 multi-node endpoint routing correctness blocker。继续相关
production 改动前，还必须完整读取
[`reimplementation-stage1-routing-amendment.md`](./reimplementation-stage1-routing-amendment.md)。
用户已于 2026-08-23 明确批准该 amendment 的方案 A；Stage 2 必须使用完整 immutable
Prefill-rank endpoint tuple 替换 scalar `RemoteSource` endpoint，并遵守 amendment 的
行数预算、TDD 和再次停审条件。该增量批准不改变本文件规定的 replacement 方向，也不
授权新增 standalone subsystem。

Stage 3 static review 又发现 request-ID terminal tombstone、真实 replay-forward evidence
和 structured replay observation 三个收尾缺口。继续相关 production source 修改前，
必须完整读取
[`reimplementation-stage3-closure-amendment.md`](./reimplementation-stage3-closure-amendment.md)。
用户已于 2026-08-24 明确批准该 amendment 的方案 A，以及 production additions
`1,710`、focused test additions `1,200` 的修订停审线；Stage 3 source/test 收尾必须
遵守该 amendment 的 snapshot、public replay、structured observation、TDD 与再次停审
条件。该批准不授权 commit、push、lock/repo-state/issues 更新或 final feature status。

Stage 3 final review 对 terminal retirement、public replay-forward、structured replay
observation、async scheduling 和 one-shot finish delivery 做了统一收敛。唯一有效的 Stage 3
增量门禁是 `reimplementation-stage3-closure-amendment.md`；曾提出的 private terminal
interval fence 已被 command-never-emitted reservation 反例推翻，不再是候选方案。

Closure implementation 的 post-approval budget audit 已触发 focused tests `1,200` 停审线：
当前实际为 `1,237` additions，且 real Scheduler preemption、rebound Indexer table、
preserved Main suffix-only D2H 和 nonzero exact-TP observation evidence 尚未补齐。继续任何
replacement source/test 修改或 Pod 验证前，必须完整读取
[`reimplementation-stage3-test-budget-amendment.md`](./reimplementation-stage3-test-budget-amendment.md)。
用户已于 2026-08-24 明确批准该 amendment 的方案 A：production stop line 保持 `1,710`，
focused-test stop line 修订为 `1,320`，并授权 thin replay admission 修复、public evidence
收尾与 UT Pod 验证。不得把删除必要 boundary tests 或压缩可读性作为满足预算的方法；该
批准不授权 commit、push、lock/repo-state/issues 更新或 final feature status。

Four-commit replacement implementation完成后的 white-box review 又确认三项 corrective
implementation delta，并留下一个
worker ordering决策点。继续 replacement source/test修改前，必须完整读取
[`reimplementation-whitebox-review-amendment.md`](./reimplementation-whitebox-review-amendment.md)。
用户已于 2026-08-24 明确采纳 Main reservation按 `max_model_len`截断、DSA receive复用
receiver request queue/per-peer serialization、stale result bounded observation三项方向；当前
三项必须与后续 ordering gate统一实现。

Worker ordering white-box review已经证明 generic non-`QUIESCE` pending successor在当前
scheduler causality下不可达，并确认 cancellation ack drain race与 terminal atomicity要求；
最初提出的旧 receive result按 `QUIESCE` action错误 fail-fast假设已被 deterministic test反证。
继续 replacement
source/test修改前，还必须完整读取
[`reimplementation-whitebox-ordering-amendment.md`](./reimplementation-whitebox-ordering-amendment.md)。
用户已于 2026-08-24 明确批准删除 generic `pending_command`、newer non-`QUIESCE`
overlap fail closed、`QUIESCE` terminal synchronization与atomic ordinary ack drain，并把
production/focused-test stop line修订为 `1,770`/`1,460`。该批准授权在 amendment allowlist内
执行 TDD source/test修改和 CPU/mock focused validation；不授权 NPU、commit、push、
lock/repo-state/issues更新或 final feature status。

Ordering implementation完成首轮 TDD 后，完整 diff预算核对发现 focused tests实际为
`1,478` additions，超过已批准的 `1,460` stop line共18行。继续任何 replacement
source/test修改或 Pod验证前，还必须完整读取
[`reimplementation-whitebox-ordering-budget-amendment.md`](./reimplementation-whitebox-ordering-budget-amendment.md)。
用户已于 2026-08-24 明确批准该 amendment 的方案 A：production stop line保持`1,770`，
focused-test stop line修订为`1,500`，并授权恢复现有allowlist内的必要source/test修正与
CPU/mock验证。该批准不授权 NPU、commit、push、lock/repo-state/issues更新或 final feature
status。

本指令覆盖旧 goal 中以下方向：

- 继续完善、发布或把 `60eb76e` 记录为最终实现；
- 主 agent 只跟踪进度、由 subagents 自行决定架构。

仓库 `AGENTS.md`、当前 feature spec 和 accepted ADR 继续生效。旧 issue answer 或 status 如果基于 `f826ea3f`、`60eb76e` 且与本文件冲突，在 tracker 被纠正前以本文件为准。

## 目标

1. 安全完成当前 goal 的审计与保全收尾，但不发布超出设计范围的旧实现。
2. vLLM-Ascend commit `60eb76e46225e9aaec1493fb247313f8642486ad` 只作为行为参考和 test oracle。
3. 从其干净 parent `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 重新实现，架构收敛为：
   - `MooncakeConnectorV1` 内的 opt-in mode；
   - 一套独立的 typed DSA metadata contract；
   - 对现有 SFA scheduler、worker、memory 和 `fused_overlap` 行为的 thin extension 或 adapter。
4. 不在 `60eb76e` 引入的 standalone DSA subsystem 上继续补代码。

## Stage 0：安全收尾当前实现

修改源码前必须：

- 重新核对 control repo 和所有相关 source repo 的 cwd、branch、HEAD、remote、tracking status、dirty state、worktree binding 与 `workspace.lock.json`。
- 声称 commit 是否发布前必须实时核对 remote state。
- 保留 `60eb76e` 和已有 dirty/untracked work 作为 reference evidence；不得 reset、删除、覆盖、amend、merge 或 push 它。
- `deployment_yaml/` 和其他无关用户 WIP 不得进入任何 staging 操作。
- 识别 stale `f826ea3f`/`60eb76e` 引用和过早 resolved 的 issue，但不得用旧实现刷新最终 lock、repo-state、issue answer 或 release claim。
- Static、CPU/mock 和 NPU evidence 分开；NPU 在真实执行前始终为 `planned / not run`。
- 完成或终止当前实现遗留的 command session。长期 UT Pod 默认保留；任何 Kubernetes cleanup 前必须核对 context、显式 namespace 和精确资源名。
- 先向用户报告 Stage 0 结果与保留的 reference point，再进入 redesign。

“继续完成当前 goal”不表示继续发布 `60eb76e`，而是先让旧实现处于已知、可恢复、报告准确的状态，再进行 replacement。

## Stage 1：最小改动设计门禁

修改 production source 前，必须先向用户提交以下内容并等待明确批准：

- `60eb76e` 中 replacement 必须保留的 externally observable behavior；
- `MooncakeConnectorV1`、`MooncakeConnectorScheduler`、`MooncakeConnectorWorker`、`SFAPDCpuOffloadScheduler` 和 `SFAKVOffloadWorker` 已有的可复用行为；
- state ownership map，明确 scheduler state、worker state、SFA state、Mooncake transfer state 和 memory ownership 的唯一事实来源；
- 逐文件 implementation plan 和预计 additions/deletions；
- 与 accepted ADR boundary 和行数估算的对照。

默认 production change surface：

- `mooncake_connector.py` 是主要 integration/lifecycle 位置；
- 一个 feature-local typed DSA metadata module；
- 只在必须扩展现有行为时，对现有 SFA scheduler、worker、metadata 或 memory binding 做薄改动；
- 聚焦 public lifecycle 和 contract 的 tests。

Accepted design 要求 Decode blockwise scheduler 继承或薄扩展现有 `SFAPDCpuOffloadScheduler`。如果源码分析证明不可行，必须暂停并提出 ADR change，不得静默替换成 independent scheduler。

Replacement 默认禁止引入或保留下列 parallel components：

- 重写 connector scheduler hook surface 的 standalone `MooncakeDsaScheduler`；
- `DsaWorkerLifecycleExecutor` 加 `DsaWorkerAdapter` framework；
- 独立的 `MooncakeDsaDecodeRuntime` lifecycle layer；
- 大型 independent `MooncakeDsaDecodeWorker`；
- 可以在现有实现上扩展、却重新建立的 Mooncake transport、rendezvous、memory 或 Prefill worker subsystem。

如果额外 component 确实不可避免，必须先说明现有代码为什么不能承担该职责、比较至少一个更小方案、估算代码量，并等待用户明确批准。仅以 testability 或 separation 为由不能扩大架构。

以下数字是 stop-and-review threshold，不是目标：

- planned production additions 超过 1,950 行时暂停评审；
- planned focused tests 超过 spec 的 1,100 行时暂停评审；
- 方案超过一个主要 `MooncakeConnectorV1` lifecycle seam，加 typed metadata 与 SFA memory/data-plane support seams 时暂停评审。

## Stage 2：重新实现

- 在基于 `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 的新 branch 或 worktree 中非破坏性工作，不得 reset reference branch。
- 不 cherry-pick `60eb76e`，也不整体复制其 subsystem；只迁移 approved behavior list 和当前 spec/ADR 要求的行为。
- `dsa_pd_offload=false` 时，普通 `MooncakeConnectorV1` scheduler、metadata、worker、transfer 和 completion path 保持不变。
- 复用 Decode-initiated block pull、现有 endpoint routing、Mooncake transfer helpers、SFA scheduler lifecycle 和 `SFAKVOffloadWorker` 的 `fused_overlap` 行为。
- Typed metadata 只承载 cross-process contract，不得把 process-local runtime state 扩张成新 framework。
- 每个 request lifecycle fact 只有一个 authoritative owner，避免在 connector、runtime、executor 和 worker wrapper 中镜像状态。
- 按可审查行为形成小 commit，不得再次生成单一 oversized commit。

Main agent 负责 source tracing、架构、文件/行数预算、diff review 和最终集成。Subagents 只可执行有边界的只读审计或独立 test review，不得自行决定架构，也不得并发修改核心实现文件。

## Stage 3：验证与发布门禁

- 主 test seam 是 public `MooncakeConnectorV1` lifecycle：admission、allocation、metadata、worker receive、worker result、scheduler output consumption、request completion 和 default-mode isolation。
- 只为 typed metadata contract 和无法通过主 seam 观察的 SFA memory/data-plane boundary 增加直接 tests；不得为每个 private helper 或内部 module 建立镜像 test suite。
- CPU/mock tests 按 `AGENTS.md` 在 `liangjiahao` namespace 的专用长期 UT Pod 中运行，遵守 source sync 和 no-cache 要求。
- Static、CPU/mock、default V1 regression 和 NPU runtime evidence 分别报告。不得由 mock 推断真实 D2D、D2RH、NPU-addressable Host registration、fused kernel correctness 或 performance。

任何 push 或最终 control-repo 更新前，必须先展示：

- base/head SHA；
- 完整逐文件 diffstat；
- production/test additions 与 deletions 总量；
- 对本文件、spec 和 ADR 0002 的 architecture compliance；
- test commands 与 results；
- 剩余 correctness/NPU risks；
- proposed source commits、lock update、repo-state update、issue-status update 和 control-repo staging allowlist。

Replacement push、`workspace.lock.json` 刷新、issue resolved 和最终 feature status commit 都必须等待用户明确批准。批准后按 `AGENTS.md` 顺序执行：source commit/push、lock refresh、repo-state、feature docs、control-repo commit。

用户已于 2026-08-24 明确批准 source commit/push，随后明确批准整理 control repo。最终 source branch 为 `feature/blockwise-dsa-mooncake-v1-reimplementation`，published HEAD 为 `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`。Control-repo 收尾必须使用该 fetchable identity，修正所有基于 `f826ea3f`/`60eb76e` 的旧答案，并保持 NPU 为 `planned / not run`。

## 完成条件

仅当以下条件全部满足时，goal 才算完成：

- 最终 implementation branch 不包含 `60eb76e` 的 standalone DSA subsystem；
- 实现以 `MooncakeConnectorV1`、typed metadata 和 thin SFA extensions 为主；
- Default V1 isolation 和要求的 DSA behavior 都有可审查 evidence；
- 实际代码量和 module boundary 已与 approved design/estimate 对齐；
- NPU 未真实执行时始终为 `planned / not run`；
- source commits、remote state、workspace lock、repo-state、issues、feature docs 和 validation evidence 一致且可恢复。
