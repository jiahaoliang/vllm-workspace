# Blockwise DSA PD Offload NPU E2E 测试计划

## 状态与结论边界

- 文档状态：计划已定义。
- NPU runtime 状态：`planned / not run`。
- 本文所有 case 均未执行，不包含 NPU correctness、性能或稳定性结果。
- Static、CPU/mock 与 NPU runtime evidence 必须分别报告。只有全部 mandatory case 实际通过、证据归档且 cleanup audit 通过后，才能声明 `NPU runtime validated`。
- 本计划中的 preflight 是测试执行 gate，不是 connector handshake，也不代表已经实现 production deployment admission gate。
- 当前 handshake 是 positional ABI；connector 不验证 P/D 间的 dtype、shape、memory kind、tuple role、leader coverage 或 layout compatibility。即使 transfer status 成功，错误配对仍可能 silent corruption。
- Versioned harness 位于 [npu-e2e/](npu-e2e/README.md)。它已通过 repository-local static/offline synthetic validation；这不改变 NPU runtime 的 `planned / not run` 状态。

## 范围与首个拓扑

首个执行拓扑为 `P TP8/DP2 -> D TP2/DP8`。它只是第一组验证输入，不是产品唯一拓扑。后续拓扑只要重新执行完整 preflight 和全部 mandatory case，并满足以下约束，即可使用本计划：

- `P_TP >= D_TP` 且 `P_TP % D_TP == 0`；
- Decode PP=1，Decode `DCP * PCP == 1`；
- 每个 Prefill TP group 是连续的，group size 为 `P_TP / D_TP`；
- 每组首 rank 是对应 Decode TP 的唯一 payload source；
- fixed leader 必须拥有目标 Decode TP 所需的完整 Main K/V、Indexer 和可选 Indexer scale replica。

在首个拓扑中，每个 Prefill DP replica 的 TP group 为 `[0,1,2,3]` 与 `[4,5,6,7]`，fixed leaders 分别为 rank 0 和 rank 4。Decode DP 到 Prefill endpoint 的 routing 必须由 rendered manifest 明确记录，不能从 DP 数量猜测。

Mandatory runtime scope：

1. happy path 与 partial physical block；
2. multi-block 与持续 Decode/fused D2H；
3. concurrency、request-lifetime reservation pressure 与 HOL admission；
4. Indexer-before-Main ordering 和分 phase failure injection；
5. exact TP terminal barrier 与 all-TP full replay；
6. preemption epoch rebind 与 confirmed Main prefix reuse；
7. cancellation drain-and-ack 与 `DONE_RECVING_MSG` ordering；
8. `dsa_pd_offload=false` 的 default `MooncakeConnectorV1` isolation。

## Run Identity 与资源命名

执行者先创建独立 artifact directory，并在任何 cluster mutation 前冻结以下输入。示例变量只是接口；发流量前必须全部解析成实际值，文件中不得保留 `<...>`、mutable image tag 或未解析环境变量。

```bash
export NS=liangjiahao
export HARNESS=features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-e2e
export RUN_ID=dsa-npu-YYYYMMDDTHHMMSS
export RUN_DIR=/absolute/artifact/root/${RUN_ID}
export BASELINE_MANIFEST=${RUN_DIR}/manifests/baseline.json
export BASELINE_JOB_MANIFEST=${RUN_DIR}/manifests/baseline-oracle.json
export PD_MANIFEST=${RUN_DIR}/manifests/dsa-pd.json
export V1_MANIFEST=${RUN_DIR}/manifests/default-v1-pd.json
export REQUESTS=${RUN_DIR}/fixtures/requests.jsonl
export RUN_CONFIG=${RUN_DIR}/run-config.json
test "${NS}" = liangjiahao
test -d "${RUN_DIR}"
install -d "${RUN_DIR}/preflight" "${RUN_DIR}/baseline"
```

所有对象必须带 labels `app.kubernetes.io/managed-by=dsa-npu-e2e` 和 `test-run=${RUN_ID}`。名称固定为：

