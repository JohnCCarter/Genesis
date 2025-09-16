# AI Change: Add dev startup script for backend to stabilize Uvicorn reloads on Windows. (Agent: Codex, Date: 2025-09-15)
$env:UVICORN_WORKERS = "1"
$env:PYTHONUNBUFFERED = "1"
$env:WATCHFILES_FORCE_POLLING = "true"   # Windows-fix om fil-watcher strular

# AI Change: Ensure working directory is tradingbot-backend so 'main:app' can be imported
$projectRoot = Split-Path -Path $PSScriptRoot -Parent
Push-Location $projectRoot

# Använd splatting för att robust hantera argument till externa program
$uvicorn_args = @(
    "--host", "127.0.0.1",
    "--port", "8000",
    "--reload",
    "--reload-dir", ".",
    "main:app"
)

# Use python -m uvicorn to avoid PATH issues on Windows
python -m uvicorn @uvicorn_args

# Restore previous working directory
Pop-Location
