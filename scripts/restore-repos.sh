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
    local origin_url
    local remote_name
    local remote_url
    local locked_ref
    local commit
    local operation=${WORKSPACE_OPERATION:-Restore}

    require_no_args "${0##*/}" "$@"
    require_command git
    require_command jq
    root=$(workspace_root)
    lock_path=$(load_workspace_lock "$root")
    validate_workspace_lock "$lock_path"

    while IFS= read -r repo_name; do
        relative_path=$(repo_field "$lock_path" "$repo_name" path)
        repo_path=$(resolve_repo_path "$root" "$relative_path")
        origin_url=$(repo_field "$lock_path" "$repo_name" remotes | jq -er '.origin')

        if [[ ! -e $repo_path ]]; then
            mkdir -p -- "$(dirname -- "$repo_path")"
            printf 'Cloning %s from %s\n' "$repo_name" "$origin_url"
            git clone -- "$origin_url" "$repo_path"
        elif ! is_git_repository "$repo_path"; then
            die "$repo_path exists but is not a Git repository."
            return 1
        fi

        assert_no_uncommitted_changes "$repo_path"
        while IFS=$'\t' read -r remote_name remote_url; do
            ensure_remote "$repo_path" "$remote_name" "$remote_url"
        done < <(repo_remote_entries "$lock_path" "$repo_name")

        fetch_all_remotes "$repo_path"
        locked_ref=$(repo_field "$lock_path" "$repo_name" branch)
        commit=$(repo_field "$lock_path" "$repo_name" commit)
        checkout_locked_commit "$repo_path" "$locked_ref" "$commit"
    done < <(repo_names "$lock_path")

    printf '%s complete.\n' "$operation"
}

main "$@"
