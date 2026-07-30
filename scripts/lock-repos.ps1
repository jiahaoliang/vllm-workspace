. "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$LockPath = Join-Path $Root "workspace.lock.json"
$Lock = Get-WorkspaceLock -Root $Root
$WorkspaceBranch = Get-GitOutput -RepoPath $Root -GitArgs @("branch", "--show-current")
$StateName = $WorkspaceBranch
$StatePath = $null

if ($WorkspaceBranch -ne "main") {
    $featuresRoot = Join-Path $Root "features"
    $featureDir = Get-Item -LiteralPath (Join-Path $featuresRoot $WorkspaceBranch) -ErrorAction SilentlyContinue
    if ($null -eq $featureDir -or -not $featureDir.PSIsContainer) {
        $featureDir = Get-ChildItem -LiteralPath $featuresRoot -Directory |
            Where-Object {
                $WorkspaceBranch.StartsWith(
                    "$($_.Name)-",
                    [System.StringComparison]::Ordinal
                )
            } |
            Sort-Object { $_.Name.Length } -Descending |
            Select-Object -First 1
    }
    if ($null -eq $featureDir) {
        throw "Missing feature directory for branch $WorkspaceBranch"
    }
    $StateName = $featureDir.Name
    $StatePath = Join-Path $featureDir.FullName "repo-state.md"
}

$Lock.updated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")

$stateLines = @(
    "# $StateName Repo State",
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

if ($null -ne $StatePath) {
    $stateLines -join "`n" | Set-Content -Encoding UTF8 -LiteralPath $StatePath
    Write-Host "Updated workspace.lock.json and features/$StateName/repo-state.md"
}
else {
    Write-Host "Updated workspace.lock.json"
}
