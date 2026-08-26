# Blockwise DSA NPU E2E Harness

本目录是 issue 07 的 repository-local 测试工件。它负责冻结输入、render Kubernetes JSON、执行 fail-closed preflight、运行单个 mandatory case 并归档证据。它不是 production deployment system，不会自动决定 NPU placement、构建 image、安装 probe/fault hook 或编排 serving phase。

Host 需要 Bash 4+、jq、coreutils、Python 3 与 `jsonschema`。Live preflight/runner 还需要已配置的 kubectl；缺少任一依赖均 fail closed。

当前 8 个 case 均为 planned / not run。run-config.template.json 故意保留 REQUIRED identity，所有 runtime capability 默认为 UNKNOWN；模板本身不能 render 或发流量。

## 目录契约

- schema/：run config、capability evidence、fixture 和 case catalog 的 versioned JSON Schema；由 `validate-json-schema.py` 实际执行，不只是文档。
- config/run-config.template.json：每个 run 必须解析并冻结的 identity/topology/capability 输入。
- fixtures/requests.template.jsonl：10 条固定 token-ID fixture，按 block size 16 冻结 reservation block 数和 canonical input SHA256。
- cases/cases.json：NPU-01 至 NPU-08 的 manifest、输入、dependency、capability、structured control、oracle、成功条件、失败证据和 cleanup。
- templates/：只供 render.sh 使用的 Kubernetes JSON 模板。
- scripts/render.sh：生成 immutable run directory，不覆盖已有非空目录。
- scripts/preflight.sh：offline 不调用 cluster；live 仅执行 read-only 查询和 server-side dry-run。
- scripts/run-case.sh：确认同名对象不存在后逐个 create 一个已 render 的 case ConfigMap/Job，记录 UID，收证后只删除 UID/labels 仍匹配的对象。

## 1. 冻结并 Render

先从 template 生成 repository 外的 resolved config。至少解析唯一 RUN_ID、精确 kube context、liangjiahao、target node、所有 immutable image digest、dependency revisions、model/configuration/positional ABI fingerprint、完整 topology/routes、serving/client command、fixture/catalog SHA256 和 capability evidence。

capability 允许 PASS、FAIL、UNKNOWN。只有 PASS 要求 artifact_root 下各自独立的 absolute evidence JSON path 和匹配 SHA256。该 JSON 必须符合 capability-evidence.schema.json，绑定同一 run_id/capability，包含 common.sh 冻结的 exact assertion IDs，并为每个 ID 提供 capability-specific artifact path/SHA256；普通文件、generic assertion、跨 capability 复用的 evidence/artifact 都不能把 capability 标成 PASS。`output_oracle` 的固定 claims 明确要求 baseline capture、identity match 与 allocation release。{RUN_ID} 与 {CASE_ID} 只允许出现在 commands.session_cleanup 中；runner 以 argv 替换，不使用 shell eval。

    export HARNESS=features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-e2e
    export RUN_CONFIG=/absolute/path/run-config.json
    export RUN_ID=$(jq -r '.run_id' "${RUN_CONFIG}")
    export RUN_DIR=$(jq -r '.artifact_root' "${RUN_CONFIG}")/${RUN_ID}

    bash "${HARNESS}/scripts/validate-static.sh"
    bash "${HARNESS}/scripts/render.sh" "${RUN_CONFIG}" "${RUN_DIR}"

renderer 输出 baseline.json、baseline-oracle.json、dsa-pd.json、default-v1-pd.json、NPU-01.json 至 NPU-08.json，以及 frozen config/catalog/fixtures 和 rendered-sha256.txt。

## 2. Preflight

Offline preflight 只验证 repository-local 工件。它固定返回 overall_status=UNKNOWN 和 exit code 2，因为 cluster identity 与 server admission 未知；该模式保证不调用 kubectl。

    set +e
    bash "${HARNESS}/scripts/preflight.sh" --offline "${RUN_DIR}"
    test "$?" -eq 2
    set -e
    jq . "${RUN_DIR}/preflight/preflight.json"

Live preflight 只读取 current context、liangjiahao namespace、target node/node Pods，计算 physical Ascend910 allocatable 减去其他 non-terminal Pod requests 的可用量，并对全部 12 个 manifest 执行 kubectl apply --dry-run=server -n liangjiahao；它不创建 workload。runner 只接受 generated_at/epoch 一致且不超过 10 分钟的 live result。

    kubectl config current-context
    bash "${HARNESS}/scripts/preflight.sh" --live "${RUN_DIR}"
    jq '{overall_status, cases}' "${RUN_DIR}/preflight/preflight.json"

overall_status 只表示 common static/cluster/server-dry-run gate。case status 单独计算：

- required capability 为 FAIL、common gate 为 FAIL 或任一 latest attempt cleanup FAIL：case FAIL；
- required capability 为 UNKNOWN、common gate 未 PASS、任一 latest cleanup evidence 无法校验，或 required case 没有最新 cleanup-PASS 的 PASS result：case UNKNOWN；
- 全部满足：case PASS，runner 才允许启动。

因此缺少 cache_probe、phase_fault、tp_terminal_barrier、preemption_control 或 cancellation_control 时，依赖 case 必须保持 UNKNOWN/FAIL 与 planned / not run。

## 3. Serving Phase

以下命令是人工审核后的测试 phase，不由 harness 自动运行。所有命令使用 frozen context 和显式 liangjiahao。

