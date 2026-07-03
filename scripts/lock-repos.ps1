. "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$LockPath = Join-Path $Root "workspace.lock.json"
$Lock = Get-WorkspaceLock -Root $Root
$Lock.updated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
$WorkspaceBranch = Get-GitOutput -RepoPath $Root -GitArgs @("branch", "--show-current")

$stateLines = @(
    "# $WorkspaceBranch Repo State",
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

    $branch = Get-GitRefName -RepoPath $repoPath
    $head = Get-GitOutput -RepoPath $repoPath -GitArgs @("rev-parse", "HEAD")
    $dirty = [bool](Get-GitOutput -RepoPath $repoPath -GitArgs @("status", "--porcelain"))

    $spec.branch = $branch
    $spec.commit = $head
    $stateLines += "| $name | ``$($spec.path)`` | ``$branch`` | ``$head`` | $dirty | $($spec.purpose) |"
}

ConvertTo-WorkspaceJson -Value $Lock | Set-Content -Encoding UTF8 -LiteralPath $LockPath

if ($WorkspaceBranch -ne "main") {
    $statePath = Join-Path $Root "features/$WorkspaceBranch/repo-state.md"
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $statePath))) {
        throw "Missing feature directory for branch $WorkspaceBranch"
    }
    $stateLines -join "`n" | Set-Content -Encoding UTF8 -LiteralPath $statePath
    Write-Host "Updated workspace.lock.json and features/$WorkspaceBranch/repo-state.md"
}
else {
    Write-Host "Updated workspace.lock.json"
}
