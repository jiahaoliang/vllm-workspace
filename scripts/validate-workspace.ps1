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

$featuresRoot = Join-Path $Root "features"
if (Test-Path -LiteralPath $featuresRoot) {
    $featureDirs = Get-ChildItem -LiteralPath $featuresRoot -Directory
    foreach ($feature in $featureDirs) {
        $featureName = $feature.Name
        foreach ($relativePath in @(
            "features/$featureName/README.md",
            "features/$featureName/status.md",
            "features/$featureName/sync-log.md",
            "features/$featureName/repo-state.md",
            "features/$featureName/references/sources.md"
        )) {
            Require-Path $relativePath
        }

        $snapshotRoot = Join-Path $feature.FullName "references/snapshots"
        if (Test-Path -LiteralPath $snapshotRoot) {
            foreach ($snapshot in Get-ChildItem -LiteralPath $snapshotRoot -Filter "*.md") {
                $rootPrefix = $Root.TrimEnd("\") + "\"
                $relativeSnapshot = $snapshot.FullName.Substring($rootPrefix.Length).Replace("\", "/")
                Require-Text $relativeSnapshot "(?m)^Source:" "snapshot source header"
                Require-Text $relativeSnapshot "(?m)^Captured At:" "snapshot captured-at header"
                Require-Text $relativeSnapshot "(?m)^Notes:" "snapshot notes header"
            }
        }
    }
}

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
