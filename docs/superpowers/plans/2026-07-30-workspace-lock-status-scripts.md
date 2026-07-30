# Workspace Lock and Status Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `lock-repos.ps1` and `status-all.ps1` handle untagged detached repos and renamed feature branches in the current workspace.

**Architecture:** Keep Git ref formatting in `scripts/common.ps1`. Add only a local exact-or-longest-prefix directory fallback in `scripts/lock-repos.ps1`, then validate with temporary Git states and the real feature workspace.

**Tech Stack:** Windows PowerShell 5, Git, existing workspace scripts

## Global Constraints

- Public changes are committed and pushed on `main`, then merged into `kv-pool-layerwise-reuse-redesign`.
- Preserve `branch`, `tag:<name>`, and `detached:<short-sha>` output formats.
- Do not stage existing untracked feature research snapshots.

---

### Task 1: Fix Ref and Feature Resolution

**Files:**
- Modify: `scripts/common.ps1`
- Modify: `scripts/lock-repos.ps1`

**Interfaces:**
- Consumes: existing `Get-GitOutput -RepoPath <path> -GitArgs <args>`
- Produces: unchanged `Get-GitRefName -RepoPath <path>` contract and automatic repo-state path selection

- [ ] **Step 1: Confirm the existing red behavior**

Run `scripts/status-all.ps1` with vLLM detached at `d02df748b`.

Expected: failure from `git describe --tags --exact-match HEAD`.

- [ ] **Step 2: Make exact-tag lookup non-throwing**

Replace the `git describe` probe with:

```powershell
$tags = Get-GitOutput -RepoPath $RepoPath -GitArgs @(
    "tag", "--points-at", "HEAD", "--sort=-version:refname"
)
$tag = @($tags -split "\r?\n" | Where-Object { $_ })[0]
if ($tag) {
    return "tag:$tag"
}
```

- [ ] **Step 3: Add the local feature-directory fallback**

Before constructing or writing state, resolve the exact feature directory. If
it does not exist, select the longest directory whose name plus `-` prefixes the
workspace branch. Fail when no candidate exists.

- [ ] **Step 4: Run static checks**

Run:

```powershell
git diff --check
```

Expected: exit code 0.

- [ ] **Step 5: Commit and push main**

```powershell
git add scripts/common.ps1 scripts/lock-repos.ps1 docs/superpowers
git commit -m "fix: support detached and renamed workspace refs"
git push origin main
```

### Task 2: Merge and Verify the Real Workspace

**Files:**
- Update: `workspace.lock.json`
- Update: `features/kv-pool-layerwise-reuse/repo-state.md`

**Interfaces:**
- Consumes: fixed public scripts from Task 1
- Produces: lock and repo-state matching all three nested repo HEADs

- [ ] **Step 1: Merge main into the feature branch**

```powershell
git switch kv-pool-layerwise-reuse-redesign
git merge main
```

- [ ] **Step 2: Run integration commands**

```powershell
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
```

Expected: vLLM is `detached:d02df748b`; vLLM, vLLM-Ascend, and Mooncake all
show `match: True`.

- [ ] **Step 3: Commit and push feature state**

Stage only the public merge and generated workspace state, then push
`kv-pool-layerwise-reuse-redesign`.

### Task 3: Fold the Mooncake Session API Commit

**Files:**
- Rewrite: `repos/vllm-ascend` branch `feature/mooncake-layerwise-redesign`

**Interfaces:**
- Consumes: rebased feature history rooted at `upstream/main` `b2f683ca3`
- Produces: the session API adaptation folded into `feat(kv_pool): define Mooncake layerwise backend contract`

- [ ] **Step 1: Rewrite the source history**

Move `fix(kv_pool): adapt renamed Mooncake session APIs` next to the backend
contract commit and mark it as `fixup`, preserving all later patches.

- [ ] **Step 2: Verify source behavior**

Run the isolated `tests/ut/distributed/ascend_store` CPU/mock suite, Python
compilation, and `git diff --check`.

Expected: the complete suite passes and the final tree matches the pre-rewrite
tree.

- [ ] **Step 3: Push and refresh workspace state**

Force-push with an exact lease, rerun `lock-repos.ps1` and `status-all.ps1`, then
commit and push the refreshed feature state.