- `Deployment/${RUN_ID}-baseline`、`Service/${RUN_ID}-baseline`；
- baseline 采集使用 `Job/${RUN_ID}-baseline`、`ConfigMap/${RUN_ID}-baseline`；
- 每个 Prefill DP rank 使用 `Deployment/Service/${RUN_ID}-prefill-dp<RANK>`，并提供 aggregate `Service/${RUN_ID}-prefill`；
- 每个 Decode DP rank 使用 `Deployment/Service/${RUN_ID}-decode-dp<RANK>`，并提供 aggregate `Service/${RUN_ID}-decode`；
- default V1 同样使用 per-DP `v1-prefill-dp<RANK>`、`v1-decode-dp<RANK>` 和 aggregate Services；
- 每个 case 的 `Job/ConfigMap/${RUN_ID}-<case-id-lower>`，例如 `${RUN_ID}-npu-01`。

`run-config.json` 至少保存 kube context、node、NPU resource requests、P/D image digest、vLLM/vLLM-Ascend/Mooncake revisions、model/tokenizer revision、全部 serving flags、cache dtype、block size、positional ABI fingerprint、fixture/catalog SHA256、fault/probe capability evidence、Mooncake session cleanup command和数值 oracle tolerance。PASS capability 必须使用 artifact_root 下 capability 专属的 structured evidence document，绑定同一 RUN_ID 和 exact assertion IDs，为每个 assertion 提供不跨 capability 复用的 artifact 并逐项校验 SHA256；`output_oracle` 必须显式证明 baseline capture/identity/allocation release。变更任一字段都产生新的 `RUN_ID`，不能复用旧 baseline。resolved config 用 `npu-e2e/scripts/render.sh` 生成 run directory；模板中的 REQUIRED/UNKNOWN 不能被当作已满足。

## Mandatory Preflight Gate

Preflight 的每项结果写入 `${RUN_DIR}/preflight/` 和 `preflight.json`。先运行 `scripts/preflight.sh --offline ${RUN_DIR}` 验证本地 frozen 工件；offline 固定返回 UNKNOWN/exit 2 且不调用 kubectl。执行前再运行 `scripts/preflight.sh --live ${RUN_DIR}`；live 仅做 read-only cluster identity/capacity 查询和 server-side dry-run。runner 自行重算 live preflight，不信任调用者提供的 PASS 文件，并只接受 generated_at/epoch 一致且 10 分钟内生成的 result。任一 latest cleanup FAIL 或 unverifiable 时，全局 gate 阻断后续 case。common gate 或 case gate 不是 PASS 时，不发流量，对应 case 保持 `planned / not run`。

### 1. Context、namespace 与 manifest

```bash
bash "${HARNESS}/scripts/preflight.sh" --live "${RUN_DIR}"
jq '{overall_status, checks, cases}' "${RUN_DIR}/preflight/preflight.json"
```

人工复核 current context、`liangjiahao`、精确对象名、node affinity、P/D resource requests 和 cleanup target。不得删除 namespace。

### 2. Image、source 与 overlay identity

- P/D 必须使用同一 immutable `image@sha256:...`；baseline/V1 image identity也写入报告。
- 记录 image 内 vLLM、vLLM-Ascend、Mooncake source/native library、CANN 和 torch_npu identity。P/D 的 positional tuple adapter 与 transfer builder 必须来自同一组 revision。
- 优先复用 native 依赖兼容的已有 image。只有 Python 文件变化时允许 overlay，不能把 overlay 描述为完整 image rebuild。
- Overlay 必须在服务启动前完成。冻结文件清单，记录 base image reference/digest、三个源码 revision，并逐文件保存 host SHA256 与每个 P/D Pod 内 SHA256；所有 P/D Pod 的结果必须一致。
- Mooncake/native/CANN/torch_npu 变化、目标 image 缺少依赖或 overlay 无法在启动前生效时，停止 preflight，改用新的 immutable image digest 后重新开始 run。

若使用 overlay，serving container 必须先停在 manifest 定义的启动 barrier。`${RUN_DIR}/preflight/overlay-sha256.txt` 每行是 `<sha256>  <relative-path>`，`${RUN_DIR}/preflight/pod-list.txt` 是已核对的精确 P/D Pod 名；执行并保存以下命令输出后才能解除 barrier：