先采集 non-PD baseline：

    export KUBE_CONTEXT=$(jq -r '.kube_context' "${RUN_DIR}/run-config.json")
    kubectl --context "${KUBE_CONTEXT}" apply -n liangjiahao -f "${RUN_DIR}/manifests/baseline.json"
    kubectl --context "${KUBE_CONTEXT}" rollout status -n liangjiahao "deployment/${RUN_ID}-baseline" --timeout=30m
    kubectl --context "${KUBE_CONTEXT}" apply -n liangjiahao -f "${RUN_DIR}/manifests/baseline-oracle.json"
    kubectl --context "${KUBE_CONTEXT}" wait -n liangjiahao --for=condition=complete --timeout=30m "job/${RUN_ID}-baseline"
    kubectl --context "${KUBE_CONTEXT}" logs -n liangjiahao "job/${RUN_ID}-baseline" --all-containers=true > "${RUN_DIR}/results/baseline.log"
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/baseline-oracle.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/baseline.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" wait -n liangjiahao --for=delete pod -l "test-run=${RUN_ID},test-role=baseline" --timeout=10m

只有 baseline evidence 完整且 NPU allocation 已释放，才启动 DSA P/D。renderer 为每个 DP rank 生成一个 Deployment：

    kubectl --context "${KUBE_CONTEXT}" apply -n liangjiahao -f "${RUN_DIR}/manifests/dsa-pd.json"
    for rank in $(seq 0 $(($(jq -r '.topology.prefill_dp' "${RUN_DIR}/run-config.json") - 1))); do
      kubectl --context "${KUBE_CONTEXT}" rollout status -n liangjiahao "deployment/${RUN_ID}-prefill-dp${rank}" --timeout=30m
    done
    for rank in $(seq 0 $(($(jq -r '.topology.decode_dp' "${RUN_DIR}/run-config.json") - 1))); do
      kubectl --context "${KUBE_CONTEXT}" rollout status -n liangjiahao "deployment/${RUN_ID}-decode-dp${rank}" --timeout=30m
    done

## 4. 单 Case 执行

runner 会自行重新运行 live preflight，使手写/stale result 不能绕过 gate；也可先单独运行一次供人工复核。gate PASS 后，runner 确认同名对象不存在，只从 manifests/NPU-XX.json 逐个 create 一个 ConfigMap 和 Job：

    export CASE_ID=NPU-01
    bash "${HARNESS}/scripts/preflight.sh" --live "${RUN_DIR}"
    bash "${HARNESS}/scripts/run-case.sh" "${RUN_DIR}" "${CASE_ID}"

client stdout 必须恰有一行 DSA_NPU_RESULT=<json>。每个被 result 引用的 evidence 还必须有一行 DSA_NPU_ARTIFACT=<json>，artifact record 绑定 run_id/case_id 和 oracle/criterion/failure kind/index，使用安全文件名，并携带 content_base64 与匹配 SHA256；每项 evidence 必须使用独立 artifact，runner 解码并校验后才允许引用该 hash。Result JSON 必须匹配 frozen run_id、case_id、config SHA256 和 request IDs，并为 catalog 中每个 oracle/success criterion 提供连续 index、PASS/FAIL/INVALID 与可解析的 evidence SHA256。顶层 PASS 要求所有 oracle/criterion 为 PASS 且无 failure evidence；generic 单 blob、缺行、多行、字段缺失、identity 不符、artifact 缺失或 hash 不匹配均为 INVALID。

session cleanup command 必须恰有一行结构化记录：

    DSA_NPU_CLEANUP={"schema_version":1,"run_id":"...","case_id":"NPU-XX","status":"PASS","sessions_closed":true,"barriers_reset":true,"resource_baseline_restored":true,"evidence_sha256":["...","..."]}

cleanup command 还必须输出两行 `DSA_NPU_CLEANUP_ARTIFACT=<json>`：`session-inventory.json` 证明 open sessions/barriers 为空，`resource-delta.json` 证明 reservation、delayed NPU block、active command、tracker 与 NPU request delta 都为 0。布尔自报、record 不完整、command 非零、created UID/labels 漂移、精确对象删除失败或 Job/ConfigMap 仍存在时，case 为 FAIL，并封锁整个 run。runner 不覆盖或删除 pre-existing 同名对象。每次 attempt 保存在 results/NPU-XX/attempt-*/，旧 attempt 不覆盖。

NPU-08 前必须先精确删除 DSA P/D，确认 Pod/NPU/session 已释放，再启动 default V1：

    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/dsa-pd.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" wait -n liangjiahao --for=delete pod -l "test-run=${RUN_ID}" --timeout=10m
    kubectl --context "${KUBE_CONTEXT}" apply -n liangjiahao -f "${RUN_DIR}/manifests/default-v1-pd.json"

## 5. Final Cleanup

per-case cleanup 不删除 serving resources。完成收证后只按 frozen manifest 精确删除，不删除 namespace，也不使用 label deletion：

    kubectl config current-context
    kubectl --context "${KUBE_CONTEXT}" get namespace liangjiahao -o name
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/default-v1-pd.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/dsa-pd.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/baseline-oracle.json" --ignore-not-found
    kubectl --context "${KUBE_CONTEXT}" delete -n liangjiahao -f "${RUN_DIR}/manifests/baseline.json" --ignore-not-found

只有 8 个 case 全为 PASS、所有 cleanup evidence 完整且 final NPU allocation audit PASS，才能声明 NPU runtime validated。本目录当前不包含该结论。
