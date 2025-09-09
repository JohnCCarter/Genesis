# AI Agent Notification System
# Provides notifications when new messages arrive for AI agents

Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('check', 'monitor', 'stop')]
    [string]$Command,
    
    [string]$Agent = "Cursor",
    [int]$IntervalSeconds = 30,
    [switch]$AutoReply,
    [string]$AutoReplyTemplate = 'ACK from {Agent}: received {id} from {from} ({context})',
    [switch]$Toast,
    [switch]$ToastInstall,
    [switch]$Sound,
    [switch]$OnlyHigh,
    [switch]$Watch,
    [switch]$LogThreads,
    [string]$ThreadsFile = 'AGENT_THREADS.md'
)

$ErrorActionPreference = 'Stop'

# Communication file paths (absolute)
$REPO_ROOT = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$COMM_DIR = Join-Path $REPO_ROOT ".agent-communication"
$MESSAGES_FILE = Join-Path $COMM_DIR "messages.json"
$NOTIFICATION_FILE = Join-Path $COMM_DIR "notifications.json"

function Ensure-BurntToast {
    param([switch]$Install)
    try {
        if (Get-Module -ListAvailable -Name BurntToast) { return $true }
        if (-not $Install) { return $false }
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
        $psRepo = Get-PSRepository -Name 'PSGallery' -ErrorAction SilentlyContinue
        if ($psRepo -and $psRepo.InstallationPolicy -ne 'Trusted') {
            Set-PSRepository -Name 'PSGallery' -InstallationPolicy Trusted -ErrorAction SilentlyContinue | Out-Null
        }
        if (-not (Get-PackageProvider -Name NuGet -ErrorAction SilentlyContinue)) {
            Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
        }
        Install-Module -Name BurntToast -Scope CurrentUser -Force -AllowClobber -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
        if (Get-Module -ListAvailable -Name BurntToast) { return $true }
    } catch { }
    return $false
}

function Show-FallbackToast {
    param(
        [string]$Title,
        [string]$Body
    )
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue | Out-Null
        Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue | Out-Null
        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.Visible = $true
        $ni.BalloonTipTitle = $Title
        $ni.BalloonTipText = $Body
        $ni.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
        $ni.ShowBalloonTip(5000)
        Start-Sleep -Milliseconds 200
        $ni.Dispose()
    } catch {
        # Fallback to console + beep if needed
        Write-Host "[Toast] $Title - $Body" -ForegroundColor Yellow
    }
}

function Send-CommandReplies {
    param(
        [array]$Replies
    )
    if (-not $Replies -or $Replies.Count -eq 0) { return }
    $comm = Join-Path $PSScriptRoot 'agent_communication.ps1'
    foreach ($r in $Replies) {
        try {
            $pri = if ($r.priority) { $r.priority } else { 'normal' }
            $ctx = if ($r.context) { $r.context } else { 'auto-cmd' }
            & $comm send -Message $r.message -To $r.to -From $r.from -Priority $pri -Context $ctx | Out-Null
        } catch { }
    }
}

