param(
    [Parameter(Mandatory=$true)][string]$Username,
    [Parameter(Mandatory=$true)][ValidateSet('administrator','mission_operator','detection_analyst','supervisor','field_personnel')][string]$Role
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& ./.venv/Scripts/python.exe -m app.manage $Username $Role
if ($LASTEXITCODE -ne 0) { throw 'Account provisioning failed. Check migrations and username.' }
