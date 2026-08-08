#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

FAILED=0

usage() {
    printf 'Usage: %s [--root PATH]\n' "${0##*/}"
}

fail_check() {
    printf 'error: %s\n' "$*" >&2
    FAILED=1
}

require_path() {
    local root=$1
    local relative_path=$2

    [[ -e $root/$relative_path ]] || fail_check "Missing required path: $relative_path"
}

require_executable() {
    local root=$1
    local relative_path=$2

    [[ -x $root/$relative_path ]] || fail_check "Required script is not executable: $relative_path"
}

require_text() {
    local root=$1
    local relative_path=$2
    local pattern=$3
    local description=$4

    if [[ ! -f $root/$relative_path ]]; then
        fail_check "Missing file for text check: $relative_path"
        return
    fi
    grep -Eq -- "$pattern" "$root/$relative_path" || \
        fail_check "$relative_path does not contain expected text: $description"
}

main() {
    local root
    local lock_path
    local relative_path
    local feature
    local feature_name
    local tracked_feature_files
    local snapshot
    local repo_name
    local repo_path
    local -a required_paths=(
        AGENTS.md
        README.md
        .gitignore
        workspace.lock.json
        docs/workspace-guide.md
        docs/git-workflow.md
        docs/repo-map.md
        scripts/common.ps1
        scripts/bootstrap-repos.ps1
        scripts/lock-repos.ps1
        scripts/restore-repos.ps1
        scripts/status-all.ps1
        scripts/sync-kv-offload.ps1
        scripts/validate-workspace.ps1
        scripts/common.sh
        scripts/bootstrap-repos.sh
        scripts/lock-repos.sh
        scripts/restore-repos.sh
        scripts/status-all.sh
        scripts/sync-kv-offload.sh
        scripts/validate-workspace.sh
        scripts/tests/test-linux-maintenance-scripts.sh
    )
    local -a executable_paths=(
        scripts/bootstrap-repos.sh
        scripts/lock-repos.sh
        scripts/restore-repos.sh
        scripts/status-all.sh
        scripts/sync-kv-offload.sh
        scripts/validate-workspace.sh
        scripts/tests/test-linux-maintenance-scripts.sh
    )

    root=$(workspace_root)
    while (($# > 0)); do
        case "$1" in
            --root)
                (($# >= 2)) || {
                    usage >&2
                    return 2
                }
                root=$2
                shift 2
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
    require_command jq
    require_command grep
    require_command find
    if [[ ! -d $root ]]; then
        die "Workspace root does not exist: $root"
        return 1
    fi
    root=$(cd -- "$root" && pwd -P)

    for relative_path in "${required_paths[@]}"; do
        require_path "$root" "$relative_path"
    done
    for relative_path in "${executable_paths[@]}"; do
        require_executable "$root" "$relative_path"
    done

    require_text "$root" .gitignore '^repos/\*$' 'repos/* is ignored'
    require_text "$root" .gitignore '^!repos/\.gitkeep$' 'repos/.gitkeep remains trackable'
    require_text "$root" AGENTS.md 'control repo' 'root repo role'
    require_text "$root" AGENTS.md 'repos/\*' 'nested source repositories are not root-tracked'
    require_text "$root" AGENTS.md 'workspace\.lock\.json' 'lock file workflow'

    if [[ -d $root/features && -d $root/.git ]]; then
        while IFS= read -r -d '' feature; do
            feature_name=${feature##*/}
            tracked_feature_files=$(git_output "$root" ls-files -- "features/$feature_name")
            [[ -n $tracked_feature_files ]] || continue

            for relative_path in \
                "features/$feature_name/README.md" \
                "features/$feature_name/status.md" \
                "features/$feature_name/sync-log.md" \
                "features/$feature_name/repo-state.md" \
                "features/$feature_name/references/sources.md"; do
                require_path "$root" "$relative_path"
            done

            if [[ -d $feature/references/snapshots ]]; then
                while IFS= read -r -d '' snapshot; do
                    relative_path=${snapshot#"$root/"}
                    require_text "$root" "$relative_path" '^Source:' 'snapshot source header'
                    require_text "$root" "$relative_path" '^Captured At:' 'snapshot captured-at header'
                    require_text "$root" "$relative_path" '^Notes:' 'snapshot notes header'
                done < <(find "$feature/references/snapshots" -type f -name '*.md' -print0)
            fi
        done < <(find "$root/features" -mindepth 1 -maxdepth 1 -type d -print0)
    fi

    lock_path=$root/workspace.lock.json
    if [[ -f $lock_path ]]; then
        if ! validate_workspace_lock "$lock_path"; then
            fail_check "Invalid workspace.lock.json"
        else
            for repo_name in vllm vllm-ascend Mooncake; do
                if ! jq -e --arg name "$repo_name" '.repos | has($name)' "$lock_path" >/dev/null; then
                    fail_check "workspace.lock.json missing repo: $repo_name"
                    continue
                fi
                relative_path=$(repo_field "$lock_path" "$repo_name" path)
                if ! repo_path=$(resolve_repo_path "$root" "$relative_path"); then
                    fail_check "workspace.lock.json has unsafe path for repo: $repo_name"
                fi
            done
        fi
    fi

    if ((FAILED != 0)); then
        return 1
    fi

    printf 'Workspace validation passed.\n'
}

main "$@"
