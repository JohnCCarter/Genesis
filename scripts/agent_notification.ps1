# AI Agent Notification System
# Provides notifications when new messages arrive for AI agents

Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('check','monitor','stop')]
    [string]$Command,
    
    [string]$Agent = "Cursor",
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'

# Communication file paths
$COMM_DIR = ".agent-communication"
$MESSAGES_FILE = "$COMM_DIR\messages.json"
$NOTIFICATION_FILE = "$COMM_DIR\notifications.json"

function Initialize-Notifications {
    if (-not (Test-Path $COMM_DIR)) {
        New-Item -ItemType Directory -Path $COMM_DIR -Force | Out-Null
    }
    
    if (-not (Test-Path $NOTIFICATION_FILE)) {
        @{
            "last_checked" = @{
                "Cursor" = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
                "Codex" = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
            }
            "notifications_enabled" = $true
        } | ConvertTo-Json -Depth 3 | Out-File -FilePath $NOTIFICATION_FILE -Encoding UTF8
    }
}

function Check-NewMessages {
    param([string]$Agent)
    
    Initialize-Notifications
    
    if (-not (Test-Path $MESSAGES_FILE)) {
        return @()
    }
    
    $messages = Get-Content $MESSAGES_FILE | ConvertFrom-Json
    if (-not $messages) { $messages = @() } else { $messages = @($messages) }
    
    $notifications = Get-Content $NOTIFICATION_FILE | ConvertFrom-Json
    $lastChecked = $notifications.last_checked.$Agent
    
    if (-not $lastChecked) {
        $lastChecked = (Get-Date).AddDays(-1).ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
    
    $newMessages = $messages | Where-Object { 
        $_.to -eq $Agent -and 
        $_.timestamp -gt $lastChecked -and 
        -not $_.read 
    }
    
    return $newMessages
}

function Show-Notification {
    param(
        [string]$Agent,
        [array]$Messages
    )
    
    if ($Messages.Count -eq 0) {
        return
    }
    
    Write-Host ""
    Write-Host "🔔 NOTIFICATION for $Agent" -ForegroundColor Yellow
    Write-Host "================================" -ForegroundColor Yellow
    Write-Host "You have $($Messages.Count) new message(s)!" -ForegroundColor Cyan
    Write-Host ""
    
    foreach ($msg in $Messages) {
        $priorityColor = switch ($msg.priority) {
            "high" { "Red" }
            "normal" { "White" }
            "low" { "Gray" }
            default { "White" }
        }
        
        Write-Host "From: $($msg.from)" -ForegroundColor $priorityColor
        Write-Host "Priority: $($msg.priority)" -ForegroundColor $priorityColor
        if ($msg.context) {
            Write-Host "Context: $($msg.context)" -ForegroundColor Gray
        }
        Write-Host "Message: $($msg.message)" -ForegroundColor White
        Write-Host "Time: $($msg.timestamp)" -ForegroundColor Gray
        Write-Host "--------------------------------" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "To read all messages: .\scripts\agent_communication.ps1 read -From `"$Agent`"" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Yellow
    Write-Host ""
}

function Update-LastChecked {
    param([string]$Agent)
    
    Initialize-Notifications
    
    $notifications = Get-Content $NOTIFICATION_FILE | ConvertFrom-Json
    $notifications.last_checked.$Agent = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    
    $notifications | ConvertTo-Json -Depth 3 | Out-File -FilePath $NOTIFICATION_FILE -Encoding UTF8
}

function Start-Monitoring {
    param(
        [string]$Agent,
        [int]$IntervalSeconds
    )
    
    Write-Host "🔔 Starting notification monitoring for $Agent" -ForegroundColor Green
    Write-Host "Checking every $IntervalSeconds seconds..." -ForegroundColor Gray
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""
    
    try {
        while ($true) {
            $newMessages = Check-NewMessages -Agent $Agent
            
            if ($newMessages.Count -gt 0) {
                Show-Notification -Agent $Agent -Messages $newMessages
                Update-LastChecked -Agent $Agent
            }
            
            Start-Sleep -Seconds $IntervalSeconds
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host ""
        Write-Host "🛑 Monitoring stopped" -ForegroundColor Yellow
    }
    catch {
        Write-Host ""
        Write-Host "❌ Error in monitoring: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Stop-Monitoring {
    Write-Host "🛑 Stopping all notification monitoring..." -ForegroundColor Yellow
    
    # Kill any running monitoring processes
    $processes = Get-Process | Where-Object { 
        $_.ProcessName -eq "powershell" -and 
        $_.CommandLine -like "*agent_notification.ps1*" 
    }
    
    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.Id -Force
            Write-Host "Stopped monitoring process $($process.Id)" -ForegroundColor Gray
        }
        catch {
            Write-Host "Could not stop process $($process.Id): $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# Main execution
switch ($Command) {
    "check" {
        $newMessages = Check-NewMessages -Agent $Agent
        if ($newMessages.Count -gt 0) {
            Show-Notification -Agent $Agent -Messages $newMessages
            Update-LastChecked -Agent $Agent
        } else {
            Write-Host "No new messages for $Agent" -ForegroundColor Green
        }
    }
    "monitor" {
        Start-Monitoring -Agent $Agent -IntervalSeconds $IntervalSeconds
    }
    "stop" {
        Stop-Monitoring
    }
    default {
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  Check:   .\agent_notification.ps1 check -Agent 'Cursor'" -ForegroundColor Gray
        Write-Host "  Monitor: .\agent_notification.ps1 monitor -Agent 'Cursor' -IntervalSeconds 30" -ForegroundColor Gray
        Write-Host "  Stop:    .\agent_notification.ps1 stop" -ForegroundColor Gray
    }
}
