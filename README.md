# vLLM Workspace

这个仓库是 `vllm-workspace` 的 control repo，用来管理跨仓开发资料、脚本、版本锁定和特性记录。源码仓库放在 `repos/` 下，但源码内容不提交到本仓库。

## 目录

- `AGENTS.md`: Codex 和其他 agent 的 workspace 运作规范。
- `workspace.lock.json`: 三个源码仓库的 remote、branch 和精确 commit 锁定。
- `docs/`: 通用 workspace 说明、Git 工作流和仓库地图。
- `features/kv_offload/`: `kv_offload` 特性的资料、状态、同步日志和笔记。
- `repos/`: 本地源码仓库位置，包含 `vllm`、`vllm-ascend`、`Mooncake`。
- `scripts/`: 初始化、恢复、锁定、同步和状态检查脚本。

## 常用命令

```powershell
.\scripts\bootstrap-repos.ps1
.\scripts\status-all.ps1
.\scripts\lock-repos.ps1
.\scripts\restore-repos.ps1
.\scripts\validate-workspace.ps1
```

跨机器恢复时，先 clone 本仓库，再运行：

```powershell
.\scripts\restore-repos.ps1
.\scripts\status-all.ps1
```

可恢复进度以 `workspace.lock.json` 中记录的已提交 commit 为准，不包含未提交 WIP。
