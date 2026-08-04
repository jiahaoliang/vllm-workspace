# Multi-DP/TP、并发与长上下文验证计划

**状态：** Approved for execution on 2026-07-24。详细实施顺序、文件接口和命令边界见
[multi-dp-tp-stress-validation-execution-plan.md](multi-dp-tp-stress-validation-execution-plan.md)。
本文只定义验收目标，不记录测试结果。

## 1. 目标与验证边界

在已经完成的 G0-G4 基础上，继续验证当前 layerwise Mooncake KVPool 路径在下列组合条件下的行为：

1. Prefill 使用 local `DP=2, TP=2`，Decode 使用 `DP=1, TP=2`；
2. 通过 proxy 同时处理 16 个请求；
3. 处理 16K 和 32K 级别的长 prompt；
4. 用运行时 iteration evidence 证明长 prompt 确实被 chunked prefill 拆成多轮执行；
5. 在上述压力下继续满足逐层 ranged save/load、final commit、whole-key exclusion 和输出正确性。

本轮是部署和边界验证，不建设新的通用测试框架，也不修改 `repos/vllm`、
`repos/vllm-ascend` 或 `repos/Mooncake` 的生产代码。复用现有：

- `AscendStoreConnector + backend=mooncake + use_layerwise=true`；
- `[KVPOOL_RANGE_DEBUG]` instrumentation；
- response signature、marker isolation 和 empty-pool baseline 方法；
- `sleep infinity` engine Pod、`kubectl cp` source sync 和 Pod 内手动进程重启流程。

本轮不验证 PP、PCP、DCP、TP mismatch、multi-node DP，也不设置吞吐或 latency 的 pass/fail
阈值。性能数据只作为后续比较基线。

### 1.1 Runtime contract 修正（2026-07-25）

失败 run `20260725T015720Z` 证明当前 `AscendStoreConnector + backend=mooncake + use_layerwise=true`
使用共享 block hash KVPool，而不是依赖 Prefill response 携带 PD metadata：运行中的 proxy 在 Prefill
返回 `kv_transfer_params: null` 时直接向 Decode 发送原始 request body。该 run 还证明 chunked
Prefill 每个 chunk 分别执行 final-layer commit；16K case 的 16 次成功 commit 的 `key_count` 总和为
127。后续 pinned driver 和 checker 按此真实合同执行，最终报告必须链接该失败 run 并说明修正。

## 2. 固定基线与当前环境

