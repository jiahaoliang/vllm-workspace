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
