param(
  [switch]$Fix
)

$ErrorActionPreference = 'Stop'

# Ensure we run from the backend root, regardless of where the script is invoked
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $backendRoot

Write-Host '=== Black check ==='
python -m black . --check

Write-Host '=== Ruff check (per pyproject) ==='
python -m ruff check .

if ($Fix) {
  Write-Host '=== Ruff auto-fix (non-gating) ==='
  python -m ruff check . --fix
}

Write-Host '=== Pytest ==='
python -m pytest -q

Write-Host '=== Bandit (exclude tests via bandit.yaml) ==='
python -m bandit -c bandit.yaml -r services rest utils models indicators -q -f json

Write-Host '=== Pylint (report only) ==='
python -m pylint services rest utils models indicators --exit-zero -j 0

# Path hygiene: block accidental /api/v2/v2 patterns
# Rule: In files that define APIRouter(prefix="/api/v2"), disallow route decorators starting with "/v2/"
Write-Host '=== Path hygiene check (/api/v2/v2 guard) ==='
$routeFiles = Get-ChildItem -Recurse -File rest | Where-Object { $_.Extension -eq '.py' }
$violations = @()
foreach ($f in $routeFiles) {
  $content = Get-Content -Raw $f.FullName
  if ($content -match 'APIRouter\(\s*prefix\s*=\s*"/api/v2"') {
    if ($content -match '@router\.(get|post|put|delete|patch)\("/v2/') {
      $violations += $f.FullName
    }
  }
}
if ($violations.Count -gt 0) {
  Write-Error ("Path hygiene violation: '/v2/*' routes found in files already under APIRouter(prefix='/api/v2'). Files:\n" + ($violations -join "`n"))
}

Write-Host 'CI checks completed.'
