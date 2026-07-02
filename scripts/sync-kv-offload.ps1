. "$PSScriptRoot\common.ps1"

param(
    [switch]$Merge
)

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$repos = @("vllm", "vllm-ascend")

foreach ($name in $repos) {
    $repoPath = Join-Path $Root "repos/$name"
    if (-not (Test-Path -LiteralPath (Join-Path $repoPath ".git"))) {
        throw "$name is missing. Run .\scripts\bootstrap-repos.ps1 first."
    }

    Assert-NoUncommittedChanges -RepoPath $repoPath
    Invoke-Git -RepoPath $repoPath -GitArgs @("fetch", "collaborator", "--prune")
    Invoke-Git -RepoPath $repoPath -GitArgs @("switch", "kv_offload")
    if ($Merge) {
        Invoke-Git -RepoPath $repoPath -GitArgs @("merge", "collaborator/kv_offload")
    }
    else {
        Invoke-Git -RepoPath $repoPath -GitArgs @("rebase", "collaborator/kv_offload")
    }
}

$logPath = Join-Path $Root "features/kv_offload/sync-log.md"
$mode = if ($Merge) { "merge" } else { "rebase" }
$entry = @(
    "",
    "## $(Get-Date -Format yyyy-MM-dd)",
    "",
    "- Synced `repos/vllm` and `repos/vllm-ascend` from `collaborator/kv_offload` using $mode.",
    "- Run `.\scripts\lock-repos.ps1` after verifying and pushing source commits."
)
Add-Content -Encoding UTF8 -LiteralPath $logPath -Value ($entry -join "`n")

Write-Host "kv_offload sync complete. Review, test, push source repos, then lock."
