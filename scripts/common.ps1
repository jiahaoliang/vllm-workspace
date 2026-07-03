function Get-WorkspaceRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-WorkspaceLock {
    param([string]$Root = (Get-WorkspaceRoot))
    $lockPath = Join-Path $Root "workspace.lock.json"
    if (-not (Test-Path -LiteralPath $lockPath)) {
        throw "Missing workspace.lock.json"
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $lockPath | ConvertFrom-Json
}

function Invoke-Git {
    param(
        [string]$RepoPath,
        [string[]]$GitArgs
    )
    Push-Location $RepoPath
    try {
        & git @GitArgs
        if ($LASTEXITCODE -ne 0) {
            throw "git $($GitArgs -join ' ') failed in $RepoPath"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-GitOutput {
    param(
        [string]$RepoPath,
        [string[]]$GitArgs
    )
    Push-Location $RepoPath
    try {
        $output = & git @GitArgs
        if ($LASTEXITCODE -ne 0) {
            throw "git $($GitArgs -join ' ') failed in $RepoPath"
        }
        return ($output | Out-String).Trim()
    }
    finally {
        Pop-Location
    }
}

function Get-GitRefName {
    param([string]$RepoPath)

    $branch = Get-GitOutput -RepoPath $RepoPath -GitArgs @("branch", "--show-current")
    if ($branch) {
        return $branch
    }

    $tag = Get-GitOutput -RepoPath $RepoPath -GitArgs @("describe", "--tags", "--exact-match", "HEAD")
    if ($tag) {
        return "tag:$tag"
    }

    $head = Get-GitOutput -RepoPath $RepoPath -GitArgs @("rev-parse", "--short", "HEAD")
    return "detached:$head"
}

function Assert-NoUncommittedChanges {
    param([string]$RepoPath)
    $status = Get-GitOutput -RepoPath $RepoPath -GitArgs @("status", "--porcelain")
    if ($status) {
        throw "Refusing to change $RepoPath because it has uncommitted changes."
    }
}

function Ensure-Remote {
    param(
        [string]$RepoPath,
        [string]$Name,
        [string]$Url
    )
    Push-Location $RepoPath
    try {
        $remoteNames = @(& git remote)
        if ($remoteNames -notcontains $Name) {
            & git remote add $Name $Url
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to add remote $Name in $RepoPath"
            }
        }
        else {
            $existing = (& git remote get-url $Name | Out-String).Trim()
            if ($existing -ne $Url) {
                & git remote set-url $Name $Url
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to update remote $Name in $RepoPath"
                }
            }
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-BranchAtCommit {
    param(
        [string]$RepoPath,
        [string]$Branch,
        [string]$Commit
    )
    Push-Location $RepoPath
    try {
        & git show-ref --verify --quiet "refs/heads/$Branch"
        if ($LASTEXITCODE -eq 0) {
            $contains = (& git branch --contains $Commit) -match "^\*?\s+$([regex]::Escape($Branch))$"
            if ($contains) {
                & git switch $Branch
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to switch to $Branch in $RepoPath"
                }
                & git reset --hard $Commit
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to reset $Branch to $Commit in $RepoPath"
                }
            }
            else {
                Write-Warning "Restored to detached commit because branch $Branch does not contain $Commit."
            }
        }
        else {
            Write-Warning "Restored to detached commit because local branch $Branch does not exist."
        }
    }
    finally {
        Pop-Location
    }
}

function Get-RepoDefinitions {
    param([object]$Lock)
    return $Lock.repos.PSObject.Properties | ForEach-Object {
        [PSCustomObject]@{
            Name = $_.Name
            Spec = $_.Value
        }
    }
}

function ConvertTo-WorkspaceJson {
    param(
        [Parameter(Mandatory = $true)]
        [AllowNull()]
        $Value,
        [int]$Indent = 0
    )

    $space = " " * $Indent
    $childSpace = " " * ($Indent + 2)

    if ($null -eq $Value) {
        return "null"
    }

    if ($Value -is [string]) {
        return ($Value | ConvertTo-Json -Compress)
    }

    if ($Value -is [bool]) {
        return $Value.ToString().ToLowerInvariant()
    }

    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return [string]$Value
    }

    if ($Value -is [array]) {
        if ($Value.Count -eq 0) {
            return "[]"
        }

        $items = foreach ($item in $Value) {
            "$childSpace$(ConvertTo-WorkspaceJson -Value $item -Indent ($Indent + 2))"
        }
        return "[`n$($items -join ",`n")`n$space]"
    }

    $properties = $Value.PSObject.Properties | Where-Object {
        $_.MemberType -eq "NoteProperty" -or $_.MemberType -eq "Property"
    }

    if (-not $properties) {
        return ($Value | ConvertTo-Json -Compress)
    }

    $lines = foreach ($property in $properties) {
        $name = $property.Name | ConvertTo-Json -Compress
        $propertyValue = ConvertTo-WorkspaceJson -Value $property.Value -Indent ($Indent + 2)
        "$childSpace${name}: $propertyValue"
    }

    return "{`n$($lines -join ",`n")`n$space}"
}
