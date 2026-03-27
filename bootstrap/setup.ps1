param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..")
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonVersion {
    # Try py launcher with 3.12
    try {
        $output = & py -3.12 --version 2>&1
        if ($LASTEXITCODE -eq 0) { return $output }
    } catch {}
    
    # Try py launcher with 3.11
    try {
        $output = & py -3.11 --version 2>&1
        if ($LASTEXITCODE -eq 0) { return $output }
    } catch {}
    
    # Try plain py launcher
    try {
        $output = & py --version 2>&1
        if ($LASTEXITCODE -eq 0) { return $output }
    } catch {}
    
    # Try python
    try {
        $output = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) { return $output }
    } catch {}
    
    return $null
}

function Test-PythonVersion {
    $pyVersionOutput = Get-PythonVersion
    if ($null -eq $pyVersionOutput) {
        return $false
    }
    # Python 3.11+ required
    if ($pyVersionOutput -match "3\.(1[1-9]|[2-9]\d)") {
        return $true
    }
    return $false
}

function Get-PythonLauncher {
    # Try py launcher with 3.12
    try {
        $null = & py -3.12 --version 2>&1
        if ($LASTEXITCODE -eq 0) { return @("py", "-3.12") }
    } catch {}
    
    # Try py launcher with 3.11
    try {
        $null = & py -3.11 --version 2>&1
        if ($LASTEXITCODE -eq 0) { return @("py", "-3.11") }
    } catch {}
    
    # Try plain py launcher
    try {
        $null = & py --version 2>&1
        if ($LASTEXITCODE -eq 0) { return @("py") }
    } catch {}
    
    # Try python
    try {
        $null = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) { return @("python") }
    } catch {}

    throw "Python 3.11+ is required but not found. Install Python 3.11+ from python.org, then rerun setup."
}

function Get-ChromePath {
    $paths = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    try {
        $appPath = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" -ErrorAction Stop).'(default)'
        if ($appPath -and (Test-Path $appPath)) { return $appPath }
    } catch {}
    try {
        $cmd = Get-Command chrome.exe -ErrorAction Stop
        if ($cmd.Source -and (Test-Path $cmd.Source)) { return $cmd.Source }
    } catch {}
    return $null
}

function Get-EdgePath {
    $paths = @(
        "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    try {
        $appPath = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe" -ErrorAction Stop).'(default)'
        if ($appPath -and (Test-Path $appPath)) { return $appPath }
    } catch {}
    try {
        $cmd = Get-Command msedge.exe -ErrorAction Stop
        if ($cmd.Source -and (Test-Path $cmd.Source)) { return $cmd.Source }
    } catch {}
    return $null
}

Write-Host "Running preflight..."
& (Join-Path $ProjectRoot "scripts\preflight.ps1") -ProjectRoot $ProjectRoot

$pythonExists = (Test-CommandExists "python") -or (Test-CommandExists "python3") -or (Test-CommandExists "py")
if (-not $pythonExists) {
    if (Test-CommandExists "winget") {
        Write-Host "Installing Python via winget..."
        winget install -e --id Python.Python.3.12 --source winget --disable-interactivity --accept-source-agreements --accept-package-agreements
    } else {
        throw "Python is missing. Install Python 3.11+ from python.org, then rerun setup."
    }
}

$chromePath = Get-ChromePath
$edgePath = Get-EdgePath
if ([string]::IsNullOrWhiteSpace($chromePath) -and [string]::IsNullOrWhiteSpace($edgePath)) {
    if (Test-CommandExists "winget") {
        Write-Host "Installing Chrome via winget..."
        winget install -e --id Google.Chrome --source winget --disable-interactivity --accept-source-agreements --accept-package-agreements
    } elseif (Test-CommandExists "choco") {
        Write-Host "Installing Chrome via chocolatey..."
        choco install googlechrome --yes
    } else {
        throw "Chrome is missing and no package manager found. Install Google Chrome manually and rerun setup."
    }
}

