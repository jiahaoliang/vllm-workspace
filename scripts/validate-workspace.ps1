param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$failed = $false

function Fail($Message) {
    Write-Error $Message
    $script:failed = $true
}

function Require-Path($RelativePath) {
    $path = Join-Path $Root $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        Fail "Missing required path: $RelativePath"
    }
}

function Require-Text($RelativePath, $Pattern, $Description) {
    $path = Join-Path $Root $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        Fail "Missing file for text check: $RelativePath"
        return
    }
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
    if ($content -notmatch $Pattern) {
        Fail "$RelativePath does not contain expected text: $Description"
    }
}

$requiredPaths = @(
    "AGENTS.md",
    "README.md",
    ".gitignore",
    "workspace.lock.json",
    "docs/workspace-guide.md",
    "docs/git-workflow.md",
    "docs/repo-map.md",
    "features/kv_offload/README.md",
    "features/kv_offload/status.md",
    "features/kv_offload/sync-log.md",
    "features/kv_offload/repo-state.md",
    "features/kv_offload/references/sources.md",
    "features/kv_offload/references/snapshots/hackmd-dsaoffloading.md",
    "features/kv_offload/references/snapshots/rfc-33398-layerwise-kv-offload.md",
    "features/kv_offload/references/snapshots/rfc-33980-sparse-attention-kv-offload.md",
    "features/kv_offload/notes/investigation-log.md",
    "features/kv_offload/notes/design-notes.md",
    "scripts/bootstrap-repos.ps1",
    "scripts/lock-repos.ps1",
    "scripts/restore-repos.ps1",
    "scripts/status-all.ps1",
    "scripts/sync-kv-offload.ps1"
)

foreach ($relativePath in $requiredPaths) {
    Require-Path $relativePath
}

Require-Text ".gitignore" "(?m)^repos/\*$" "repos/* is ignored"
Require-Text ".gitignore" "(?m)^!repos/\.gitkeep$" "repos/.gitkeep remains trackable"
Require-Text "AGENTS.md" "control repo" "root repo role"
Require-Text "AGENTS.md" "repos/\*" "nested source repositories are not root-tracked"
Require-Text "AGENTS.md" "workspace\.lock\.json" "lock file workflow"
Require-Text "features/kv_offload/references/snapshots/hackmd-dsaoffloading.md" "(?m)^Source:" "snapshot source header"
Require-Text "features/kv_offload/references/snapshots/rfc-33398-layerwise-kv-offload.md" "(?m)^Source:" "snapshot source header"
Require-Text "features/kv_offload/references/snapshots/rfc-33980-sparse-attention-kv-offload.md" "(?m)^Source:" "snapshot source header"

$lockPath = Join-Path $Root "workspace.lock.json"
if (Test-Path -LiteralPath $lockPath) {
    $lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $lockPath | ConvertFrom-Json
    foreach ($name in @("vllm", "vllm-ascend", "Mooncake")) {
        if (-not $lock.repos.PSObject.Properties.Name.Contains($name)) {
            Fail "workspace.lock.json missing repo: $name"
            continue
        }
        $repo = $lock.repos.$name
        foreach ($field in @("path", "remotes", "branch", "commit", "purpose")) {
            if (-not $repo.PSObject.Properties.Name.Contains($field)) {
                Fail "workspace.lock.json repo $name missing field: $field"
            }
        }
    }
}

if ($failed) {
    exit 1
}

Write-Host "Workspace validation passed."
