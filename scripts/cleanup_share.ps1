[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [switch]$IncludePhotos
)

$ErrorActionPreference = "Stop"
$resolvedRoot = [System.IO.Path]::GetFullPath((Resolve-Path $ProjectRoot).Path)

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
    @{ Path = "state/change_history.jsonl"; Recurse = $false },
    @{ Path = "state/pipeline.db"; Recurse = $false },
    @{ Path = "logs/pipeline.log"; Recurse = $false },
    @{ Path = "src/state/browser_profile"; Recurse = $true },
    @{ Path = "src/state/change_history.jsonl"; Recurse = $false },
    @{ Path = "src/state/pipeline.db"; Recurse = $false },
    @{ Path = "src/logs/pipeline.log"; Recurse = $false }
)

foreach ($item in $removePaths) {
    $target = Get-UnderRootPath $item.Path
    if (Test-Path $target) {
        if ($PSCmdlet.ShouldProcess($target, "Remove")) {
            Remove-Item $target -Force -Recurse:$item.Recurse -ErrorAction SilentlyContinue
            Write-Host "Removed: $($item.Path)"
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

if ($IncludePhotos) {
    foreach ($photosPath in @("photos", "src/photos")) {
        $target = Get-UnderRootPath $photosPath
        if ((Test-Path $target) -and $PSCmdlet.ShouldProcess($target, "Remove")) {
            Remove-Item $target -Force -Recurse -ErrorAction SilentlyContinue
            Write-Host "Removed: $photosPath"
        }
    }
    Write-Host "Optional photo cleanup enabled: photos removed"
}

$placeholders = @("state", "logs", "photos")
foreach ($placeholder in $placeholders) {
    $target = Get-UnderRootPath $placeholder
    if ($PSCmdlet.ShouldProcess($target, "Ensure directory exists")) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
    }
}

$srcRoot = Get-UnderRootPath "src"
if (Test-Path $srcRoot) {
    foreach ($placeholder in @("src/state", "src/logs")) {
        $target = Get-UnderRootPath $placeholder
        if ($PSCmdlet.ShouldProcess($target, "Ensure directory exists")) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        }
    }

    if (-not $IncludePhotos) {
        $srcPhotos = Get-UnderRootPath "src/photos"
        if ($PSCmdlet.ShouldProcess($srcPhotos, "Ensure directory exists")) {
            New-Item -ItemType Directory -Force -Path $srcPhotos | Out-Null
        }
    }
}

Write-Host "Cleanup complete."
Write-Host "Share package guidance: docs/SHARING_AND_CLEANUP.md"
