# AGENTS.md

本文件是 Codex 和其他 agent 在 `vllm-workspace` 中工作的约定。默认用中文协作，保留英文 API、类名、配置项、Git remote 名和源码术语，方便 grep 与源码阅读。

## Workspace 角色

- 根仓库是 control repo，只提交文档、脚本、资料快照、`workspace.lock.json` 和 workspace 元数据。
- 不要把 `repos/*` 下的源码内容提交到根仓库。
- `repos/vllm`、`repos/vllm-ascend`、`repos/Mooncake` 都是普通独立 Git 仓库，不是 submodule。
- 根仓库 `main` 只保存 workspace 基础规范、通用说明和上游社区相关总结；特性开发使用独立 branch。

## 修改源码前检查

修改 `repos/*` 中源码前，必须确认：

1. 当前工作目录属于哪个源码仓库。
2. 当前 branch 是否符合任务，例如 `kv_offload`。
3. `git remote -v` 是否包含约定的 `origin`、`upstream`、`collaborator`。
4. `workspace.lock.json` 当前记录的 commit 是否代表预期基线。
5. 该源码仓库是否有未提交改动。

## kv_offload 约定

- `kv_offload` 默认涉及 `repos/vllm` 和 `repos/vllm-ascend`。
- `repos/Mooncake` 默认只读，用于依赖阅读和必要验证；除非用户明确要求，不创建 `kv_offload` 分支。
- 从合作者分支同步时，必须记录到 `features/kv_offload/sync-log.md`。
- 每个有意义的开发节点应按顺序完成：源码仓库 commit 并 push 到个人 fork，刷新 `workspace.lock.json`，更新 `features/kv_offload/repo-state.md`，最后提交根仓库状态记录。

## 可追溯与恢复

- 不要依赖未提交 WIP 作为可恢复进度。
- 跨机器恢复只保证已提交且可 fetch 的 commit。
- `workspace.lock.json` 是机器可读的恢复依据；`features/kv_offload/repo-state.md` 是人类可读的状态说明。
- 更新源码仓库 commit 后，运行 `.\scripts\lock-repos.ps1` 刷新锁文件。
- 恢复 workspace 时，运行 `.\scripts\restore-repos.ps1`，再运行 `.\scripts\status-all.ps1` 检查状态。

## 外部资料

- 外部需求文档和 RFC 必须保存 Markdown 快照。
- 每个快照文件头必须包含 `Source`, `Captured At`, `Notes`。
- 原始链接索引维护在 `features/kv_offload/references/sources.md`。
- 遇到 `mooncake-learning` 相关资料时，只引用必要概念或路径，不直接迁移整个学习仓库内容。
