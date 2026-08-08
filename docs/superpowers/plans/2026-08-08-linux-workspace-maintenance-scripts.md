# Linux Workspace Maintenance Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide tested Linux-native maintenance commands for bootstrapping, locking, restoring, inspecting, validating, and synchronizing this workspace.

**Architecture:** Add Bash entry points beside the existing PowerShell scripts and centralize Git, lock-file, ref, remote, and path safety rules in `scripts/common.sh`. Parse and update `workspace.lock.json` with `jq`, write generated files through temporary files, and test behavior against disposable local Git repositories so validation never mutates the real nested source repositories.

**Tech Stack:** Bash 4+, Git 2.23+, jq 1.6+, GNU core utilities

## Global Constraints

- Implement and push public files on `main` before merging `main` into `kv-pool-layerwise-reuse`.
- Keep `/root/ljh/vllm-workspace` files, index, and existing untracked paths unchanged.
- Preserve the lock schema and ref contract: attached branch, `tag:<name>`, or `detached:<short-sha>`.
- Refuse destructive checkout operations when an existing nested repository is dirty.
- Resolve repository paths only below `repos/`; never write nested source into the control repository index.
- Use only local temporary Git repositories in automated tests; do not require GitHub or Kubernetes.

---

### Task 1: Shared Linux Maintenance Library and Status Command

**Files:**
- Create: `scripts/common.sh`
- Create: `scripts/status-all.sh`
- Create: `scripts/tests/test-linux-maintenance-scripts.sh`

**Interfaces:**
- Produces: `workspace_root`, `load_workspace_lock`, `validate_workspace_lock`, `repo_names`, `repo_field`, `repo_remote_entries`, `resolve_repo_path`, `git_ref_name`, `assert_no_uncommitted_changes`, `ensure_remote`, and `checkout_locked_commit` Bash functions.
- Produces: `status-all.sh` output fields `branch`, `head`, `lock`, `match`, and `dirty`; exits nonzero for missing repositories or lock mismatches.

- [ ] **Step 1: Write failing common/status tests**