```bash
while read -r POD; do
  while read -r EXPECTED FILE; do
    test "$(sha256sum "${RUN_DIR}/overlay/${FILE}" | awk '{print $1}')" = "${EXPECTED}"
    kubectl cp -n "${NS}" "${RUN_DIR}/overlay/${FILE}" "${POD}:/workspace/${FILE}"
    kubectl exec -n "${NS}" "${POD}" -- sha256sum "/workspace/${FILE}"
  done < "${RUN_DIR}/preflight/overlay-sha256.txt"
done < "${RUN_DIR}/preflight/pod-list.txt" > "${RUN_DIR}/preflight/pod-overlay-sha256.txt"
```

Pod Ready 后保存实际 runtime identity：

```bash
kubectl get pod -n "${NS}" -l "test-run=${RUN_ID}" -o json > "${RUN_DIR}/preflight/pods.json"
kubectl get pod -n "${NS}" -l "test-run=${RUN_ID}" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.imageID}{" "}{end}{"\n"}{end}' > "${RUN_DIR}/preflight/runtime-imageids.txt"
```

### 3. Model、configuration 与 positional ABI

P/D 必须逐项相同：model/tokenizer revision、DSA/C8/offload flags、cache dtype、block size、layer name/index mapping、cache tuple construction、`tensor_group_idx` interpretation 和 optional scale placement。禁止 mixed-version rolling upgrade。

从每个 P/D rank 归档本地 registration dump。当前 wire contract 只能声明：

```text
layer_metadata[layer_name]
  tensor_group_idx[]
  kv_caches_base_addr[]
  block_len[]
  block_size_scale[]
```

本地 gate 验证四个数组等长、地址非零、length/scale 为正、layer 完整且 registration 成功。报告必须明确这些不是跨端 semantic compatibility proof。

### 4. Topology、leader replica 与 memory placement

- 从每个 Prefill DP replica 采集 TP rank/group/leader mapping，证明首个拓扑只由 ranks 0、4 发 payload；非 leader 不得提交重叠 payload。
- 用 deployment owner 提供的 replica evidence 证明每个 leader 拥有对应 Decode TP 的完整 Main/Indexer/scale 内容。若只能证明 shard，测试不运行。
- 每个 Decode TP 独立报告 Indexer destination 为该 TP HBM，Main destination 为该 TP 的 NPU-addressable Swapped Host pool；不同 Decode TP 不共享 Main pool ownership。
- Decode Swapped Main block ID 0 保留。对每个 TP 验证 scheduler capacity、Host tensor capacity、registered range 一致，并满足 `usable_blocks >= ceil(max_model_len / block_size)`。
- 保存 Mooncake Transfer Engine/Store endpoint、registered range、session ID 与 cleanup 方法。registration 或 endpoint readiness 不完整时不发流量。

### 5. Cluster capacity 与 observability

- 在 apply 前后保存目标 node 的 allocatable/requested `huawei.com/Ascend910`、精确 Pod resource requests 和 device-plugin allocation；遵守执行时生效的设备排除清单。
- 确认 artifact filesystem 容量足够保存 P/D/baseline logs、events、request detail、Mooncake logs、NPU allocation、state transitions 和 tensor oracle。
- Cache oracle 必须是现有只读 test probe 或单独批准的 instrumentation。Fault injection 必须能按 request、Decode TP、phase 和 occurrence 精确命中。缺少任一能力时，依赖它的 case 保持 `planned / not run`；本计划不假设 production code 已有这些 hook。

## Baseline 与公共 Correctness Oracle

先用 `${BASELINE_MANIFEST}` 启动非 PD baseline。它使用同一 model/tokenizer revision、相同 DSA/C8 语义、cache dtype、block size、sampling 参数和固定 token-ID fixture；仅移除 PD transfer 这一变量。每条请求使用固定 seed、`temperature=0` 和冻结的 `max_tokens`。保存完整 output token IDs、finish reason 和可用时的 logits/logprobs。

`requests.jsonl` 在 preflight 前生成并冻结，至少包含：

