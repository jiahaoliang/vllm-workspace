# Shared helpers for Linux workspace maintenance commands.

workspace_root() {
    local script_dir

    script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
    cd -- "$script_dir/.." && pwd -P
}

die() {
    printf 'error: %s\n' "$*" >&2
    return 1
}

require_command() {
    local command_name=$1

    if ! command -v "$command_name" >/dev/null 2>&1; then
        die "Required command is not installed: $command_name"
        return 1
    fi
}

require_no_args() {
    local command_name=$1
    shift

    if (($# != 0)); then
        die "Usage: $command_name"
        return 1
    fi
}

load_workspace_lock() {
    local root=$1
    local lock_path=$root/workspace.lock.json

    if [[ ! -f $lock_path ]]; then
        die "Missing workspace.lock.json"
        return 1
    fi
    printf '%s\n' "$lock_path"
}

validate_workspace_lock() {
    local lock_path=$1

    jq -e '
        def nonempty_string: type == "string" and length > 0;
        (.version == 1) and
        (.updated_at | nonempty_string) and
        (.repos | type == "object" and length > 0) and
        (.repos | to_entries | all(.[];
            (.key | nonempty_string) and
            (.value | type == "object") and
            (.value.path | nonempty_string) and
            (.value.remotes | type == "object" and length > 0) and
            (.value.remotes.origin | nonempty_string) and
            (.value.remotes | to_entries | all(.[];
                (.key | nonempty_string) and (.value | nonempty_string)
            )) and
            (.value.branch | nonempty_string) and
            (.value.commit | type == "string" and
                (. == "" or test("^[0-9A-Fa-f]{40}$"))) and
            (.value.purpose | nonempty_string)
        ))
    ' "$lock_path" >/dev/null 2>&1 || {
        die "Invalid workspace.lock.json: expected version 1 repository definitions"
        return 1
    }
}

repo_names() {
    local lock_path=$1

    jq -r '.repos | keys_unsorted[]' "$lock_path"
}

repo_field() {
    local lock_path=$1
    local repo_name=$2
    local field=$3

    jq -er --arg repo "$repo_name" --arg field "$field" '.repos[$repo][$field]' "$lock_path"
}

repo_remote_entries() {
    local lock_path=$1
    local repo_name=$2

    jq -r --arg repo "$repo_name" \
        '.repos[$repo].remotes | to_entries[] | [.key, .value] | @tsv' "$lock_path"
}

resolve_repo_path() {
    local root=$1
    local relative_path=$2
    local repos_root
    local resolved_path

    if [[ $relative_path != repos/* || $relative_path == repos/ ]]; then
        die "Repository path must be below repos/: $relative_path"
        return 1
    fi
    case "/$relative_path/" in
        *'/../'* | *'/./'* | *'//'*)
            die "Repository path contains an unsafe segment: $relative_path"
            return 1
            ;;
    esac
    if [[ $relative_path == *$'\n'* || $relative_path == *$'\t'* ]]; then
        die "Repository path contains control characters"
        return 1
    fi
    if ! command -v realpath >/dev/null 2>&1; then
        die "Required command is not installed: realpath"
        return 1
    fi
    repos_root=$(realpath -m -- "$root/repos")
    resolved_path=$(realpath -m -- "$root/$relative_path")
    if [[ $resolved_path != "$repos_root/"* ]]; then
        die "Repository path resolves outside repos/: $relative_path"
        return 1
    fi
    printf '%s\n' "$resolved_path"
}

is_git_repository() {
    local repo_path=$1

    git -C "$repo_path" rev-parse --git-dir >/dev/null 2>&1
}

git_output() {
    local repo_path=$1
    shift

    git -C "$repo_path" "$@"
}

git_ref_name() {
    local repo_path=$1
    local branch
    local tag
    local head

    branch=$(git_output "$repo_path" branch --show-current)
    if [[ -n $branch ]]; then
        printf '%s\n' "$branch"
        return 0
    fi

    tag=$(git_output "$repo_path" tag --points-at HEAD --sort=-version:refname | sed -n '1p')
    if [[ -n $tag ]]; then
        printf 'tag:%s\n' "$tag"
        return 0
    fi

    head=$(git_output "$repo_path" rev-parse --short HEAD)
    printf 'detached:%s\n' "$head"
}

assert_no_uncommitted_changes() {
    local repo_path=$1

    if [[ -n $(git_output "$repo_path" status --porcelain) ]]; then
        die "Refusing to change $repo_path because it has uncommitted changes."
        return 1
    fi
}

ensure_remote() {
    local repo_path=$1
    local name=$2
    local url=$3
    local existing

    if git_output "$repo_path" remote get-url "$name" >/dev/null 2>&1; then
        existing=$(git_output "$repo_path" remote get-url "$name")
        if [[ $existing != "$url" ]]; then
            git_output "$repo_path" remote set-url "$name" "$url"
        fi
    else
        git_output "$repo_path" remote add "$name" "$url"
    fi
}

fetch_all_remotes() {
    local repo_path=$1

    git_output "$repo_path" fetch --all --prune
}

checkout_locked_commit() {
    local repo_path=$1
    local locked_ref=$2
    local commit=$3

    if [[ -z $commit ]]; then
        if [[ $locked_ref == tag:* || $locked_ref == detached:* ]]; then
            die "A $locked_ref lock requires an exact commit"
            return 1
        fi
        git_output "$repo_path" switch -- "$locked_ref"
        return 0
    fi

    git_output "$repo_path" cat-file -e "$commit^{commit}"

    case "$locked_ref" in
        tag:* | detached:*)
            git_output "$repo_path" checkout --detach "$commit"
            ;;
        *)
            if git_output "$repo_path" show-ref --verify --quiet "refs/heads/$locked_ref" && \
                git_output "$repo_path" merge-base --is-ancestor "$commit" "refs/heads/$locked_ref"; then
                git_output "$repo_path" switch -- "$locked_ref"
                git_output "$repo_path" reset --hard "$commit"
            else
                git_output "$repo_path" checkout --detach "$commit"
                printf 'warning: restored %s to detached HEAD because branch %s does not contain %s\n' \
                    "$repo_path" "$locked_ref" "$commit" >&2
            fi
            ;;
    esac
}

resolve_feature_directory() {
    local root=$1
    local workspace_branch=$2
    local features_root=$root/features
    local exact=$features_root/$workspace_branch
    local candidate
    local candidate_name
    local best=''

    if [[ -d $exact ]]; then
        printf '%s\n' "$exact"
        return 0
    fi
    [[ -d $features_root ]] || return 1

    while IFS= read -r -d '' candidate; do
        candidate_name=${candidate##*/}
        if [[ $workspace_branch == "$candidate_name-"* && ${#candidate_name} -gt ${#best} ]]; then
            best=$candidate_name
        fi
    done < <(find "$features_root" -mindepth 1 -maxdepth 1 -type d -print0)

    [[ -n $best ]] || return 1
    printf '%s/%s\n' "$features_root" "$best"
}
