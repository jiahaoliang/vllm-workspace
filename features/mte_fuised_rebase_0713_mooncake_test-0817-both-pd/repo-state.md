# mte_fuised_rebase_0713_mooncake_test-0817-both-pd Repo State

Captured At: 2026-08-27T01:17:34+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | false | upstream vLLM baseline |
| vllm-ascend | `repos/vllm-ascend-blockwise-dsa-reimplementation` | `feature/blockwise-dsa-mooncake-v1-reimplementation` | `8f7c17f9f8490b001107e498b3db297c91f81531` | false | lock source; restores to `repos/vllm-ascend` |
| Mooncake | `repos/Mooncake` | `tag:v0.3.12.post1` | `6041a609a8c3af35e778f70db344f145c2914980` | false | dependency reading and validation |

## Validation State

- vLLM-Ascend `7401ae79c` contains the replacement implementation and focused tests. The production shape is existing `MooncakeConnectorV1`, one typed metadata module and a thin SFA scheduler extension; the obsolete standalone subsystem is not present.
- Static gates passed. Focused DSA/SFA tests were `47 passed`, the complete connector/default-V1 target was `111 passed`, and the broad CPU/mock regression excluding one known baseline-broken file was `221 passed`; see [CPU/mock validation report](cpu-mock-validation-report.md).
- The full CPU/mock root was `241 passed / 5 failed`. All five failures are missing test imports in unchanged `test_mooncake_to_dram_asymmetric_push.py`, not replacement regressions.
- Ticket 18 added the non-gating D2H plan/progress slice. In the CPU-only `liangjiahao/vllm-ascend-ut` Pod, metadata plus connector targets were `137 passed` and the complete remote-prefill lifecycle file was `6 passed`; independent two-axis review had no blocking finding after review fixes.
- Ticket 18 does not validate terminal ownership, preemption, real Mooncake, fused kernel, graph capture, serving, or NPU runtime.
- Ticket 19 added the async normal-finish terminal barrier. CPU/mock connector/metadata targets were `140 passed` and the A2 lifecycle file was `6 passed`; independent rereview had no blocking ticket 19 finding.
- Ticket 19 does not validate preemption, abort, other terminal reasons, real Mooncake, fused kernel, graph capture, serving, or NPU runtime.
- NPU runtime remains `planned / not run`; see [NPU E2E test plan](npu-e2e-test-plan.md).

## Publish State

- The replacement through ticket 19 range `0d6dd0d26..8f7c17f9` is signed off and published to GitCode branch `feature/blockwise-dsa-mooncake-v1-reimplementation`.
- `git ls-remote origin refs/heads/feature/blockwise-dsa-mooncake-v1-reimplementation` was verified for the ticket 19 publication and returned exactly `8f7c17f9f8490b001107e498b3db297c91f81531`.
- Cross-machine restore is available from the branch and commit recorded in `workspace.lock.json`.

## Lock Refresh Note

The source was implemented in a separate non-destructive worktree, while the standard restore destination remains `repos/vllm-ascend`. `workspace.lock.json` and this file were therefore refreshed manually with the published branch and exact commit. The existing canonical checkout at `repos/vllm-ascend` remains an old behavior-reference checkout and is not the locked replacement source. The public lock script was not changed on this feature branch.
