$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Push-Location backend
try {
    & ../.venv/Scripts/python.exe -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
} finally { Pop-Location }
Push-Location web
try {
    npm run format:check
    if ($LASTEXITCODE -ne 0) { throw 'Frontend formatting check failed' }
    npm test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed' }
