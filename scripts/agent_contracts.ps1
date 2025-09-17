Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('propose', 'accept', 'start', 'heartbeat', 'complete', 'fail', 'cancel', 'list', 'show', 'sweep')]
    [string]$Command,

    # Common
    [string]$Id,
    [string]$From,
    [string]$To,

    # Propose
    [string]$Title,
    [string]$Description = "",
    [ValidateSet('low', 'normal', 'high')]
    [string]$Priority = 'normal',
    [int]$TTLMinutes = 120,
    [int]$HeartbeatSec = 60,
    [switch]$AutoAccept,
    [int]$MaxSteps,

    # Start / Locks
    [string[]]$Lock,

    # Heartbeat / Updates
    [string]$Note = "",

    # Completion / Failure
    [string]$Result = "",
    [string]$Reason = "",

    # List filters
    [string]$Agent,
    [ValidateSet('proposed', 'accepted', 'in_progress', 'completed', 'failed', 'cancelled', 'expired')]
    [string]$Status
)

$ErrorActionPreference = 'Stop'

# Paths
$REPO_ROOT = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$COMM_DIR = Join-Path $REPO_ROOT '.agent-communication'
$CONTRACTS_FILE = Join-Path $COMM_DIR 'contracts.json'

# Utilities
function Read-JsonSafe {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $raw) { return $null }
    $raw = $raw -replace "`0", ''
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return ($raw | ConvertFrom-Json)
}

