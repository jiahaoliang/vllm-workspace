. "$PSScriptRoot\common.ps1"

$ErrorActionPreference = "Stop"
$Root = Get-WorkspaceRoot
$Lock = Get-WorkspaceLock -Root $Root

foreach ($repoDef in Get-RepoDefinitions -Lock $Lock) {
    $name = $repoDef.Name
    $spec = $repoDef.Spec
    $repoPath = Join-Path $Root $spec.path
    $originUrl = $spec.remotes.origin

    if (-not (Test-Path -LiteralPath $repoPath)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $repoPath) | Out-Null
        Write-Host "Cloning $name from $originUrl"
        & git clone $originUrl $repoPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone $name"
        }
    }
    else {
        Write-Host "$name already exists at $($spec.path)"
    }

    foreach ($remote in $spec.remotes.PSObject.Properties) {
        Ensure-Remote -RepoPath $repoPath -Name $remote.Name -Url $remote.Value
    }

    Invoke-Git -RepoPath $repoPath -GitArgs @("fetch", "--all", "--prune")

    if ($name -eq "Mooncake") {
        Invoke-Git -RepoPath $repoPath -GitArgs @("switch", $spec.branch)
    }
    else {
        Push-Location $repoPath
        try {
            & git show-ref --verify --quiet "refs/heads/$($spec.branch)"
            if ($LASTEXITCODE -eq 0) {
                & git switch $spec.branch
            }
            else {
                & git show-ref --verify --quiet "refs/remotes/collaborator/$($spec.branch)"
                if ($LASTEXITCODE -eq 0) {
                    & git switch -c $spec.branch "collaborator/$($spec.branch)"
                }
                else {
                    & git switch -c $spec.branch
                }
            }
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to switch $name to $($spec.branch)"
            }
        }
        finally {
            Pop-Location
        }
    }
}

Write-Host "Bootstrap complete. Run .\scripts\lock-repos.ps1 to record exact commits."
