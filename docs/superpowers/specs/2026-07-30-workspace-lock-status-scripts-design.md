# Workspace Lock and Status Script Compatibility Design

Date: 2026-07-30
Status: Approved

## Context

`scripts/lock-repos.ps1` and `scripts/status-all.ps1` share
`Get-GitRefName` from `scripts/common.ps1`. The helper currently calls
`git describe --tags --exact-match HEAD` through a wrapper that throws on every
nonzero exit code. An untagged detached checkout is therefore treated as an
error before the intended `detached:<short-sha>` fallback can run.

`lock-repos.ps1` also assumes that the workspace branch maps directly to
`features/<branch>/repo-state.md`. Branches such as
`kv-pool-layerwise-reuse-redesign` intentionally reuse
`features/kv-pool-layerwise-reuse`, so the script fails after collecting repo
state.

## Goals

- Preserve the existing ref-name contract:
  attached branch, then `tag:<name>`, then `detached:<short-sha>`.
- Make untagged detached repositories a normal supported state.
- Let renamed feature branches reuse an existing feature directory without
  changing the normal no-argument command.
- Reject an unresolved feature directory before writing the lock or state file.
- Cover the behavior with PowerShell regression tests.

## Non-Goals

- Do not change `workspace.lock.json` schema.
- Do not change restore behavior or Git branch creation.
- Do not infer a feature directory from Git history, changed files, or arbitrary
  substring matches.
- Do not change public workspace validation rules in this work.

## Design

### Git Ref Resolution

`Get-GitRefName` keeps its existing precedence:

1. Return `git branch --show-current` when nonempty.
2. Query exact tags with `git tag --points-at HEAD --sort=-version:refname`.
   This command exits successfully when no tags exist. If several tags point to
   the commit, use the first nonempty result so selection is deterministic.
3. Return `detached:<short-sha>` from `git rev-parse --short HEAD`.

Both `lock-repos.ps1` and `status-all.ps1` continue using the shared helper, so
the ref fix is implemented once.

### Feature Directory Resolution

Keep the fallback local to `lock-repos.ps1`. For a non-main workspace branch,
resolution order is:

1. An exact `features/<workspace-branch>` directory.
2. The longest existing feature directory name that is a hyphen-boundary prefix
   of the branch. For example,
   `kv-pool-layerwise-reuse-redesign` resolves to
   `features/kv-pool-layerwise-reuse`.

If no directory resolves, fail before writing either output file. The generated
state heading uses the resolved feature name, while the source-repo branch
values continue to come from `Get-GitRefName`.

On `main`, `lock-repos.ps1` continues updating only `workspace.lock.json`.

### Failure Behavior

- Git failures other than "no exact tag" remain fatal.
- The inferred feature directory must already exist.
- No fallback creates a new feature directory implicitly.

## Tests

Use the existing workspace as the regression test after merging the public
change into `kv-pool-layerwise-reuse-redesign`:

```powershell
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
```

Verify that vLLM is reported as `detached:d02df748b`, all three repo HEADs match
the lock, and `features/kv-pool-layerwise-reuse/repo-state.md` is refreshed.
A temporary Git repository smoke also covers attached, tagged detached, and
untagged detached ref formatting without adding a new test framework.

## Delivery

Implement and push the public script and test changes on `main`, then merge
`main` into `kv-pool-layerwise-reuse-redesign`, run the integration checks, and
push the feature branch. Existing untracked feature research snapshots remain
outside both commits.
