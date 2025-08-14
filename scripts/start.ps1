<#
  Startar backend (FastAPI/Uvicorn) på Windows/PowerShell.
  - Skapar .venv i repo-roten om den saknas
  - Installerar beroenden om uvicorn saknas
  - Startar uvicorn med korrekt app-dir (tradingbot-backend)

  Användning (kör från repo-roten):
    pwsh -File .\scripts\start.ps1

  Parametrar:
    -NoReload    Starta utan --reload
    -AuthRequired:$true|$false   Sätt AUTH_REQUIRED (default: $true)
#>

[CmdletBinding()]
param(
    [switch]$NoReload,
    [bool]$AuthRequired = $false,
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

# Läs .env och exponera GITHUB_TOKEN (för MCP) om satt
function Load-DotEnv($path) {
    if (Test-Path $path) {
        Get-Content $path | ForEach-Object {
            if ($_ -match '^[#;]') { return }
            if ($_ -match '^(?<k>[A-Za-z_][A-Za-z0-9_]*)=(?<v>.*)$') {
                $k = $Matches['k']
                $v = $Matches['v']
                if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                    $v = $v.Substring(1, $v.Length - 2)
                }
                Set-Item -Path Env:$k -Value $v | Out-Null
            }
        }
    }
}

# Repo-rot och app-katalog
$repoRoot = Split-Path -Parent $PSScriptRoot
$rootEnv = Join-Path $repoRoot '.env'
$appEnv = Join-Path $repoRoot 'tradingbot-backend' | Join-Path -ChildPath '.env'
Load-DotEnv $rootEnv
Load-DotEnv $appEnv
if (-not $env:GITHUB_TOKEN -and $env:GITHUB_PAT) { $env:GITHUB_TOKEN = $env:GITHUB_PAT }
try { if ($env:GITHUB_TOKEN) { setx GITHUB_TOKEN "$($env:GITHUB_TOKEN)" | Out-Null } } catch {}
$appDir = Join-Path $repoRoot 'tradingbot-backend'

if (-not (Test-Path $appDir)) {
    Write-Error "Kunde inte hitta tradingbot-backend i $repoRoot"
}

# Välj Python-tolk (.venv i repo-roten). Skapa om saknas
$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Host 'Skapar .venv i repo-roten...'
    & py -3 -m venv (Join-Path $repoRoot '.venv')
    $py = Join-Path $repoRoot '.venv\Scripts\python.exe'
}

# Se till att uvicorn finns (annars installera beroenden)
try {
    & $py -m pip show uvicorn 1>$null 2>$null
}
catch {
    Write-Host 'Installerar beroenden...'
    & $py -m pip install --upgrade pip setuptools wheel
    & $py -m pip install -r (Join-Path $appDir 'requirements.txt')
}

# Döda ev. gamla processer så att porten är fri
Get-Process -Name python, uvicorn -ErrorAction SilentlyContinue | ForEach-Object { try { $_.Kill() } catch {} }

# Miljövariabler
$env:AUTH_REQUIRED = ($AuthRequired ? 'True' : 'False')
$env:PYTHONPATH = $appDir

$argsList = @('-m', 'uvicorn', 'main:app', '--app-dir', "$appDir", '--host', "$HostName", '--port', "$Port")
if (-not $NoReload) { $argsList += '--reload' }

Write-Host "Startar Uvicorn på http://${HostName}:$Port (AUTH_REQUIRED=$($env:AUTH_REQUIRED))..."
& $py @argsList