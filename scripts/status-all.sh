#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

main() {
    local root
    local lock_path
    local repo_name
    local relative_path
    local repo_path
    local branch
    local head
    local lock_commit
    local dirty
    local matches_lock
    local result=0

    require_no_args "${0##*/}" "$@"
    require_command git
    require_command jq
    root=$(workspace_root)
    lock_path=$(load_workspace_lock "$root")
    validate_workspace_lock "$lock_path"

    while IFS= read -r repo_name; do
        relative_path=$(repo_field "$lock_path" "$repo_name" path)
        repo_path=$(resolve_repo_path "$root" "$relative_path")

        printf '\n[%s] %s\n' "$repo_name" "$relative_path"
        if ! is_git_repository "$repo_path"; then
            printf '  missing\n'
            result=1
            continue
        fi

        branch=$(git_ref_name "$repo_path")
        head=$(git_output "$repo_path" rev-parse HEAD)
        lock_commit=$(repo_field "$lock_path" "$repo_name" commit)
        if [[ -n $(git_output "$repo_path" status --porcelain) ]]; then
            dirty=true
        else
            dirty=false
        fi
        if [[ -n $lock_commit && $head == "$lock_commit" ]]; then
            matches_lock=true
        else
            matches_lock=false
            result=1
        fi

        printf '  branch: %s\n' "$branch"
        printf '  head:   %s\n' "$head"
        printf '  lock:   %s\n' "$lock_commit"
        printf '  match:  %s\n' "$matches_lock"
        printf '  dirty:  %s\n' "$dirty"
    done < <(repo_names "$lock_path")

    return "$result"
}

main "$@"
