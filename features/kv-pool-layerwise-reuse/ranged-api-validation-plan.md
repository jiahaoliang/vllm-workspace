# Mooncake Ranged API 最小验证实施计划

**状态：** Approved for execution；独立 review findings 已纳入。本文定义实施步骤；实际结果
由后续 validation report 记录。

## 1. 目标与结论

本轮目标是验证当前 branch 和 image 中已有能力，不建设新的通用测试框架。

必须回答三个问题：

1. 当前 image 内安装的 Mooncake Client/TransferEngine 能否使用 Ascend NPU buffer 正确执行
   ranged put/get；
2. 当前 vLLM-Ascend branch 的 layerwise session、partial failure、commit/revoke 和
   get-end orchestration 是否通过已有 unit tests；
3. 当前 Kubernetes 1P1D deployment 是否能完成真实 external KVPool save/load，并在并发下
   保持 request/cache isolation 和 response metadata；只有 exact-match case 才进一步证明
   concurrent output equality。

“每个线上 request 的每个物理层都实际调用 ranged API”是更强的运行时审计结论。现有日志
不能单独证明这一点，因此把它放在可选阶段。只有 reviewer 明确要求该结论时，才增加最小
instrumentation；它不能反向扩大前三项 mandatory validation 的范围。

## 2. 固定基线

