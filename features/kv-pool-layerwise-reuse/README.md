# kv-pool-layerwise-reuse

本目录维护 vLLM、vLLM Ascend 与 Mooncake 的 layerwise KVPool reuse feature
资料，包括设计决策、部署工具、测试计划、validation report 和正式 evidence。

## 快速入口

| 目标 | 入口 |
| --- | --- |
| 查看源码仓库、branch 和锁定 commit | [repo-state.md](repo-state.md) 与根仓库 `workspace.lock.json` |
| 查看 feature 进展和历史 checkpoint | [status.md](status.md) |
| 部署 1P1D、启动/停止引擎或运行 smoke test | [deployment/README.md](deployment/README.md) |
| 在长期 CPU-only Pod 中运行 vLLM-Ascend UT | [UT Pod design](ut-pod-design.md) 与 [run-vllm-ascend-ut.sh](deployment/run-vllm-ascend-ut.sh) |
| 运行 Multi-DP/TP stress test | [deployment/stress/README.md](deployment/stress/README.md) 与 [run-stress-test.sh](deployment/run-stress-test.sh) |
| 运行 lease-expiry validation | [lease-expiry validation report 与完整 runbook](lease-expiry-validation-2026-07-27.md) |
| 代码或依赖变化后执行完整 validation | [Reusable full validation guide](implementation-plans/full-validation-guide.md) |
| 查看正式结果和校验 checksum | [evidence/README.md](evidence/README.md) |
| 构建或检查 feature image | [nerdctl-build.md](nerdctl-build.md) |
| 阅读设计、RFC 和外部实现快照 | [references/sources.md](references/sources.md) |

