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
