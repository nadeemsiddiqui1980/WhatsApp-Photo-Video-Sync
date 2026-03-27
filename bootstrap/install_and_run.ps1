param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..")
)

$ErrorActionPreference = "Stop"

& (Join-Path $ProjectRoot "bootstrap\setup.ps1") -ProjectRoot $ProjectRoot

Write-Host "Starting pipeline..."
& (Join-Path $ProjectRoot "scripts\run_pipeline.ps1") -ProjectRoot $ProjectRoot
