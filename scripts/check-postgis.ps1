param([switch]$IncludeSitl)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& ./scripts/configure-local.ps1
if ($IncludeSitl) {
    Write-Host 'This check explicitly flies an isolated simulated mission; no physical UAV is supported.'
    docker compose up -d --build --wait db simulation
} else { docker compose up -d --build --wait db }
if ($LASTEXITCODE -ne 0) { throw 'Required Docker services failed to start' }
$arguments = @('backend/tests/run_integration.py')
if ($IncludeSitl) { $arguments += '--sitl' }
& ./.venv/Scripts/python.exe @arguments
if ($LASTEXITCODE -ne 0) { throw 'Integration checks failed' }
