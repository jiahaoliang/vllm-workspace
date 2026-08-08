# vLLM Workspace

这个仓库是 `vllm-workspace` 的 control repo，用来管理跨仓开发的公共规范、脚本、版本锁定和通用文档。源码仓库放在 `repos/` 下，但源码内容不提交到本仓库。

## 目录

- `AGENTS.md`: Codex 和其他 agent 的 workspace 运作规范。
- `workspace.lock.json`: 三个源码仓库的 remote、branch 和精确 commit 锁定。
- `docs/`: 通用 workspace 说明、Git 工作流和仓库地图。
- `features/`: 特性分支中的特性资料目录；`main` 只保留公共信息。
- `repos/`: 本地源码仓库位置，包含 `vllm`、`vllm-ascend`、`Mooncake`。
- `scripts/`: 初始化、恢复、锁定、同步和状态检查脚本。

## 分支约定

- `main`: 只保存公共 workspace 结构、通用脚本、上游基线和通用文档。
- feature branch: 从 `main` 创建，例如 `kv_offload`，保存该特性的资料、lock、同步记录和开发笔记。

## 常用命令

Linux 需要 Bash 4+、Git 2.23+ 和 jq 1.6+：

```bash
./scripts/bootstrap-repos.sh
./scripts/status-all.sh
./scripts/lock-repos.sh
./scripts/restore-repos.sh
./scripts/validate-workspace.sh
```

PowerShell 环境使用等价入口：

```powershell
.\scripts\bootstrap-repos.ps1
.\scripts\status-all.ps1
.\scripts\lock-repos.ps1
.\scripts\restore-repos.ps1
.\scripts\validate-workspace.ps1
```

跨机器恢复时，先 clone 本仓库；Linux 运行：

```bash
./scripts/restore-repos.sh
./scripts/status-all.sh
```

PowerShell 运行：

```powershell
.\scripts\restore-repos.ps1
.\scripts\status-all.ps1
```

可恢复进度以 `workspace.lock.json` 中记录的已提交 commit 为准，不包含未提交 WIP。
Linux 的 `restore-repos.sh` 和 `bootstrap-repos.sh` 都恢复精确 lock；如果已有源码仓库包含未提交改动，脚本会在 fetch 或 checkout 前拒绝执行。