| 输入 | 当前值 |
|---|---|
| control repo branch | `kv-pool-layerwise-reuse` |
| control repo deployment baseline | `faa84c94d8a72c67c6e3058eb941b88a1208150d` |
| G3 deployment fixture | `commit:faa84c94d8a72c67c6e3058eb941b88a1208150d` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` (`v0.24.0`) |
| vLLM-Ascend | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| node/device | `n1`, two `Ascend910B4` |
| namespace | `ai-inference` |

`repos/Mooncake` 保持只读。mandatory 路径不修改 `repos/vllm` 或
`repos/vllm-ascend` 的生产源码。

当前 G3 fixture 已由 `test(kv_pool): add concurrent cache isolation smoke` commit 保存并 push，
local HEAD 与 upstream 一致。它包含 runtime ConfigMap、runbook、smoke wrapper、validation
record 和 status，是本轮默认 authoritative fixture。

当前仍有下列无关 untracked files。所有 agent 必须保留，不得 reset、checkout、stash 或
覆盖，也不得使用 `git add -A`：

```text
deployment_yaml/
dockerfile.vllm23
```

T0 必须确认实际执行文件仍与 `faa84c9` 一致。如果这些文件之后再次出现修改，则当前
fixture identity 立即失效，必须为新内容生成独立 identity：

- 推荐：用户确认内容后，以独立 path-scoped commit 保存 deployment/smoke fixture，使用
  `commit:<full SHA>`；
- 一次性 fallback：在任何 agent 开始前复制完整 fixture 到 workspace 外的 artifact 目录，
  生成 manifest，使用 `sha256:<manifest digest>`。所有 task brief 固定引用该 digest，执行前
  重新校验，最终 report 明确说明它不是可 fetch 的 Git baseline。

snapshot fallback 的 manifest 必须排除 manifest 本身。对 `SOURCE-SHA256SUMS` 文件本身
执行 `sha256sum`，取第一列并写成 `G3_FIXTURE_ID=sha256:<digest>`。snapshot 至少包含所有
实际 apply 的 deployment manifests、`run-smoke-test.sh` 及其中调用/嵌入的 smoke code。

未经用户确认不得擅自提交未来的 dirty fixture。fixture 任一文件变化后，旧
`<G3_FIXTURE_ID>` 立即失效，T3 review 和 G3 必须重新执行。

## 3. 验证边界

| Gate | 验证对象 | 主要证据 | mandatory 生产代码改动 |
|---|---|---|---|
| G0 Preflight | image、wheel、Pod、脚本是否可用 | runtime check | 0 |
| G1 Mooncake Contract | Ascend buffer 上的 ranged API/offset/bytes | direct NPU runner | 0 |
| G2 vLLM-Ascend Logic | session 和 failure orchestration | 已有 CPU mock UT | 0 |
| G3 Deployment E2E | 1P1D save/load、reuse、并发隔离 | 现有 smoke + artifacts | 0 |
| G4 Runtime Audit | 每层 ranged call、whole-key exclusion | 可选 debug log | 最多 3 个 source files |

G1 证明依赖 contract，G2 证明 adapter/orchestration，G3 证明部署行为。三者通过后可以报告：

> 当前 image 的 Mooncake ranged API 在 Ascend 上可用；当前 branch 的 layerwise orchestration
> 单测通过；实际 1P1D deployment 能命中 external KVPool，并保持 request/cache isolation。
> exact-match case 进一步证明对应 concurrent output equality。

如果没有执行 G4，报告必须同时保留以下边界：

> 本轮没有从生产进程日志独立重建每个物理层的 ranged API 调用记录。

### 3.1 非目标

- 不新增通用 trace schema、request/key/owner event model 或 trace helper。
- 不新增通用 offline validator 或 Kubernetes evidence collector。
- 不在 vLLM-Ascend 重复实现 Mooncake 已覆盖的全部 invalid-parameter/lease tests。
- 不修改 Mooncake Master、Client、TransferEngine 或 wheel 源码。
- 不验证 `MooncakeLayerwiseConnector` P2P 路径。
- 不扩展 PP、PCP、DCP、GQA/C8 或其他模型/拓扑。
- 不把 Master metrics 当作 ranged data-plane 调用计数。

## 4. 直接复用的现有能力

### 4.1 Mooncake contract tests

- [`session_ranges_tcp_e2e.py`](../../repos/Mooncake/mooncake-store/tests/e2e/session_ranges_tcp_e2e.py)
  已包含 multi-key、multi-layer、ranged put/get、byte compare 和 revoke 主流程。
- [`pybind_client_test.cpp`](../../repos/Mooncake/mooncake-store/tests/pybind_client_test.cpp)
  已覆盖 no session、shape/arity mismatch、overflow、duplicate start、after-end 和 lease
  expiration。

G1 复用前者的 test shape 和断言，只把 host `ctypes` buffer/setup 换成当前 image 已使用的
Ascend NPU tensor、buffer registration 和 `protocol=ascend`。不复制整个 Mooncake test suite。

### 4.2 vLLM-Ascend AscendStore unit tests

直接运行以下现有文件：

```text
tests/ut/distributed/ascend_store/test_backend.py
tests/ut/distributed/ascend_store/test_kv_transfer.py
tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py
tests/ut/distributed/ascend_store/test_pool_worker.py
```

它们已经覆盖：

- ranged backend delegation 和 result-shape guard；
- multi-layer range metadata、positive result 和 final-layer commit；
- partial put/get failure、malformed result、exception、commit/revoke cleanup；
- duplicate save key、duplicate remote key 和 distinct local block row；
- chunk renewal、shared owner、preemption/abort/timeout 和 exactly-once get-end。

G2 先运行这些测试。只有发现一个与本分支需求直接相关且确实未覆盖的行为时，才在现有
test file 中补一个 focused test；不得先创建新的测试框架。

### 4.3 vLLM-Ascend E2E infrastructure

- [`tests/e2e/conftest.py`](../../repos/vllm-ascend/tests/e2e/conftest.py) 已提供
  `MooncakeLauncher` 和 `RemoteOpenAIServer`。
- 当前 feature deployment 已提供手工 start、runtime check、standard proxy 和 Mooncake
  Master。
- [`run-smoke-test.sh`](deployment/run-smoke-test.sh) 已执行 baseline、warmup/reuse、四并发
  KV-load，并收集 engine/proxy/Master logs、metrics 和 summary。

当前没有可直接运行且完全匹配
`AscendStoreConnector + use_layerwise=true + 1P1D + DeepSeek-V2-Lite-W8A8` 的 upstream
pytest E2E。因此 G3 复用 feature deployment smoke，而不是新建第二套 launcher/collector。

## 5. 实施拓扑

### 5.1 任务依赖

```text
T0 Freeze scope and verify dependencies
  ├── T1 Adapt direct Ascend ranged runner ─┐
  ├── T2 Run/audit existing AscendStore UT ├── T4 Execute G1-G3 and report
  └── T3 Review existing deployment smoke ─┘
                                                │
                                                └── D1 Need strict runtime proof?
                                                     ├── No: finish with stated limit
                                                     └── Yes: T5 minimal instrumentation
