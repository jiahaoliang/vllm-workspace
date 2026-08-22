# mte_fuised_rebase_0713_mooncake_test-0817-both-pd Repo State

Captured At: 2026-08-23T02:54:10+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | false | upstream vLLM baseline |
| vllm-ascend | `repos/vllm-ascend` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `f826ea3f354f87cdf95895addbdaaad6ca92dd7c` | false | upstream vLLM Ascend baseline |
| Mooncake | `repos/Mooncake` | `tag:v0.3.12.post1` | `6041a609a8c3af35e778f70db344f145c2914980` | false | dependency reading and validation |

## Validation State

- vLLM-Ascend `f826ea3f3` contains the Blockwise DSA implementation and focused tests.
- Static, Phase A, Phase B and post-DSA default V1 regression passed; see [CPU/mock validation report](cpu-mock-validation-report.md).
- NPU runtime remains `planned / not run`; see [NPU E2E test plan](npu-e2e-test-plan.md).

## Publish State

- vLLM-Ascend commit `f826ea3f3` exists locally with sign-off.
- HTTPS push to `origin/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` was attempted and failed because this environment has no GitCode credential. The local tracking ref therefore remains at `0d6dd0d26`.
- Cross-machine restore of the new vLLM-Ascend lock is not available until `f826ea3f3` is pushed to the configured GitCode origin.

## Lock Refresh Note

`./scripts/lock-repos.sh` was run after the source commit but failed before writing because `resolve_feature_directory()` does not map the control branch `feature/<name>` to the existing directory `features/<name>`. `workspace.lock.json` and this file were refreshed manually with the exact repository identities above; the public script was not changed on this feature branch.
