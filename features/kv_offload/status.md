# kv_offload Status

Captured At: 2026-07-02

## 当前状态

- Workspace 初始化中。
- `vllm` 和 `vllm-ascend` 计划使用 `kv_offload` 分支。
- Mooncake 默认跟随 `main`，用于阅读和验证。

## 下一步

1. 运行 `.\scripts\bootstrap-repos.ps1` 初始化三个源码仓库。
2. 运行 `.\scripts\lock-repos.ps1` 写入实际 commit。
3. 阅读 `references/snapshots/` 下的需求和 RFC。
4. 根据源码状态拆分具体开发任务。
