# AI Change: Add dev startup script for backend to stabilize Uvicorn reloads on Windows. (Agent: Codex, Date: 2025-09-15)
$env:UVICORN_WORKERS = "1"
$env:PYTHONUNBUFFERED = "1"
$env:WATCHFILES_FORCE_POLLING = "true"   # Windows-fix om fil-watcher strular

# Använd splatting för att robust hantera argument till externa program
$uvicorn_args = @(
    "main:app",
    "--host", "127.0.0.1",
    "--port", "8000",
    "--reload",
    "--reload-dir", "tradingbot-backend",
    '--reload-exclude', '.venv/*',
    '--reload-exclude', 'frontend/*',
    '--reload-exclude', 'node_modules/*',
    '--reload-exclude', '*.log'
)

uvicorn @uvicorn_args
