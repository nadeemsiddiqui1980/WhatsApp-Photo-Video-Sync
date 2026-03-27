param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [string]$OutputFile = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $ProjectRoot "config\config.shareable.yaml"
}

Copy-Item (Join-Path $ProjectRoot "config\config.yaml") $OutputFile -Force
Write-Host "Shareable config exported to $OutputFile"
Write-Host "Do not include secrets from .env when sharing."