```

T1-T3 的代码/审查工作可以并行。T1 direct runner 和 T3 deployment smoke 都使用当前两张
NPU，因此真实集群执行必须由集成负责人串行调度。

### 5.2 Agent ownership

| Task | Owner | 允许修改 |
|---|---|---|
| T0 | Integrator | 本计划和 task brief |
| T1 | Agent A | 新 direct runner 及其 focused test |
| T2 | Agent B | 默认只读；输出测试结果 |
| T3 | Agent C | 默认只读；review 现有 smoke 和 runbook |
| T4 | Integrator | 运行集群、汇总 artifact/report |
| T5 | Source owner | 仅在 D1=Yes 时修改明确列出的 source/test file |

T1 如需独立 worktree，必须从包含 reviewed plan 的 control-repo commit 创建。T2 在当前
`repos/vllm-ascend` commit 上运行，不创建无意义 source branch。T3 不修改 frozen fixture 或
无关 untracked files。

## 6. T0：冻结范围与 preflight

### 6.1 冻结决策

- [ ] 确认 G1-G3 是 mandatory。
- [ ] 确认 G4 是显式 decision gate，不默认实施。
- [ ] 确认 mandatory 路径 vLLM-Ascend production source change 为 0。
- [ ] 确认 G3 fixture commit `faa84c9` 可 fetch，且相关 deployment files 与该 commit 一致。
- [ ] task brief 记录完整 `<G3_FIXTURE_ID>` 和 fixture file list；若 fixture 已变化，必须先由
  用户选择新 commit 或一次性 snapshot identity。
- [ ] path-scoped commit 本计划并记录 `<PLAN_COMMIT_SHA>`。
- [ ] T1-T3 task brief 固定引用 plan SHA；T3/T4 还必须引用 `<G3_FIXTURE_ID>`。

### 6.2 Workspace 和 dependency check

- [ ] control repo、vLLM、vLLM-Ascend、Mooncake branch/HEAD 与 §2 一致。
- [ ] 三个源码 repo 都没有 agent 未识别的 source change。
- [ ] 实际 G3 fixture 与 `<G3_FIXTURE_ID>` 一致；snapshot fallback 的每个文件 hash 都通过。
- [ ] image 存在于 containerd `k8s.io` namespace，Pod image ID 与预期一致。
- [ ] prefill/decode/proxy/Master 各只有一个 Running Pod。
- [ ] 两张 NPU health 正常，模型权重可读。
- [ ] 两端 `check-runtime.py` 通过，七个 Mooncake session/range methods callable。
- [ ] direct runner 使用的 TransferEngine methods `get_engine`、`get_rpc_port`、
  `register_memory`、`unregister_memory` callable。
- [ ] image 内能定位 vLLM-Ascend source、Python interpreter、`torch_npu` 和 Mooncake wheel。
- [ ] 确认 image/source 环境能运行 targeted pytest；如果 image 未包含 test dependencies，
  只补项目标准 dev dependencies，不修改生产 package 版本。
- [ ] 保存 `pip show mooncake-transfer-engine`、module path、source commit 和 runtime config。

任一 locked commit/image/module 不一致时停止正式测试，先更新基线；不能把不同版本产生的
结果合并到同一 validation report。

## 7. T1：Direct Ascend ranged contract runner

### 7.1 文件范围

只新增：

```text
features/kv-pool-layerwise-reuse/deployment/range-api-smoke.py
features/kv-pool-layerwise-reuse/deployment/tests/test_range_api_smoke.py
```

禁止修改 vLLM、vLLM-Ascend、Mooncake 源码和现有 deployment YAML/README。

### 7.2 Delivery 和初始化

`/opt/vllm-layerwise` 是只读 ConfigMap mount。runner 不修改 ConfigMap，也不假设文件已在
image 中；集成负责人按固定方式交付：

1. control host 对 runner 执行 `sha256sum`；
2. resolve 唯一 prefill Pod，停止 prefill vLLM 并确认 PID 已退出；
3. 使用 `kubectl cp -c prefill-engine` 复制到 Pod 可写路径
   `/tmp/range-api-smoke.py`；
4. 在 Pod 内再次执行 `sha256sum`，必须与 control host 一致；
5. 通过 `kubectl exec` 运行，summary 写到 `/tmp/range-api-summary.json`；
6. 把 summary 和 stdout/stderr 复制回 control-host artifact，记录 Pod name、container、device
   和 runner digest。

命令形态固定为：

```bash
: "${artifact_root:?set artifact_root to an absolute workspace-external path}"
runner=features/kv-pool-layerwise-reuse/deployment/range-api-smoke.py
prefill_pod=$(kubectl get pods -n ai-inference -l app=prefill \
  -o jsonpath='{.items[0].metadata.name}')
