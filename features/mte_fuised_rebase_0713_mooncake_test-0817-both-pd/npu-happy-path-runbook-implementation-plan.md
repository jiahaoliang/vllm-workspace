# Blockwise DSA NPU Happy Path Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute this plan task-by-task in the current session. Subagent dispatch is not used for this documentation-only change.

**Goal:** 编写一份人类可读、命令可复制的裸机多节点 NPU Happy Path Runbook，并保持真实 NPU 状态为 `planned / not run`。

**Architecture:** 单一 Markdown Runbook 内嵌 `happy-path.env`、基于 SSH 的逐角色启动命令、固定请求生成与执行命令、人工语义 oracle、日志检查和精确 PID 清理。Mooncake Transfer Engine 由 `MooncakeConnectorV1` worker 内部初始化，不部署 Mooncake Master；PD proxy 同时承载 `/v1/metaserver` 控制面。

**Tech Stack:** Bash 4+、OpenSSH、curl、jq、Python 3、vLLM OpenAI-compatible API、vLLM-Ascend、Mooncake Transfer Engine。

## Global Constraints

- 被测源码固定为 vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`。
- 被测模式固定为 `MooncakeConnectorV1` 与 `dsa_pd_offload=true`。
- 拓扑固定为 `P TP8/DP2 -> D TP2/DP8`，Decode PP=1 且不启用 `async_scheduling`。
- 模型固定为 GLM W4A8；执行者填写实际 `MODEL_PATH`。
- 只完整定义 correctness Happy Path；基础性能和 Lifecycle 只保留后续章节边界。
- oracle 是人工比较 baseline 与 P/D 回答的语义一致性，加服务与 transfer 无报错。
- 通过结论只能是 `Happy Path smoke passed`。
- 不启动 Mooncake Master/Store，不运行 Kubernetes 命令，不执行真实 NPU 测试。
- 只提交本计划与新 Runbook；保留现有未提交 WIP。

---

### Task 1: 编写配置、启动与请求执行 Runbook

**Files:**
- Create: `features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-happy-path-runbook.md`
- Reference: `features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-happy-path-runbook-design.md`
- Reference: `repos/vllm-ascend-blockwise-dsa-reimplementation/PUNCTURE-mooncake-dsa-fused-swapped-dram.md`
- Reference: `repos/vllm-ascend-blockwise-dsa-reimplementation/examples/disaggregated_prefill_v1/load_balance_proxy_layerwise_server_example.py`

**Interfaces:**
- Consumes: execution values from a Bash-sourceable `happy-path.env`.
- Produces: one sequential manual workflow from baseline startup through evidence collection and cleanup.

- [x] **Step 1: Write the document header and environment template**

Include exact source identity, conclusion boundary, prerequisites, `RUN_ROOT`, `MODEL_PATH`, `SERVED_MODEL_NAME`, `VLLM_ASCEND_ROOT`, `PROXY_SCRIPT`, SSH/NIC values, aligned P/D host/device/HTTP/KV/engine-ID lists, and separate P/D external-DP coordinator address/RPC port values.

- [x] **Step 2: Add local initialization and environment validation commands**

Commands must create `RUN_ID`, copy the resolved environment, split aligned lists, require exactly 2 P and 8 D entries, reject `REPLACE_ME`, and avoid cluster mutation or NPU execution in this workspace.

- [x] **Step 3: Add baseline startup, health, request capture, and exact stop commands**

Baseline uses the first Prefill host/devices with TP8/DP1, no KV connector, `use_offload=false`, the same model/sampling parameters, a PID file, `/health`, and precise PID shutdown.

- [x] **Step 4: Add Decode, Prefill, and proxy startup commands**

Decode starts first with TP2/DP8, `dsa_pd_offload=true`, `sfa_kv_offload_backend=mooncake`, `use_offload=true`, and `kv_offload_mode=fused_overlap`. Prefill starts second with TP8/DP2 and `use_offload=false`. Proxy starts last with exactly 2 P and 8 D endpoints and a concrete reachable host.

- [x] **Step 5: Add four fixed Happy Path request groups**

Generate request JSON/JSONL for `HP-01 short`, `HP-02 long-prompt`, `HP-03 long-output`, and 16-request `HP-04 low-concurrency`. Run identical payloads against baseline and P/D endpoints and preserve raw responses.

- [x] **Step 6: Add human oracle, log audit, evidence collection, and cleanup**

Provide a Markdown result table, objective HTTP/log checks, fail-fast rules, `scp` collection, reverse-order role shutdown by exact PID, port/process checks, and a result summary template.

- [x] **Step 7: Add future performance and Lifecycle boundaries**

Name performance metrics and Lifecycle boundary/failure/control families, explicitly state that commands and thresholds are outside this Runbook, and do not leave unresolved placeholder markers or imply validation.

### Task 2: Static review and narrow publication

**Files:**
- Verify: `features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-happy-path-runbook.md`
- Verify: `features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/npu-happy-path-runbook-implementation-plan.md`

**Interfaces:**
- Consumes: the completed Runbook and approved design.
- Produces: one reviewable control-repo commit pushed to the current feature branch.

- [x] **Step 1: Check Markdown and shell blocks statically**

Run `git diff --check`, extract every fenced `bash` block for `bash -n` where the block is a complete shell unit, and manually classify non-standalone snippets rather than executing NPU commands.

- [x] **Step 2: Check required and forbidden content**

Use `rg` to require `MooncakeConnectorV1`, `dsa_pd_offload`, `P2PHANDSHAKE` explanation, `P TP8/DP2`, `D TP2/DP8`, all four Happy Path IDs, PID cleanup, and `planned / not run`. Reject Mooncake Master startup, Kubernetes commands, broad process-kill commands, token-level validation claims, and unresolved placeholder markers.

- [x] **Step 3: Review the staged allowlist**

Stage only the implementation plan and Runbook. Confirm `git diff --cached --stat` lists exactly those two files and existing WIP remains unstaged.

- [x] **Step 4: Commit and push**

Commit with `docs: add NPU happy path runbook`, push the current branch to its same-name `origin` branch, and verify local/remote tracking counts are `0 0`.
