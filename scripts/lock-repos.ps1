. "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$LockPath = Join-Path $Root "workspace.lock.json"
$Lock = Get-WorkspaceLock -Root $Root
$Lock.updated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")

$stateLines = @(
    "# kv_offload Repo State",
    "",
    "Captured At: $($Lock.updated_at)",
    "",
    "| Repo | Path | Branch | HEAD | Dirty | Lock Role |",
    "| --- | --- | --- | --- | --- | --- |"
)

foreach ($repoDef in Get-RepoDefinitions -Lock $Lock) {
    $name = $repoDef.Name
    $spec = $repoDef.Spec
    $repoPath = Join-Path $Root $spec.path

    if (-not (Test-Path -LiteralPath (Join-Path $repoPath ".git"))) {
        Write-Warning "$name is missing; leaving commit unchanged."
        $stateLines += "| $name | ``$($spec.path)`` | missing |  | true | $($spec.purpose) |"
        continue
    }

    $branch = Get-GitOutput -RepoPath $repoPath -GitArgs @("branch", "--show-current")
    $head = Get-GitOutput -RepoPath $repoPath -GitArgs @("rev-parse", "HEAD")
    $dirty = [bool](Get-GitOutput -RepoPath $repoPath -GitArgs @("status", "--porcelain"))

    $spec.branch = $branch
    $spec.commit = $head
    $stateLines += "| $name | ``$($spec.path)`` | ``$branch`` | ``$head`` | $dirty | $($spec.purpose) |"
}

$Lock | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $LockPath
$statePath = Join-Path $Root "features/kv_offload/repo-state.md"
$stateLines -join "`n" | Set-Content -Encoding UTF8 -LiteralPath $statePath

Write-Host "Updated workspace.lock.json and features/kv_offload/repo-state.md"
