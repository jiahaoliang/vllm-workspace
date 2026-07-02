# Git Workflow

## main 分支 Remote 命名

`main` 记录上游社区基线：

`repos/vllm`:

- `origin`: `https://github.com/vllm-project/vllm.git`

`repos/vllm-ascend`:

- `origin`: `https://github.com/vllm-project/vllm-ascend.git`

`repos/Mooncake`:

- `origin`: `https://github.com/kvcache-ai/Mooncake.git`

## Feature 分支 Remote 命名示例

以 `kv_offload` 为例，feature branch 可以把 `origin` 指向个人 fork，并额外添加 `upstream` 和 `collaborator`：

`repos/vllm`:

- `origin`: `https://github.com/jiahaoliang/vllm.git`
- `upstream`: `https://github.com/vllm-project/vllm.git`
- `collaborator`: `https://github.com/zhangsicheng5/vllm.git`

`repos/vllm-ascend`:

- `origin`: `https://github.com/jiahaoliang/vllm-ascend.git`
- `upstream`: `https://github.com/vllm-project/vllm-ascend.git`
- `collaborator`: `https://github.com/zhangsicheng5/vllm-ascend.git`

## Feature 分支同步

特性分支初始基线可以来自合作者分支，本地开发提交推送到个人 fork。

示例：

```powershell
cd repos\vllm-ascend
git fetch collaborator
git switch kv_offload
git rebase collaborator/kv_offload
git push origin kv_offload
cd ..\..
.\scripts\lock-repos.ps1
```

如果分支已经多人共享并且不适合改写历史，可以改用 merge；同步原因和冲突处理必须写入对应 feature branch 的 `features/<feature>/sync-log.md`。