sha256sum "${runner}"
kubectl cp -n ai-inference -c prefill-engine \
  "${runner}" "${prefill_pod}:/tmp/range-api-smoke.py"
kubectl exec -n ai-inference "${prefill_pod}" -c prefill-engine -- \
  sha256sum /tmp/range-api-smoke.py
kubectl exec -n ai-inference "${prefill_pod}" -c prefill-engine -- \
  python3 /tmp/range-api-smoke.py \
  --run-negative --output /tmp/range-api-summary.json
kubectl cp -n ai-inference -c prefill-engine \
  "${prefill_pod}:/tmp/range-api-summary.json" \
  "${artifact_root}/direct/range-api-summary.json"
```

执行前仍须由 runbook 停止 prefill vLLM 并确认 PID 退出；上述命令不得在 vLLM 仍占用同一
NPU 时运行。

runner 复用 Mooncake `session_ranges_tcp_e2e.py` 的 multi-key/multi-layer structure，但明确
复刻当前 production initialization contract：

- `torch.npu.set_device(0)` 选择 Pod 内唯一可见 NPU，并记录 logical/physical device；
- 创建 `mooncake.engine.TransferEngine`，以 local IP、`P2PHANDSHAKE`、`ascend` 和空
  device name 初始化；
- 用 `local_ip:transfer_engine.get_rpc_port()` 作为 store local endpoint；
- `MooncakeDistributedStore.setup()` 使用现有 Master address、64 MiB test segment、
  `protocol=ascend`，并显式传 `engine=transfer_engine.get_engine()`；
- source/destination 使用 `torch.uint8` NPU tensor；
- 对两个 tensor 的 `data_ptr()` 和 `numel() * element_size()` 分别调用
  `transfer_engine.register_memory()`；不使用 host `ctypes` buffer 作为最终证据；
- 使用带 timestamp/PID/random suffix 的 key，避免和模型 session 冲突；
- 默认使用 3 keys、4 layers、4096-byte page；每层至少两个 fragment。

### 7.3 Cleanup contract

runner 必须跟踪 active put keys、active get keys 和 successfully registered pointers，并在
`try/finally` 中清理：

1. 对仍 active 的 get session 调用 `batch_get_end`；
2. 对仍 active 的 put session 调用 `batch_put_revoke`；
3. `torch.npu.synchronize()`，确保没有 in-flight transfer；
4. 对每个已注册 tensor 调用 `transfer_engine.unregister_memory(data_ptr)`；
5. 调用 `store.close()`；
6. 删除 tensor reference，必要时执行 `torch.npu.empty_cache()`。

cleanup 每一步都记录结果并继续尝试后续步骤。任何 cleanup failure 都使 summary
`passed=false` 和进程返回非零，不能因主断言通过而忽略泄漏。

### 7.4 Mandatory cases

正向：

- [ ] put-start 全部成功；
- [ ] 每层 ranged put 的每-key result 等于 fragment bytes 总和；
- [ ] put-end 全部成功；
- [ ] get-start 全部成功；
- [ ] 每层 ranged get 的每-key result 等于 fragment bytes 总和；
- [ ] get-end 返回 0；
- [ ] source/destination 逐字节一致；
- [ ] 至少一个 fragment 使用非零 object offset。

从 Mooncake abnormal suite 只抽取与本 image contract 最相关的边界：

- [ ] no put/get session；
- [ ] offset overflow；
- [ ] buffer/size/offset arity mismatch；
- [ ] duplicate put-start；
- [ ] ranged call after put-end/get-end；
- [ ] revoke 后 object 不可 get-start。

lease expiration 已由 pinned Mooncake source test 覆盖，不作为本轮 mandatory cluster mutation。
只有 wheel/version 怀疑 lease contract 回归时，才单独安排短 TTL 测试窗口。

### 7.5 CLI 和输出

```text
--output PATH
--num-keys N
--num-layers N
--page-size BYTES
--run-negative
```

JSON summary 记录版本、runtime config、每次 API result、offset/size、source/destination
checksum、case pass/fail 和异常。任一 mandatory case 失败时进程返回非零。

focused unit test 只 mock Mooncake Client/TransferEngine，验证 batch shape、offset、pattern、
return code，以及 setup/mid-put/mid-get exception 下的 cleanup 顺序和 failure propagation；
不重新模拟 vLLM scheduler/owner state。

## 8. T2：运行现有 vLLM-Ascend tests

### 8.1 Targeted command

在与 image/source commit 匹配的 vLLM-Ascend environment 中执行：

```bash
TORCH_DEVICE_BACKEND_AUTOLOAD=0 pytest -q \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py \
  tests/ut/distributed/ascend_store/test_pool_worker.py
