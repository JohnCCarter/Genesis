# Genesis Trading Bot - Process Manager
# Hanterar start/stopp av trading bot-processer på ett säkert sätt

param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start",

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# Konfiguration
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "tradingbot-backend"
$ProcessName = "genesis-trading-bot"
$Port = 8000
$LogFile = Join-Path $BackendDir "tradingbot.log"

# Funktioner
function Write-Status {
    param([string]$Message, [string]$Type = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Type) {
        "SUCCESS" { "Green" }
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        default { "White" }
    }
    Write-Host "[$timestamp] $Message" -ForegroundColor $color
}

function Get-TradingBotProcesses {
    # Hitta alla python-processer som kör uvicorn för vår trading bot
    $processes = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        try {
            $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            # Kontrollera om det är en uvicorn-process som kör main:app
            return $cmdline -like "*uvicorn*" -and $cmdline -like "*main:app*"
        }
        catch {
            return $false
        }
    }
    return $processes
}

function Stop-TradingBot {
    Write-Status "Stoppar Genesis Trading Bot..." "INFO"

    $processes = Get-TradingBotProcesses
    if ($processes) {
        Write-Status "Hittade $($processes.Count) aktiva processer" "INFO"

        foreach ($process in $processes) {
            try {
                Write-Status "Stoppar process $($process.Id)..." "INFO"
                $process.Kill()
                Start-Sleep -Seconds 2

                if ($process.HasExited) {
                    Write-Status "Process $($process.Id) stoppad" "SUCCESS"
                }
                else {
                    Write-Status "Process $($process.Id) kunde inte stoppas, använder Force" "WARNING"
                    Stop-Process -Id $process.Id -Force
                }
            }
            catch {
                Write-Status "Fel vid stopp av process $($process.Id): $($_.Exception.Message)" "ERROR"
            }
        }

        # Vänta lite extra för att säkerställa att alla processer är stängda
        Start-Sleep -Seconds 3

        # Kontrollera att alla är stängda
        $remaining = Get-TradingBotProcesses
        if ($remaining) {
            Write-Status "Varning: $($remaining.Count) processer kvarstår" "WARNING"
        }
        else {
            Write-Status "Alla trading bot-processer stoppade" "SUCCESS"
        }
    }
    else {
        Write-Status "Inga aktiva trading bot-processer hittades" "INFO"
    }
}

function Start-TradingBot {
    Write-Status "Startar Genesis Trading Bot..." "INFO"

    # Kontrollera om redan körs
    $existing = Get-TradingBotProcesses
    if ($existing -and -not $Force) {
        Write-Status "Trading bot körs redan! Använd -Force för att starta om" "WARNING"
        return
    }

    # Stoppa befintliga om Force
    if ($Force -and $existing) {
        Stop-TradingBot
        Start-Sleep -Seconds 2
    }

    # Kontrollera att backend-katalogen finns
    if (-not (Test-Path $BackendDir)) {
        Write-Status "Backend-katalog hittades inte: $BackendDir" "ERROR"
        return
    }

    # Aktivera virtual environment (.venv_clean prioriteras, fallback till .venv)
    $venvPathClean = Join-Path $ProjectRoot ".venv_clean\Scripts\Activate.ps1"
    $venvPath = if (Test-Path $venvPathClean) { $venvPathClean } else { Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1" }
    if (-not (Test-Path $venvPath)) {
        Write-Status "Virtual environment hittades inte: $venvPath" "ERROR"
        return
    }

    try {
        # Starta trading bot i bakgrunden
        $startCmd = @"
& "$venvPath"
cd "$BackendDir"
`$env:PYTHONPATH = "$BackendDir"
uvicorn main:app --reload --host 0.0.0.0 --port $Port
"@

        Write-Status "Startar uvicorn på port $Port..." "INFO"

        # Starta process i bakgrunden med unik identifierare
        $job = Start-Job -ScriptBlock {
            param($cmd, $backendDir, $logFile)

            # Ändra till backend-katalogen
            Set-Location $backendDir

            # Kör kommandot och logga output
            try {
                Invoke-Expression $cmd 2>&1 | Tee-Object -FilePath $logFile
            }
            catch {
                $errorMsg = $_.Exception.Message
                Add-Content -Path $logFile -Value "ERROR: $errorMsg"
                throw $_
            }

        } -ArgumentList $startCmd, $BackendDir, $LogFile

        # Vänta lite och kontrollera job status
        Start-Sleep -Seconds 3
        $jobStatus = Get-Job -Id $job.Id
        if ($jobStatus.State -eq "Failed") {
            $errorOutput = Receive-Job -Id $job.Id -ErrorAction SilentlyContinue
            Write-Status "Job failed: $errorOutput" "ERROR"
        }

        # Vänta lite för att processen ska starta
        Start-Sleep -Seconds 5

        # Kontrollera att processen startade
        $processes = Get-TradingBotProcesses
        if ($processes) {
            Write-Status "Trading bot startad! Processer: $($processes.Count)" "SUCCESS"
            Write-Status "Dashboard: http://localhost:$Port" "INFO"
            Write-Status "API: http://localhost:$Port/docs" "INFO"
            Write-Status "Logg: $LogFile" "INFO"
        }
        else {
            Write-Status "Varning: Ingen process hittades efter start" "WARNING"
        }

    }
    catch {
        Write-Status "Fel vid start av trading bot: $($_.Exception.Message)" "ERROR"
    }
}

function Show-Status {
    Write-Status "=== Genesis Trading Bot Status ===" "INFO"

    $processes = Get-TradingBotProcesses
    if ($processes) {
        Write-Status "Status: KÖR" "SUCCESS"
        Write-Status "Aktiva processer: $($processes.Count)" "INFO"

        foreach ($process in $processes) {
            $uptime = (Get-Date) - $process.StartTime
            Write-Status "  Process $($process.Id): $($process.CPU)s CPU, $($uptime.ToString('hh\:mm\:ss')) uptime" "INFO"
        }

        Write-Status "Dashboard: http://localhost:$Port" "INFO"
        Write-Status "API: http://localhost:$Port/docs" "INFO"
    }
    else {
        Write-Status "Status: STOPPAD" "WARNING"
        Write-Status "Inga aktiva processer" "INFO"
    }

    # Visa senaste logg-rader
    if (Test-Path $LogFile) {
        Write-Status "=== Senaste logg-rader ===" "INFO"
        Get-Content $LogFile -Tail 5 | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Gray
        }
    }
}

# Huvudlogik
switch ($Action.ToLower()) {
    "start" {
        Start-TradingBot
    }
    "stop" {
        Stop-TradingBot
    }
    "restart" {
        Write-Status "Startar om Genesis Trading Bot..." "INFO"
        Stop-TradingBot
        Start-Sleep -Seconds 3
        Start-TradingBot
    }
    "status" {
        Show-Status
    }
    default {
        Write-Status "Ogiltig action: $Action" "ERROR"
        Write-Status "Använd: start, stop, restart, status" "INFO"
    }
}
