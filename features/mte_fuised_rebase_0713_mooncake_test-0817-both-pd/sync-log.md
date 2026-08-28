# Sync Log

## 2026-08-22

- Verified origin and collaborator GitCode branches resolve to the same vLLM-Ascend commit.
- Created the control-repo and source-repo feature branches.
- Pinned vLLM to `v0.23.0` and Mooncake to `v0.3.12.post1`.

## 2026-08-23

- Implemented issues 01-07 in vLLM-Ascend commit `f826ea3f354f87cdf95895addbdaaad6ca92dd7c` with sign-off.
- Validated the exact source tree in `liangjiahao/vllm-ascend-ut`: Phase A `306 passed`, Phase B `355 passed`, standalone scheduler/connector `43 passed`, and post-DSA default V1 regression `93 passed`.
- Added the CPU/mock validation report and the 8-case NPU E2E plan; all NPU cases remain `planned / not run`.
- Attempted to push vLLM-Ascend to the configured personal GitCode origin; push failed because no GitCode credential is available in this environment. No remote or credential configuration was changed.
- Ran `./scripts/lock-repos.sh`; it failed before writing because the existing resolver cannot map `feature/<name>` to `features/<name>`. Refreshed `workspace.lock.json` and `repo-state.md` manually from exact repository identities.
- Deleted the exact UT temporary directory `/workspace/dsa-final-4rjqdZ`; retained `liangjiahao/vllm-ascend-ut` in `Running/Ready` state.

## 2026-08-24

- Superseded `f826ea3f` as the production candidate and retained it only as behavior-reference evidence.
- Reimplemented the feature from clean base `0d6dd0d26` on `feature/blockwise-dsa-mooncake-v1-reimplementation`, using existing `MooncakeConnectorV1`, one typed metadata module and a thin SFA scheduler extension.
- Completed white-box ordering corrections and published signed-off source HEAD `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` to the personal GitCode origin; live `ls-remote` verification matched the exact SHA.
- Recorded final static/CPU-mock evidence: focused DSA/SFA `47 passed`, connector/default V1 `111 passed`, broad regression `221 passed`, and full CPU root `241 passed / 5 pre-existing failures`.
- Kept real multi-node and NPU runtime evidence at `planned / not run`.

## 2026-08-28

- Fetched `origin/feature/blockwise-dsa-mooncake-v1-reimplementation` from GitCode and fast-forwarded the clean replacement worktree from `e61dacccc27ee965410c60c0d8cedaf38d66ccc6` to `117637d205603b0c1e43aa0ea3e141de926ff3b1`; local and tracking refs are `0 ahead / 0 behind`.
- The fetched range adds runtime fixes at `59fd10b0d` plus the final `docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md`. Branch history records passing glm-5.1/glm5.2 smoke, long-request and approximately 4k-input concurrent NPU E2E runs, followed by service shutdown and NPU release.
- Kept the evidence boundary explicit: the referenced `experiments/20260827-blockwise-dsa-mooncake-v1/` ledger is not tracked in the fetched source tree, this workspace did not rerun NPU jobs, and the older 8-case plan has not been reconciled case by case.
- Refreshed `workspace.lock.json`, `repo-state.md` and current feature status manually because the locked replacement source lives in a separate worktree while the standard restore destination remains `repos/vllm-ascend`.
