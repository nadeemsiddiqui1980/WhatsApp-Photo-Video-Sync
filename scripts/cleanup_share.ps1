[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ProjectRoot,
    [switch]$IncludePhotos,
    [switch]$IncludeMedia
)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) {
    $ProjectRoot = Join-Path $PSScriptRoot ".."
}

$resolvedRoot = [System.IO.Path]::GetFullPath((Resolve-Path $ProjectRoot).Path)

function Remove-TargetPath {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][bool]$Recurse,
        [Parameter(Mandatory = $true)][string]$DisplayPath
    )

    if (-not (Test-Path $TargetPath)) {
        return $true
    }

    try {
        Remove-Item $TargetPath -Force -Recurse:$Recurse -ErrorAction Stop
    }
    catch {
        # .venv can be locked by a running Python interpreter from that virtual env.
        if ($DisplayPath -ieq ".venv") {
            $locking = Get-Process -ErrorAction SilentlyContinue | Where-Object {
                $_.Path -and $_.Path.StartsWith($TargetPath, [System.StringComparison]::OrdinalIgnoreCase)
            }
            foreach ($proc in $locking) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }

            Start-Sleep -Milliseconds 500
            try {
                Remove-Item $TargetPath -Force -Recurse -ErrorAction Stop
            }
            catch {
                cmd /c "rmdir /s /q \"$TargetPath\"" | Out-Null
            }
        }
    }

    return -not (Test-Path $TargetPath)
}

function Get-UnderRootPath {
    param([string]$RelativePath)

    $candidate = [System.IO.Path]::GetFullPath((Join-Path $resolvedRoot $RelativePath))
    if (-not $candidate.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to access path outside project root: $RelativePath"
    }
    return $candidate
}

$removePaths = @(
    @{ Path = ".env"; Recurse = $false },
    @{ Path = ".venv"; Recurse = $true },
    @{ Path = "state/browser_profile"; Recurse = $true },
    @{ Path = "state/temp_downloads"; Recurse = $true },
    @{ Path = "state/quarantine"; Recurse = $true },
    @{ Path = "state/change_history.jsonl"; Recurse = $false },
    @{ Path = "state/pipeline.db"; Recurse = $false },
    @{ Path = "logs/pipeline.log"; Recurse = $false },
    @{ Path = "src/state/browser_profile"; Recurse = $true },
    @{ Path = "src/state/temp_downloads"; Recurse = $true },
    @{ Path = "src/state/quarantine"; Recurse = $true },
    @{ Path = "src/state/change_history.jsonl"; Recurse = $false },
    @{ Path = "src/state/pipeline.db"; Recurse = $false },
    @{ Path = "src/logs/pipeline.log"; Recurse = $false }
)

foreach ($item in $removePaths) {
    $target = Get-UnderRootPath $item.Path
    if (Test-Path $target) {
        if ($PSCmdlet.ShouldProcess($target, "Remove")) {
            $removed = Remove-TargetPath -TargetPath $target -Recurse:$item.Recurse -DisplayPath $item.Path
            if ($removed) {
                Write-Host "Removed: $($item.Path)"
            }
            else {
                Write-Warning "Could not remove: $($item.Path). Close terminals using the virtual environment and rerun cleanup."
            }
        }
    }
}

$clearDirs = @("state/temp_downloads", "state/quarantine", "src/state/temp_downloads", "src/state/quarantine")
foreach ($relativeDir in $clearDirs) {
    $directory = Get-UnderRootPath $relativeDir
    if (-not (Test-Path $directory)) {
        continue
    }

    $children = Get-ChildItem -Path $directory -Force -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        if ($PSCmdlet.ShouldProcess($child.FullName, "Remove")) {
            Remove-Item $child.FullName -Force -Recurse -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Cleared: $relativeDir"
}

$debugPatterns = @("e2e_*.txt", "post_fix_*.txt", "run_output*.txt", "*probe*")
$debugRoots = @("state", "src/state")
foreach ($debugRoot in $debugRoots) {
    $directory = Get-UnderRootPath $debugRoot
    if (-not (Test-Path $directory)) {
        continue
    }

    foreach ($pattern in $debugPatterns) {
        $matches = Get-ChildItem -Path $directory -Filter $pattern -Force -File -ErrorAction SilentlyContinue
        foreach ($match in $matches) {
            if ($PSCmdlet.ShouldProcess($match.FullName, "Remove")) {
                Remove-Item $match.FullName -Force -ErrorAction SilentlyContinue
                Write-Host "Removed debug output: $($match.FullName.Replace($resolvedRoot + '\\', ''))"
            }
        }
    }
}

if ($IncludePhotos -or $IncludeMedia) {
    foreach ($mediaPath in @("photos", "videos", "src/photos", "src/videos")) {
        if (-not (Test-Path (Get-UnderRootPath $mediaPath))) {
            continue
        }
        $target = Get-UnderRootPath $mediaPath
        if ((Test-Path $target) -and $PSCmdlet.ShouldProcess($target, "Remove")) {
            Remove-Item $target -Force -Recurse -ErrorAction SilentlyContinue
            Write-Host "Removed: $mediaPath"
        }
    }
    Write-Host "Optional media cleanup enabled: photos/videos removed"
}

$placeholders = @("state", "state/temp_downloads", "state/quarantine", "logs", "photos", "videos")
foreach ($placeholder in $placeholders) {
    $target = Get-UnderRootPath $placeholder
    if ($PSCmdlet.ShouldProcess($target, "Ensure directory exists")) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
    }
}

$srcRoot = Get-UnderRootPath "src"
if (Test-Path $srcRoot) {
    foreach ($placeholder in @("src/state", "src/state/temp_downloads", "src/state/quarantine", "src/logs")) {
        $target = Get-UnderRootPath $placeholder
        if ($PSCmdlet.ShouldProcess($target, "Ensure directory exists")) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        }
    }

    if (-not ($IncludePhotos -or $IncludeMedia)) {
        foreach ($srcMedia in @("src/photos", "src/videos")) {
            $target = Get-UnderRootPath $srcMedia
            if ($PSCmdlet.ShouldProcess($target, "Ensure directory exists")) {
                New-Item -ItemType Directory -Force -Path $target | Out-Null
            }
        }
    }
}

Write-Host "Cleanup complete."
Write-Host "Share package guidance: docs/SHARING_AND_CLEANUP.md"