function Run-AutoCommands {
    param(
        [string]$Agent,
        [array]$Messages
    )
    try {
        $auto = Join-Path $PSScriptRoot 'agent_auto_commands.ps1'
        if (Test-Path -LiteralPath $auto) {
            . $auto
            $replies = AutoCommands-Process -Agent $Agent -Messages $Messages
            Send-CommandReplies -Replies $replies
        }
    } catch { }
}

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
    $json = $Object | ConvertTo-Json -Depth 5
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Acquire-CommLock {
    param([int]$TimeoutMs = 3000)
    $lockPath = Join-Path $COMM_DIR ".comm.lock"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        try {
            if (-not (Test-Path -LiteralPath $COMM_DIR)) {
                New-Item -ItemType Directory -Path $COMM_DIR -Force | Out-Null
            }
            $script:__commLockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        }
        catch {
            if ($sw.ElapsedMilliseconds -ge $TimeoutMs) { break }
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

function Initialize-Notifications {
    if (-not (Test-Path $COMM_DIR)) {
        New-Item -ItemType Directory -Path $COMM_DIR -Force | Out-Null
    }
    
    if (-not (Test-Path $NOTIFICATION_FILE)) {
        @{
            "last_checked"          = @{
                "Cursor" = "1970-01-01T00:00:00Z"
                "Codex"  = "1970-01-01T00:00:00Z"
            }
            "notifications_enabled" = $true
        } | Write-JsonSafe -Path $NOTIFICATION_FILE
    }
}

function Check-NewMessages {
    param(
        [string]$Agent,
        [switch]$All
    )
    
    Initialize-Notifications
    
    if (-not (Test-Path $MESSAGES_FILE)) {
        return @()
    }
    
    Acquire-CommLock
    try {
        $messages = Read-JsonSafe -Path $MESSAGES_FILE
        if (-not $messages) { $messages = @() } else { $messages = @($messages) }
        
        $notifications = Read-JsonSafe -Path $NOTIFICATION_FILE
        $lastChecked = $notifications.last_checked.$Agent
        if (-not $lastChecked) { $lastChecked = (Get-Date).AddDays(-1).ToUniversalTime().ToString('o') }

        if ($All) {
            $newMessages = $messages | Where-Object { $_.to -eq $Agent -and -not $_.read }
        }
        else {
            $lc = [datetime]$lastChecked
            $newMessages = $messages | Where-Object { 
                $_.to -eq $Agent -and 
                ([datetime]$_.timestamp) -gt $lc -and 
                -not $_.read 
            }
        }
        return $newMessages
    }
    finally {
        Release-CommLock
    }
}

function Show-Notification {
    param(
        [string]$Agent,
        [array]$Messages,
        [switch]$Toast,
        [switch]$Sound,
        [switch]$OnlyHigh
    )
    
    if ($Messages.Count -eq 0) {
        return
    }
    
    Write-Host ""
    Write-Host "ðŸ”” NOTIFICATION for $Agent" -ForegroundColor Yellow
    Write-Host "================================" -ForegroundColor Yellow
    Write-Host "You have $($Messages.Count) new message(s)!" -ForegroundColor Cyan
    Write-Host ""
    
    $burntToastReady = $false
    if ($Toast) { $burntToastReady = Ensure-BurntToast -Install:$ToastInstall }

    foreach ($msg in $Messages) {
        $priorityColor = switch ($msg.priority) {
            "high" { "Red" }
            "normal" { "White" }
            "low" { "Gray" }
            default { "White" }
        }
        $isHigh = ($msg.priority -eq 'high' -or $msg.priority -eq 'critical')
        
        Write-Host "From: $($msg.from)" -ForegroundColor $priorityColor
        Write-Host "Priority: $($msg.priority)" -ForegroundColor $priorityColor
        if ($msg.context) {
            Write-Host "Context: $($msg.context)" -ForegroundColor Gray
        }
        Write-Host "Message: $($msg.message)" -ForegroundColor White
        Write-Host "Time: $($msg.timestamp)" -ForegroundColor Gray
        Write-Host "--------------------------------" -ForegroundColor Gray

        if (-not $OnlyHigh -or $isHigh) {
            $title = "${Agent}: $($msg.from) [$($msg.priority)]"
            $body1 = if ($msg.context) { $msg.context } else { "Message" }
            $body2 = $msg.message
            if ($Toast -and $burntToastReady) {
                try {
                    Import-Module BurntToast -ErrorAction SilentlyContinue | Out-Null
                    New-BurntToastNotification -Text $title, $body1, $body2 -Silent:$(! $Sound) | Out-Null
                } catch { }
            } elseif ($Toast) {
                # Use built-in Windows Forms balloon as fallback
                Show-FallbackToast -Title $title -Body ("{0} — {1}" -f $body1, $body2)
                if ($Sound) { try { [console]::Beep(1000, 300) } catch { } }
            } elseif ($Sound) {
                try { [console]::Beep(1000, 300) } catch { }
            }
        }
    }
    
    Write-Host ""
    Write-Host "To read all messages: .\scripts\agent_communication.ps1 read -Agent `"$Agent`"" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Yellow
    Write-Host ""
}

function Update-LastChecked {
    param([string]$Agent)
    
    Initialize-Notifications
    
    Acquire-CommLock
    try {
        $notifications = Read-JsonSafe -Path $NOTIFICATION_FILE
        $notifications.last_checked.$Agent = (Get-Date).ToUniversalTime().ToString('o')
        Write-JsonSafe -Path $NOTIFICATION_FILE -Object $notifications
    }
    finally {
        Release-CommLock
    }
}

function Start-Monitoring {
    param(
        [string]$Agent,
        [int]$IntervalSeconds,
        [switch]$AutoReply,
        [string]$AutoReplyTemplate,
        [switch]$Toast,
        [switch]$Sound,
        [switch]$OnlyHigh,
        [switch]$Watch,
        [switch]$LogThreads,
        [string]$ThreadsFile = 'AGENT_THREADS.md'
    )
    
    Write-Host "ðŸ”” Starting notification monitoring for $Agent" -ForegroundColor Green
    if ($Watch) { Write-Host "Mode: Event-driven (FileSystemWatcher)" -ForegroundColor Gray } else { Write-Host "Checking every $IntervalSeconds seconds..." -ForegroundColor Gray }
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""
    
    try { if ($Watch) { Start-EventWatch -Agent $Agent -AutoReply:$AutoReply -AutoReplyTemplate $AutoReplyTemplate -Toast:$Toast -Sound:$Sound -OnlyHigh:$OnlyHigh -LogThreads:$LogThreads -ThreadsFile $ThreadsFile; return }`n        $first = $true
        while ($true) {
            $newMessages = Check-NewMessages -Agent $Agent -All:([bool]$first)
            
            if ($newMessages.Count -gt 0) {
                Show-Notification -Agent $Agent -Messages $newMessages -Toast:$Toast -Sound:$Sound -OnlyHigh:$OnlyHigh
                if ($LogThreads) { try { Append-ThreadLog -Agent $Agent -Messages $newMessages -ThreadsFile $ThreadsFile } catch { } }
                try { Run-AutoCommands -Agent $Agent -Messages $newMessages } catch { }
                if ($AutoReply) {
                    foreach ($msg in $newMessages) {
                        if ($msg.context -ne 'auto-reply') {
                            try {
                                Send-AutoReply -Agent $Agent -MessageObj $msg -Template $AutoReplyTemplate
                            }
                            catch { }
                        }
                    }
                }
                Update-LastChecked -Agent $Agent
                $first = $false
            }
            
            Start-Sleep -Seconds $IntervalSeconds
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host ""
        Write-Host "ðŸ›‘ Monitoring stopped" -ForegroundColor Yellow
    }
    catch {
        Write-Host ""
        Write-Host "âŒ Error in monitoring: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Send-AutoReply {
    param(
        [string]$Agent,
        [Parameter(Mandatory = $true)]$MessageObj,
        [string]$Template
    )
    $comm = Join-Path $PSScriptRoot 'agent_communication.ps1'
    if (-not (Test-Path -LiteralPath $comm)) { return }
    $text = $Template
    $replacements = @{
        '{Agent}'   = $Agent
        '{id}'      = $MessageObj.id
        '{from}'    = $MessageObj.from
        '{to}'      = $MessageObj.to
        '{context}' = $MessageObj.context
        '{message}' = $MessageObj.message
        '{time}'    = $MessageObj.timestamp
    }
    foreach ($k in $replacements.Keys) { $text = $text -replace [regex]::Escape($k), [string]$replacements[$k] }
    & $comm send -Message $text -To $MessageObj.from -From $Agent -Priority 'low' -Context 'auto-reply' | Out-Null
}

function Append-ThreadLog {
    param(
        [string]$Agent,
        [array]$Messages,
        [string]$ThreadsFile = 'AGENT_THREADS.md'
    )
    if (-not $Messages -or $Messages.Count -eq 0) { return }
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $path = Join-Path $repoRoot $ThreadsFile
    Acquire-CommLock
    try {
        if (-not (Test-Path -LiteralPath $path)) {
            @(
                "# Agent Threads",
                "",
                "Logg över agentdiskussioner och brainstormtrådar.",
                "",
                "---"
            ) | Set-Content -LiteralPath $path -Encoding UTF8
        }
        foreach ($m in $Messages) {
            $isBrain = ($m.context -and ($m.context -like 'brainstorm*')) -or ($m.message -like '/brainstorm*')
            if ($isBrain) {
                $topic = ''
                if ($m.context -and $m.context.StartsWith('brainstorm')) {
                    $parts = $m.context.Split(':',2)
                    if ($parts.Count -ge 2) { $topic = $parts[1].Trim() }
                }
                if (-not $topic) { $topic = 'general' }
                $line = "- [{0}] {1} -> {2} | topic: {3} | {4}" -f $m.timestamp, $m.from, $m.to, $topic, $m.message
                Add-Content -LiteralPath $path -Value $line -Encoding UTF8
            }
        }
    }
    finally {
        Release-CommLock
    }
}

function Start-EventWatch {
    param(
        [string]$Agent,
        [switch]$AutoReply,
        [string]$AutoReplyTemplate,
        [switch]$Toast,
        [switch]$Sound,
        [switch]$OnlyHigh,
        [switch]$LogThreads,
        [string]$ThreadsFile = 'AGENT_THREADS.md'
    )
    Initialize-Notifications
    $script:lastEventAt = Get-Date '1970-01-01T00:00:00Z'
    $fsw = New-Object System.IO.FileSystemWatcher
    $fsw.Path = (Resolve-Path -LiteralPath $COMM_DIR).Path
    $fsw.Filter = 'messages.json'
    $fsw.IncludeSubdirectories = $false
    $fsw.NotifyFilter = [System.IO.NotifyFilters]'FileName, LastWrite, Size'
    $action = {
        $now = Get-Date
        if ($script:lastEventAt) {
            $delta = ($now - $script:lastEventAt).TotalMilliseconds
            if ($delta -lt 600) { return }
        }
        $script:lastEventAt = $now
        try {
            $newMessages = Check-NewMessages -Agent $using:Agent
                    if ($newMessages -and $newMessages.Count -gt 0) {
                        Show-Notification -Agent $using:Agent -Messages $newMessages -Toast:$using:Toast -Sound:$using:Sound -OnlyHigh:$using:OnlyHigh
                        if ($using:LogThreads) { try { Append-ThreadLog -Agent $using:Agent -Messages $newMessages -ThreadsFile $using:ThreadsFile } catch { } }
                        try { Run-AutoCommands -Agent $using:Agent -Messages $newMessages } catch { }
                        if ($using:AutoReply) {
                    foreach ($m in $newMessages) {
                        if ($m.context -ne 'auto-reply') {
                            try { Send-AutoReply -Agent $using:Agent -MessageObj $m -Template $using:AutoReplyTemplate } catch { }
                        }
                    }
                }
                Update-LastChecked -Agent $using:Agent
            }
        } catch { }
    }
    $null = Register-ObjectEvent -InputObject $fsw -EventName Created -Action $action
    $null = Register-ObjectEvent -InputObject $fsw -EventName Changed -Action $action
    $fsw.EnableRaisingEvents = $true
    # Initial sweep
    $initial = Check-NewMessages -Agent $Agent -All
    if ($initial.Count -gt 0) {
        Show-Notification -Agent $Agent -Messages $initial -Toast:$Toast -Sound:$Sound -OnlyHigh:$OnlyHigh
        if ($LogThreads) { try { Append-ThreadLog -Agent $Agent -Messages $initial -ThreadsFile $ThreadsFile } catch { } }
        if ($AutoReply) {
            foreach ($m in $initial) { if ($m.context -ne 'auto-reply') { try { Send-AutoReply -Agent $Agent -MessageObj $m -Template $AutoReplyTemplate } catch { } } }
        }
        Update-LastChecked -Agent $Agent
    }
    while ($true) { Start-Sleep -Seconds 86400 }
}function Stop-Monitoring {
    Write-Host "ðŸ›‘ Stopping all notification monitoring..." -ForegroundColor Yellow
    
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
        $newMessages = Check-NewMessages -Agent $Agent -All
        if ($newMessages.Count -gt 0) {
            Show-Notification -Agent $Agent -Messages $newMessages -Toast:$Toast -Sound:$Sound -OnlyHigh:$OnlyHigh
            if ($LogThreads) { try { Append-ThreadLog -Agent $Agent -Messages $newMessages -ThreadsFile $ThreadsFile } catch { } }
            try { Run-AutoCommands -Agent $Agent -Messages $newMessages } catch { }
            Update-LastChecked -Agent $Agent
        }
        else {
            Write-Host "No new messages for $Agent" -ForegroundColor Green
        }
    }
    "monitor" {
        Start-Monitoring -Agent $Agent -IntervalSeconds $IntervalSeconds -AutoReply:$AutoReply -AutoReplyTemplate $AutoReplyTemplate -Toast:$Toast -Sound:$Sound -OnlyHigh:$OnlyHigh -Watch:$Watch -LogThreads:$LogThreads -ThreadsFile $ThreadsFile
    }
    "stop" {
        Stop-Monitoring
    }
    default {
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  Check:   .\agent_notification.ps1 check -Agent 'Cursor' [-Toast] [-Sound] [-OnlyHigh]" -ForegroundColor Gray
        Write-Host "  Monitor: .\agent_notification.ps1 monitor -Agent 'Cursor' -IntervalSeconds 30 [-Toast] [-Sound] [-OnlyHigh] [-AutoReply]" -ForegroundColor Gray
        Write-Host "  Stop:    .\agent_notification.ps1 stop" -ForegroundColor Gray
    }
}





