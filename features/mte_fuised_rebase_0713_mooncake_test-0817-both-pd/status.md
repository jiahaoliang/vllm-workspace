# Blockwise DSA PD Offload Status

Updated At: 2026-08-24T22:58:32+08:00

| Area | Status | Evidence |
| --- | --- | --- |
| Issues 01-07 | `resolved` | [Issue map](map.md) |
| Production source | committed and published | vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` |
| Architecture | replacement boundary met | `MooncakeConnectorV1` + typed metadata + thin SFA extension |
| Static | `PASS` | compile and `git diff --check`; no new ruff failure |
| Focused DSA/SFA | `PASS` | `47 passed` |
| Connector/default V1 | `PASS` | `111 passed` |
| Broad CPU/mock | `PASS` | `221 passed` after excluding one known baseline-broken file |
| Full CPU/mock root | baseline exceptions | `241 passed / 5 pre-existing failures` |
| NPU runtime | `planned / not run` | [8-case plan](npu-e2e-test-plan.md) |
| vLLM-Ascend publish | verified | GitCode remote ref equals `7401ae79c` |
| Cross-machine restore | available | [workspace lock](../../workspace.lock.json) records the fetchable branch/SHA |

Control repo 和 replacement vLLM-Ascend worktree 都保留在各自 feature branch。vLLM、replacement vLLM-Ascend 与 Mooncake checkout clean。Production/focused-test budget 分别为 `+1704/-41` 与 `+1478/-43`，低于批准的 `1770/1500` stop lines。真实 multi-node transfer、NPU、cache contents、fused kernel 与 performance 仍未验证。
