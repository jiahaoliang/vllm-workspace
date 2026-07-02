# Workspace Guide

`vllm-workspace` 是跨仓开发的控制仓库，不直接承载 `vllm`、`vllm-ascend`、`Mooncake` 的源码历史。源码仓库使用普通 `git clone` 放在 `repos/` 下，根仓库通过 `.gitignore` 忽略 `repos/*`。

这种结构的目标是同时满足两件事：

1. 日常开发保持普通 Git 仓库体验，方便在源码仓库里同步分支、rebase、commit 和 push。
2. 根仓库通过 `workspace.lock.json` 记录精确 commit，使另一台机器可以恢复到相同的已提交进度。

## 分支模型

`main` 只保存所有特性共享的 workspace 规范、通用脚本、上游基线 lock 和通用文档。具体特性从 `main` 创建独立分支，例如 `kv_offload`。

feature-specific 内容必须放在对应 feature branch 的 `features/<feature>/` 下，包括需求快照、RFC 快照、同步日志、调查笔记和特性状态。

## 开发节点

每完成一个可回溯的开发节点：

1. 在源码仓库 commit。
2. push 到对应远端。
3. 回到根仓库运行 `.\scripts\lock-repos.ps1`。
4. 在 feature branch 更新相关 `features/<feature>/` 状态或同步日志。
5. 提交根仓库。

未提交的 WIP 不属于可恢复进度。