- `partial-1`：prompt token 数小于一个 block，最后 block 为 partial；
- `multiblock-1`：prompt 跨至少三个完整 block 且有 partial tail；
- `decode-grow-1`：生成长度跨至少两个新 block；
- `pressure-old`、`pressure-head`、`pressure-young`：reservation block 数可制造一次确定的 HOL capacity miss；
- `failure-1`、`preempt-1`、`cancel-1`、`v1-1`：各 lifecycle case 的独立 request ID。

记录每条请求的 token IDs、token 数、`max_tokens`、期望 reservation blocks 和 SHA256。执行前必须用目标 tokenizer round-trip 核对；不能只保存自然语言 prompt。

每个 runtime case 同时使用两类 oracle：

1. Output oracle：与 baseline output token IDs、finish reason 对比；若使用数值 logits/tensor 对比，`atol`/`rtol` 必须在 `run-config.json` 中预先冻结，不能看到结果后放宽。
2. Cache oracle：对首层、中间层和末层的选定 physical block，按 `(request_id, DP, TP, layer, role, block_id, phase, epoch)` 保存 source/destination checksum；representation 不同则使用预先批准的等价 tensor projection。Partial tail 对整个 physical block校验，同时只按 token state 认定有效 token。

只看最终文本、只看 transfer return code或只看 worker log都不足以判定通过。

Baseline 与 DSA P/D 顺序占用 NPU，不要求同时驻留。先采集 baseline，再按精确 manifest 删除 baseline 并确认其 Pod/NPU allocation 已释放，最后启动 DSA P/D：

```bash
kubectl apply -n "${NS}" -f "${BASELINE_MANIFEST}"
kubectl rollout status -n "${NS}" "deployment/${RUN_ID}-baseline" --timeout=30m
kubectl apply -n "${NS}" -f "${BASELINE_JOB_MANIFEST}"
kubectl wait -n "${NS}" --for=condition=complete --timeout=30m "job/${RUN_ID}-baseline"
kubectl logs -n "${NS}" "job/${RUN_ID}-baseline" --all-containers > "${RUN_DIR}/baseline/client.log"
kubectl delete -n "${NS}" -f "${BASELINE_JOB_MANIFEST}" --ignore-not-found
kubectl delete -n "${NS}" -f "${BASELINE_MANIFEST}" --ignore-not-found
kubectl wait -n "${NS}" --for=delete pod -l "test-run=${RUN_ID},test-role=baseline" --timeout=10m
kubectl apply -n "${NS}" -f "${PD_MANIFEST}"
for rank in $(seq 0 $(($(jq -r '.topology.prefill_dp' "${RUN_CONFIG}") - 1))); do
  kubectl rollout status -n "${NS}" "deployment/${RUN_ID}-prefill-dp${rank}" --timeout=30m
done
for rank in $(seq 0 $(($(jq -r '.topology.decode_dp' "${RUN_CONFIG}") - 1))); do
  kubectl rollout status -n "${NS}" "deployment/${RUN_ID}-decode-dp${rank}" --timeout=30m
done
```

Baseline 删除后和 DSA P/D 启动后都重新归档 node resource requests 与 device-plugin allocation。任一 baseline artifact 不完整或 allocation 未释放时，不启动 DSA P/D。

## 公共执行与证据模板

每个 `${CASE_ID}` 的 rendered manifest 只能创建该 case 的 ConfigMap/Job；Job 在 `liangjiahao` 内访问 service，不依赖 port-forward。先重跑 live preflight 使 prerequisite result 生效，再使用 fail-closed runner：

```bash
export CASE_ID=NPU-XX
bash "${HARNESS}/scripts/preflight.sh" --live "${RUN_DIR}"
bash "${HARNESS}/scripts/run-case.sh" "${RUN_DIR}" "${CASE_ID}"
```

