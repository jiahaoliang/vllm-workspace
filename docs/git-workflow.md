# Git Workflow

## Remote 命名

`repos/vllm`:

- `origin`: `https://github.com/jiahaoliang/vllm.git`
- `upstream`: `https://github.com/vllm-project/vllm.git`
- `collaborator`: `https://github.com/zhangsicheng5/vllm.git`

`repos/vllm-ascend`:

- `origin`: `https://github.com/jiahaoliang/vllm-ascend.git`
- `upstream`: `https://github.com/vllm-project/vllm-ascend.git`
- `collaborator`: `https://github.com/zhangsicheng5/vllm-ascend.git`

`repos/Mooncake`:

- `origin`: `https://github.com/kvcache-ai/Mooncake.git`

## kv_offload 分支

`vllm` 和 `vllm-ascend` 使用 `kv_offload` 分支。初始基线优先来自 `collaborator/kv_offload`，本地开发提交推送到 `origin/kv_offload`。

推荐同步流程：

```powershell
cd repos\vllm-ascend
git fetch collaborator
git switch kv_offload
git rebase collaborator/kv_offload
git push origin kv_offload
cd ..\..
.\scripts\lock-repos.ps1
```

如果分支已经多人共享并且不适合改写历史，可以改用 merge；同步原因和冲突处理必须写入 `features/kv_offload/sync-log.md`。
