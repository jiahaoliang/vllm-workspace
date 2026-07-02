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
    elseif (-not (Test-Path -LiteralPath (Join-Path $repoPath ".git"))) {
        throw "$repoPath exists but is not a Git repository."
    }
    else {
        Assert-NoUncommittedChanges -RepoPath $repoPath
    }

    foreach ($remote in $spec.remotes.PSObject.Properties) {
        Ensure-Remote -RepoPath $repoPath -Name $remote.Name -Url $remote.Value
    }

    Invoke-Git -RepoPath $repoPath -GitArgs @("fetch", "--all", "--prune")

    if ($spec.commit) {
        Push-Location $repoPath
        try {
            & git show-ref --verify --quiet "refs/heads/$($spec.branch)"
            if ($LASTEXITCODE -eq 0) {
                $contains = (& git branch --contains $spec.commit) -match "^\*?\s+$([regex]::Escape($spec.branch))$"
                if ($contains) {
                    & git switch $spec.branch
                    if ($LASTEXITCODE -ne 0) {
                        throw "Failed to switch $name to $($spec.branch)"
                    }
                    & git reset --hard $spec.commit
                    if ($LASTEXITCODE -ne 0) {
                        throw "Failed to reset $name to $($spec.commit)"
                    }
                }
                else {
                    & git checkout $spec.commit
                    if ($LASTEXITCODE -ne 0) {
                        throw "Failed to checkout $name locked commit"
                    }
                    Write-Warning "$name restored to detached commit because branch $($spec.branch) does not contain the locked commit."
                }
            }
            else {
                & git checkout $spec.commit
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to checkout $name locked commit"
                }
                Write-Warning "$name restored to detached commit because local branch $($spec.branch) does not exist."
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Warning "$name has no locked commit; switching to branch $($spec.branch)."
        Invoke-Git -RepoPath $repoPath -GitArgs @("switch", $spec.branch)
        continue
    }
}

Write-Host "Restore complete."