function Write-JsonSafe {
    param([string]$Path, $Object)
    $json = $Object | ConvertTo-Json -Depth 7
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Acquire-CommLock {
    param([int]$TimeoutMs = 5000)
    $lockPath = Join-Path $COMM_DIR '.comm.lock'
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        try {
            if (-not (Test-Path -LiteralPath $COMM_DIR)) { New-Item -ItemType Directory -Force -Path $COMM_DIR | Out-Null }
            $script:__commLockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        }
        catch {
            if ($sw.ElapsedMilliseconds -ge $TimeoutMs) { throw "Communication lock timeout ($TimeoutMs ms)." }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Release-CommLock {
    try {
        if ($script:__commLockStream) { $script:__commLockStream.Close(); $script:__commLockStream.Dispose(); $script:__commLockStream = $null }
    }
    catch { }
}

function Initialize-Contracts {
    if (-not (Test-Path -LiteralPath $COMM_DIR)) { New-Item -ItemType Directory -Force -Path $COMM_DIR | Out-Null }
    if (-not (Test-Path -LiteralPath $CONTRACTS_FILE)) { @() | Write-JsonSafe -Path $CONTRACTS_FILE }
}

function NowIso { (Get-Date).ToUniversalTime().ToString('o') }

function Send-Message {
    param([string]$To, [string]$From, [string]$Message, [string]$Context = 'contract', [string]$Priority = 'normal')
    try {
        $comm = Join-Path $PSScriptRoot 'agent_communication.ps1'
        if (Test-Path -LiteralPath $comm) { & $comm send -Message $Message -To $To -From $From -Priority $Priority -Context $Context | Out-Null }
    }
    catch { }
}

function Update-Status {
    param([string]$Agent, [string]$Status, [string]$Task)
    try {
        $comm = Join-Path $PSScriptRoot 'agent_communication.ps1'
        if (Test-Path -LiteralPath $comm) { & $comm update-status -Agent $Agent -Status $Status -Task $Task | Out-Null }
    }
    catch { }
}

function Load-Contracts { $c = Read-JsonSafe -Path $CONTRACTS_FILE; if (-not $c) { @() } else { @($c) } }

function Save-Contracts([array]$contracts) {
    # PowerShell 5 ConvertTo-Json collapses single-element arrays; build JSON array manually
    if (-not $contracts -or $contracts.Count -eq 0) {
        Set-Content -LiteralPath $CONTRACTS_FILE -Value '[]' -Encoding UTF8
        return
    }
    $parts = @()
    foreach ($c in $contracts) { $parts += ($c | ConvertTo-Json -Depth 7) }
    $json = "[" + [string]::Join(",`n", $parts) + "]"
    Set-Content -LiteralPath $CONTRACTS_FILE -Value $json -Encoding UTF8
}

function Get-ById([array]$contracts, [string]$id) { $contracts | Where-Object { $_.id -eq $id } }

function Ensure-Id([string]$id) { if (-not $Id) { throw 'Missing -Id' } }

function Sweep-Expire([array]$contracts) {
    $now = Get-Date
    foreach ($c in $contracts) {
        if ($c.status -in @('completed', 'failed', 'cancelled', 'expired')) { continue }
        # Deadline expiry
        $deadline = $null
        try { if ($c.deadline) { $deadline = [datetime]$c.deadline } } catch { $deadline = $null }
        if ($deadline -and $now.ToUniversalTime() -gt $deadline.ToUniversalTime()) {
            $c.status = 'expired'
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = (NowIso); from = 'system'; message = 'expired by deadline' }
            $c.last_updated = NowIso
            continue
        }
        # Heartbeat expiry
        $hb = 0
        try { $hb = [int]$c.heartbeat_interval_sec } catch { $hb = 0 }
        if ($hb -gt 0 -and $c.last_heartbeat) {
            try {
                $last = [datetime]$c.last_heartbeat
                $max = $last.AddSeconds([math]::Max(30, $hb * 2))
                if ($now.ToUniversalTime() -gt $max.ToUniversalTime()) {
                    $c.status = 'expired'
                    if (-not $c.updates) { $c.updates = @() }
                    $c.updates += @{ timestamp = (NowIso); from = 'system'; message = 'expired by heartbeat timeout' }
                    $c.last_updated = NowIso
                }
            }
            catch { }
        }
    }
}

function Lock-Paths([string[]]$paths, [string]$by, [string]$reason) {
    if (-not $paths -or $paths.Count -eq 0) { return }
    $lock = Join-Path $PSScriptRoot 'agent_lock.ps1'
    if (-not (Test-Path -LiteralPath $lock)) { return }
    foreach ($p in $paths) { try { & $lock lock -Path $p -By $by -Reason $reason -Notify | Out-Null } catch { } }
}

function Unlock-Paths([string[]]$paths, [string]$by, [string]$reason) {
    if (-not $paths -or $paths.Count -eq 0) { return }
    $lock = Join-Path $PSScriptRoot 'agent_lock.ps1'
    if (-not (Test-Path -LiteralPath $lock)) { return }
    foreach ($p in $paths) { try { & $lock unlock -Path $p -By $by -Notify | Out-Null } catch { } }
}

Initialize-Contracts

switch ($Command) {
    'propose' {
        if (-not $From) { throw 'Missing -From' }
        if (-not $To) { throw 'Missing -To' }
        if (-not $Title) { throw 'Missing -Title' }
        $id = [System.Guid]::NewGuid().ToString()
        $created = NowIso
        $deadline = if ($TTLMinutes -gt 0) { (Get-Date).AddMinutes($TTLMinutes).ToUniversalTime().ToString('o') } else { $null }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            if (-not $contracts) { $contracts = @() } else { $contracts = @($contracts) }
            $payload = [ordered]@{
                id                     = $id
                created_at             = $created
                last_updated           = $created
                from                   = $From
                to                     = $To
                title                  = $Title
                description            = $Description
                priority               = $Priority
                status                 = 'proposed'
                deadline               = $deadline
                heartbeat_interval_sec = $HeartbeatSec
                last_heartbeat         = $null
                related_locks          = @()
                safeguards             = @{ max_steps = $(if ($MaxSteps) { $MaxSteps } else { $null }); auto_accept = [bool]$AutoAccept; loop_guard = $true }
                updates                = @(@{ timestamp = $created; from = $From; message = 'proposed' })
            }
            $contracts += $payload
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        # Notify receiver
        Send-Message -To $To -From $From -Priority $Priority -Message ("/contract accept id={0}" -f $id)
        Write-Host ("PROPOSED {0}" -f $id)
    }

    'accept' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From (accepting agent)' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            if ($c.status -ne 'proposed') { throw "Invalid state ($($c.status)); expected 'proposed'" }
            $c.status = 'accepted'
            $c.last_updated = NowIso
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = (NowIso); from = $From; message = 'accepted' }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        # Prompt the doer (c.to) to start; often this is the accepting agent itself
        Send-Message -To $c.to -From $From -Priority 'normal' -Message ("/contract start id={0}" -f $Id)
        Write-Host ("ACCEPTED {0}" -f $Id)
    }

    'start' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From (starting agent)' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            if ($c.status -notin @('accepted', 'proposed')) { throw "Invalid state ($($c.status)); expected 'accepted' or 'proposed'" }
            # Optional lock resources
            if ($Lock -and $Lock.Count -gt 0) {
                Lock-Paths -paths $Lock -by $From -reason ("contract {0}" -f $Id)
                if (-not $c.related_locks) { $c.related_locks = @() }
                $c.related_locks = @($c.related_locks + $Lock)
            }
            $c.status = 'in_progress'
            $c.last_heartbeat = NowIso
            $c.last_updated = $c.last_heartbeat
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = $c.last_heartbeat; from = $From; message = 'started' }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Update-Status -Agent $From -Status 'busy' -Task $c.title
        Send-Message -To $c.from -From $From -Priority 'normal' -Message ("heartbeat started id={0}" -f $Id)
        Write-Host ("STARTED {0}" -f $Id)
    }

    'heartbeat' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From (sending agent)' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            if ($c.status -ne 'in_progress') { throw "Invalid state ($($c.status)); expected 'in_progress'" }
            $c.last_heartbeat = NowIso
            $c.last_updated = $c.last_heartbeat
            if (-not $c.updates) { $c.updates = @() }
            $msg = if ($Note) { "hb: $Note" } else { 'heartbeat' }
            $c.updates += @{ timestamp = $c.last_heartbeat; from = $From; message = $msg }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Write-Host ("HEARTBEAT {0}" -f $Id)
    }

    'complete' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            if ($c.status -notin @('in_progress', 'accepted')) { throw "Invalid state ($($c.status))" }
            $c.status = 'completed'
            $c.result = $Result
            $c.last_updated = NowIso
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = $c.last_updated; from = $From; message = ('completed: ' + [string]$Result) }
            # Unlock any paths
            if ($c.related_locks) { Unlock-Paths -paths @($c.related_locks) -by $From -reason 'contract completed' }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Update-Status -Agent $From -Status 'available' -Task ''
        Send-Message -To $c.from -From $From -Priority 'normal' -Message ("contract completed id={0}" -f $Id)
        Write-Host ("COMPLETED {0}" -f $Id)
    }

    'fail' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            $c.status = 'failed'
            $c.error = $Reason
            $c.last_updated = NowIso
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = $c.last_updated; from = $From; message = ('failed: ' + [string]$Reason) }
            if ($c.related_locks) { Unlock-Paths -paths @($c.related_locks) -by $From -reason 'contract failed' }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Update-Status -Agent $From -Status 'available' -Task ''
        Send-Message -To $c.from -From $From -Priority 'high' -Message ("contract failed id={0}" -f $Id)
        Write-Host ("FAILED {0}" -f $Id)
    }

    'cancel' {
        Ensure-Id $Id
        if (-not $From) { throw 'Missing -From' }
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            $c = Get-ById $contracts $Id
            if (-not $c) { throw "Contract not found: $Id" }
            $c.status = 'cancelled'
            $c.last_updated = NowIso
            if (-not $c.updates) { $c.updates = @() }
            $c.updates += @{ timestamp = $c.last_updated; from = $From; message = ('cancelled: ' + [string]$Reason) }
            if ($c.related_locks) { Unlock-Paths -paths @($c.related_locks) -by $From -reason 'contract cancelled' }
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Update-Status -Agent $From -Status 'available' -Task ''
        Send-Message -To $c.from -From $From -Priority 'normal' -Message ("contract cancelled id={0}" -f $Id)
        Write-Host ("CANCELLED {0}" -f $Id)
    }

    'list' {
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            Sweep-Expire -contracts $contracts
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        $contracts = Load-Contracts
        $filtered = $contracts
        if ($Agent) { $filtered = $filtered | Where-Object { $_.from -eq $Agent -or $_.to -eq $Agent } }
        if ($Status) { $filtered = $filtered | Where-Object { $_.status -eq $Status } }
        if (-not $filtered) { Write-Host 'No contracts.' -ForegroundColor Green; return }
        foreach ($c in $filtered) {
            Write-Host ("- {0} [{1}] {2} -> {3} | {4}" -f $c.id, $c.status, $c.from, $c.to, $c.title)
        }
    }

    'show' {
        Ensure-Id $Id
        $contracts = Load-Contracts
        $c = Get-ById $contracts $Id
        if (-not $c) { throw "Contract not found: $Id" }
        ($c | ConvertTo-Json -Depth 7) | Write-Output
    }

    'sweep' {
        Acquire-CommLock
        try {
            $contracts = Load-Contracts
            Sweep-Expire -contracts $contracts
            Save-Contracts $contracts
        }
        finally { Release-CommLock }
        Write-Host 'SWEPT'
    }
}