Write-Host "Creating Python virtual environment..."
Push-Location $ProjectRoot
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if ((-not (Test-Path $venvPython)) -or (-not (Test-Path (Join-Path $ProjectRoot ".venv\pyvenv.cfg")))) {
    # Auto-heal partially broken virtual environments (e.g., missing pyvenv.cfg)
    if (Test-Path (Join-Path $ProjectRoot ".venv")) {
        Write-Host "Existing .venv appears invalid; recreating..."
        try {
            Remove-Item (Join-Path $ProjectRoot ".venv") -Recurse -Force -ErrorAction Stop
        } catch {
            throw "Could not remove existing .venv. Close any running pipeline/python process and retry setup. Details: $($_.Exception.Message)"
        }
    }
    $pythonLauncher = Get-PythonLauncher
    if ($pythonLauncher.Length -eq 1) {
        & $pythonLauncher[0] -m venv .venv
    } else {
        & $pythonLauncher[0] $pythonLauncher[1] -m venv .venv
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython) -or -not (Test-Path (Join-Path $ProjectRoot ".venv\pyvenv.cfg"))) {
        throw "Failed to create a valid .venv. Ensure Python 3.11+ is installed and no process is locking .venv, then rerun setup."
    }
}

$venvVersionRaw = (& $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Failed to run .venv python interpreter. Recreate .venv and rerun setup. Output: $venvVersionRaw"
}
$venvVersionMatch = [regex]::Match($venvVersionRaw, "(\d+\.\d+)")
if (-not $venvVersionMatch.Success) {
    throw "Could not determine Python version from .venv interpreter output: $venvVersionRaw"
}

$venvVersion = $venvVersionMatch.Groups[1].Value
if ([Version]($venvVersion + ".0") -lt [Version]"3.11.0") {
    throw "Existing .venv uses Python $venvVersion. Python 3.11+ is required. Delete .venv and rerun bootstrap\setup.ps1 after installing Python 3.11+."
}

& $venvPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) {
    throw "Failed to bootstrap pip in .venv. Recreate .venv and rerun setup."
}

& $venvPython -m pip --version
if ($LASTEXITCODE -ne 0) {
    throw "pip is not available in .venv after ensurepip."
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in .venv."
}

$requirementsFile = Join-Path $ProjectRoot "requirements.txt"
$pipInstallSucceeded = $false
for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ($attempt -gt 1) {
        Write-Host "Retrying dependency install (attempt $attempt/3)..."
        Start-Sleep -Seconds 2
    }

    & $venvPython -m pip install -r $requirementsFile
    if ($LASTEXITCODE -eq 0) {
        $pipInstallSucceeded = $true
        break
    }
}

if (-not $pipInstallSucceeded) {
    throw "Failed to install dependencies from requirements.txt after 3 attempts. If you see WinError 5 (Access is denied), close any running pipeline/python process using this project and rerun setup."
}

# Validate critical imports; if PyYAML is partially corrupted, repair it once.
$yamlImportOk = $false
try {
    & $venvPython -c "import yaml" *> $null
    $yamlImportOk = ($LASTEXITCODE -eq 0)
} catch {
    $yamlImportOk = $false
}

if (-not $yamlImportOk) {
    Write-Host "Detected broken PyYAML install. Repairing..."
    & $venvPython -m pip install --force-reinstall --no-cache-dir PyYAML
    if ($LASTEXITCODE -ne 0) {
        # Fallback for corrupted installs with missing RECORD metadata.
        & $venvPython -m pip install --ignore-installed --no-cache-dir PyYAML==6.0.3
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to repair PyYAML install in .venv."
        }
    }

    $yamlImportOk = $false
    try {
        & $venvPython -c "import yaml" *> $null
        $yamlImportOk = ($LASTEXITCODE -eq 0)
    } catch {
        $yamlImportOk = $false
    }

    if (-not $yamlImportOk) {
        throw "PyYAML import validation failed after repair."
    }
}

$depsImportOk = $false
try {
    & $venvPython -c "import dotenv, paramiko, selenium, webdriver_manager" *> $null
    $depsImportOk = ($LASTEXITCODE -eq 0)
} catch {
    $depsImportOk = $false
}

if (-not $depsImportOk) {
    throw "Dependency validation failed after install. Re-run setup once more; if it persists, delete .venv and run setup again."
}

$folders = @("logs", "state", "photos", "state\temp_downloads", "state\quarantine", "state\browser_profile", "docs")
foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $folder) | Out-Null
}

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
    Write-Host "Created .env from .env.example. Please fill SFTP and group values."
}

if (-not (Test-Path (Join-Path $ProjectRoot "config\config.yaml"))) {
    Copy-Item (Join-Path $ProjectRoot "config\config.template.yaml") (Join-Path $ProjectRoot "config\config.yaml")
    Write-Host "Created config/config.yaml from config/config.template.yaml."
}

Pop-Location

Write-Host "Setup complete."
