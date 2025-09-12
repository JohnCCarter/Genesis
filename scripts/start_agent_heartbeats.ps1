# AI Change: Add simple heartbeat loop to keep agent last_seen fresh (Agent: Codex, Date: 2025-09-12)
Param(
    [int]$IntervalSeconds = 600
)

$ErrorActionPreference = 'Stop'

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $comm = Join-Path $repoRoot 'scripts/agent_communication.ps1'
    if (-not (Test-Path -LiteralPath $comm)) { throw "Missing: $comm" }

    Write-Host "Starting agent heartbeats every $IntervalSeconds sec..." -ForegroundColor Green
    while ($true) {
        try { & $comm update-status -Agent 'Codex'  | Out-Null } catch { }
        try { & $comm update-status -Agent 'Cursor' | Out-Null } catch { }
        Start-Sleep -Seconds ([math]::Max(60,[int]$IntervalSeconds))
    }
}
catch {
    Write-Host ("Heartbeat loop error: {0}" -f $_.Exception.Message) -ForegroundColor Red
}
