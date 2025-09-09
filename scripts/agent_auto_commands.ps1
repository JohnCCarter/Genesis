param()

function Get-RepoRoot { return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }

function Get-GitInfo {
    $root = Get-RepoRoot
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { return [pscustomobject]@{ hasGit=$false; branch=$null; commit=$null; short=$null; remote=$null; path=$root } }
    try {
        Push-Location $root
        $branch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim()
        $commit = (git rev-parse HEAD 2>$null).Trim()
        $short  = (git rev-parse --short HEAD 2>$null).Trim()
        $remote = (git config --get remote.origin.url 2>$null).Trim()
        Pop-Location
        return [pscustomobject]@{ hasGit=$true; branch=$branch; commit=$commit; short=$short; remote=$remote; path=$root }
    } catch {
        try { Pop-Location } catch {}
        return [pscustomobject]@{ hasGit=$false; branch=$null; commit=$null; short=$null; remote=$null; path=$root }
    }
}

function AutoCommands-Process {
    param([string]$Agent,[array]$Messages)
    $out = @()
    if (-not $Messages) { return $out }

    function Reply($to,$from,$message,$priority='normal',$context='auto-cmd') { [pscustomobject]@{ to=$to; from=$from; message=$message; priority=$priority; context=$context } }

    function Get-AgentStatusSummary {
        $root = Get-RepoRoot
        $statusPath = Join-Path (Join-Path $root '.agent-communication') 'status.json'
        if (-not (Test-Path -LiteralPath $statusPath)) { return 'No status.json found' }
        try {
            $raw = Get-Content -LiteralPath $statusPath -Raw -ErrorAction Stop
            $raw = $raw -replace "`0", ''
            $obj = $raw | ConvertFrom-Json
            $lines = @()
            foreach ($p in $obj.PSObject.Properties) {
                $a = $p.Name; $v = $p.Value
                $task = if ($v.current_task) { ", task=" + $v.current_task } else { '' }
                $lines += ("{0}: status={1}, last_seen={2}{3}" -f $a, $v.status, $v.last_seen, $task)
            }
            ($lines -join '; ')
        } catch { 'Failed to read status.json' }
    }

    function Lock-Target([string]$path,[string]$by,[string]$reason='auto-cmd lock') {
        $lock = Join-Path $PSScriptRoot 'agent_lock.ps1'
        if (-not (Test-Path -LiteralPath $lock)) { return 'Lock script missing' }
        try { & $lock lock -Path $path -By $by -Reason $reason -Notify | Out-Null; "LOCKED: $path" } catch { "LOCK FAILED: $path - $($_.Exception.Message)" }
    }

    function Unlock-Target([string]$path,[string]$by,[string]$reason='auto-cmd unlock') {
        $lock = Join-Path $PSScriptRoot 'agent_lock.ps1'
        if (-not (Test-Path -LiteralPath $lock)) { return 'Unlock script missing' }
        try { & $lock unlock -Path $path -By $by -Notify | Out-Null; "UNLOCKED: $path" } catch { "UNLOCK FAILED: $path - $($_.Exception.Message)" }
    }

    function Plan-Add([string]$by,[string]$text) {
        $root = Get-RepoRoot
        $planPath = Join-Path $root 'AGENT_PLAN.md'
        $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $line = "- [$stamp] ${by}: $text"
        try { Add-Content -LiteralPath $planPath -Value $line -Encoding UTF8; "PLAN+ $text" } catch { "PLAN FAILED: $($_.Exception.Message)" }
    }

    foreach ($m in $Messages) {
        $t = ($m.message | Out-String).Trim().ToLowerInvariant()
        $ctx = ($m.context | Out-String).Trim().ToLowerInvariant()
        $isBranch = ($ctx -eq 'branch-query') -or $t.StartsWith('/branch') -or ($t -like '*branch*' -and $t -like '*commit*')
        if ($isBranch) {
            $gi = Get-GitInfo
            if ($gi.hasGit -and $gi.branch -and $gi.commit) { $remoteVal = if ($gi.remote) { $gi.remote } else { 'n/a' }; $msg = "Branch: {0} | Commit: {1} ({2}) | Remote: {3}" -f $gi.branch, $gi.commit, $gi.short, $remoteVal }
            else { $msg = "Branchinfo: Git ej tillgängligt eller repo ej initialiserat (path: {0})." -f $gi.path }
            $out += (Reply -to $m.from -from $Agent -message $msg -priority 'normal' -context 'branch-info')
            continue
        }
        if ($t.StartsWith('/help')) { $msg = '/help; /branch - branch/commit/remote; /status - agentstatus; /lock <path>; /unlock <path>; /plan add <text>'; $out += (Reply -to $m.from -from $Agent -message $msg -priority 'low' -context 'auto-help'); continue }
        if ($t.StartsWith('/status')) { $summary = Get-AgentStatusSummary; $out += (Reply -to $m.from -from $Agent -message $summary -priority 'normal' -context 'auto-status'); continue }
        if ($t.StartsWith('/lock ')) { $path = ($m.message.Substring(6)).Trim(); $res = Lock-Target -path $path -by $Agent -reason 'auto-cmd lock'; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-lock'); continue }
        if ($t.StartsWith('/unlock ')) { $path = ($m.message.Substring(8)).Trim(); $res = Unlock-Target -path $path -by $Agent -reason 'auto-cmd unlock'; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-unlock'); continue }
        if ($t.StartsWith('/plan add ')) { $text = ($m.message.Substring(10)).Trim(); $res = Plan-Add -by $Agent -text $text; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-plan'); continue }
    }
    return $out
}
