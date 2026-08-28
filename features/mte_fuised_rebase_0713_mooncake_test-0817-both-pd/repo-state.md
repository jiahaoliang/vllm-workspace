# mte_fuised_rebase_0713_mooncake_test-0817-both-pd Repo State

Captured At: 2026-08-29T02:12:23+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | false | upstream vLLM baseline |
| vllm-ascend | `repos/vllm-ascend` | `feature/blockwise-dsa-mooncake-v1-reimplementation` | `6d0ca14d2b5b82bcfc466ab1dad1a2a471a10bc2` | false | Blockwise DSA MooncakeV1 replacement source |
| Mooncake | `repos/Mooncake` | `tag:v0.3.12.post1` | `6041a609a8c3af35e778f70db344f145c2914980` | false | dependency reading and validation |

## Validation State

- vLLM-Ascend `7401ae79c` contains the replacement implementation and focused tests. The production shape is existing `MooncakeConnectorV1`, one typed metadata module and a thin SFA scheduler extension; the obsolete standalone subsystem is not present.
- Static gates passed. Focused DSA/SFA tests were `47 passed`, the complete connector/default-V1 target was `111 passed`, and the broad CPU/mock regression excluding one known baseline-broken file was `221 passed`; see [CPU/mock validation report](cpu-mock-validation-report.md).
- The full CPU/mock root was `241 passed / 5 failed`. All five failures are missing test imports in unchanged `test_mooncake_to_dram_asymmetric_push.py`, not replacement regressions.
- Ticket 18 added the non-gating D2H plan/progress slice. In the CPU-only `liangjiahao/vllm-ascend-ut` Pod, metadata plus connector targets were `137 passed` and the complete remote-prefill lifecycle file was `6 passed`; independent two-axis review had no blocking finding after review fixes.
- Ticket 18 does not validate terminal ownership, preemption, real Mooncake, fused kernel, graph capture, serving, or NPU runtime.
- Ticket 19 added the async normal-finish terminal barrier. CPU/mock connector/metadata targets were `140 passed` and the A2 lifecycle file was `6 passed`; independent rereview had no blocking ticket 19 finding.
- Ticket 19 does not validate preemption, abort, other terminal reasons, real Mooncake, fused kernel, graph capture, serving, or NPU runtime.
- Ticket 20 added the async preemption replay barrier. Focused CPU/mock connector/metadata targets were `145 passed`, A2 lifecycle was `6 passed`, and broad kv_offload excluding the known baseline-broken file was `228 passed`; independent rereview had no blocking finding.
- Ticket 20 focused evidence does not expand the canonical Preemption runtime claim, which remains “未测试”.
- Ticket 21 added async compatibility classification. Focused startup smoke was `2 passed` and the complete connector target was `123 passed`; independent review found no blocking issue.
- Ticket 21 follow-up `ffbafcc1` fixed real `MultiprocExecutor` DSA Decode handshake startup; the complete connector target was `124 passed`, and independent two-axis review reported zero findings.
- Nondefault executor/scheduler lifecycle and speculative configuration remain untested.
- Ticket 22's mandatory CPU/mock gate passed at `e61daccc`: supervisor reran five explicit targets in `liangjiahao/vllm-ascend-ut` and obtained `5 passed, 14 warnings in 1.82s`. The host and Pod test-file SHA256 matched, and final independent review had no Spec finding or blocking issue.
- Allowed claim: `GitCode reporter happy path 已通过 CPU/mock validation`.
- Ticket 23 added exact Prefill DCP Main shard assembly at `6d0ca14d2`. In the CPU-only
  `liangjiahao/vllm-ascend-ut` Pod, the complete applicable `kv_offload` CPU/mock root excluding
  NPU `a2/` and the known baseline-broken asymmetric-push file was `263 passed, 14 warnings`; the
  async happy-path target passed independently as `1 passed, 14 warnings`. Six changed Python files
  passed bytecode compile, Host/Pod SHA256 matched before the gate, and final Standards/Spec delta
  review found no blocking code or spec issue after cleanup.
- Ticket 23 real Mooncake/NPU DCP2/DCP4, partial-block, prefix-cache, multi-request and cache-content/
  output-oracle validation remains `planned / not run`. The CPU/mock result does not expand the older
  bounded NPU evidence or satisfy the repository's NPU merge-readiness guideline.
- Origin commit `59fd10b0d` added the runtime fixes found while closing the Blockwise DSA Mooncake PD path for glm-5.1 and glm5.2. The branch history records passing short/long generation and approximately 4k-input concurrent NPU E2E runs for both models; the final analysis at `117637d20` states that services were stopped and NPU resources released.
- This is bounded E2E evidence, not proof that every mandatory case in the older [NPU E2E test plan](npu-e2e-test-plan.md) ran. The referenced `experiments/20260827-blockwise-dsa-mooncake-v1/` ledger is not tracked in the fetched source tree, and this workspace did not rerun the NPU jobs. Graph capture, the full failure/lifecycle matrix, and any unrecorded plan cases remain unverified.

## Publish State

- The replacement through ticket 22 and subsequent E2E closure remain in history through
  `117637d20`; ticket 23 is published at `6d0ca14d2` on GitCode branch
  `feature/blockwise-dsa-mooncake-v1-reimplementation`.
- `git ls-remote` on 2026-08-29 confirmed
  `origin/feature/blockwise-dsa-mooncake-v1-reimplementation` at exactly
  `6d0ca14d2b5b82bcfc466ab1dad1a2a471a10bc2`; the canonical checkout at
  `repos/vllm-ascend` is `0 ahead / 0 behind` with a clean tracked tree.
- Cross-machine restore is available from the branch and commit recorded in `workspace.lock.json`.

## Lock Refresh Note

The source was implemented in a separate non-destructive worktree. On 2026-08-29 that clean worktree was removed and the published replacement branch was checked out at the standard `repos/vllm-ascend` path. Ticket 23 then continued in that canonical checkout. `./scripts/lock-repos.sh` could not resolve the historical control branch name `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` to its existing feature directory; it exited before writing. The lock and table were therefore refreshed with the script-equivalent exact branch/HEAD/dirty checks recorded above. The public lock script was not changed on this feature branch.
