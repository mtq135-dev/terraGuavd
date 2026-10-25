$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env) -or -not (Test-Path .venv/Scripts/python.exe)) { throw 'Run .\scripts\setup.ps1 first' }
& ./scripts/configure-local.ps1
docker compose up -d --build --wait --wait-timeout 180 db simulation
if ($LASTEXITCODE -ne 0) { throw 'Database or simulator service startup failed. Check Docker Desktop / WSL 2, ports 5432/8090, and build logs.' }
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
Push-Location backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    Write-Host 'Database migrated. API: http://127.0.0.1:8000/docs; readiness: /api/v1/health/ready'
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'API startup failed' }
} finally { Pop-Location }
