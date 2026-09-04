# Dev launcher (Windows PowerShell)
# Usage: .\scripts\dev.ps1

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "src"
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  Write-Error "Create venv first: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
}

Write-Host "Starting Postgres/Redis/Jaeger..."
docker compose up -d postgres redis jaeger

Write-Host @"

Run these in separate terminals:

  1) API:
     `$env:PYTHONPATH='src'; .\.venv\Scripts\uvicorn orchestrator.main:app --reload --app-dir src --port 8000

  2) Celery:
     `$env:PYTHONPATH='src'; .\.venv\Scripts\celery -A orchestrator.worker.celery_app worker --loglevel=INFO --pool=solo

  3) React UI:
     cd web; npm run dev

  4) Demo:
     .\.venv\Scripts\python demos\research_brief.py

UI http://localhost:5173
API http://localhost:8000/docs
Jaeger http://localhost:16686
"@
