# mte_fuised_rebase_0713_mooncake_test-0817-both-pd Repo State

Captured At: 2026-08-24T22:58:32+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | false | upstream vLLM baseline |
| vllm-ascend | `repos/vllm-ascend-blockwise-dsa-reimplementation` | `feature/blockwise-dsa-mooncake-v1-reimplementation` | `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` | false | lock source; restores to `repos/vllm-ascend` |
| Mooncake | `repos/Mooncake` | `tag:v0.3.12.post1` | `6041a609a8c3af35e778f70db344f145c2914980` | false | dependency reading and validation |

## Validation State

- vLLM-Ascend `7401ae79c` contains the replacement implementation and focused tests. The production shape is existing `MooncakeConnectorV1`, one typed metadata module and a thin SFA scheduler extension; the obsolete standalone subsystem is not present.
- Static gates passed. Focused DSA/SFA tests were `47 passed`, the complete connector/default-V1 target was `111 passed`, and the broad CPU/mock regression excluding one known baseline-broken file was `221 passed`; see [CPU/mock validation report](cpu-mock-validation-report.md).
- The full CPU/mock root was `241 passed / 5 failed`. All five failures are missing test imports in unchanged `test_mooncake_to_dram_asymmetric_push.py`, not replacement regressions.
- NPU runtime remains `planned / not run`; see [NPU E2E test plan](npu-e2e-test-plan.md).

## Publish State

- The five-commit replacement range `0d6dd0d26..7401ae79c` is signed off and published to GitCode branch `feature/blockwise-dsa-mooncake-v1-reimplementation`.
- `git ls-remote origin refs/heads/feature/blockwise-dsa-mooncake-v1-reimplementation` was verified at capture time and returned exactly `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`.
- Cross-machine restore is available from the branch and commit recorded in `workspace.lock.json`.

## Lock Refresh Note

The source was implemented in a separate non-destructive worktree, while the standard restore destination remains `repos/vllm-ascend`. `workspace.lock.json` and this file were therefore refreshed manually with the published branch and exact commit. The existing canonical checkout at `repos/vllm-ascend` remains an old behavior-reference checkout and is not the locked replacement source. The public lock script was not changed on this feature branch.