runner 先证明同名 case 对象不存在，再逐对象 create ConfigMap/Job 并记录 API server 返回的 UID；它在 `${RUN_DIR}/results/${CASE_ID}/attempt-*/` 保存起止时间、client/P/D logs、Job、Pods、events、结构化 result、cleanup record 和 recursive artifact checksums。client 的 `DSA_NPU_RESULT=<json>` 缺失、多行、identity 不符、oracle/criterion 不完整，或每个 kind/index 独占的 `DSA_NPU_ARTIFACT=<json>` 缺失/hash 不匹配时为 INVALID/FAIL，绝不判 PASS。Job timeout、crash 或缺失 rank result是失败证据，不得通过无限增加 timeout 改写结果。

每个 case 结束后先收证，再执行精确清理：取消未结束请求、等待 worker quiesce、按 `run-config.json` 中已解析的命令清理该 case 的 Mooncake sessions，复位 fault/barrier，确认 reservation、delayed NPU blocks、command state、tracker 与 NPU requests 回到 case 前基线。cleanup command 必须输出可校验的 session inventory 与 resource delta artifacts，不能只自报 boolean。runner 在删除前重新核对 created UID 与 `managed-by`/run/case labels；不匹配时拒绝删除并判 cleanup FAIL。人工核查目标为：

```bash
kubectl config current-context
kubectl get namespace "${NS}"
CASE_OBJECT="${RUN_ID}-$(printf '%s' "${CASE_ID}" | tr '[:upper:]' '[:lower:]')"
kubectl get -n "${NS}" "job/${CASE_OBJECT}" "configmap/${CASE_OBJECT}"
kubectl delete -n "${NS}" "job/${CASE_OBJECT}" "configmap/${CASE_OBJECT}" --ignore-not-found
```

若 cleanup 未通过，停止后续 case，保留服务与证据用于受控诊断，并将 run 标记为未完成。

## Mandatory Case Matrix

| Case | 目标 | Status |
|---|---|---|
| NPU-01 | Happy path 与 partial physical block | `planned / not run` |
| NPU-02 | Multi-block、持续 Decode 与 fused D2H | `planned / not run` |
| NPU-03 | Concurrency、reservation pressure 与 HOL | `planned / not run` |
| NPU-04 | Indexer-before-Main 与 phase failure injection | `planned / not run` |
| NPU-05 | Exact TP terminal barrier 与 all-TP replay | `planned / not run` |
| NPU-06 | Preemption epoch rebind 与 Main reuse | `planned / not run` |
| NPU-07 | Cancellation drain-and-ack | `planned / not run` |
| NPU-08 | Default V1 isolation | `planned / not run` |

### NPU-01 — Happy path 与 partial physical block

**Status:** `planned / not run`

- Prerequisite：完整 preflight PASS；baseline 的 `partial-1` 已归档；cache probe 能覆盖 leaders 0/4 和所有 Decode TP。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-01.json`；只发送固定 `partial-1`，单并发，禁止 transport fault。
- Oracle：baseline output；首/中/末层 Main K/V、Indexer 和 optional scale 的 source/destination oracle；partial tail 按完整 physical block checksum。
- 成功条件：每个 Decode TP 只从自己的 fixed leader 拉取；Indexer D2D terminal success 后才开始 Main D2RH；每 phase 在 connector 边界各提交一次；Main 落在 per-TP Swapped Host pool、Indexer 落在该 TP HBM；exact TP `RECEIVE_COMPLETE` 后才可见 cache hit。
- 失败证据：任一非 leader payload、phase 逆序/重叠、地址越界、缺 rank、checksum mismatch、output mismatch、reservation 泄漏或 unexpected retry。
- Cleanup：执行公共收证/清理；确认 ordinary completion 对实际使用 endpoint 的 `DONE_RECVING_MSG` 状态、Main reservation release-once、NPU blocks 与 Mooncake session 回到基线。

### NPU-02 — Multi-block、持续 Decode 与 fused D2H

**Status:** `planned / not run`

- Prerequisite：NPU-01 PASS；baseline 的 `multiblock-1`、`decode-grow-1` 已归档；fused D2H range/validity probe 可用。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-02.json`；顺序执行两个固定请求，随后以相同输入执行 manifest 中冻结的低并发持续 Decode wave。
- Oracle：baseline output；每个 transfer block 的选定 layer oracle；每次 `FUSED_D2H` 前后 Main destination 与 confirmed valid prefix 的等价 tensor oracle。
- 成功条件：多 block address/range 无重叠或遗漏；partial tail 仍传完整 physical block；fused D2H 只写 command-bound Main prefix，`D2H_COMPLETE` 单调推进 validity；所有 TP 的 output/cache oracle一致。
- 失败证据：block mapping 缺口/覆盖、stale epoch/command 被接受、validity 越界或倒退、D2H failure 未 fail fast、output/cache mismatch。
- Cleanup：执行公共收证/清理；等待所有 fused operation terminal 后释放 request-owned资源，不为 unquiesced operation 伪造 completion。

