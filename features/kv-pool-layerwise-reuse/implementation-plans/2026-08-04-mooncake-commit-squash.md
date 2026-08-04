# Mooncake Commit Squash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Those sub-skills are unavailable in
> this session, so the explicitly authorized autonomous execution continues
> inline with the same checkpoints.

**Goal:** Rewrite the commits authored and committed by `jiahaoliang` on
`feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` into coherent
functional groups while keeping the final source tree byte-for-byte identical
to `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`.

**Architecture:** Keep the pinned integration parent
`a46a1dabbc260e8695002969f29528eb555eb583`, preserve original patch order, and
replace 16 consecutive commits with 8 commits whose trees are the exact trees
at selected original group endpoints. Protect the old tip with a local backup
ref, prove final tree identity by Git tree object and zero diff, then publish
only with `--force-with-lease` against the observed remote checkpoint.

**Tech Stack:** Git, Bash, pytest, Ruff, Python `py_compile`, Kubernetes CPU-only
UT Pod, JSON, Markdown, PowerShell workspace scripts or their documented Linux
equivalents.

## Global Constraints

- The source parent stays pinned to
  `a46a1dabbc260e8695002969f29528eb555eb583`; the fetched collaborator branch
  moved to `e4f2dd3e663c4d44b3c770f59424b83252df8608` and is outside this rewrite.
- The reference result is old source tip
  `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`, tree
  `ca363697034538b86626517066940315283ac8ad`.
- Preserve original patch order. Do not introduce source changes, conflict
  resolutions, merge commits, or §5.8 Mooncake multi-group behavior.
- Preserve local/origin `feature/mooncake-layerwise-kv-pool` at
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`.
- Preserve `repos/Mooncake`, all historical validation evidence, and user-owned
  untracked `deployment_yaml/` and `dockerfile.vllm23`.
- Every rewritten source commit must contain
  `Signed-off-by: jiahaoliang <gzliangjiahao@gmail.com>`.
- Runtime validation evidence for `d5f0ea7f8` remains historical and immutable.
  The rewritten tip may inherit that evidence only through exact tree identity;
  do not claim a new full NPU validation run.
- CPU/mock UT must use `liangjiahao/vllm-ascend-ut`, explicit namespace,
  tar synchronization, `PYTHONDONTWRITEBYTECODE=1`, and disabled pytest cache.
- Rewrite the source remote only with an exact old-SHA lease. Never force-push
  the protected original feature branch or collaborator refs.

---

## File Structure And Responsibilities

| File | Responsibility |
| --- | --- |
| `repos/vllm-ascend/.git/refs/heads/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | Rewritten source branch ref |
| `workspace.lock.json` | Machine-readable rewritten source tip |
| `features/kv-pool-layerwise-reuse/repo-state.md` | Current checkout, tree-equivalence, and validation boundary |
| `features/kv-pool-layerwise-reuse/sync-log.md` | Chronological rewrite and publication record |
| `features/kv-pool-layerwise-reuse/mooncake-commit-squash-report-2026-08-04.md` | Chinese reviewer report for all original and rewritten commits |
| `features/kv-pool-layerwise-reuse/implementation-plans/2026-08-04-mooncake-commit-squash.md` | Recoverable execution checklist |

## Target Commit Groups

| New order | New subject | Original inclusive range | Endpoint tree source |
| --- | --- | --- | --- |
| 1 | `feat(kv_pool): establish Mooncake layerwise range foundations` | `3676b98f1` + `7f8bdf290` + `baa547632` | `baa547632` |
| 2 | `feat(kv_pool): implement Mooncake ranged layer transfers` | `d6f6a2622` + `4f87dfb6b` + `88f850172` | `88f850172` |
| 3 | `feat(kv_pool): orchestrate Mooncake layerwise sessions` | `bcc2b916f` + `35d64610c` + `a2d654419` | `a2d654419` |
| 4 | `feat(kv_pool): add ranged transfer audit logging` | `4da8b2deb` | `4da8b2deb` |
| 5 | `fix(kv_pool): adapt renamed Mooncake session APIs` | `14beaf161` | `14beaf161` |
| 6 | `fix(kv_pool): isolate Mooncake ranged request failures` | `d28c52958` + `8d9897143` | `8d9897143` |
| 7 | `refactor(kv_pool): centralize ranged audit events` | `189dcdd2c` | `189dcdd2c` |
| 8 | `fix(kv_pool): align ranged performance validation contract` | `6451f9010` + `d5f0ea7f8` | `d5f0ea7f8` |

The single-commit groups are deliberately retained: audit introduction and
Mooncake Client API compatibility are independent reviewer decisions, while
audit centralization occurs later and depends on the intervening final code.

---

### Task 1: Audit And Freeze Rewrite Inputs

**Files:**
- Inspect: `repos/vllm-ascend/.git`
- Inspect: `workspace.lock.json`

**Interfaces:**
- Consumes: fetched local refs and the clean current checkout.
- Produces: exact base, old tip, remote checkpoint, tree hash, ownership range,
  protected-ref hashes, and eight immutable group endpoints.

- [x] **Step 1: Read workspace instructions and inspect both repository states**

Run `git status --short --branch`, `git remote -v`, `git worktree list`, and the
current feature records. Preserve the two existing untracked control paths.

- [x] **Step 2: Fetch origin, upstream, and collaborator**

Run `git fetch --all --prune`. Record that origin remains at `d5f0ea7f8` and
that collaborator moved independently from the pinned base.

