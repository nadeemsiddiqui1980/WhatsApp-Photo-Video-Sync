param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [string]$ReportFile = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ReportFile)) {
    $ReportFile = Join-Path $ProjectRoot "state\preflight_report.json"
}
New-Item -ItemType Directory -Force -Path (Split-Path $ReportFile -Parent) | Out-Null

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
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

$os = Get-CimInstance Win32_OperatingSystem
$pythonExists = Test-CommandExists "python"
$wingetExists = Test-CommandExists "winget"
$chocoExists = Test-CommandExists "choco"
$chromePath = Get-ChromePath
$chromeExists = -not [string]::IsNullOrWhiteSpace($chromePath)
$edgePath = Get-EdgePath
$edgeExists = -not [string]::IsNullOrWhiteSpace($edgePath)

$report = [ordered]@{
    timestampUtc = (Get-Date).ToUniversalTime().ToString("o")
    windows = [ordered]@{
        caption = $os.Caption
        version = $os.Version
        buildNumber = $os.BuildNumber
        supported = ($os.Caption -match "Windows 10|Windows 11")
    }
    tools = [ordered]@{
        python = $pythonExists
        winget = $wingetExists
        chocolatey = $chocoExists
        chrome = $chromeExists
        chromePath = $chromePath
        edge = $edgeExists
        edgePath = $edgePath
        supportedBrowser = ($chromeExists -or $edgeExists)
    }
    checks = @()
}

if ($pythonExists) {
    try {
        $pyVersion = python --version 2>&1
        if ($pyVersion -match "Python") {
            $report.checks += "Python OK: $pyVersion"
        } else {
            $report.checks += "Python detected but version unclear: $pyVersion"
        }
    } catch {
        # Fallback: try python3
        if (Test-CommandExists "python3") {
            try {
                $pyVersion = python3 --version 2>&1
                $report.checks += "Python OK (python3): $pyVersion"
            } catch {
                $report.checks += "Python command exists but version check failed"
            }
        }
    }
} else {
    $report.checks += "Python missing"
}

if ($chromeExists) {
    $report.checks += "Chrome OK"
} else {
    $report.checks += "Chrome missing"
}
if ($edgeExists) {
    $report.checks += "Edge OK"
}

$canReachWhatsApp = $false
$canReachSftpHost = $false
try {
    $canReachWhatsApp = Test-NetConnection -ComputerName "web.whatsapp.com" -Port 443 -InformationLevel Quiet
} catch {}

if ($env:SFTP_HOST) {
    try {
        $canReachSftpHost = Test-NetConnection -ComputerName $env:SFTP_HOST -Port 22 -InformationLevel Quiet
    } catch {}
}

$report.network = [ordered]@{
    whatsapp443 = $canReachWhatsApp
    sftp22 = $canReachSftpHost
}

$report | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $ReportFile
Write-Host "Preflight report saved to $ReportFile"
Write-Host "Windows supported: $($report.windows.supported) | Python: $pythonExists | Chrome: $chromeExists | WhatsApp reachable: $canReachWhatsApp"
