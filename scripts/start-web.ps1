$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'web')
if (-not (Test-Path node_modules)) { throw 'Run .\scripts\setup.ps1 first' }
try { Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/ready' -TimeoutSec 5 | Out-Null }
catch { throw 'Backend is not ready. Run .\scripts\start-backend.ps1 first.' }
Write-Host 'Web: http://127.0.0.1:5173 (API proxy: 127.0.0.1:8000)'
npm run dev
if ($LASTEXITCODE -ne 0) { throw 'Frontend startup failed' }
