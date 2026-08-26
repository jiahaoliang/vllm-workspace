# Blockwise DSA handoff

Captured: `2026-08-24T17:03:35+08:00`

## Next session focus

Diagnose or restore GitCode HTTPS authentication, then complete the already
approved normal push of the source branch. While fixing authentication, do not
change source files, commits, or control-repo state.

## Mandatory resume reads

Before any action, read these files completely:

- `/root/ljh/vllm-workspace/AGENTS.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-goal.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage1-design-gate.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage1-routing-amendment.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-test-budget-amendment.md`
- `/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/CONTEXT.md`

These artifacts are authoritative. In particular, the Stage 3 test-budget
amendment is approved; do not treat it as the earlier unapproved proposal.

## Verified local state

- Source worktree: `/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation`
- Branch: `feature/blockwise-dsa-mooncake-v1-reimplementation`
- Base: `0d6dd0d26ab69219f861c9b312329f4c60fe36f2`
- HEAD: `3a22c5a6d697250dbf942354bfdac1781af3077d`
- Source worktree: clean at the captured time
- Backup ref: `backup/blockwise-dsa-base-0d6dd0d-20260823` at the base
- Behavior reference: canonical `repos/vllm-ascend` at `60eb76e`

The approved four-commit range is `0d6dd0d26..3a22c5a6d`. Inspect it with
`git log` instead of copying commit metadata from this handoff. All four commits
have `Signed-off-by` trailers; identity values are intentionally omitted here.

The range contains seven files and `+2990/-82`: production `+1670/-39` and
focused tests `+1320/-43`. `git diff --check 0d6dd0d26..HEAD` passed again during
this handoff repair. The implementation remains within the approved
`MooncakeConnectorV1 + typed metadata + thin SFA extension` architecture.

## Recorded validation

These results were recorded before the failed push and were not rerun while
repairing this handoff:

- A2 public lifecycle: `6 passed`
- Connector and worker: `107 passed`
- Typed metadata: `27 passed`
- Affected SFA: `14 passed`
- Default V1: `97 passed, 10 deselected`
- Complete `kv_offload`, run as isolated files: `245 passed, 5 failed`

The five failures were reported as unchanged baseline asymmetric-push tests
with missing imports; the relevant test and production files did not differ
from the base. AST and `git diff --check` passed. Ruff was unavailable. Real
multi-node, NPU, runtime, and performance validation remain `planned / not run`.

## Push and authentication state

The target remote ref was absent immediately before the previous push attempt.
The push failed before publication with this redacted error:

```text
fatal: could not read Password for 'https://<redacted>@gitcode.com':
No such device or address
```

Do not assume the target ref is still absent. Recheck it after authentication
works.

Observed credential configuration at the captured time:

- Global credential helper: `store`
- Repository config clears inherited helpers, then uses
  `store --file=/root/.config/git/credentials-vllm-workspace`
- Credential file exists with mode `0600` and size 72 bytes

No credential content was inspected or copied into this file. Do not print
tokens, passwords, credential-file contents, Authorization headers, remote URL
userinfo, or personal identity values while diagnosing the failure.

## Safe continuation

1. Read all mandatory artifacts.
2. Recheck source worktree cleanliness, HEAD, remotes, and credential-helper
   configuration without exposing secrets.
3. Run `git ls-remote origin refs/heads/feature/blockwise-dsa-mooncake-v1-reimplementation`.
4. If the ref is absent, run the approved normal push:
   `git push origin feature/blockwise-dsa-mooncake-v1-reimplementation`.
5. If the remote ref exists at a different SHA, stop. Do not force-push.
6. Re-run `ls-remote` and require the remote SHA to equal local HEAD.
7. Report the remote SHA and stop at the next gate. Do not start role swap,
   lock refresh, repo-state, issue, docs, or control-repo work.

## Authorization boundary

The user authorized only the four existing source commits and their normal
push. This does not authorize force-push, commit rewrite, source changes,
canonical worktree role swap, lock-script changes, `workspace.lock.json`,
repo-state, issues, docs, or any control-repo commit or push.

Preserve all dirty control-repo WIP, including `deployment_yaml/`, feature docs,
and `npu-e2e/`. At the captured time, the control branch was two commits ahead
of its remote.

## Suggested skills

- Use `diagnosing-bugs` if GitCode credential lookup still fails.
- Use `handoff` again if another session boundary occurs before remote-SHA
  verification.
