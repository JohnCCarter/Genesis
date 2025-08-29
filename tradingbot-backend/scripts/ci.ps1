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
pytest -q

Write-Host '=== Bandit (exclude tests via bandit.yaml) ==='
python -m bandit -c bandit.yaml -r services rest utils models indicators -q

Write-Host '=== Pylint (report only) ==='
python -m pylint services rest utils models indicators --exit-zero -j 0

Write-Host 'CI checks completed.'
