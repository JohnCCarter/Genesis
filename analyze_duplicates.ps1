# AI Change: Create analysis script for duplicates/overlaps (Agent: Codex, Date: 2025-09-11)
$ErrorActionPreference = "Stop"
$root = "tradingbot-backend"
$out  = Join-Path $root "analysis"

if (!(Test-Path $root)) { throw "Hittar inte mappen: $root. Kör scriptet i repo-roten." }

New-Item -ItemType Directory -Force -Path $out | Out-Null

# Filurval (exkludera .venv/__pycache__/archived/readme_docs/scripts) – inkluderar tests
$files = Get-ChildItem $root -Recurse -File -Include *.py | Where-Object {
  $_.FullName -notmatch '\\.venv\\' -and
  $_.FullName -notmatch '\\__pycache__\\' -and
  $_.FullName -notmatch '\\archived\\' -and
  $_.FullName -notmatch '\\readme_docs\\' -and
  $_.FullName -notmatch '\\scripts\\'
}

# Kategorier
$cats = [ordered]@{
  endpoints = @{ rx='@app\.(get|post|put|delete)\("([^"\n]+)"';     file=(Join-Path $out 'endpoints.txt') }
  ws_topics = @{ rx='subscribe|publish|emit|on_message';            file=(Join-Path $out 'ws_topics.txt') }
  metrics   = @{ rx='metrics\.|prometheus|Counter\(|Gauge\(';       file=(Join-Path $out 'metrics.txt') }
  config    = @{ rx='os\.environ\[|Settings\(|FEATURE_|DRY_RUN|AUTH_REQUIRED'; file=(Join-Path $out 'config_flags.txt') }
  pydantic  = @{ rx='class .*BaseModel';                             file=(Join-Path $out 'pydantic_models.txt') }
  circuit   = @{ rx='circuit|rate[_-]?limit';                        file=(Join-Path $out 'circuit_rate_limit.txt') }
  risk      = @{ rx='(?i)\brisk\b|guard|pre_trade|constraint';       file=(Join-Path $out 'risk.txt') }
  sched     = @{ rx='schedule|cron|job|refresh';                     file=(Join-Path $out 'scheduling.txt') }
  logging   = @{ rx='logging|logger\.|log\(';                        file=(Join-Path $out 'logging.txt') }
  tests     = @{ rx='(?m)^def test_';                                file=(Join-Path $out 'tests_functions.txt') }
}

# Sök & skriv små rader (Path:Line: Text[<=160 tecken])
foreach($k in $cats.Keys) {
  $rx = $cats[$k].rx; $dst = $cats[$k].file
  $hits = $files | Select-String -Pattern $rx -AllMatches
  $fmt  = { '{0}:{1}: {2}' -f $_.Path, $_.LineNumber, ( $_.Line.Substring(0, [Math]::Min($_.Line.Length,160)) ) }
  $hits | ForEach-Object $fmt | Set-Content -Encoding UTF8 -Path $dst
}

# Sammanfatta överlapp per fil
$acc = @{}
foreach($k in $cats.Keys){
  $file = $cats[$k].file
  if(Test-Path $file){
    Get-Content -Path $file | ForEach-Object {
      if($_ -match '^(.*?):\d+:'){ $p=$matches[1] } elseif($_ -match '^([^:]+):'){ $p=$matches[1] } else { return }
      try { $full=[IO.Path]::GetFullPath($p) } catch { $full=$p }
      if(-not $acc.ContainsKey($full)){ $acc[$full]=New-Object System.Collections.Generic.HashSet[string] }
      $null = $acc[$full].Add($k)
    }
  }
}

$rows = foreach($key in $acc.Keys){ $set=$acc[$key]; [pscustomobject]@{ Path=$key; Count=$set.Count; Categories=($set -join ',') } }
$rows_sorted = $rows | Sort-Object -Property @{Expression='Count';Descending=$true}, @{Expression='Path';Descending=$false}

$summary = Join-Path $out 'summary.txt'
$csv     = Join-Path $out 'summary_top.csv'

'Top 30 files by category overlap:' | Out-File -Encoding UTF8 $summary
$rows_sorted | Select-Object -First 30 | Format-Table -Auto | Out-File -Encoding UTF8 -Append $summary
$over5 = $rows_sorted | Where-Object { $_.Count -ge 5 }
(''+[Environment]::NewLine+'Files with >=5 categories: '+$over5.Count) | Out-File -Encoding UTF8 -Append $summary
$over5 | Select-Object -First 50 | Format-Table -Auto | Out-File -Encoding UTF8 -Append $summary

$rows_sorted | Select-Object Path,Count,Categories | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8

Write-Host ('Klart   -> ' + $out) -ForegroundColor Green
