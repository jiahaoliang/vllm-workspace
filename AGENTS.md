# AGENTS.md

本文件是 Codex 和其他 agent 在 `vllm-workspace` 中工作的约定。默认用中文协作，保留英文 API、类名、配置项、Git remote 名和源码术语，方便 grep 与源码阅读。

## Workspace 角色

- 根仓库是 control repo，只提交文档、脚本、资料快照、`workspace.lock.json` 和 workspace 元数据。
- 不要把 `repos/*` 下的源码内容提交到根仓库。
- `repos/vllm`、`repos/vllm-ascend`、`repos/Mooncake` 都是普通独立 Git 仓库，不是 submodule。
- 根仓库 `main` 只保存 workspace 基础规范、通用说明、上游基线 lock 和上游社区相关总结。
- feature-specific 信息必须放在对应 feature branch，例如 `kv_offload` 分支中的 `features/kv_offload/`。

## 修改源码前检查

修改 `repos/*` 中源码前，必须确认：

1. 当前工作目录属于哪个源码仓库。
2. 当前 branch 是否符合当前 workspace 分支的目标。
3. `git remote -v` 是否符合当前 workspace 分支的约定。
4. `workspace.lock.json` 当前记录的 commit 是否代表预期基线。
5. 该源码仓库是否有未提交改动。

## Feature 分支约定

- 新特性从 `main` 创建独立 branch。
- feature-specific 资料、同步日志、需求快照、开发笔记必须放在 `features/<feature>/`。
- `repos/Mooncake` 默认只读，用于依赖阅读和必要验证；除非用户明确要求，不创建 feature branch。
- 从合作者分支同步时，必须记录到对应 `features/<feature>/sync-log.md`。
- 每个有意义的开发节点应按顺序完成：源码仓库 commit 并 push 到个人 fork，刷新 `workspace.lock.json`，更新 `features/<feature>/repo-state.md`，最后提交根仓库状态记录。

## 公共内容更新流程

- 修改公共内容时，必须先切到 `main`，在 `main` 上完成修改、验证、提交并推送。
- 公共内容包括 `AGENTS.md`、`README.md`、`docs/`、通用 `scripts/`、根 `.gitignore`、通用 workspace 规范和上游基线 lock。
- `main` 推送完成后，再切到每个受影响的 feature branch，例如 `kv_offload`，执行 `git merge main`，解决冲突后验证、提交并推送该 feature branch。
- 不要直接只在 feature branch 修改公共规则；如果确实先在 feature branch 发现公共问题，也要把公共改动移回 `main`，再 merge 回 feature branch。
- 本流程本身也属于公共规则；修改本流程时必须遵守同样的 `main -> feature branch` 同步顺序。

## 可追溯与恢复

- 不要依赖未提交 WIP 作为可恢复进度。
- 跨机器恢复只保证已提交且可 fetch 的 commit。
- `workspace.lock.json` 是机器可读的恢复依据。
- 更新源码仓库 commit 后，运行 `.\scripts\lock-repos.ps1` 刷新锁文件。
- 恢复 workspace 时，运行 `.\scripts\restore-repos.ps1`，再运行 `.\scripts\status-all.ps1` 检查状态。

## 外部资料

- 外部需求文档和 RFC 必须保存 Markdown 快照。
- 每个快照文件头必须包含 `Source`, `Captured At`, `Notes`。
- 原始链接索引维护在对应 feature branch 的 `features/<feature>/references/sources.md`。
- 遇到 `mooncake-learning` 相关资料时，只引用必要概念或路径，不直接迁移整个学习仓库内容。
