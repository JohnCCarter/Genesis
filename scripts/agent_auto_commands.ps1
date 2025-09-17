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

    # Contracts helpers (used by /contract and free-text fallbacks)
    function Contract-Exec($args) {
        try {
            $contracts = Join-Path $PSScriptRoot 'agent_contracts.ps1'
            if (-not (Test-Path -LiteralPath $contracts)) { return 'Contracts script missing' }
            $res = & $contracts @args 2>&1 | Out-String
            return ($res.Trim())
        } catch { return "Contract error: $($_.Exception.Message)" }
    }
    function Parse-KV($s) {
        $dict = @{}
        $rx = [regex]'(\w+)=\"([^\"]*)\"|(\w+)=([^\s]+)'
        $ms = $rx.Matches($s)
        foreach ($m2 in $ms) {
            if ($m2.Groups[1].Success) { $dict[$m2.Groups[1].Value] = $m2.Groups[2].Value }
            elseif ($m2.Groups[3].Success) { $dict[$m2.Groups[3].Value] = $m2.Groups[4].Value }
        }
        return $dict
    }
    function Parse-ProposedId($text) {
        if (-not $text) { return $null }
        $m = [regex]::Match($text, 'PROPOSED\s+([0-9a-fA-F\-]{36})')
        if ($m.Success) { return $m.Groups[1].Value }
        return $null
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
        if ($t.StartsWith('/help')) { $msg = '/help; /branch - branch/commit/remote; /status - agentstatus; /lock <path>; /unlock <path>; /plan add <text>; /contract help'; $out += (Reply -to $m.from -from $Agent -message $msg -priority 'low' -context 'auto-help'); continue }
        if ($t.StartsWith('/status')) { $summary = Get-AgentStatusSummary; $out += (Reply -to $m.from -from $Agent -message $summary -priority 'normal' -context 'auto-status'); continue }
        if ($t.StartsWith('/lock ')) { $path = ($m.message.Substring(6)).Trim(); $res = Lock-Target -path $path -by $Agent -reason 'auto-cmd lock'; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-lock'); continue }
        if ($t.StartsWith('/unlock ')) { $path = ($m.message.Substring(8)).Trim(); $res = Unlock-Target -path $path -by $Agent -reason 'auto-cmd unlock'; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-unlock'); continue }
        if ($t.StartsWith('/plan add ')) { $text = ($m.message.Substring(10)).Trim(); $res = Plan-Add -by $Agent -text $text; $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-plan'); continue }

        # --- Contract commands ---
        if ($t.StartsWith('/contract')) {
            $parts = $t.Split(' ',3,[System.StringSplitOptions]::RemoveEmptyEntries)
            $verb = if ($parts.Length -ge 2) { $parts[1] } else { 'help' }
            $rest = if ($parts.Length -ge 3) { $parts[2] } else { '' }
            if ($verb -eq 'help') {
                $msg = @(
                    '/contract propose title="..." to=Codex ttl=120 hb=60',
                    '/contract accept id=<id>',
                    '/contract start id=<id> lock=path/to/file',
                    '/contract heartbeat id=<id> note="..."',
                    '/contract complete id=<id> result="..."',
                    '/contract fail id=<id> reason="..."',
                    '/contract list [agent=Codex] [status=in_progress]',
                    '/contract show id=<id>'
                ) -join '; '
                $out += (Reply -to $m.from -from $Agent -message $msg -priority 'low' -context 'auto-contract-help')
                continue
            }
            $kv = Parse-KV $rest
            $args = @('-Command', $verb, '-From', $Agent)
            switch ($verb) {
                'propose' {
                    # Proposals originate from the sender ($m.from) to the local agent ($Agent)
                    $to = $Agent
                    $fromSender = $m.from
                    $title = $kv['title']
                    $ttl = if ($kv['ttl']) { [int]$kv['ttl'] } else { 120 }
                    $hb = if ($kv['hb']) { [int]$kv['hb'] } else { 60 }
                    if (-not $title) { $out += (Reply -to $m.from -from $Agent -message 'Missing title' -priority 'high' -context 'auto-contract'); continue }
                    $args = @('-Command', 'propose', '-From', $fromSender, '-To', $to, '-Title', $title, '-TTLMinutes', $ttl, '-HeartbeatSec', $hb)
                }
                'accept' { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']) }
                'start'  { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']); if ($kv['lock']) { $args += @('-Lock',$kv['lock']) } }
                'heartbeat' { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']); if ($kv['note']) { $args += @('-Note',$kv['note']) } }
                'complete' { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']); if ($kv['result']) { $args += @('-Result',$kv['result']) } }
                'fail'     { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']); if ($kv['reason']) { $args += @('-Reason',$kv['reason']) } }
                'list'     { if ($kv['agent']) { $args += @('-Agent',$kv['agent']) }; if ($kv['status']) { $args += @('-Status',$kv['status']) } }
                'show'     { if (-not $kv['id']) { $out += (Reply -to $m.from -from $Agent -message 'Missing id' -priority 'high' -context 'auto-contract'); continue }; $args += @('-Id',$kv['id']) }
                default    { $out += (Reply -to $m.from -from $Agent -message 'Unknown /contract verb' -priority 'low' -context 'auto-contract'); continue }
            }
            $res = Contract-Exec -args $args
            # Auto-accept + start for trusted senders when we receive a /contract propose
            if ($verb -eq 'propose') {
                $newId = Parse-ProposedId $res
                $trusted = ($m.from -in @('Cursor','Codex'))
                if ($newId -and $trusted) {
                    $a1 = Contract-Exec -args @('-Command','accept','-From',$Agent,'-Id',$newId)
                    $a2 = Contract-Exec -args @('-Command','start','-From',$Agent,'-Id',$newId)
                    $res = "$res; $a1; $a2"
                }
            }
            $out += (Reply -to $m.from -from $Agent -message $res -priority 'normal' -context 'auto-contract')
            continue
        }

        # --- Free-text fallbacks (light intent detection) ---
        $handled = $false
        # Dashboard/layout discussion
        if ($ctx -eq 'dashboard-layout-discussion' -or ($t -match '\b(layout|dashboard|grid|panel)\b')) {
            $suggest = 'Förslag: 12-col grid, panel-templates (min/max-height), spara layout (user+scope) i backend, snabbfilter i toppbar.'
            # Propose a contract from local agent to sender
            $p = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Improve dashboard layout','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$suggest | $p") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Ledger/missing modules support
        elseif ($ctx -eq 'fixing_missing_modules' -or ($t -match '\bledger\b')) {
            $suggest2 = 'Jag kan ta LedgerService + history-koppling. Startar kontrakt.'
            $p2 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Implementera ledger pipeline','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$suggest2 | $p2") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Regime/signal fel och indikatorproblem
        elseif ($t -match '\b(regime|signal(er)?|adx|ema_z|unified signal)\b') {
            $msg = 'Regime/signal: Jag kan patcha UnifiedSignalService att skicka cfg till detect_regime och verifiera indikatorer. Initierar kontrakt?'
            $p3 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Fixa regime-konfig och signal-pipeline','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p3") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Prestanda/latens/tidsgräns problem
        elseif ($t -match '\b(långsam|latens|latency|timeout|seg|trög|hänger|time out)\b' -or $t -like '*slow*request*') {
            $msg = 'Prestanda: Jag kan analysera långsamma endpoints, föreslå cache/TTL-justeringar och lägga till mätpunkter.'
            $p4 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Utred långsamma endpoints och caching','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p4") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # WebSocket/token/autentisering
        elseif ($t -match '\b(websocket|socket\.io|ws[- ]?token|401|403|unauthor|forbidden|connect)\b') {
            $msg = 'WS/Auth: Jag kan verifiera ws-token generering, scope=read, och WS_CONNECT_ON_START-flaggor samt klientanslutning.'
            $p5 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Granska WS-anslutning och autentisering','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p5") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Nonce-fel / 500 från privata endpoints
        elseif ($t -match '\bnonce\b' -or $t -like '*500 Internal Server Error*trades/hist*') {
            $msg = 'Nonce/API: Jag kan granska ExchangeClient.signed_request och återförsökshantering vid nonce/500.'
            $p6 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Stabilisera nonce/REST-återförsök','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p6") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Teckenkodning/loggproblem
        elseif ($t -match '\b(unicode|utf-8|cp1252|teckenkod|encoding)\b') {
            $msg = 'Encoding: Jag kan normalisera loggutskrifter och säkerställa UTF-8 i konsol/fil.'
            $p7 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Åtgärda logg-encoding och symboler','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p7") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Feature-flaggor
        elseif ($t -match '\b(feature flag|validation_on_start|ws_connect_on_start|ws_strategy_enabled)\b') {
            $msg = 'Feature-flaggor: Jag kan uppdatera strategiflaggor (validation_on_start, ws_connect_on_start, ws_strategy_enabled) och bekräfta status.'
            $p8 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Justera strategi/feature-flaggor','-TTLMinutes',60,'-HeartbeatSec',30)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p8") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Risk/Guards
        elseif ( ($ctx -like 'risk*') -or ( ($t -match '\brisk\b') -and ($t -match '\bguards?\b') ) ) {
            $msg = 'Risk/Guards: Jag kan granska guard-regler, thresholds, /api/v2/risk/* endpoints och notifieringar.'
            $p9 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Revidera risk guards och notifieringar','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p9") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Refresh Manager
        elseif ($t -match '\brefresh[- ]manager\b') {
            $msg = 'RefreshManager: Jag kan analysera schemaläggning, TTL, concurrency och förbättra refresh-logik.'
            $p10 = Contract-Exec -args @('-Command','propose','-From',$Agent,'-To',$m.from,'-Title','Optimera RefreshManager scheman och TTL','-TTLMinutes',120,'-HeartbeatSec',60)
            $out += (Reply -to $m.from -from $Agent -message ("$msg | $p10") -priority 'normal' -context 'auto-intent')
            $handled = $true
        }
        # Status fråga i fri text
        elseif ($t -match '\b(status|läget|hur går det)\b') {
            $msg = 'Jag kan skicka en statusöversikt och föreslå nästa kontrakt.'
            $out += (Reply -to $m.from -from $Agent -message $msg -priority 'low' -context 'auto-intent')
            $handled = $true
        }
        if ($handled) { continue }

        # Default: ACK-style hint
        $out += (Reply -to $m.from -from $Agent -message 'Jag kan svara autonomt på /status, /help, /contract ... eller skapa ett kontrakt åt dig. Skriv t.ex. "/contract propose title=\"Uppgift\" ttl=60 hb=30".' -priority 'low' -context 'auto-help')
    }
    return $out
}
