#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
    printf 'Usage: %s [--merge]\n' "${0##*/}"
}

main() {
    local merge=false
    local root
    local workspace_branch
    local feature_root
    local repo_name
    local repo_path
    local mode
    local log_path
    local -a repos=(vllm vllm-ascend)

    while (($# > 0)); do
        case "$1" in
            --merge)
                merge=true
                shift
                ;;
            -h | --help)
                usage
                return 0
                ;;
            *)
                usage >&2
                return 2
                ;;
        esac
    done

    require_command git
    root=$(workspace_root)
    workspace_branch=$(git_output "$root" branch --show-current)
    if [[ $workspace_branch != kv_offload ]]; then
        die "Current workspace branch is $workspace_branch. Switch to kv_offload before running this script."
        return 1
    fi

    feature_root=$root/features/kv_offload
    if [[ ! -d $feature_root ]]; then
        die "features/kv_offload is missing. Switch to the kv_offload workspace branch before running this script."
        return 1
    fi

    # Complete all local safety checks before fetching or changing either repository.
    for repo_name in "${repos[@]}"; do
        repo_path=$(resolve_repo_path "$root" "repos/$repo_name")
        if ! is_git_repository "$repo_path"; then
            die "$repo_name is missing. Run ./scripts/bootstrap-repos.sh first."
            return 1
        fi
        assert_no_uncommitted_changes "$repo_path"
        if ! git_output "$repo_path" remote get-url collaborator >/dev/null 2>&1; then
            die "$repo_name has no collaborator remote."
            return 1
        fi
    done

    for repo_name in "${repos[@]}"; do
        repo_path=$(resolve_repo_path "$root" "repos/$repo_name")
        git_output "$repo_path" fetch collaborator --prune
        if ! git_output "$repo_path" show-ref --verify --quiet refs/remotes/collaborator/kv_offload; then
            die "$repo_name is missing collaborator/kv_offload after fetch."
            return 1
        fi
    done

    for repo_name in "${repos[@]}"; do
        repo_path=$(resolve_repo_path "$root" "repos/$repo_name")
        git_output "$repo_path" switch kv_offload
        if [[ $merge == true ]]; then
            git_output "$repo_path" merge --no-edit collaborator/kv_offload
        else
            git_output "$repo_path" rebase collaborator/kv_offload
        fi
    done

    if [[ $merge == true ]]; then
        mode=merge
    else
        mode=rebase
    fi
    log_path=$feature_root/sync-log.md
    {
        printf '\n## %s\n\n' "$(date +%Y-%m-%d)"
        printf -- '- Synced `repos/vllm` and `repos/vllm-ascend` from `collaborator/kv_offload` using %s.\n' "$mode"
        printf -- '- Run `./scripts/lock-repos.sh` after verifying and pushing source commits.\n'
    } >>"$log_path"

    printf 'kv_offload sync complete. Review, test, push source repos, then lock.\n'
}

main "$@"