```

T2 mandatory 是只读 test execution：运行前后分别保存 `git status --porcelain=v1`，并要求
输出完全一致。不要在 source checkout 运行 `bash format.sh ci`；它会执行 all-files
pre-commit，部分 hook 带 `--fix`，与 Agent B 的只读职责冲突。

如果 reviewer 额外要求全仓 lint evidence，只能从 locked source commit 创建 disposable
detached worktree/container copy，在副本中运行 `bash format.sh ci`。保存其 log 和最终 diff，
不把自动修复结果复制回 source checkout。mandatory source repo 在任务结束时仍必须 clean。

### 8.2 结果分类

- `passed`：targeted files 全部通过；
- `product failure`：断言暴露本 branch 行为错误，需要独立 bugfix task；
- `environment failure`：import/CANN/dependency 与 locked environment 不一致，先修环境再重跑；
- `coverage gap`：需求行为确实不存在对应 case，只在原 test file 补 focused test。

T2 不因追求 test count 创建 trace tests、collector tests 或重复 Mooncake contract tests。

## 9. T3：复用 deployment smoke

### 9.1 Read-only review

- [ ] review 当前 `10-runtime-config.yaml` 的 `--max-num-seqs 4`、failure policy 和 layerwise config。
- [ ] 根据 `<G3_FIXTURE_ID>` 校验 review 的正是本轮将执行的文件，不是旧 baseline 内容。
- [ ] review `run-smoke-test.sh` 不覆盖已有 artifact，失败时仍收集 logs。
- [ ] review smoke summary 的 exact-match 和 quantized fallback 分类，禁止把两者写成同一
  output-equivalence 结论。
- [ ] 确认 direct decoder baseline 在 empty Mooncake pool 上运行。
- [ ] 确认 target 通过 standard proxy，且每个 response ID 有 KV hit evidence。
- [ ] 执行前确认 live ConfigMap/workload 与 frozen fixture 一致；差异必须进入 report 并阻止 G3。

发现问题时只报告给 integrator；Agent C 不直接修改 frozen fixture 或无关 untracked files。

### 9.2 G3 acceptance

执行前停止两个 vLLM、重启 Mooncake Master、等待 Ready，再手工启动两个 engine，确保旧
Client/session 和旧日志不参与本轮。

现有 smoke 必须证明：

- [ ] empty-pool direct decoder baseline 全部 HTTP 200；
- [ ] warmup/reuse 请求全部 HTTP 200；
- [ ] 四个 concurrent proxy target 全部 HTTP 200 且 choices 非空；
- [ ] 每个 target response ID 都有 positive KVPool hit block/token log；
- [ ] config 和日志表明 `use_layerwise=True`；
- [ ] `kv_load_failure_policy=fail`，不允许 hidden recompute；
- [ ] exact-match case 的 concurrent target signature 与 baseline 完全一致；
- [ ] fallback case 的 concurrent target 保留 own marker、无 foreign marker，且 response
  metadata 一致；
- [ ] fallback 的 serial replay 与 baseline exact match，但不把另一次 serial request 当作原
  concurrent text equality 的证明；
- [ ] no foreign marker/request-state contamination；
- [ ] `concurrent-summary.json` 和 log validation 均为 passed。

G3 report 必须分别统计 `exact_match` 和 `concurrent_generation_variation`：前者可以声明
concurrent output equality；后者只声明 marker/request-state isolation 和 response metadata
preserved。若本轮仍是历史结果中的 4/4 exact match，则可以对四个 case 都声明 output equality。

这一步不把“日志出现 layerwise load”解释成“已审计每个物理层 ranged call”。后者只属于 G4。

## 10. T4：串行执行与 artifact

### 10.1 执行顺序

1. 完成 G0 preflight；
2. 创建 workspace 外 artifact root，冻结并校验 `<G3_FIXTURE_ID>`；
3. 停止 prefill vLLM，按 §7.2 复制并校验 runner 后执行 G1；
4. 重启 prefill，确认 readiness；
5. 完成 G2 targeted UT，并确认 source `git status` 前后一致；
6. 再次校验 G3 fixture 未变化，停止两端 vLLM 并重启 Master，按 runbook 重新启动；
7. 运行 G3 deployment smoke；
8. 生成并验证全部 checksums，汇总 G0-G3，再做 D1 decision。

direct runner 不申请第三张 NPU，不替换 engine Pod。Master 重启后必须重启两个 vLLM，不能
让旧 Client 继续连接新 Master。

### 10.2 Artifact layout

直接复用 `run-smoke-test.sh` 的收集能力，不新增 collector。artifact root 必须是显式、绝对、
workspace 外路径；默认使用 `/tmp/ranged-api-<UTC timestamp>`。调用 smoke wrapper 时把
`${artifact_root}/deployment` 作为其 output directory，禁止使用 repo-relative `artifacts/`。

control host 保存：

```text
/tmp/ranged-api-<UTC timestamp>/
  environment/
    versions.txt
    runtime-prefill.txt
    runtime-decode.txt
    pods.yaml
    deployment-fixture/
      IDENTITY.txt
      source/
        applied-*.yaml
        run-smoke-test.sh
        SOURCE-SHA256SUMS
      live/
        configmap.yaml
        workloads.yaml
  direct/
    range-api-smoke.py
    range-api-summary.json
    range-api.log
  unit/
    pytest.log
    git-status-before.txt
    git-status-after.txt
    format.log                 optional disposable-worktree lint only
  deployment/
    concurrent-summary.json
    log-validation.json
    smoke-test.log
    vllm-prefill.log
    vllm-decode.log
    proxy.log
    mooncake-master.log
    mooncake-master.metrics
  SHA256SUMS
