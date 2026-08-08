#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

TEMP_PATHS=()

cleanup_temp_paths() {
    local path

    for path in "${TEMP_PATHS[@]}"; do
        [[ ! -e $path ]] || rm -f -- "$path"
    done
}

register_temp_path() {
    TEMP_PATHS+=("$1")
}

markdown_cell() {
    local value=$1

    value=${value//$'\n'/ }
    value=${value//|/\\|}
    printf '%s' "$value"
}

main() {
    local root
    local lock_path
    local workspace_branch
    local feature_dir=''
    local state_name=''
    local state_path=''
    local state_temp=''
    local lock_temp
    local updated_at
    local updates='{}'
    local repo_name
    local relative_path
    local repo_path
    local purpose
    local branch
    local head
    local dirty

    require_no_args "${0##*/}" "$@"
    require_command git
    require_command jq
    require_command find
    root=$(workspace_root)
    lock_path=$(load_workspace_lock "$root")
    validate_workspace_lock "$lock_path"
    workspace_branch=$(git_output "$root" branch --show-current)
    if [[ -z $workspace_branch ]]; then
        die "The control repository must be on an attached branch before locking."
        return 1
    fi

    if [[ $workspace_branch != main ]]; then
        if ! feature_dir=$(resolve_feature_directory "$root" "$workspace_branch"); then
            die "Missing feature directory for branch $workspace_branch"
            return 1
        fi
        state_name=${feature_dir##*/}
        state_path=$feature_dir/repo-state.md
    fi

    trap cleanup_temp_paths EXIT
    updated_at=$(date '+%Y-%m-%dT%H:%M:%S%:z')
    lock_temp=$(mktemp "$root/.workspace.lock.json.XXXXXX")
    register_temp_path "$lock_temp"

    if [[ -n $state_path ]]; then
        state_temp=$(mktemp "$feature_dir/.repo-state.md.XXXXXX")
        register_temp_path "$state_temp"
        {
            printf '# %s Repo State\n\n' "$state_name"
            printf 'Captured At: %s\n\n' "$updated_at"
            printf '| Repo | Path | Branch | HEAD | Dirty | Lock Role |\n'
            printf '| --- | --- | --- | --- | --- | --- |\n'
        } >"$state_temp"
    fi

    while IFS= read -r repo_name; do
        relative_path=$(repo_field "$lock_path" "$repo_name" path)
        repo_path=$(resolve_repo_path "$root" "$relative_path")
        purpose=$(repo_field "$lock_path" "$repo_name" purpose)

        if ! is_git_repository "$repo_path"; then
            printf 'warning: %s is missing; leaving commit unchanged.\n' "$repo_name" >&2
            if [[ -n $state_temp ]]; then
                printf '| %s | `%s` | missing |  | true | %s |\n' \
                    "$(markdown_cell "$repo_name")" \
                    "$(markdown_cell "$relative_path")" \
                    "$(markdown_cell "$purpose")" >>"$state_temp"
            fi
            continue
        fi

        branch=$(git_ref_name "$repo_path")
        head=$(git_output "$repo_path" rev-parse HEAD)
        if [[ -n $(git_output "$repo_path" status --porcelain) ]]; then
            dirty=true
        else
            dirty=false
        fi
        updates=$(jq -c \
            --arg name "$repo_name" \
            --arg branch "$branch" \
            --arg commit "$head" \
            '. + {($name): {branch: $branch, commit: $commit}}' <<<"$updates")

        if [[ -n $state_temp ]]; then
            printf '| %s | `%s` | `%s` | `%s` | %s | %s |\n' \
                "$(markdown_cell "$repo_name")" \
                "$(markdown_cell "$relative_path")" \
                "$(markdown_cell "$branch")" \
                "$head" \
                "$dirty" \
                "$(markdown_cell "$purpose")" >>"$state_temp"
        fi
    done < <(repo_names "$lock_path")

    jq --arg updated_at "$updated_at" --argjson updates "$updates" '
        .updated_at = $updated_at |
        reduce ($updates | to_entries[]) as $item (.;
            .repos[$item.key].branch = $item.value.branch |
            .repos[$item.key].commit = $item.value.commit
        )
    ' "$lock_path" >"$lock_temp"
    chmod --reference="$lock_path" "$lock_temp"

    if [[ -n $state_temp ]]; then
        if [[ -e $state_path ]]; then
            chmod --reference="$state_path" "$state_temp"
        else
            chmod 0644 "$state_temp"
        fi
    fi

    mv -- "$lock_temp" "$lock_path"
    if [[ -n $state_temp ]]; then
        mv -- "$state_temp" "$state_path"
        printf 'Updated workspace.lock.json and features/%s/repo-state.md\n' "$state_name"
    else
        printf 'Updated workspace.lock.json\n'
    fi
}

main "$@"
