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

## Kubernetes 测试命名空间

- 本 workspace 创建或运行的 Kubernetes 测试 workload 必须使用 `liangjiahao` namespace。
- 禁止在 manifest、脚本、测试计划、validation 文档或 runbook 中将 `ai-inference` 用作可执行命令的 namespace；发现旧引用时应先迁移到 `liangjiahao` 再运行。
- 所有 `kubectl apply`、`exec`、`logs`、`cp`、`port-forward`、`rollout` 和清理命令必须显式限定 `liangjiahao`，不得依赖当前 context 的 default namespace。
- 唯一例外是共享镜像构建基础设施 `buildkitd`：它必须运行在 `default` namespace，相关 `kubectl apply`、`exec`、`logs` 和清理命令必须显式指定 `-n default`，`BUILDKIT_HOST` 必须使用显式 namespace 的 `kube-pod://buildkitd?namespace=default`；此例外不适用于 UT、serving 或其他 feature workload。
- 清理测试资源前必须同时核对 kube context、namespace 和目标资源名；不得删除整个 namespace，除非用户明确要求。

## Kubernetes UT 执行环境

- 当前工作环境可访问 Kubernetes 且已有适配当前源码基线的测试镜像时，CPU/mock unit tests 必须在 `liangjiahao` namespace 的专用长期运行 UT Pod 中执行，不得复用 Prefill、Decode 等 serving Pod。
- CPU/mock UT Pod 不得申请 `huawei.com/Ascend910`，不得挂载 NPU device、driver、`npu-smi` 或模型缓存；只有测试目录或测试说明明确要求真实 NPU 的测试才允许使用 NPU test Pod。
- 当前 checkout 必须通过 tar + `kubectl exec` 同步到 Pod 的临时 workspace；不得使用 hostPath 挂载源码。每次执行前必须记录或核对源码 commit、branch 和 dirty 状态。
- UT Pod 只提供执行环境，不得隐式运行默认 test suite；调用者必须在命令行显式指定 pytest target 或其他测试命令，并禁用会污染同步源码的 bytecode 和 pytest cache。
- UT 完成后默认保留长期运行 Pod。需要清理时只能删除明确命名的 UT Pod，不得删除 `liangjiahao` namespace。

## 测试镜像复用

- 默认优先复用已有且 native 依赖兼容的测试镜像，不要仅因 vLLM 或 vLLM-Ascend 的 Python 源码变化就重新构建镜像。镜像构建通常耗时较长，只有复用路径不能满足测试身份或运行要求时才执行。
- Mooncake 源码、native library、CANN/torch_npu 等二进制依赖未变化时，应使用包含对应 Mooncake/native 版本的已有镜像，并在目标 Pod 启动服务前，通过显式 `-n liangjiahao` 的 `kubectl cp` 或 tar + `kubectl exec` 覆盖修改后的 Python 文件。
- Python 覆盖必须限定为本次需要的文件；覆盖后、启动流量前必须记录基础镜像 reference/digest、对应 native/Mooncake 源码身份、Python 源 commit、覆盖文件列表，并逐文件校验 Pod 内 SHA256。不得把 Python 覆盖描述为完整镜像重建。
- 只有 Mooncake/native 源码或二进制依赖更新、目标镜像缺少必要运行依赖、Python 覆盖无法在服务启动前生效，或用户明确要求新镜像时，才构建或派生新镜像；执行前应说明不能复用已有镜像的具体原因。

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
- Linux 更新源码仓库 commit 后，运行 `./scripts/lock-repos.sh` 刷新锁文件；PowerShell 使用 `.\scripts\lock-repos.ps1`。
- Linux 恢复 workspace 时，运行 `./scripts/restore-repos.sh`，再运行 `./scripts/status-all.sh` 检查状态；PowerShell 使用对应的 `.ps1` 入口。
- Linux 维护脚本要求 Bash 4+、Git 2.23+ 和 jq 1.6+；执行公共脚本回归测试使用 `./scripts/tests/test-linux-maintenance-scripts.sh`。

## 外部资料

- 外部需求文档和 RFC 必须保存 Markdown 快照。
- 每个快照文件头必须包含 `Source`, `Captured At`, `Notes`。
- 原始链接索引维护在对应 feature branch 的 `features/<feature>/references/sources.md`。
- 遇到 `mooncake-learning` 相关资料时，只引用必要概念或路径，不直接迁移整个学习仓库内容。

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default triage label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Use the single-context domain documentation layout. See `docs/agents/domain.md`.
