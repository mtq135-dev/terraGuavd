$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) {
    $secret = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    @("POSTGRES_DB=terraguavd", "POSTGRES_USER=terraguavd", "POSTGRES_PASSWORD=$secret", "DATABASE_URL=postgresql+psycopg://terraguavd:${secret}@127.0.0.1:5432/terraguavd") | Set-Content .env -Encoding ascii
}
if (-not (Test-Path .venv/Scripts/python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ virtual environment creation failed' }
}
& ./scripts/configure-local.ps1
& ./.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt -e './backend[test]' -e ./detection
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed' }
Push-Location web
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
} finally { Pop-Location }
Write-Host 'Setup complete. Start backend, then provision accounts in another terminal.'
