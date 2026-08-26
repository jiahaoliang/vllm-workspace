# Blockwise DSA PD Offload Status

Updated At: 2026-08-27

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
| Async production implementation | committed and published | vLLM-Ascend `e61dacccc27ee965410c60c0d8cedaf38d66ccc6` |
| GitCode reporter async happy path | `PASS` | [CPU/mock validation report](async-happy-path-validation-report.md) |
| Full async failure/lifecycle matrix | 未测试 | 未测试 |
| Graph-capture runtime | `planned / not run` | No runtime evidence |
| NPU runtime | `planned / not run` | [8-case plan](npu-e2e-test-plan.md) |
| vLLM-Ascend publish | verified | GitCode remote ref equals `e61daccc` |
| Cross-machine restore | available | [workspace lock](../../workspace.lock.json) records the fetchable branch/SHA |

Control repo 和 replacement vLLM-Ascend worktree 都保留在各自 feature branch。既有sync replacement的production/focused-test budget分别为`+1704/-41`与`+1478/-43`，低于当时批准的`1770/1500` stop lines；这些历史数字不约束已独立review的async implementation，validation仍只覆盖reporter happy path。真实multi-node transfer、NPU、cache contents、fused kernel、graph-capture与performance仍未验证。
