. "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$Lock = Get-WorkspaceLock -Root $Root

foreach ($repoDef in Get-RepoDefinitions -Lock $Lock) {
    $name = $repoDef.Name
    $spec = $repoDef.Spec
    $repoPath = Join-Path $Root $spec.path

    Write-Host ""
    Write-Host "[$name] $($spec.path)"
    if (-not (Test-Path -LiteralPath (Join-Path $repoPath ".git"))) {
        Write-Host "  missing"
        continue
    }

    $branch = Get-GitRefName -RepoPath $repoPath
    $head = Get-GitOutput -RepoPath $repoPath -GitArgs @("rev-parse", "HEAD")
    $dirty = Get-GitOutput -RepoPath $repoPath -GitArgs @("status", "--porcelain")
    $lockCommit = $spec.commit
    $matchesLock = ($lockCommit -and $head -eq $lockCommit)

    Write-Host "  branch: $branch"
    Write-Host "  head:   $head"
    Write-Host "  lock:   $lockCommit"
    Write-Host "  match:  $matchesLock"
    Write-Host "  dirty:  $([bool]$dirty)"
}