### NPU-03 — Concurrency、Reservation Pressure 与 HOL

**Status:** `planned / not run`

- Prerequisite：NPU-02 PASS；已记录每 TP usable Host blocks；driver 能以 barrier 固定 admission/release 顺序。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-03.json`；按 fixture 顺序提交 `pressure-old`、`pressure-head`、`pressure-young`，其冻结 reservation blocks 使 old 持有容量、head 首先 capacity miss、young 即使可装入也在本 step 不尝试；另执行固定并发 wave。
- Oracle：三条请求各自 baseline output/cache oracle；逐 step reservation ledger 与 scheduler/worker ownership timeline。
- 成功条件：reservation 在 receive 前一次性覆盖 prompt+最大输出；capacity miss 不产生 partial ownership；本 step HOL 阻止 younger reservation，下一 step 按原顺序重试；请求间 Host/Indexer ownership 隔离；每个 terminal path release-once。
- 失败证据：bypass HOL、超卖、等待期间 ownership 泄漏、重复/提前 release、request 交叉写、持续无进展或 output/cache mismatch。
- Cleanup：driver 释放 barrier 并结束所有请求；执行公共收证/清理；usable reservation、delayed blocks、trackers 必须精确回到 case 前计数。

### NPU-04 — Indexer-before-Main 与 Phase Failure Injection

**Status:** `planned / not run`

- Prerequisite：NPU-01 PASS；可控 hook 能只命中 `failure-1` 的指定 Decode TP、phase 和 occurrence，并能区分 Mooncake internal retry 与 connector outer retry。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-04.json` 包含两个独立 subrun：A 在 `INDEXER_D2D` 注入 final failure；B 允许 Indexer success 后在 `MAIN_D2RH` 注入 final failure。每个 subrun 前恢复干净 request/session state。
- Oracle：每个 subrun 的 baseline output/cache oracle；phase submit/terminal timeline；Main destination before/after checksum。
- 成功条件：A 不提交 Main 且产生 `TRANSFER_FAILED(INDEXER_D2D)`；B 不产生 `RECEIVE_COMPLETE` 且产生 `TRANSFER_FAILED(MAIN_D2RH)`；connector 无 outer retry；局部成功不提升为 cache hit。
- 失败证据：Indexer final failure 后出现 Main submit、错误 phase、receive-complete、无界 retry、未跟踪写入或 output/cache mismatch。
- Cleanup：每个 subrun 后关闭精确 fault rule、等待 terminal、清理 session并执行公共清理；记录 fault rule 已复位。缺少 hook 时本 case 不运行，不能用 kill Pod 代替 phase-specific injection。

### NPU-05 — Exact TP Terminal Barrier 与 All-TP Replay

**Status:** `planned / not run`