```

`IDENTITY.txt` 记录 identity 类型和值。commit mode 必须从该 commit 导出 source fixture，
并验证对应 paths 与 commit tree 一致；snapshot mode 的 `<G3_FIXTURE_ID>` 必须等于
`SOURCE-SHA256SUMS` 文件自身 digest。live ConfigMap/workload 单独保存，因为 Kubernetes
metadata 会变化；T3 比较的是实际 command、args、mounted ConfigMap data、image 和关键 spec，
不能要求 resourceVersion 等动态字段逐字节匹配。direct 目录保留与 Pod 内执行内容完全相同的
runner，并校验其 hash。

完成收集后在 artifact root 执行：

```bash
find . -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum > SHA256SUMS
sha256sum -c SHA256SUMS
sha256sum SHA256SUMS
```

artifact 不提交 Git。validation report 记录绝对归档路径、`SHA256SUMS` 自身 digest、
`<G3_FIXTURE_ID>`、image/source identity 和每个 gate 的状态。checksum verification 非零时
本轮 evidence 不完整，不能标记 passed。`/tmp` 只作为执行 staging；发布 report 前必须复制
到用户选择的持久、workspace 外归档位置，并在目标位置重新执行 `sha256sum -c SHA256SUMS`。

## 11. D1/T5：可选的最小 runtime instrumentation

### 11.1 进入条件

只有满足以下任一条件才进入 T5：

- reviewer 明确要求生产 request 的 per-physical-layer ranged call 证据；
- G1-G3 结果出现矛盾，需要区分 ranged/whole-key 实际路径；
- 准备把该可观测性长期作为 upstream regression signal。

仅为了“边界测试更多”不能触发 T5。

### 11.2 Source change 上限

production source 上限为 3 个文件：central env definition 加两个 instrumentation call-site
files。连同对应 tests，只允许修改：

```text
vllm_ascend/envs.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py
tests/ut/test_envs.py
tests/ut/distributed/ascend_store/test_kv_transfer.py
tests/ut/distributed/ascend_store/test_backend.py
```

control repo 最多新增一个小型 log checker。禁止新增 `trace.py`，禁止修改
`config_data.py`、`pool_scheduler.py`、`pool_worker.py`，禁止新增 owner/request trace framework。

### 11.3 最小日志

使用默认关闭的 `VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1`。按照 vLLM-Ascend repo-local 规则，
该变量必须在 `vllm_ascend/envs.py` 的 centralized `env_variables` dictionary 中定义、注明默认
值/有效值/非敏感属性，并由业务文件通过 `from vllm_ascend import envs` 读取；禁止散落
`os.getenv`：

- `kv_transfer.py` 在 ranged put/get 返回后记录 direction、layer ID、key count、sizes、object
  offsets 和 results；
- `kv_transfer.py` 在 final-layer `batch_commit` 返回后记录 committed key count 和 results；
- `mooncake_backend.py` 在 whole-key `put/get` 入口记录 backstop event；
- 不记录 pointer/GVA；
- disabled path 不构造 debug payload；
- logger failure 不改变推理行为。

小型 checker 只断言：

- save/load layer set 均为 `0..num_layers-1`；
- ranged results 非负且等于 requested bytes；
- final publish 晚于 final ranged put；
- whole-key backstop count 为 0。

owner、shared-key 和 get-end correctness 继续由 G2 现有 UT 负责，不在 runtime log 重建。

### 11.4 Source workflow

进入 T5 前按 workspace 规则重新确认 vLLM-Ascend branch、remote、locked commit 和 clean
worktree。修改后：

1. 运行三个 affected test files 和完整 AscendStore targeted UT；
2. `bash format.sh ci`，然后 review 自动修复 diff，禁止保留无关格式修改；
3. 创建 signed source commit；
4. push personal fork；
5. Python-only sync 到两个现有 Pod，不替换 Pod；
6. 运行一次 clean single-request G4；
7. 刷新 `workspace.lock.json`、`repo-state.md` 和 `sync-log.md`。

## 12. 验收矩阵

| Case | 来源 | 必须结果 |
|---|---|---|
| method availability | existing runtime check | 7/7 callable |
| Ascend ranged put/get | direct runner | exact bytes and checksum |
| non-zero object offset | direct runner | destination exact |
| no session/overflow/arity | direct runner | negative result, no crash |
| duplicate/end/revoke | direct runner | expected session cleanup |
| backend delegation/shape | existing UT | passed |
| partial/malformed failure | existing UT | exact per-key cleanup |
| shared owner/get-end | existing UT | last owner only |
| clean miss/hit | deployment smoke | expected blocks/tokens |
| four-request isolation | deployment smoke | 4/4 classified; exact cases additionally prove output equality |
| hidden recompute | config + logs | fail policy, zero load failure |
| physical layer audit | optional G4 | all layers, ranged only |

## 13. Definition of Done

Mandatory：

- [ ] G0 environment/image/wheel identity 已保存。
- [ ] G1 direct Ascend contract positive、selected negative 和 cleanup cases 全部通过。
- [ ] G2 四个 existing AscendStore test files 全部通过，source status 前后一致。
- [ ] G3 fixture identity 已冻结，sequential/reuse/concurrent deployment smoke 全部通过。
- [ ] report 分开记录 exact/fallback case，未夸大 fallback 的 output-correctness 结论。
- [ ] artifact 已复制到持久 workspace 外路径，`SHA256SUMS` 校验通过。
- [ ] report 分别说明 dependency、orchestration、deployment 各自证明了什么。
- [ ] report 明确说明是否执行 G4；未执行时保留 per-layer runtime evidence limitation。

只有 D1=Yes 时增加：

- [ ] instrumentation 只触及 §11.2 文件。
- [ ] env var 通过 `vllm_ascend/envs.py` centralized definition 和 test。
- [ ] default-disabled 和 affected tests 通过。
- [ ] clean run 覆盖全部 save/load physical layers，whole-key event 为 0。
- [ ] source commit/push 和 workspace state 更新完成。

## 14. 交付和 commit 边界

Mandatory 实施预计新增：

```text
1 个 direct runner
1 个 focused runner unit test
1 份 validation report
0 个 vLLM-Ascend production source change
```

建议 control repo commit：

```text
test(kv_pool): add Ascend Mooncake ranged API smoke
docs(kv_pool): record ranged API validation
```

任何 commit 都不得包含 `deployment_yaml/`、`dockerfile.vllm23`、artifact 或用户未确认的
dirty deployment files。

可选 T5 若执行，使用独立 signed vLLM-Ascend commit；不得把 debug instrumentation 混入
direct runner/control-repo commit。

## 15. 参考资料

- 权威设计：
  [design-mooncake-layerwise-gva-put.md](references/snapshots/design-mooncake-layerwise-gva-put.md)
- 开发确认：
  [development-confirmation-request.md](development-confirmation-request.md)
- 当前 deployment runbook：
  [deployment/README.md](deployment/README.md)
- 当前 smoke result：
  [deployment/validation-2026-07-23.md](deployment/validation-2026-07-23.md)
- vLLM-Ascend testing guide：
  [testing.md](../../repos/vllm-ascend/docs/source/developer_guide/contribution/testing.md)
- vLLM-Ascend CI selection：
  [TEST_README.md](../../repos/vllm-ascend/.github/TEST_README.md)
