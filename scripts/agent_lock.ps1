Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('lock','unlock','status')]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Path,

    [string]$By,
    [string]$Reason,
    [int]$TTLMinutes = 240,
    [switch]$Force,
    [switch]$Notify
)

$ErrorActionPreference = 'Stop'

function Write-Usage {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  Lock  : scripts/agent_lock.ps1 lock   -Path <relative> -By <Agent> -Reason <text> [-TTLMinutes 240]" -ForegroundColor Gray
    Write-Host "  Unlock: scripts/agent_lock.ps1 unlock -Path <relative> -By <Agent> [-Force]" -ForegroundColor Gray
    Write-Host "  Status: scripts/agent_lock.ps1 status [ -Path <relative> ]" -ForegroundColor Gray
}

function Get-RepoRoot {
    # Resolve repo root as parent of this script (assumes script resides in scripts/)
    $root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
    return $root.Path
}

function Notify-OtherAgent {
    param(
        [string]$Event,
        [string]$TargetPath,
        [string]$By,
        [string]$Reason
    )
    if (-not $Notify) { return }
    try {
        $other = if ($By -eq 'Codex') { 'Cursor' } elseif ($By -eq 'Cursor') { 'Codex' } else { 'Cursor' }
        $msg = "${Event}: ${TargetPath} (by ${By})" + ($(if ($Reason) { " Reason: ${Reason}" } else { '' }))
        $comm = Join-Path $PSScriptRoot 'agent_communication.ps1'
        if (Test-Path -LiteralPath $comm) {
            & $comm send -Message $msg -To $other -From $By -Priority 'normal' -Context 'lock-notify' | Out-Null
        }
    } catch { }
}

function Sanitize([string]$p) {
    if (-not $p) { return $null }
    # Normalize separators and replace characters unsuitable for filenames
    $norm = $p -replace '\\','/'
    $san = $norm -replace '[:/\\]','__'
    $san = $san -replace '[^A-Za-z0-9_\.-]','_'
    return $san
}

function Get-LockRoot {
    $root = Get-RepoRoot
    $lockRoot = Join-Path $root '.agent-locks'
    if (-not (Test-Path -LiteralPath $lockRoot)) {
        New-Item -ItemType Directory -Force -Path $lockRoot | Out-Null
    }
    return $lockRoot
}

function Get-LockPath([string]$relativePath) {
    $lockRoot = Get-LockRoot
    $san = Sanitize $relativePath
    if (-not $san) { throw 'Missing -Path' }
    return (Join-Path $lockRoot ("{0}.lock" -f $san))
}

function Is-Stale([datetime]$createdAt, [int]$ttlMinutes) {
    if (-not $createdAt) { return $false }
    $age = (Get-Date).ToUniversalTime() - $createdAt.ToUniversalTime()
    return ($age.TotalMinutes -ge $ttlMinutes)
}

switch ($Command) {
    'lock' {
        if (-not $Path) { Write-Usage; throw 'Missing -Path' }
        if (-not $By)   { $By = $env:USERNAME; if (-not $By) { $By = 'UnknownAgent' } }
        $lockFile = Get-LockPath -relativePath $Path
        if (Test-Path -LiteralPath $lockFile) {
            try {
                $existing = Get-Content -LiteralPath $lockFile -Raw | ConvertFrom-Json
            } catch { $existing = $null }
            if ($existing) {
                $isStale = Is-Stale -createdAt ([datetime]$existing.created_at) -ttlMinutes $TTLMinutes
                if (-not $isStale -and -not $Force) {
                    throw "Already locked by '$($existing.locked_by)' since $($existing.created_at). Path: $($existing.path)"
                }
            }
        }
        $payload = [ordered]@{
            path       = $Path
            locked_by  = $By
            reason     = ($Reason | ForEach-Object { $_ })
            created_at = (Get-Date).ToUniversalTime().ToString('o')
        }
        ($payload | ConvertTo-Json -Depth 3) | Set-Content -LiteralPath $lockFile -Encoding UTF8
        Write-Host "Locked: $Path (by $By)" -ForegroundColor Green
        Notify-OtherAgent -Event 'LOCK' -TargetPath $Path -By $By -Reason $Reason
    }

    'unlock' {
        if (-not $Path) { Write-Usage; throw 'Missing -Path' }
        if (-not $By)   { $By = $env:USERNAME; if (-not $By) { $By = 'UnknownAgent' } }
        $lockFile = Get-LockPath -relativePath $Path
        if (-not (Test-Path -LiteralPath $lockFile)) {
            Write-Host "No lock present for: $Path" -ForegroundColor Yellow
            break
        }
        $okToRemove = $true
        try {
            $existing = Get-Content -LiteralPath $lockFile -Raw | ConvertFrom-Json
            if ($existing -and ($existing.locked_by -ne $By) -and -not $Force) {
                $okToRemove = $false
                throw "Locked by '$($existing.locked_by)'; use -Force to override if stale."
            }
        } catch {
            if (-not $Force) { throw }
        }
        if ($okToRemove) {
            Remove-Item -LiteralPath $lockFile -Force
            Write-Host "Unlocked: $Path (by $By)" -ForegroundColor Green
            Notify-OtherAgent -Event 'UNLOCK' -TargetPath $Path -By $By -Reason $Reason
        }
    }

    'status' {
        $lockRoot = Get-LockRoot
        $items = Get-ChildItem -LiteralPath $lockRoot -Filter '*.lock' -File -ErrorAction SilentlyContinue
        if ($Path) {
            $target = Get-LockPath -relativePath $Path
            $items = $items | Where-Object { $_.FullName -eq (Resolve-Path -LiteralPath $target).Path }
        }
        if (-not $items -or $items.Count -eq 0) {
            Write-Host 'No active locks.' -ForegroundColor Green
            break
        }
        foreach ($i in $items) {
            try {
                $data = Get-Content -LiteralPath $i.FullName -Raw | ConvertFrom-Json
                $created = [datetime]$data.created_at
                $stale = Is-Stale -createdAt $created -ttlMinutes $TTLMinutes
                $staleMark = if ($stale) { ' (STALE)' } else { '' }
                Write-Host ("- {0} by {1} at {2}{3}" -f $data.path, $data.locked_by, $data.created_at, $staleMark)
            } catch {
                Write-Host ("- {0} (unreadable)" -f $i.Name) -ForegroundColor Yellow
            }
        }
    }
}