| 输入 | 固定值 |
|---|---|
| control repo branch | `kv-pool-layerwise-reuse` |
| plan 编写时 control HEAD | `83ad04821a2ba252a329910d0c407b61b52a3e39` |
| vLLM | `d02df748bf9efd99022f1a062597dc3cb3808485` |
| vLLM-Ascend | `08b4f531d585fbfa5e365fa7d5f5e812bc80ab16` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-08b4f531-20260730` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| namespace / node | `liangjiahao` / `n1` |
| model layers | `27` |
| model max positions | `163840` |

2026-07-24 的只读检查结果：

- `n1` 有 8 张 `Ascend910`，所选 profile 需要 6 张；替换现有 1+1 卡 engine Pods 后，
  当前其他 workload 不阻止该 placement；
- host 约有 2 TiB RAM，model cache 约 17 GiB，model-cache filesystem 约有 4 TiB 可用；
- Prefill 和 Decode Pod 的 `/dev/shm` 均为 24 GiB；
- 两个 Pod 内现有 `check-runtime.py` 均通过，确认 editable vLLM-Ascend import、
  vLLM `0.25.1` compatibility gate、固定 `PYTHONHASHSEED=0` 和 Mooncake session/range APIs；
- 当前 vLLM engine 进程已经停止，Pod 仍为 Running。

这些是 plan 编写时的快照，不是执行时保证。正式执行必须重新完成 preflight，并把实时结果归档。

根仓库中现有无关 untracked 文件必须保留，不得 stage、覆盖、reset 或 stash：

```text
deployment_yaml/
dockerfile.vllm23
```

## 3. 单一 Stress Deployment Profile

所有 workload 使用同一组 Pod 和 engine 参数。只在进入 stress profile 时重建一次 engine Pods；
三个场景之间只停止/启动 Pod 内 vLLM 进程，并在进程停止期间重启 Mooncake Master 清空 pool。

### 3.1 固定并行拓扑

| 参数 | Prefill | Decode |
|---|---:|---:|
| `--data-parallel-size` | `2` | `1` |
| `--data-parallel-size-local` | `2` | 不设置 |
| `--tensor-parallel-size` | `2` | `2` |
| `--pipeline-parallel-size` | `1` | `1` |
| `--prefill-context-parallel-size` | `1` | `1` |
| `--decode-context-parallel-size` | `1` | `1` |
| requested `huawei.com/Ascend910` | `4` | `2` |

两端必须保持相同 TP。当前 block-key layerwise Mooncake 路径允许 DP，但明确拒绝
PP/PCP/DCP 大于 1；`use_layerwise=true` 也不支持 Prefill/Decode TP mismatch。

DeepSeek-V2 使用 MLA。在 `TP=2` 时，两个 TP rank 参与模型计算，但 layerwise transfer 的
logical key owner 由 `put_step` 合并，因此不能用“每 block 必须产生两个 Mooncake keys”证明 TP。
TP 必须通过 engine config、进程和 NPU device evidence 证明。

### 3.2 固定 serving 参数

两端都使用：

```text
--block-size 128
--enable-chunked-prefill
--max-model-len 65536
--max-num-batched-tokens 1024
--max-num-seqs 16
--no-enable-prefix-caching
--enable-logging-iteration-details
--gpu-memory-utilization 0.90
```

保留现有 quantization、eager mode、served model、KV transfer config 和 Mooncake config。
启动环境增加 `VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1`。`max-model-len=65536` 同时覆盖三档
workload，且低于模型声明的 163840 positions。

### 3.3 Manifest 组织

- 保留现有 `deployment/10-runtime-config.yaml`、`40-prefill-engine.yaml` 和
  `50-decode-engine.yaml`，避免改变 G0-G4 历史 live-rerun 基线。
- 在 `deployment/stress/` 新增完整的 stress runtime ConfigMap 和两个 engine Deployment
  manifests；Deployment resource 名和 label 保持现有值，以便 proxy 无需修改。
- stress ConfigMap 使用独立名称 `layerwise-stress-runtime-config`，包含同等功能的
  `mooncake.json`、runtime check、start/stop scripts，但启动参数固定为本节定义的 profile。
- engine 容器仍以 `sleep infinity` 作为 PID 1，不增加 hostPath source mount。
- namespace、Mooncake Master 和 proxy 继续直接复用现有 manifests，不复制或修改。

## 4. 实施产物

新增最小、feature-local 的测试工具：

1. `deployment/run-stress-test.sh`
   - 执行 preflight、profile apply、source sync、手动启停、Master reset、artifact capture 和
     fail-closed 汇总；
   - 任一 `kubectl`、HTTP、checker、artifact write 或 checksum 失败即返回非零；
   - 不自动删除或修改其他 namespace 的 workload。
2. `features/kv-pool-layerwise-reuse/deployment/stress-test.py`
   - 构造 deterministic token-ID prompts；
   - 建立 empty-pool decoder baselines；
   - 支持 direct pinned PD 两段调用以及 proxy concurrent 调用；
   - 比较 response signature、request marker 和 usage token counts。
3. `deployment/check-stress-log.py`
   - 解析 `EngineCore_DP*` iteration details 和 `[KVPOOL_RANGE_DEBUG]` JSON；
   - 同时支持单请求 line window 和并发 aggregate window；
   - 校验 layer set、bytes、commit ordering、whole-key exclusion 和 DP activity。

给 fixture builder 和 checker 增加窄范围 unit tests。不得引入新的测试框架或复制一套 vLLM
upstream harness。

## 5. 公共执行生命周期

每次正式 run 按以下顺序执行：

1. 确认 control/source repos、`workspace.lock.json`、image digest 和 model identity；
2. 确认 `n1` 在 Recreate 旧 engine Pods 后能够调度 4-card Prefill 和 2-card Decode；
3. 停止现有 vLLM 进程，apply stress ConfigMap 和 engine Deployments；
4. 等待两个 Pod Running；由于 PID 1 是 `sleep infinity`，此时不要求 readiness probe 成功；
5. 运行 `sync-vllm-ascend-python.sh`，再在两个 Pod 中运行 `check-runtime.py`；
6. 在 engine 尚未启动时重启 Mooncake Master，并要求 key、allocated bytes、active clients 都为 0；
7. 手动启动 Prefill 和 Decode，等待 `/v1/models` 和 proxy health ready；
8. 采集启动日志、process tree、Pod device annotations、`npu-smi info` 和实际 CLI config；
9. 依次执行 S1、S2、S3；每个场景前停止两个 engine、重启 Master、确认 empty pool、再启动 engine；
10. 最终采集证据并停止 vLLM 进程，保留 stress Pods 及其 6-card allocation，方便后续 source sync
    和进程级重跑。

如果需要释放资源，必须由用户单独确认后再 apply 原 1+1-card engine manifests；不得把该恢复动作
隐含在 validator 中。

## 6. Test Matrix

### S1：4 个 pinned 16K requests

目的：确定性覆盖 Prefill DP0、DP1，证明两个 DP rank 都能完成 chunked prefill 和 layerwise
ranged save；Decode 固定 DP0、TP2。

Fixture：

- 构造 4 个从第一个 full block 起就互不相同的 prompts；
- 每个 prompt 有 127 个完整 cached blocks，即 16256 cached tokens；
- 在 cached boundary 后追加相同、小于 128 tokens 且不含任何 marker 的 instruction；
- 四个 marker 全部位于各自 cached 区域；
- Prefill rank 依次固定为 `0, 1, 0, 1`，Decode rank 固定为 `0`。

执行：

1. Mooncake 为空时，四个请求直接请求 Decode，记录 recompute baselines；consumer 不得写入 pool；
2. 对每个请求记录 Prefill/Decode log 起始行号；
3. 使用 `X-data-parallel-rank` 直接请求指定 Prefill rank，body 使用 proxy 相同的
   `kv_transfer_params` prefill contract；
4. 与当前 proxy 保持一致：Prefill 仅在返回非空 transfer params 字典时才放入原请求；返回 null 或
   空字典时直接用原始请求访问 Decode rank 0；
5. 截取该请求专属 log line window 并运行严格 checker。

通过条件：

- `4/4` HTTP 200，cached response signature 与对应 empty-pool baseline 完全一致；
- 每个 response 只包含自己的 marker，不包含 foreign marker；
- usage 中 prompt token count 与 fixture 实际长度一致；
- 每个 Prefill window 至少有 16 个 non-dummy context iterations；
- 每轮 context tokens 不超过 1024，累计 context tokens 等于该请求实际 prompt tokens；
- range event 所属 `EngineCore_DP*` 与指定 Prefill rank 相同；
- 每个 window 中 Prefill ranged-load/ranged-save 和 Decode ranged-load layer set 都精确为 `0..26`；
  Prefill 每个 chunk commit 都成功、紧跟该 chunk 的 layer 26 save，commit `key_count` 总和等于
  127；Decode 无 commit，whole-key event 为 0；
- Decode 日志报告每个请求命中 16256 tokens；
- 最终 Mooncake key union 为 `4 * 127 = 508`。

### S2：16 并发 × 8K prompts

目的：在同一 deployment 中组合验证 proxy、16 concurrency、shared-prefix contention、DP load
balancing、chunked prefill 和 ranged KV reuse。

Fixture：

- 48 个公共 blocks，即 6144 shared tokens；
- 每个请求 15 个互不相同的 blocks，即 1920 unique tokens；
- cached boundary 为 63 blocks，即 8064 tokens；
- boundary 后追加相同、小于 128 tokens 且 marker-free 的 instruction；
- 共 16 个 markers，分别只存在于各自 unique cached 区域；
- 预期 key union 为 `48 + 16 * 15 = 288`。

执行与通过条件：

1. empty pool 下向 Decode 并发发送 16 个请求，保存 recompute baselines，并要求 master key count
   保持 0；
2. 通过 proxy 同时发送同一组 16 个请求；client timeout 固定为 1800 秒；
3. `16/16` HTTP 200，无 timeout、retry exhaustion、OOM、worker exit 或 traceback；
4. `16/16` response signatures 与 baseline 完全一致，并全部通过 marker isolation；
5. Prefill DP0 和 DP1 都必须出现至少一个真实、non-dummy context iteration；
6. 所有 context iteration 都不超过 1024 tokens，并出现持续多轮的 concurrent context activity；
   per-request 多轮 chunking 由 S1 的 isolated line windows 证明，不从缺少 request ID 的并发
   iteration 行推断逐请求归属；
7. ranged event 聚合覆盖全部 `0..26` 层，所有 result 为对齐的非负成功值，所有 commit
   成功且 whole-key event 为 0；
8. 最终 master key count 精确为 288。

### S3：4 并发 × 32K prompts

目的：在控制 KVPool 占用的前提下进一步提高单请求长度，验证 32K 级 prompt 与并发、DP、TP、
chunked prefill 和 layerwise transfer 的组合路径。

Fixture：

- 224 个公共 blocks，即 28672 shared tokens；
- 每个请求 31 个互不相同的 blocks，即 3968 unique tokens；
- cached boundary 为 255 blocks，即 32640 tokens；
- boundary 后追加相同、小于 128 tokens 且 marker-free 的 instruction；
- 共 4 个 markers，分别位于各自 unique cached 区域；
- 预期 key union 为 `224 + 4 * 31 = 348`。

先使用 S3 case 0 执行一次 direct pinned cold Prefill→Decode 并截取 isolated line window；不清空
pool，再通过 proxy 并发执行全部 4 个 cases。基础正确性判定与 S2 相同，另外要求：

- `4/4` exact baseline match；
- Prefill DP0 和 DP1 都承担至少一个真实请求；
- pinned cold probe 观察到 `hit_blocks=0/255`；
- pinned cold 32K window 至少产生 32 个 context iterations，且每轮不超过 1024 tokens；
- 最终 master key count 精确为 348。

## 7. 日志和 Evidence Contract

每次运行先在 `/tmp/layerwise-stress-<UTC>/` 建立 staging directory。成功或失败都保存现场，不得只在
成功时生成 evidence。

最终 validation report 引用的 run 无论 passed 或 failed，都必须从 staging directory 复制到
control repo。若为了修复环境问题产生多个 run identity，报告引用的每个 run 都必须归档，不能只上传
最后一次结果：

```text
features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-<UTC>/
```

`/tmp` 只用于运行中 staging，不是最终交付位置。最终报告不得把 `/tmp`、`/root` 下的绝对路径或
Pod 内路径作为证据链接。

必须采集：

- control/source commits、Git trees/status、workspace lock 和 image identity；
- live stress manifests、Pod YAML、proxy endpoints、model config 和 runtime checks；
- 各阶段的 master-before/master-after metrics；
- Prefill/Decode 完整日志以及每个 pinned request 的 line window；
- process tree、Pod device allocation 和 `npu-smi info`；
- request payloads、raw responses、baseline comparisons 和 per-scenario summary；
- iteration checker、range checker、runner exit codes 和最终 `SHA256SUMS`。

归档目录必须包含简短 `README.md`，说明 run identity、目录结构、总结果和主要 evidence 入口；同时
更新 feature evidence 总索引 `features/kv-pool-layerwise-reuse/evidence/README.md`。`SHA256SUMS`
覆盖归档内除自身之外的所有文件，并在 copy 完成后从 control repo 路径运行一次
`sha256sum -c SHA256SUMS`。

归档前执行 credential scan，不得提交 password、API key、Bearer token、private key、kubeconfig
或 ServiceAccount token value。内部 IP、Pod IP、node name、container ID、host path、image identity
和 runtime metadata 按用户确认不视为敏感信息，可原样保留。任何单文件接近 Git hosting size limit
时必须先停止提交，保留可机器复核的 summary，将大日志按场景拆分或使用可复核的无损压缩；不得静默
丢弃失败日志或 ranged events。

最终 summary JSON 至少包含：

```text
schema_version
status
validated
identity
topology
scenarios.s1_pinned_16k
scenarios.s2_concurrent_16x8k
scenarios.s3_concurrent_4x32k
errors
```

checker 必须 fail closed：JSON 缺字段、日志截断、无法归属 DP rank、缺 layer、bytes mismatch、
commit ordering 错误、whole-key event、HTTP 非 200、response mismatch 或 artifact write 失败均使
总结果失败。

并发窗口中 ranged events 可能按 request 合并为 batch，因此不能硬编码为 `request_count * 27`
条 event。并发 checker 校验 layer union、每条 event 完整性、成功 commit 和 whole-key exclusion；
S1 的独立 line window 才执行每请求精确 traversal 判定。

## 8. Validation Report Reproduction Runbook Contract

最终 validation report 必须包含完整的 **Live Reproduction Runbook**，以 step-by-step Bash
命令呈现真实执行流程。只写“运行 `run-stress-test.sh`”或只引用本 plan 不满足交付要求。

Runbook 必须满足：

- 从 control repo 根目录开始，第一段设置 `set -euo pipefail` 和全部复现所需变量；
- 写明 namespace、node、image、model、source commits、profile 路径和新 artifact directory 的生成方式；
- 除运行时生成的 timestamp、Pod name 和 artifact path 外，不使用未解释的占位符；
- 所有命令必须来自实际成功 run；报告编写时不得凭记忆重建未经执行的命令；
- 每一步给出通过条件或预期关键输出，读者不需要回到聊天记录推断成功标准；
- runner 的一条命令入口可以保留，但后面必须展开 runner 内各阶段对应的可手工执行命令；
- 命令不得覆盖 checked-in reference evidence，每次 live rerun 必须生成新的 staging directory；
- 对会重启 Master、重建 engine Pod 或占用 6 张 NPU 的步骤明确标注状态变化；
- cleanup 明确停止哪些 vLLM 进程、保留哪些 Pods，以及如何选择性恢复原 1+1-card profile；
- 报告引用的每个脚本、manifest、request fixture、summary 和 checker 都必须已经 tracked。
- 报告中的 evidence 链接必须是指向 control repo 已 tracked 文件的相对 Markdown 链接；不得链接
  staging directory、聊天输出或未提交的本地文件。

Live Reproduction Runbook 至少按以下顺序展开：

1. **Freeze identity**：检查 branch、commits、Git trees、clean source worktrees 和
   `workspace.lock.json`；创建新的 UTC artifact directory；
2. **Preflight dependencies**：检查 node/NPU availability、image/model、Mooncake ranged APIs、
   Python import path 和 model max positions；
3. **Apply stress profile**：停止旧 engine、apply stress ConfigMap/Deployments，等待 Pod Running，
   解析唯一 Prefill/Decode Pod name；
4. **Sync and verify source**：运行 source sync、逐文件 checksum 和两个 Pod 内的
   `check-runtime.py`；
5. **Reset and start runtime**：在 engine 停止时重启 Master，验证 empty metrics，手动启动 vLLM，
   等待两个 `/v1/models` 和 proxy health；
6. **Prove topology**：采集 CLI config、Pod device annotation、process tree、`npu-smi`，验证
   Prefill DP2/TP2、Decode DP1/TP2；
7. **Run S1**：展示 empty-pool baseline、`X-data-parallel-rank` pinned prefill/decode、line-window
   capture、iteration/range checker 和 508-key assertion 的命令；
8. **Reset between scenarios**：展示 stop-engine、Master restart、empty-pool assertion 和
   process restart；S1→S2 和 S2→S3 都必须明确出现，不能隐藏状态继承；
9. **Run S2**：展示 16×8K fixture generation、baseline、16-way proxy invocation、summary/checker
   和 288-key assertion；
10. **Run S3**：展示 4×32K fixture generation、baseline、4-way proxy invocation、cold-request
    iteration proof、summary/checker 和 348-key assertion；
11. **Collect and validate evidence**：复制完整日志、metrics、Pod state、request/response、exit codes，
    运行所有 `jq` acceptance assertions，复制到 feature evidence 目录，生成并复核 `SHA256SUMS`；
12. **Cleanup and final state**：停止两个 vLLM 进程，确认 endpoints 不再接收 inference，并记录
    Master、proxy 和 stress Pods 的最终状态。

报告还必须包含独立的 **Offline Evidence Recheck** 小节。它只读取最终 checked-in evidence，
至少提供以下复核命令：

- `sha256sum -c SHA256SUMS`；
- 对总 summary 和 S1/S2/S3 summary 的完整 `jq -e` acceptance assertions；
- 对 topology、iteration、range、whole-key 和 master key-count 结论的 checker 重放；
- 检查报告引用路径全部存在且被 Git tracking；
- 明确 offline recheck 只能复核已归档结论，不能替代 live Ascend runtime rerun。

最终报告应记录实际 command transcript 或等价的命令/exit-code 索引，使失败现场也能定位到最后一个
成功步骤。若实际 run 与本文步骤不同，先在报告中如实记录真实命令和偏差原因，再决定是否回写 plan；
不得为了让文档看起来一致而改写运行历史。

### 8.1 Evidence commit、push 和报告链接顺序

最终交付按以下顺序进行，不能只在本地生成文件：

1. 只 stage 新增的 `evidence/ranged-api-stress-<UTC>/` 和 evidence index，确认无其他 dirty/untracked
   文件进入 staged set；
2. 创建 path-scoped evidence commit，并 push 到 `origin/kv-pool-layerwise-reuse`；
3. 用 `git ls-tree -r HEAD` 和 remote branch HEAD 确认全部 evidence 已 tracked 且远端包含该 commit；
4. 新建独立 validation report，记录 evidence commit SHA，并使用相对 Markdown links 指向 evidence
   `README.md`、`SHA256SUMS`、identity、总 summary、三个 scenario summaries、iteration/range summaries
   以及必要的原始日志；
5. 对 report 中的每个本地相对链接执行存在性和 Git tracking 检查；
6. 创建 report commit 并 push 到同一 remote branch，再确认 local/remote HEAD 同步。

如果 evidence commit 或 report commit 未成功 push，则报告状态只能写 `local-only` 或
`publication-blocked`，不得声称 evidence 已上传或整轮交付完成。源码仓库和 Mooncake 仓库不承载本轮
artifact；所有 evidence 和 report 都只进入 control repo 的当前 feature branch。

## 9. 工具自身验证

实施后、真实集群 run 前必须完成：

- `bash -n` 检查所有 shell runner；
- `python3 -m py_compile` 检查 Python 工具；
- fixture unit tests：prompt block layout、shared/unique union、marker-free tail、expected key count；
- checker unit tests：合法 DP0/DP1、超 budget iteration、缺 layer、bytes mismatch、commit-before-save、
  whole-key event、truncated JSON 和并发重复 layer events；
- `kubectl apply --dry-run=client` 校验 stress manifests；
- `git diff --check` 和 path-scoped Git status。

这些检查只验证测试工具，不替代真实 Ascend runtime validation。

## 10. 总体验收

只有以下条件同时满足，整轮验证才标记为 passed：

1. topology gate 证明 Prefill `DP=2/TP=2`、Decode `DP=1/TP=2`，6 张已分配 NPU 都被实际使用；
2. S1、S2、S3 全部通过各自 correctness、iteration、range 和 metrics gates；
3. Prefill DP0 和 DP1 都完成真实 16K pinned request；
4. chunked prefill 有多 iteration、每轮不超过 1024 tokens、累计 token 数和 cold 32K evidence，
   不能只引用“feature enabled”启动日志；
5. 所有 cached outputs 与 empty-pool recompute baselines 一致；
6. 所有观察到的 layerwise transfer 使用 ranged API，whole-key API event 总数为 0；
7. evidence 完整、checksum 通过、报告清楚区分新结果与历史 G0-G4 结果；
8. final validation report 包含符合第 8 节要求的 Live Reproduction Runbook 和 Offline Evidence
   Recheck，且命令、路径和预期结果能够由另一名工程师逐步重放；
9. evidence 与 validation report 均已 commit 并 push 到 `origin/kv-pool-layerwise-reuse`，报告中的
   相对链接全部指向远端 commit 中可获取的 tracked artifacts。

最终新增独立 validation report，不能回写或覆盖 2026-07-23 的历史报告。报告中记录实际运行
时间、latency 和 throughput，但不把性能值作为本轮 correctness gate。报告缺少 step-by-step
reproducible steps 时，即使 S1-S3 runtime 结果通过，也不得标记整轮交付完成。