所有当前 Kubernetes 测试使用 `liangjiahao` namespace。运行或清理前遵守
[workspace Kubernetes namespace 约束](../../AGENTS.md#kubernetes-测试命名空间)，
不得执行 `evidence/` 中归档的旧命令或脚本副本。

## 文档类型

| 类型 | 用途 |
| --- | --- |
| Runbook | 当前可执行入口；运行前仍需核对 kube context、namespace、镜像和源码身份 |
| Plan | 测试范围、调用顺序、hard gates 和完成条件 |
| Report | 某次已完成 validation 的结论、诊断和复现步骤 |
| Evidence | 按 UTC run ID 归档的原始输出和 checksum，只读且不可原地修订 |
| Reference | 外部 RFC、设计、PR snapshot 和 patch，不代表当前实现状态 |

## Deployment 与测试工具

[deployment/README.md](deployment/README.md) 是部署和日常运行的二级入口，包含
固定输入、preflight、manifest apply 顺序、vLLM 生命周期、smoke test、lease test
以及 Python source sync 说明。

| 内容 | 文件 |
| --- | --- |
| 基础 1P1D manifests | [`deployment/00-namespace.yaml`](deployment/00-namespace.yaml) 到 [`deployment/50-decode-engine.yaml`](deployment/50-decode-engine.yaml) |
| Smoke host runner | [deployment/run-smoke-test.sh](deployment/run-smoke-test.sh) |
| Ranged API driver | [deployment/range-api-smoke.py](deployment/range-api-smoke.py) |
| Lease-expiry driver | [deployment/lease-expiry-test.py](deployment/lease-expiry-test.py) |
| Stress profile | [deployment/stress/README.md](deployment/stress/README.md) 与 [deployment/stress/](deployment/stress/) |
| Stress host/Pod drivers | [deployment/run-stress-test.sh](deployment/run-stress-test.sh) 与 [deployment/stress-test.py](deployment/stress-test.py) |
| Runtime log checkers | [deployment/check-range-debug-log.py](deployment/check-range-debug-log.py) 与 [deployment/check-stress-log.py](deployment/check-stress-log.py) |
| Python-only Pod source sync | [deployment/sync-vllm-ascend-python.sh](deployment/sync-vllm-ascend-python.sh) |
| Dedicated CPU UT Pod | [deployment/60-vllm-ascend-ut-pod.yaml](deployment/60-vllm-ascend-ut-pod.yaml) 与 [deployment/run-vllm-ascend-ut.sh](deployment/run-vllm-ascend-ut.sh) |
| Driver unit tests | [deployment/tests/](deployment/tests/) |
| Original 1P1D validation report | [deployment/validation-2026-07-23.md](deployment/validation-2026-07-23.md) |

## Validation 索引

### Reusable Full Validation

- Stable guide:
  [implementation-plans/full-validation-guide.md](implementation-plans/full-validation-guide.md)
- Historical interrupted run tracker:
  [implementation-plans/2026-07-30-full-validation-rerun.md](implementation-plans/2026-07-30-full-validation-rerun.md)
- Terminated run tracker:
  [implementation-plans/2026-07-30-full-validation-rerun-20260730T130225Z.md](implementation-plans/2026-07-30-full-validation-rerun-20260730T130225Z.md)
- Termination report:
  [full-validation-rerun-2026-07-30.md](full-validation-rerun-2026-07-30.md)
- Per-run machine-readable identity:
  [deployment/validation-identity.json](deployment/validation-identity.json)

Stable guide 不携带历史 run 的默认 SHA、image tag、model dimensions 或 key counts。
每次执行必须新建 dated tracker，并优先采用用户显式指定的版本；未指定字段从当次 clean
checkout、lock、model 和 live runtime 派生后冻结。Run `20260730T130225Z` 已在 G0
因 production ABI defect 终止，修复源码后必须新建 run identity，不得从 G1 续跑。

### 1P1D Smoke

- Runbook: [deployment/README.md](deployment/README.md)
- Runner: [deployment/run-smoke-test.sh](deployment/run-smoke-test.sh)
- Report: [deployment/validation-2026-07-23.md](deployment/validation-2026-07-23.md)
- Evidence index: [evidence/README.md](evidence/README.md)

### Ranged API 与 G4 Runtime Audit

- Plan: [ranged-api-validation-plan.md](ranged-api-validation-plan.md)
- G0-G3 report/runbook:
  [ranged-api-validation-2026-07-23.md](ranged-api-validation-2026-07-23.md)
- G4 report/runbook:
  [ranged-api-g4-validation-2026-07-23.md](ranged-api-g4-validation-2026-07-23.md)
- Direct driver: [deployment/range-api-smoke.py](deployment/range-api-smoke.py)
- G4 checker:
  [deployment/check-range-debug-log.py](deployment/check-range-debug-log.py)
- Evidence index: [evidence/README.md](evidence/README.md)

### Multi-DP/TP、并发与长上下文 Stress

- Validation plan:
  [multi-dp-tp-stress-validation-plan.md](multi-dp-tp-stress-validation-plan.md)
- Implementation checklist:
  [multi-dp-tp-stress-validation-execution-plan.md](multi-dp-tp-stress-validation-execution-plan.md)
- Current deployment entry:
  [deployment/stress/README.md](deployment/stress/README.md)
- Runner: [deployment/run-stress-test.sh](deployment/run-stress-test.sh)
- Workload driver: [deployment/stress-test.py](deployment/stress-test.py)
- Report:
  [multi-dp-tp-stress-validation-2026-07-25.md](multi-dp-tp-stress-validation-2026-07-25.md)
- Evidence index: [evidence/README.md](evidence/README.md)

### Lease Expiry

- Plan: [lease-expiry-validation-plan.md](lease-expiry-validation-plan.md)
- Report and complete runbook:
  [lease-expiry-validation-2026-07-27.md](lease-expiry-validation-2026-07-27.md)
- Driver: [deployment/lease-expiry-test.py](deployment/lease-expiry-test.py)
- Evidence index: [evidence/README.md](evidence/README.md)

## 设计、Review 与实施记录

| 内容 | 文件 | 定位 |
| --- | --- | --- |
| 主实施计划 | [implementation-plan.md](implementation-plan.md) | Backend contract、metadata、ranged transfer、session orchestration 和验收边界 |
| Mooncake multi-group 设计 | [mooncake-multi-group-layerwise-design.md](mooncake-multi-group-layerwise-design.md) | §5.8 的 N-group key、object、session、range、failure contract 和测试边界 |
| Range transfer commit 拆分 | [split-range-transfer-plan.md](split-range-transfer-plan.md) | review-sized commit 与验证顺序 |
| 部署前模型/proxy 确认 | [development-confirmation-request.md](development-confirmation-request.md) | 模型支持、proxy 选择和 E2E 证据要求 |
| Feature branch 整体检视 | [feature-branch-review-2026-07-20.md](feature-branch-review-2026-07-20.md) | findings、风险和当时的验证结果 |
| 已采纳 review 决策 | [review-decisions.md](review-decisions.md) | review 流程、当前范围和用户决策 |
| Feature 状态记录 | [status.md](status.md) | 按时间累积的 checkpoint；较早结论需结合后续 report 阅读 |
| 分支同步历史 | [sync-log.md](sync-log.md) | collaborator/upstream 同步与历史重写记录 |
| 当前 repo 快照 | [repo-state.md](repo-state.md) | 与 `workspace.lock.json` 对应的人类可读状态 |
| Kubernetes UT Pod 设计 | [ut-pod-design.md](ut-pod-design.md) | 长期 CPU-only Pod、源码同步和命令执行 contract |

## References

[references/sources.md](references/sources.md) 是 references 的二级索引：

- [references/snapshots/](references/snapshots/) 保存 RFC、设计和 PR 的 Markdown
  snapshot；
- [references/patches/](references/patches/) 保存固定 revision 的 patch；
- 外部资料的来源、captured revision 和本地文件映射统一维护在
  [references/sources.md](references/sources.md)。

## Image

- Build recipe: [Dockerfile.a2](Dockerfile.a2)
- Build、inspect、containerd namespace 与清理说明:
  [nerdctl-build.md](nerdctl-build.md)

## Evidence 规则

[evidence/README.md](evidence/README.md) 是所有正式 run 的二级索引，按测试族链接
run ID、report 和 `SHA256SUMS`。`evidence/` 下的文件保留实际运行时环境，包括历史
namespace 和当时的脚本快照；这些内容只用于审计和复核，不是当前执行入口。

新增正式 validation 时：

1. 使用新的 UTC run ID。
2. 先完成 plan 定义的全部 hard gates。
3. 生成并验证 `SHA256SUMS`。
4. 将 run 加入 [evidence/README.md](evidence/README.md)。
5. 将对应 report 和本索引更新到新的当前入口。
