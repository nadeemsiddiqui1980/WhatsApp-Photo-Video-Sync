param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..")
)

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found. Run bootstrap\setup.ps1 first."
}

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    throw ".env file not found. Create it from .env.example first."
}

Push-Location (Join-Path $ProjectRoot "src")
& $venvPython main.py
Pop-Location