- Prerequisite：NPU-04 PASS；hook 能让一个 Decode TP final fail，并让其余 TP 以受控顺序返回 terminal result；可观测 cross-step rank accumulation。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-05.json`；`failure-1` 在一个指定 TP 注入一次 failure，延迟另一个 TP terminal result，随后解除 barrier。
- Oracle：baseline full-sequence output/cache oracle；每个 `(command_id, epoch, tp_rank)` result、`preserved_main_tokens` 和 replay block trace。
- 成功条件：缺 rank 时无限期 pending且不 replay；exact TP terminal set 完整后所有 TP 收到 `PREPARE_REPLAY`；所有 TP validity 归零且 `preserved_main_tokens=0`；Decode 从 token 0 full replay并重建 Indexer/Main；最终 output/cache 与 baseline一致。
- 失败证据：单 TP early replay、missing rank 被当完成、stale/conflicting result 改写 ownership、任一 TP 保留 Main validity、只 replay suffix 或 oracle mismatch。
- Cleanup：解除 barrier/fault，即使 case 已失败也收齐可达 terminal；执行公共收证/清理并验证所有 TP replay state、reservation和session归零。

### NPU-06 — Preemption Epoch Rebind 与 Main Reuse

**Status:** `planned / not run`

- Prerequisite：NPU-02 PASS；可控 preemption barrier 能在 confirmed Main prefix 形成后触发 core preemption；能读取 epoch、Indexer IDs、reservation identity 和 D2H ranges。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-06.json`；运行固定 `preempt-1`，在 manifest 指定 token boundary 触发一次 preemption，再恢复到新 execution epoch。
- Oracle：baseline output；preemption 前 confirmed Main prefix checksum；恢复后同一 Main reservation/prefix checksum、新 Indexer HBM ownership、replay trace 和 `DsaPreemptionEvidence`。
- 成功条件：旧 epoch retire；Indexer IDs 重新绑定；Main lifetime reservation identity/capacity 保留；evidence 准确记录 full replay token数、复用 Main token数、按 runtime page geometry 计算的 skipped D2H bytes和 recovery duration；可证明有效的 Main prefix 不重复 D2H，Indexer 由 full-sequence compute replay重建；stale old-epoch result不恢复旧 ownership；最终 oracle一致。
- 失败证据：复用旧 Indexer IDs、释放/更换 Main reservation、重复写 confirmed prefix、错误 preserved boundary、接受 stale result或 oracle mismatch。
- Cleanup：结束恢复后的请求，等待旧/新 epoch operation都 terminal；执行公共收证/清理并证明 Main release-once、两个 epoch 的 command/tracker均清除。

### NPU-07 — Cancellation Drain-and-Ack

**Status:** `planned / not run`

- Prerequisite：NPU-01 PASS；driver 能在 in-flight receive/fused D2H barrier 上取消 `cancel-1`；能观察 worker Quiesced、`DONE_RECVING_MSG` attempt、ordinary `finished_recving` 和 delayed-block release顺序。
- Manifest/输入：`${RUN_DIR}/manifests/NPU-07.json`；分别在 receive 与 fused D2H in-flight point 执行固定 cancellation subrun，并发送 duplicate cancellation/late completion。
- Oracle：取消前 baseline prefix 与 cache checksum；取消后不再产生用户 output，改用 ownership/state oracle确认旧 operation没有写入复用地址。
- 成功条件：取消后不启动新 receive/replay/D2H；unquiesced 期间 reservation保持隔离；每个 worker Quiesced 后，先对实际使用且未通知的 leader endpoint best-effort attempt一次 `DONE_RECVING_MSG`，再上报一次 ordinary `finished_recving`；all-worker completion 后按顺序 release-once Main 与 delayed NPU blocks；duplicate/late事件为no-op。
- 失败证据：quiesce 前释放/复用地址、新 operation启动、通知顺序倒置、重复普通 ack、partial-worker early cleanup、late write或资源泄漏。`DONE_RECVING_MSG` send failure本身不是 state-machine failure，但必须有 attempt证据并记录 hard TTL fallback。
- Cleanup：解除所有 barrier并等待实际 operation drain；执行公共收证/清理；额外确认 source notification/session、Main reservation、Indexer blocks、delayed blocks和worker command state回到基线。

### NPU-08 — Default MooncakeConnectorV1 Isolation

**Status:** `planned / not run`

