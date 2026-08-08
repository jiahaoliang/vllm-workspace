#!/usr/bin/env bash

set -Eeuo pipefail

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
SOURCE_ROOT=$(cd -- "$TEST_DIR/../.." && pwd -P)
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/vllm-workspace-linux-tests.XXXXXX")
trap 'rm -rf -- "$TMP_ROOT"' EXIT

export GIT_AUTHOR_NAME="Workspace Script Test"
export GIT_AUTHOR_EMAIL="workspace-script-test@example.com"
export GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
export GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL

REQUESTED_GROUPS=("$@")
PASSED=0

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

assert_eq() {
    local expected=$1
    local actual=$2
    local message=$3
    [[ $actual == "$expected" ]] || fail "$message: expected '$expected', got '$actual'"
}

assert_contains() {
    local haystack=$1
    local needle=$2
    local message=$3
    [[ $haystack == *"$needle"* ]] || fail "$message: missing '$needle'"
}

should_run() {
    local group=$1
    local requested

    ((${#REQUESTED_GROUPS[@]} == 0)) && return 0
    for requested in "${REQUESTED_GROUPS[@]}"; do
        [[ $requested == "$group" ]] && return 0
    done
    return 1
}

run_test() {
    local group=$1
    local name=$2
    local function_name=$3

    should_run "$group" || return 0
    "$function_name"
    PASSED=$((PASSED + 1))
    printf 'ok %d - %s (%s)\n' "$PASSED" "$name" "$group"
}

init_git_repo() {
    local path=$1
    local branch=${2:-main}

    git init -q -b "$branch" "$path"
    git -C "$path" config user.name "$GIT_AUTHOR_NAME"
    git -C "$path" config user.email "$GIT_AUTHOR_EMAIL"
}

commit_file() {
    local repo=$1
    local relative_path=$2
    local content=$3
    local message=${4:-"test commit"}

    mkdir -p -- "$(dirname -- "$repo/$relative_path")"
    printf '%s\n' "$content" >"$repo/$relative_path"
    git -C "$repo" add -- "$relative_path"
    git -C "$repo" commit -q -m "$message"
    git -C "$repo" rev-parse HEAD
}

copy_linux_scripts() {
    local root=$1
    local script

    mkdir -p -- "$root/scripts/tests"
    for script in common.sh bootstrap-repos.sh lock-repos.sh restore-repos.sh status-all.sh sync-kv-offload.sh validate-workspace.sh; do
        if [[ -f $SOURCE_ROOT/scripts/$script ]]; then
            cp -- "$SOURCE_ROOT/scripts/$script" "$root/scripts/$script"
        fi
    done
    chmod +x "$root"/scripts/*.sh 2>/dev/null || true
}

init_control_root() {
    local root=$1
    local branch=${2:-main}

    init_git_repo "$root" "$branch"
    printf 'repos/*\n!repos/.gitkeep\n' >"$root/.gitignore"
    mkdir -p -- "$root/repos"
    touch "$root/repos/.gitkeep"
    git -C "$root" add .gitignore repos/.gitkeep
    git -C "$root" commit -q -m "initialize fixture"
    copy_linux_scripts "$root"
}

write_single_repo_lock() {
    local root=$1
    local name=$2
    local path=$3
    local remote_url=$4
    local branch=$5
    local commit=$6

    jq -n \
        --arg name "$name" \
        --arg path "$path" \
        --arg remote "$remote_url" \
        --arg branch "$branch" \
        --arg commit "$commit" \
        '{
            version: 1,
            updated_at: "2026-01-01T00:00:00+00:00",
            repos: {
                ($name): {
                    path: $path,
                    remotes: {origin: $remote},
                    branch: $branch,
                    commit: $commit,
                    purpose: "fixture repository"
                }
            }
        }' >"$root/workspace.lock.json"
}

create_bare_remote() {
    local base=$1
    local name=$2
    local branch=${3:-main}
    local remote=$base/$name.git
    local seed=$base/$name-seed
    local commit

    git init -q --bare "$remote"
    init_git_repo "$seed" "$branch"
    commit=$(commit_file "$seed" README.md "initial $name" "initial commit")
    git -C "$seed" remote add origin "$remote"
    git -C "$seed" push -q -u origin "$branch"
    git -C "$remote" symbolic-ref HEAD "refs/heads/$branch"
    printf '%s\t%s\t%s\n' "$remote" "$seed" "$commit"
}

test_common_ref_and_path_contract() {
    local repo=$TMP_ROOT/common-repo
    local commit
    local short

    [[ -f $SOURCE_ROOT/scripts/common.sh ]] || fail "scripts/common.sh does not exist"
    # shellcheck source=../common.sh
    source "$SOURCE_ROOT/scripts/common.sh"

    init_git_repo "$repo" main
    commit=$(commit_file "$repo" tracked.txt one)
    assert_eq main "$(git_ref_name "$repo")" "attached branch ref"

    git -C "$repo" tag v1.0.0 "$commit"
    git -C "$repo" switch -q --detach "$commit"
    assert_eq tag:v1.0.0 "$(git_ref_name "$repo")" "tagged detached ref"

    git -C "$repo" tag -d v1.0.0 >/dev/null
    short=$(git -C "$repo" rev-parse --short HEAD)
    assert_eq "detached:$short" "$(git_ref_name "$repo")" "untagged detached ref"

    if resolve_repo_path "$TMP_ROOT" "repos/../outside" >/dev/null 2>&1; then
        fail "resolve_repo_path accepted a parent traversal"
    fi
    mkdir -p -- "$TMP_ROOT/repos" "$TMP_ROOT/outside"
    ln -s -- "$TMP_ROOT/outside" "$TMP_ROOT/repos/escape"
    if resolve_repo_path "$TMP_ROOT" "repos/escape/repository" >/dev/null 2>&1; then
        fail "resolve_repo_path accepted a symlink escape"
    fi
    assert_eq "$TMP_ROOT/repos/vllm" "$(resolve_repo_path "$TMP_ROOT" repos/vllm)" "safe repo path"
}

test_status_match_and_mismatch() {
    local root=$TMP_ROOT/status-root
    local repo=$root/repos/demo
    local commit
    local output

    init_control_root "$root"
    init_git_repo "$repo" main
    commit=$(commit_file "$repo" data.txt locked)
    write_single_repo_lock "$root" demo repos/demo unused main "$commit"

    output=$("$root/scripts/status-all.sh") || fail "status failed for matching lock"
    assert_contains "$output" "match:  true" "matching status"

    commit_file "$repo" data.txt newer >/dev/null
    if output=$("$root/scripts/status-all.sh" 2>&1); then
        fail "status succeeded for mismatching HEAD"
    fi
    assert_contains "$output" "match:  false" "mismatching status"

    git -C "$repo" reset -q --hard "$commit"
    printf 'dirty\n' >"$repo/untracked.txt"
    output=$("$root/scripts/status-all.sh") || fail "dirty matching repo should still report status"
    assert_contains "$output" "dirty:  true" "dirty status"
}

test_restore_and_bootstrap_exact_state() {
    local remote_data
    local remote
    local seed
    local commit
    local root=$TMP_ROOT/restore-root
    local output

    remote_data=$(create_bare_remote "$TMP_ROOT" restore-demo)
    IFS=$'\t' read -r remote seed commit <<<"$remote_data"

    init_control_root "$root"
    write_single_repo_lock "$root" demo repos/demo "$remote" main "$commit"
    "$root/scripts/restore-repos.sh" >/dev/null
    assert_eq "$commit" "$(git -C "$root/repos/demo" rev-parse HEAD)" "restored commit"
    assert_eq main "$(git -C "$root/repos/demo" branch --show-current)" "restored branch"

    git -C "$root/repos/demo" tag v1.0.0 "$commit"
    jq '.repos.demo.branch = "tag:v1.0.0"' "$root/workspace.lock.json" >"$root/tag-lock.json"
    mv -- "$root/tag-lock.json" "$root/workspace.lock.json"
    "$root/scripts/restore-repos.sh" >/dev/null
    assert_eq '' "$(git -C "$root/repos/demo" branch --show-current)" "tag restore is detached"
    assert_eq v1.0.0 "$(git -C "$root/repos/demo" tag --points-at HEAD)" "restored tag"

    git -C "$root/repos/demo" tag -d v1.0.0 >/dev/null
    jq --arg ref "detached:${commit:0:9}" '.repos.demo.branch = $ref' \
        "$root/workspace.lock.json" >"$root/detached-lock.json"
    mv -- "$root/detached-lock.json" "$root/workspace.lock.json"
    "$root/scripts/restore-repos.sh" >/dev/null
    assert_eq '' "$(git -C "$root/repos/demo" branch --show-current)" "detached restore"

    jq '.repos.demo.branch = "main"' "$root/workspace.lock.json" >"$root/main-lock.json"
    mv -- "$root/main-lock.json" "$root/workspace.lock.json"
    "$root/scripts/restore-repos.sh" >/dev/null
    git -C "$root/repos/demo" remote set-url origin "$TMP_ROOT/wrong.git"
    "$root/scripts/restore-repos.sh" >/dev/null
    assert_eq "$remote" "$(git -C "$root/repos/demo" remote get-url origin)" "corrected remote"

    printf 'preserve me\n' >"$root/repos/demo/untracked.txt"
    if output=$("$root/scripts/restore-repos.sh" 2>&1); then
        fail "restore succeeded with a dirty repository"
    fi
    assert_contains "$output" "uncommitted changes" "dirty restore rejection"
    assert_eq "preserve me" "$(<"$root/repos/demo/untracked.txt")" "dirty file preservation"

}

test_bootstrap_exact_state() {
    local remote_data
    local remote
    local seed
    local commit
    local root=$TMP_ROOT/bootstrap-root

    remote_data=$(create_bare_remote "$TMP_ROOT" bootstrap-demo)
    IFS=$'\t' read -r remote seed commit <<<"$remote_data"

    init_control_root "$root"
    write_single_repo_lock "$root" demo repos/demo "$remote" main "$commit"
    "$root/scripts/bootstrap-repos.sh" >/dev/null
    assert_eq "$commit" "$(git -C "$root/repos/demo" rev-parse HEAD)" "bootstrapped commit"
}

test_lock_feature_state_and_preflight() {
    local root=$TMP_ROOT/lock-root
    local repo=$root/repos/demo
    local commit
    local output
    local before
    local after

    init_control_root "$root" kv-pool-layerwise-reuse-redesign
    mkdir -p -- "$root/features/kv-pool-layerwise-reuse"
    init_git_repo "$repo" main
    commit=$(commit_file "$repo" state.txt current)
    write_single_repo_lock "$root" demo repos/demo unused old "$commit"

    output=$("$root/scripts/lock-repos.sh") || fail "lock command failed: $output"
    assert_eq main "$(jq -r '.repos.demo.branch' "$root/workspace.lock.json")" "locked branch"
    assert_eq "$commit" "$(jq -r '.repos.demo.commit' "$root/workspace.lock.json")" "locked commit"
    assert_contains "$(<"$root/features/kv-pool-layerwise-reuse/repo-state.md")" \
        "# kv-pool-layerwise-reuse Repo State" "feature state heading"

    git -C "$root" switch -q -c unrelated-feature
    before=$(sha256sum "$root/workspace.lock.json" | awk '{print $1}')
    if output=$("$root/scripts/lock-repos.sh" 2>&1); then
        fail "lock succeeded without a resolvable feature directory"
    fi
    after=$(sha256sum "$root/workspace.lock.json" | awk '{print $1}')
    assert_eq "$before" "$after" "lock preflight preserves lock file"
    assert_contains "$output" "Missing feature directory" "missing feature error"
}

create_validation_fixture() {
    local root=$1
    local file
    local dummy_commit=1111111111111111111111111111111111111111

    mkdir -p -- "$root/docs" "$root/scripts/tests"
    cp -- "$SOURCE_ROOT/AGENTS.md" "$SOURCE_ROOT/README.md" "$SOURCE_ROOT/.gitignore" "$root/"
    cp -- "$SOURCE_ROOT/docs/workspace-guide.md" "$SOURCE_ROOT/docs/git-workflow.md" \
        "$SOURCE_ROOT/docs/repo-map.md" "$root/docs/"
    for file in "$SOURCE_ROOT"/scripts/*.ps1 "$SOURCE_ROOT"/scripts/*.sh; do
        cp -- "$file" "$root/scripts/"
    done
    cp -- "$SOURCE_ROOT/scripts/tests/test-linux-maintenance-scripts.sh" "$root/scripts/tests/"
    chmod +x "$root"/scripts/*.sh "$root"/scripts/tests/*.sh

    jq -n --arg commit "$dummy_commit" '{
        version: 1,
        updated_at: "2026-01-01T00:00:00+00:00",
        repos: {
            vllm: {path: "repos/vllm", remotes: {origin: "https://example.com/vllm.git"}, branch: "main", commit: $commit, purpose: "fixture"},
            "vllm-ascend": {path: "repos/vllm-ascend", remotes: {origin: "https://example.com/vllm-ascend.git"}, branch: "main", commit: $commit, purpose: "fixture"},
            Mooncake: {path: "repos/Mooncake", remotes: {origin: "https://example.com/Mooncake.git"}, branch: "main", commit: $commit, purpose: "fixture"}
        }
    }' >"$root/workspace.lock.json"
}

test_validate_workspace() {
    local root=$TMP_ROOT/validate-root
    local output

    [[ -x $SOURCE_ROOT/scripts/validate-workspace.sh ]] || fail "validate-workspace.sh is not executable"
    "$SOURCE_ROOT/scripts/validate-workspace.sh" >/dev/null

    create_validation_fixture "$root"
    "$root/scripts/validate-workspace.sh" --root "$root" >/dev/null

    jq 'del(.repos.vllm.commit)' "$root/workspace.lock.json" >"$root/invalid.json"
    mv -- "$root/invalid.json" "$root/workspace.lock.json"
    if output=$("$root/scripts/validate-workspace.sh" --root "$root" 2>&1); then
        fail "validator accepted a lock with a missing commit"
    fi
    assert_contains "$output" "Invalid workspace.lock.json" "invalid lock error"

    if "$root/scripts/validate-workspace.sh" --unknown >/dev/null 2>&1; then
        fail "validator accepted an unknown option"
    fi
}

create_sync_repo() {
    local root=$1
    local name=$2
    local remote=$TMP_ROOT/sync-$name.git
    local seed=$TMP_ROOT/sync-$name-seed
    local repo=$root/repos/$name

    git init -q --bare "$remote"
    init_git_repo "$seed" kv_offload
    commit_file "$seed" data.txt base >/dev/null
    git -C "$seed" remote add collaborator "$remote"
    git -C "$seed" push -q -u collaborator kv_offload

    init_git_repo "$repo" kv_offload
    git -C "$repo" remote add collaborator "$remote"
    git -C "$repo" fetch -q collaborator kv_offload
    git -C "$repo" reset -q --hard collaborator/kv_offload

    commit_file "$seed" data.txt updated >/dev/null
    git -C "$seed" push -q collaborator kv_offload
    printf '%s\n' "$seed"
}

test_sync_guards_and_local_remotes() {
    local wrong_root=$TMP_ROOT/sync-wrong-root
    local root=$TMP_ROOT/sync-root
    local vllm_seed
    local ascend_seed
    local output

    init_control_root "$wrong_root" main
    mkdir -p -- "$wrong_root/features/kv_offload"
    if output=$("$wrong_root/scripts/sync-kv-offload.sh" 2>&1); then
        fail "sync succeeded on the wrong control branch"
    fi
    assert_contains "$output" "Switch to kv_offload" "wrong branch guard"

    init_control_root "$root" kv_offload
    mkdir -p -- "$root/features/kv_offload"
    printf '# Sync Log\n' >"$root/features/kv_offload/sync-log.md"
    vllm_seed=$(create_sync_repo "$root" vllm)
    ascend_seed=$(create_sync_repo "$root" vllm-ascend)

    printf 'dirty\n' >"$root/repos/vllm-ascend/untracked.txt"
    if "$root/scripts/sync-kv-offload.sh" >/dev/null 2>&1; then
        fail "sync succeeded with a dirty source repository"
    fi
    rm -- "$root/repos/vllm-ascend/untracked.txt"

    "$root/scripts/sync-kv-offload.sh" >/dev/null
    assert_eq "$(git -C "$vllm_seed" rev-parse HEAD)" \
        "$(git -C "$root/repos/vllm" rev-parse HEAD)" "vllm rebase sync"
    assert_eq "$(git -C "$ascend_seed" rev-parse HEAD)" \
        "$(git -C "$root/repos/vllm-ascend" rev-parse HEAD)" "vllm-ascend rebase sync"
    assert_contains "$(<"$root/features/kv_offload/sync-log.md")" "using rebase" "rebase sync log"

    "$root/scripts/sync-kv-offload.sh" --merge >/dev/null
    assert_contains "$(<"$root/features/kv_offload/sync-log.md")" "using merge" "merge sync log"

    if "$root/scripts/sync-kv-offload.sh" --unknown >/dev/null 2>&1; then
        fail "sync accepted an unknown option"
    fi
}

run_test common "ref and path contract" test_common_ref_and_path_contract
run_test status "status match and mismatch" test_status_match_and_mismatch
run_test restore "restore exact state and dirty guard" test_restore_and_bootstrap_exact_state
run_test bootstrap "bootstrap exact state" test_bootstrap_exact_state
run_test lock "lock feature state and preflight" test_lock_feature_state_and_preflight
run_test validate "workspace validation" test_validate_workspace
run_test sync "sync guards and local remotes" test_sync_guards_and_local_remotes

printf 'PASS: %d Linux maintenance script test(s)\n' "$PASSED"