- [x] **Step 3: Prove the ownership and scope boundary**

List `a46a1dabb..d5f0ea7f8` in chronological order with author, committer,
subject, body, changed paths, and stats. Require exactly 16 non-merge commits,
all owned by `jiahaoliang`.

### Task 2: Build The Eight-Commit History

**Files:**
- Modify: source target branch ref and index/worktree only

**Interfaces:**
- Consumes: the eight endpoint trees in `Target Commit Groups`.
- Produces: eight linear DCO-signed commits rooted directly at `a46a1dabb`.

- [x] **Step 1: Create a local recovery ref**

Create
`backup/mooncake-layerwise-kv-pool-merge-kv_offload_0723-pre-squash-d5f0ea7f8`
at the old tip and verify it resolves exactly to `d5f0ea7f8`.

- [x] **Step 2: Rebuild each group from its exact endpoint tree**

Detach at `a46a1dabb`. For each row in `Target Commit Groups`, load the named
endpoint tree into the clean index/worktree and create one `git commit -s` with
the specified subject and a body enumerating the folded original commits and
their behavior. Do not edit source files.

- [x] **Step 3: Move only the target local branch**

Point `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` to the eighth
new commit and switch the user-facing checkout back to that branch.

### Task 3: Prove Content And History Equivalence

**Files:**
- Inspect: rewritten source history and source tree

**Interfaces:**
- Consumes: old backup ref and rewritten source tip.
- Produces: exact content proof and reviewable history proof.

- [x] **Step 1: Verify exact final content**

Require both tips to resolve to tree `ca363697034538b86626517066940315283ac8ad`
and require `git diff --exit-code <backup>..HEAD` to return zero.

- [x] **Step 2: Verify history structure**

Require merge-base `a46a1dabb`, exactly 8 commits, no merge commits, exact
subject order, DCO on every commit, and a clean worktree.

- [x] **Step 3: Verify protected and excluded content**

Require protected local/origin hashes to stay at `b5b65d9bb`; confirm §5.8
prohibited symbols remain absent and `repos/Mooncake` remains unchanged.

### Task 4: Run Source Gates

**Files:**
- Test: `tests/ut/distributed/ascend_store`
- Test: `tests/ut/test_envs.py`
- Test: `tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py`

**Interfaces:**
- Consumes: the exact rewritten source tree.
- Produces: post-rewrite CPU/mock and static verification evidence.

- [x] **Step 1: Synchronize the source into the CPU-only UT Pod**

Use the feature runner or tar plus `kubectl exec -n liangjiahao`; verify the Pod
requests no NPU and no hostPath before running tests.

- [x] **Step 2: Run the CPU/mock collection**

Run AscendStore, env, and the performance test's unconfigured contract/skip
with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

- [x] **Step 3: Run static gates**

Run Ruff lint/format on the changed Python set, `py_compile` on production
Python files, `git diff --check`, and source history/DCO checks.

### Task 5: Publish Source With An Exact Lease

**Files:**
- Modify: `origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`

**Interfaces:**
- Consumes: verified rewritten tip and observed remote old tip `d5f0ea7f8`.
- Produces: remote source branch exactly equal to the rewritten local branch.

- [x] **Step 1: Recheck the live source remote**

Use `git ls-remote` and abort publication unless the target ref is still exactly
`d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`.

- [x] **Step 2: Force-push with the explicit old-SHA lease**

Push only the target ref using
`--force-with-lease=refs/heads/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723:d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873`.

- [x] **Step 3: Verify publication**

Require `git ls-remote` to equal local HEAD and
`git rev-list --left-right --count origin/<target>...HEAD` to return `0 0`.

### Task 6: Record And Publish The Control State

**Files:**
- Modify: `workspace.lock.json`
- Modify: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify: `features/kv-pool-layerwise-reuse/sync-log.md`
- Create: `features/kv-pool-layerwise-reuse/mooncake-commit-squash-report-2026-08-04.md`
- Modify: this plan's checkbox state

**Interfaces:**
- Consumes: final source SHA, all validation results, old/new commit mapping,
  and source publication evidence.
- Produces: complete Chinese reviewer report and a recoverable control state.

- [x] **Step 1: Write the detailed Chinese reviewer report**

Explain scope, grouping rationale, every original commit's behavior, each new
commit's final diff, dependency/order decisions, exact content proof, tests,
validation inheritance boundary, remote movement, and rollback ref.

- [x] **Step 2: Refresh workspace state**

Update the lock, repo state, and sync log without altering dated runtime
evidence or user-owned untracked files.

- [x] **Step 3: Run workspace gates**

Use `pwsh -File` for `lock-repos.ps1`, `status-all.ps1`, and
`validate-workspace.ps1` when available; otherwise run and record their Linux
equivalents. Also run JSON parsing and `git diff --check`.

- [x] **Step 4: Commit and normally push control metadata**

Stage only the plan, report, lock, repo state, and sync log. Commit with DCO,
fast-forward push `kv-pool-layerwise-reuse`, then verify live remote SHA and
left/right `0 0`.

## Self-Review

- [x] **Spec coverage:** The plan covers all 16 owned commits, functional
  squash grouping, exact `d5f0ea7f8` tree identity, Chinese report, source and
  control publication, tests, and protected refs.
- [x] **Placeholder scan:** No placeholder marker, deferred implementation
  step, or unspecified command target remains.
- [x] **Type consistency:** This is a history-only rewrite; endpoint SHA, branch,
  tree, ref, report, and state-file names are consistent throughout.