- Prerequisite：NPU-01 至 NPU-07 PASS；使用同一配对 image/overlay identity；`${V1_MANIFEST}` 显式设置 `dsa_pd_offload=false` 并使用普通 V1 支持的 topology/config。
- Manifest/输入：先按精确名称停止并清理 DSA P/D resources，再 apply `${V1_MANIFEST}`；`${RUN_DIR}/manifests/NPU-08.json` 发送固定 `v1-1`。
- Oracle：同一请求的 non-PD baseline output；普通 V1 KV destination 的选定 layer/block source/destination checksum或等价 tensor oracle。
- 成功条件：实例化普通 `MooncakeConnectorV1` metadata/scheduler/transfer/completion path；不构造 DSA envelope、Swapped Main lifetime reservation、Indexer-before-Main split或DSA typed result；output/cache oracle一致。
- 失败证据：任何 DSA-only state/分配、普通 V1 metadata/transfer regression、output/cache mismatch、unexpected retry或资源泄漏。
- Cleanup：执行公共收证/清理；清理普通 V1 Mooncake sessions，随后按最终 cleanup 删除精确 V1 resources。

## Final Cleanup 与 NPU Release Audit

只有每个 case 的证据已落盘后才开始。先核对 context、namespace、run label、rendered manifest 和精确对象名；不使用宽泛 label deletion，不删除 namespace。

```bash
kubectl config current-context | tee "${RUN_DIR}/cleanup-kube-context.txt"
kubectl get namespace "${NS}" -o yaml > "${RUN_DIR}/cleanup-namespace.yaml"
kubectl get all,configmap -n "${NS}" -l "test-run=${RUN_ID}" -o yaml > "${RUN_DIR}/cleanup-before.yaml"
kubectl delete -n "${NS}" -f "${V1_MANIFEST}" --ignore-not-found
kubectl delete -n "${NS}" -f "${PD_MANIFEST}" --ignore-not-found
kubectl delete -n "${NS}" -f "${BASELINE_JOB_MANIFEST}" --ignore-not-found
kubectl delete -n "${NS}" -f "${BASELINE_MANIFEST}" --ignore-not-found
kubectl wait -n "${NS}" --for=delete pod -l "test-run=${RUN_ID}" --timeout=10m
kubectl get all,configmap -n "${NS}" -l "test-run=${RUN_ID}" -o yaml > "${RUN_DIR}/cleanup-after.yaml"
```

删除 Deployment 前，使用 `run-config.json` 中冻结的 exact session IDs 和 cleanup command 关闭 Mooncake sessions。若曾建立 port-forward，按记录的 PID/command line 逐个终止并归档；默认 client Job 路径不建立 port-forward。

Cleanup PASS 还要求：

- 所有 run-owned Deployments、Services、ConfigMaps、Jobs、Pods 均不存在；
- Mooncake 中没有该 `RUN_ID` 的 session、registered test range或未完成 transfer；
- Decode Main reservation、Indexer ownership、delayed NPU blocks、worker command state和scheduler trackers均回到启动前基线；
- 目标 node 上该 run 的 Pod resource requests消失，device-plugin 与 cluster-approved NPU inventory证明所有本 run NPU allocation已释放；
- 不修改或删除其他 workload；若并发 workload使 node总量变化，只依据 test Pod UID/device allocation作归因；
- `cleanup-after.yaml`、session cleanup output、Pod deletion、node allocation before/after和NPU inventory均已归档。

Cleanup 失败是整个 run 失败，不允许声明 runtime validated。

## Evidence Schema 与最终判定

每个 case 的 `result.json` 至少包含：`case_id`、`status`、`run_id`、开始/结束时间、input SHA256、image/config identity、request IDs、P/D Pod UIDs、NPU allocation、Mooncake sessions、TP terminal set、baseline comparison、cache oracle、failure injection、resource delta、cleanup result和artifact checksums。

允许的 case status：

- `planned / not run`：未发流量；必须记录未运行原因，不填推测结果；
- `PASS`：prerequisite、runtime oracle、success criteria和per-case cleanup全部通过；
- `FAIL`：任一 oracle/contract/cleanup失败或证据不完整；
- `INVALID`：identity/config漂移、基础设施故障或注入未命中导致该次运行不能判定；修复后使用新 attempt，不改写旧证据。

最终报告必须分别列出 static、Phase A、Phase B、八个 NPU case 和 final cleanup 的实际状态。只有八个 mandatory NPU case 全部为 `PASS`、没有 `INVALID`/缺失证据且 final cleanup PASS，才能把 NPU runtime 状态从本文当前的 `planned / not run` 更新为 `NPU runtime validated`。
