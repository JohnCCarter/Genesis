# AI Agent Communication System
# Enables direct communication between Cursor AI and Codex Agent

Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('send', 'read', 'status', 'clear', 'update-status')]
    [string]$Command,
    
    [Parameter(Position = 1)]
    [string]$Message,
    
    [string]$To = "Codex",
    [string]$From = "Cursor",
    [string]$Priority = "normal",
    [string]$Context = "",
    
    # Preferred for read/clear/update-status
    [string]$Agent,

    # Only for update-status
    [ValidateSet('available','busy','offline')]
    [string]$Status,
    [string]$Task = ""
)

$ErrorActionPreference = 'Stop'

# Communication file paths
$COMM_DIR = ".agent-communication"
$MESSAGES_FILE = "$COMM_DIR\messages.json"
$STATUS_FILE = "$COMM_DIR\status.json"

function Acquire-CommLock {
    param([int]$TimeoutMs = 5000)
    $lockPath = Join-Path $COMM_DIR ".comm.lock"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        try {
            if (-not (Test-Path -LiteralPath $COMM_DIR)) {
                New-Item -ItemType Directory -Force -Path $COMM_DIR | Out-Null
            }
            $script:__commLockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        } catch {
            if ($sw.ElapsedMilliseconds -ge $TimeoutMs) { throw "Communication lock timeout ($TimeoutMs ms)." }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Release-CommLock {
    try {
        if ($script:__commLockStream) {
            $script:__commLockStream.Close()
            $script:__commLockStream.Dispose()
            $script:__commLockStream = $null
        }
    } catch { }
}

function Initialize-Communication {
    if (-not (Test-Path $COMM_DIR)) {
        New-Item -ItemType Directory -Path $COMM_DIR -Force | Out-Null
    }
    
    if (-not (Test-Path $MESSAGES_FILE)) {
        @() | ConvertTo-Json -Depth 3 | Out-File -FilePath $MESSAGES_FILE -Encoding UTF8
    }
    
    if (-not (Test-Path $STATUS_FILE)) {
        @{
            "Cursor" = @{
                "status"       = "available"
                "last_seen"    = (Get-Date).ToUniversalTime().ToString('o')
                "current_task" = ""
            }
            "Codex"  = @{
                "status"       = "available"
                "last_seen"    = (Get-Date).ToUniversalTime().ToString('o')
                "current_task" = ""
            }
        } | ConvertTo-Json -Depth 3 | Out-File -FilePath $STATUS_FILE -Encoding UTF8
    }
}

function Send-Message {
    param(
        [string]$To,
        [string]$From,
        [string]$Message,
        [string]$Priority,
        [string]$Context
    )
    
    Initialize-Communication
    
    Acquire-CommLock
    try {
        $messages = Get-Content $MESSAGES_FILE -Raw | ConvertFrom-Json
        if (-not $messages) { $messages = @() } else { $messages = @($messages) }
    
        $newMessage = @{
            "id"        = [System.Guid]::NewGuid().ToString()
            "timestamp" = (Get-Date).ToUniversalTime().ToString('o')
            "from"      = $From
            "to"        = $To
            "message"   = $Message
            "priority"  = $Priority
            "context"   = $Context
            "read"      = $false
        }
    
        $messages += $newMessage
    
    # Keep only last 50 messages
        if ($messages.Count -gt 50) {
            $messages = @($messages | Select-Object -Last 50)
        }
    
        @($messages) | ConvertTo-Json -Depth 3 | Out-File -FilePath $MESSAGES_FILE -Encoding UTF8
    }
    finally {
        Release-CommLock
    }
    
    try { Update-Status -Agent $From -Status 'available' -Task $Task } catch { }
    
    Write-Host "Message sent to $To" -ForegroundColor Green
    Write-Host "ID: $($newMessage.id)" -ForegroundColor Gray
}

function Read-Messages {
    param([string]$Agent)
    
    Initialize-Communication

    Acquire-CommLock
    try {
        $messages = Get-Content $MESSAGES_FILE -Raw | ConvertFrom-Json
        if (-not $messages) { 
            Write-Host "No messages found" -ForegroundColor Yellow
            return 
        }
        $messages = @($messages)

        $unreadMessages = $messages | Where-Object { $_.to -eq $Agent -and -not $_.read }
        
        if (-not $unreadMessages -or $unreadMessages.Count -eq 0) {
            Write-Host "No unread messages for ${Agent}" -ForegroundColor Yellow
            return
        }
        
        Write-Host "Unread messages for ${Agent}:" -ForegroundColor Cyan
        Write-Host "================================" -ForegroundColor Cyan
        
        foreach ($msg in $unreadMessages) {
            $priorityColor = switch ($msg.priority) {
                "high" { "Red" }
                "normal" { "White" }
                "low" { "Gray" }
                default { "White" }
            }
            
            Write-Host "[$($msg.timestamp)] From: $($msg.from)" -ForegroundColor $priorityColor
            Write-Host "Priority: $($msg.priority)" -ForegroundColor $priorityColor
            if ($msg.context) {
                Write-Host "Context: $($msg.context)" -ForegroundColor Gray
            }
            Write-Host "Message: $($msg.message)" -ForegroundColor White
            Write-Host "ID: $($msg.id)" -ForegroundColor Gray
            Write-Host "--------------------------------" -ForegroundColor Gray
            
            # Mark as read
            $msg.read = $true
        }
        
        # Save updated messages
        @($messages) | ConvertTo-Json -Depth 3 | Out-File -FilePath $MESSAGES_FILE -Encoding UTF8
    }
    finally {
        Release-CommLock
    }
}

function Get-Status {
    Initialize-Communication

    Acquire-CommLock
    try {
        $status = Get-Content $STATUS_FILE -Raw | ConvertFrom-Json
        
        Write-Host "Agent Status:" -ForegroundColor Cyan
        Write-Host "=============" -ForegroundColor Cyan
        
        foreach ($agent in $status.PSObject.Properties) {
            $agentName = $agent.Name
            $agentData = $agent.Value
            
            $statusColor = switch ($agentData.status) {
                "available" { "Green" }
                "busy" { "Yellow" }
                "offline" { "Red" }
                default { "White" }
            }
            
            Write-Host "${agentName}:" -ForegroundColor White
            Write-Host "  Status: $($agentData.status)" -ForegroundColor $statusColor
            Write-Host "  Last seen: $($agentData.last_seen)" -ForegroundColor Gray
            if ($agentData.current_task) {
                Write-Host "  Current task: $($agentData.current_task)" -ForegroundColor Cyan
            }
            Write-Host ""
        }
    }
    finally {
        Release-CommLock
    }
}

function Clear-Messages {
    param([string]$Agent)

    Initialize-Communication
    
    Acquire-CommLock
    try {
        if ($Agent) {
            $messages = Get-Content $MESSAGES_FILE -Raw | ConvertFrom-Json
            $messages = if ($messages) { @($messages) } else { @() }
            $remaining = $messages | Where-Object { $_.to -ne $Agent }
            @($remaining) | ConvertTo-Json -Depth 3 | Out-File -FilePath $MESSAGES_FILE -Encoding UTF8
            Write-Host "Cleared messages for ${Agent}" -ForegroundColor Green
        } else {
            @() | ConvertTo-Json -Depth 3 | Out-File -FilePath $MESSAGES_FILE -Encoding UTF8
            Write-Host "All messages cleared" -ForegroundColor Green
        }
    }
    finally {
        Release-CommLock
    }
}

function Update-Status {
    param(
        [string]$Agent,
        [string]$Status,
        [string]$Task = ""
    )
    
    Initialize-Communication
    
    Acquire-CommLock
    try {
        $statusData = Get-Content $STATUS_FILE -Raw | ConvertFrom-Json
        
        if ($statusData.$Agent) {
            if ($Status) { $statusData.$Agent.status = $Status }
            $statusData.$Agent.last_seen = (Get-Date).ToUniversalTime().ToString('o')
            if ($Task) { $statusData.$Agent.current_task = $Task }
        }
        
        $statusData | ConvertTo-Json -Depth 3 | Out-File -FilePath $STATUS_FILE -Encoding UTF8
    }
    finally {
        Release-CommLock
    }
}

# Main execution
switch ($Command) {
    "send" {
        if (-not $Message) {
            Write-Host "Error: Message is required for send command" -ForegroundColor Red
            exit 1
        }
        Send-Message -To $To -From $From -Message $Message -Priority $Priority -Context $Context
    }
    "read" {
        $target = if ($Agent) { $Agent } elseif ($To) { $To } else { $From }
        Read-Messages -Agent $target
    }
    "status" {
        Get-Status
    }
    "clear" {
        Clear-Messages -Agent $Agent
    }
    "update-status" {
        $target = if ($Agent) { $Agent } elseif ($From) { $From } else { 'Codex' }
        if (-not $Status -and -not $Task) {
            Update-Status -Agent $target -Status $null -Task $null
        } else {
            Update-Status -Agent $target -Status $Status -Task $Task
        }
    }
    default {
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  Send:   .\agent_communication.ps1 send -Message 'Hello' -To 'Codex' -From 'Cursor' -Priority 'high' -Context 'trading optimization'" -ForegroundColor Gray
        Write-Host "  Read:   .\agent_communication.ps1 read -Agent 'Cursor'" -ForegroundColor Gray
        Write-Host "  Status: .\agent_communication.ps1 status" -ForegroundColor Gray
        Write-Host "  Clear:  .\agent_communication.ps1 clear -Agent 'Cursor'  # omit -Agent to clear all" -ForegroundColor Gray
        Write-Host "  Update: .\agent_communication.ps1 update-status -Agent 'Codex' -Status 'busy' -Task 'Editing start script'  # heartbeat if no args" -ForegroundColor Gray
    }
}