Create a temporary control repository and nested repository. Assert that `git_ref_name` reports `main`, then `tag:v1.0.0`, then `detached:<short-sha>`, and that `status-all.sh` succeeds only when HEAD matches the lock.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh common status`

Expected: FAIL because `scripts/common.sh` and `scripts/status-all.sh` do not exist.

- [ ] **Step 3: Implement shared functions and status reporting**

Use `git -C`, `jq -e`, exact `refs/heads/<branch>` checks, and a `repos/*` path guard. Validate all required lock fields before any mutating command consumes them.

- [ ] **Step 4: Run the focused test**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh common status`

Expected: PASS with attached, tagged-detached, untagged-detached, matching, and mismatching cases covered.

### Task 2: Lock, Restore, and Bootstrap Commands

**Files:**
- Create: `scripts/lock-repos.sh`
- Create: `scripts/restore-repos.sh`
- Create: `scripts/bootstrap-repos.sh`
- Modify: `scripts/tests/test-linux-maintenance-scripts.sh`

**Interfaces:**
- `lock-repos.sh` consumes the current control branch and nested repository state; atomically updates `workspace.lock.json` and, on feature branches, the resolved `features/<feature>/repo-state.md`.
- `restore-repos.sh` consumes exact commits and remotes from the lock; clones missing repositories and restores clean repositories to the exact locked commit.
- `bootstrap-repos.sh` consumes the same lock and delegates exact reconstruction to the restore path, making a fresh Linux clone immediately reproducible.

- [ ] **Step 1: Add failing lock/restore/bootstrap tests**

Use local bare remotes. Assert exact clone restoration, branch/tag/detached handling, remote URL correction, dirty-worktree rejection without data loss, lock JSON updates, longest hyphen-boundary feature-directory resolution, and unresolved-feature rejection before writes.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh lock restore bootstrap`

Expected: FAIL because the three entry points do not exist.

- [ ] **Step 3: Implement exact and guarded maintenance behavior**

Fetch all configured remotes, treat the lock commit as authoritative, retain a branch only when it contains that commit, otherwise use detached HEAD, and generate lock/state files through `mktemp` files cleaned by traps.

- [ ] **Step 4: Run the focused test**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh lock restore bootstrap`

Expected: PASS and the fixture's intentional dirty file remains unchanged.

### Task 3: Validation and Feature Synchronization Commands

**Files:**
- Create: `scripts/validate-workspace.sh`
- Create: `scripts/sync-kv-offload.sh`
- Modify: `scripts/validate-workspace.ps1`
- Modify: `scripts/tests/test-linux-maintenance-scripts.sh`

**Interfaces:**
- `validate-workspace.sh [--root <path>]` validates required public files, `.gitignore`, feature metadata, snapshot headers, and lock schema.
- `sync-kv-offload.sh [--merge]` requires the `kv_offload` control branch, clean `vllm` and `vllm-ascend` repositories, and explicit collaborator fetch before rebase or merge; it appends the matching sync log entry only after both repositories succeed.

- [ ] **Step 1: Add failing validation and sync guard tests**

Assert real-main validation, invalid lock rejection, `--root` parsing, wrong-branch sync rejection, and `--merge`/unknown-option argument behavior.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh validate sync`

Expected: FAIL because the Linux entry points do not exist.

- [ ] **Step 3: Implement validators and sync command**

Keep error accumulation in the validator, require both `.ps1` and `.sh` public entry points, and preserve the existing collaborator branch and sync-log contract.

- [ ] **Step 4: Run the focused test**

Run: `bash scripts/tests/test-linux-maintenance-scripts.sh validate sync`

Expected: PASS.

### Task 4: Linux Documentation and Full Main Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/workspace-guide.md`
- Modify: `docs/git-workflow.md`

**Interfaces:**
- Produces: Linux-first command examples plus explicit Bash/Git/jq dependencies, while retaining PowerShell alternatives.

- [ ] **Step 1: Document Linux setup, maintenance, and recovery commands**

Use `./scripts/<command>.sh` in Linux examples and retain `.\\scripts\\<command>.ps1` under a separate PowerShell heading.

- [ ] **Step 2: Run all verification gates**

Run:

```bash
bash -n scripts/*.sh scripts/tests/*.sh
bash scripts/tests/test-linux-maintenance-scripts.sh
./scripts/validate-workspace.sh
git diff --check
git status --short
```

Expected: all commands exit 0 and only planned public files are modified or added.

- [ ] **Step 3: Review executable modes and diff**

Run: `git diff --summary && git diff --stat && git diff`

Expected: every entry point and test is mode `100755`; `common.sh` is not required to be directly executed; no `repos/*` content is tracked.

- [ ] **Step 4: Commit and push main**

Run:

```bash
git add AGENTS.md README.md docs scripts
git commit -s -m "feat: add Linux workspace maintenance scripts"
git push origin main
```

Expected: `origin/main` points to the signed-off implementation commit.

### Task 5: Merge Main into the Current Feature Without Touching Its Checkout

**Files:**
- Merge: `main` into a temporary branch based on `kv-pool-layerwise-reuse`

**Interfaces:**
- Consumes: published `origin/main` and the exact pre-merge feature SHA.
- Produces: a merge commit pushed to `origin/kv-pool-layerwise-reuse` with an exact `--force-with-lease` guard only if a normal fast-forward push is not sufficient.

- [ ] **Step 1: Create an independent merge worktree**

Create `/root/ljh/vllm-workspace-linux-maintenance-merge` on a temporary local branch based on the exact feature SHA, then merge `main` with a non-interactive merge commit.

- [ ] **Step 2: Verify the merged feature tree**

Run Bash syntax tests, the full local integration test, `validate-workspace.sh`, `git diff --check HEAD^1..HEAD`, and confirm feature-specific lock and documents remain present.

- [ ] **Step 3: Push the merge result with remote identity protection**

Push the temporary merge branch to `refs/heads/kv-pool-layerwise-reuse`, guarded by the exact remote SHA observed before implementation.

- [ ] **Step 4: Audit the original checkout**

Compare its HEAD, porcelain status, index diff, and untracked paths to the captured baseline. Expected: HEAD stays `972a3b78ce69af18eb508f55d7727ef509862011`; only the tracking status changes to report the newly published remote commit.
