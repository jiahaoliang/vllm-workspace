# Blockwise DSA PD Offload Status

Updated At: 2026-08-28

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
| GitCode reporter async happy path | `PASS` | [CPU/mock validation report](async-happy-path-validation-report.md) |
| Full async failure/lifecycle matrix | 未测试 | 未测试 |
| Graph-capture runtime | `planned / not run` | No runtime evidence |
| NPU runtime | bounded E2E `PASS` | Origin analysis records glm-5.1/glm5.2 smoke, long-request and approximately 4k-input concurrent runs |
| Full NPU 8-case plan | partially evidenced / not reconciled | [8-case plan](npu-e2e-test-plan.md); referenced experiment ledger is not tracked in the fetched tree |
| vLLM-Ascend publish | verified | Live fetch and local tracking ref equal `117637d20` |
| Cross-machine restore | available | [workspace lock](../../workspace.lock.json) records the fetchable branch/SHA |

Control repo 和 replacement vLLM-Ascend worktree 都保留在各自 feature branch。既有sync replacement的production/focused-test budget分别为`+1704/-41`与`+1478/-43`，低于当时批准的`1770/1500` stop lines；这些历史数字不约束后续 async implementation 与 E2E closure。远端记录的 NPU 结论仅覆盖 glm-5.1/glm5.2 冒烟、长请求和约 4k 输入并发；本 workspace 未重跑 NPU，旧 8-case plan 未逐项对账，graph-capture、完整 failure/lifecycle matrix 和未记录的 performance 边界仍未验证。
