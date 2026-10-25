$ErrorActionPreference = 'Stop'
$configPath = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Run scripts/setup.ps1 first' }
if (-not (Select-String -LiteralPath $configPath -Pattern '^SIMULATION_SECRET=' -Quiet)) {
    $runtimeSecret = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    Add-Content -LiteralPath $configPath -Value "`nSIMULATION_SECRET=$runtimeSecret" -Encoding ascii
}
