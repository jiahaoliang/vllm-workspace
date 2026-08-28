# Blockwise DSA PD Offload Status

Updated At: 2026-08-29

| Area | Status | Evidence |
| --- | --- | --- |
| Sync implementation issues 01-07 | `resolved` | [Issue map](map.md) |
| Sync production source | committed and published | vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` |
| Sync architecture | replacement boundary met | `MooncakeConnectorV1` + typed metadata + thin SFA extension |
| Static | `PASS` | compile and `git diff --check`; no new ruff failure |
| Focused DSA/SFA | `PASS` | `47 passed` |
| Connector/default V1 | `PASS` | `111 passed` |
| Broad CPU/mock | `PASS` | `221 passed` after excluding one known baseline-broken file |
| Full CPU/mock root | baseline exceptions | `241 passed / 5 pre-existing failures` |
| Async contract | approved | [Canonical spec](spec.md) and ADR 0024-0030 |
| Async production implementation and E2E closure | committed and published | vLLM-Ascend `117637d205603b0c1e43aa0ea3e141de926ff3b1` |
| Prefill DCP source shard assembly | committed and published | vLLM-Ascend `6d0ca14d2`; [Issue 23](issues/23-implement-prefill-dcp-source-shard-assembly.md) |
| Prefill DCP CPU/mock | `PASS` | applicable root `263 passed`; standalone async target `1 passed`; final two-axis review clean for code/spec |
| Prefill DCP real Mooncake/NPU | `planned / not run` | DCP2/DCP4, partial block, prefix cache, multi-request and cache/output oracles unexecuted |
| GitCode reporter async happy path | `PASS` | [CPU/mock validation report](async-happy-path-validation-report.md) |
| Full async failure/lifecycle matrix | 未测试 | 未测试 |
| Graph-capture runtime | `planned / not run` | No runtime evidence |
| NPU runtime | bounded E2E `PASS` | Origin analysis records glm-5.1/glm5.2 smoke, long-request and approximately 4k-input concurrent runs |
| Full NPU 8-case plan | partially evidenced / not reconciled | [8-case plan](npu-e2e-test-plan.md); referenced experiment ledger is not tracked in the fetched tree |
| vLLM-Ascend publish | verified | Live fetch and local tracking ref equal `117637d20` |
| Cross-machine restore | available | [workspace lock](../../workspace.lock.json) records the fetchable branch/SHA |

Control repo 和 replacement vLLM-Ascend worktree 都保留在各自 feature branch。既有sync replacement的production/focused-test budget分别为`+1704/-41`与`+1478/-43`，低于当时批准的`1770/1500` stop lines；这些历史数字不约束后续 async implementation、E2E closure与ticket 23。Ticket 23 production为`+661/-103`、净增558行，高于最初LOC估算中位数；tests为`+581/-4`，完整commit为`+1242/-107`。其scope未扩展到public schema或vLLM core。远端旧NPU结论仅覆盖 glm-5.1/glm5.2 冒烟、长请求和约 4k 输入并发；本 workspace 未运行新的Prefill DCP NPU matrix，旧8-case plan未逐项对账，graph-capture、完整failure/lifecycle matrix和未记录的performance边界仍未验证。
