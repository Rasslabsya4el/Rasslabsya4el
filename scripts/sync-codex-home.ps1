[CmdletBinding()]
param(
    [string]$SourceRoot = (Join-Path $HOME '.codex'),
    [string]$BackupRoot
)

$ErrorActionPreference = 'Stop'

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-WithinRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $fullPath = Get-FullPath -Path $Path
    $fullRoot = Get-FullPath -Path $Root
    $rootWithSeparator = if ($fullRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $fullRoot
    } else {
        $fullRoot + [System.IO.Path]::DirectorySeparatorChar
    }

    if ($fullPath -ne $fullRoot -and -not $fullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label escaped the allowed root. Path: $fullPath Root: $fullRoot"
    }

    return $fullPath
}

$repoRoot = Get-FullPath -Path (Split-Path $PSCommandPath -Parent | Split-Path -Parent)
$BackupRoot = if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    Join-Path $repoRoot 'codex-home'
} else {
    $BackupRoot
}
$sourceRoot = Get-FullPath -Path $SourceRoot
$backupRoot = Assert-WithinRoot -Path $BackupRoot -Root $repoRoot -Label 'Backup root'

if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
    throw "Codex source directory was not found: $sourceRoot"
}

$managedDirectories = @(
    'agents',
    'skills',
    'plugins',
    'rules',
    'memories',
    'automations'
)

$managedFileGlobs = @(
    '*.toml',
    '*.yaml',
    '*.yml',
    '*.md',
    '*.rules'
)

$transientDirectoryNames = @(
    '__pycache__',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '.venv',
    'venv'
)

$transientFileGlobs = @(
    '*.pyc',
    '*.pyo'
)

$transientRelativePaths = @(
    'skills/poe-build-architect/scripts/python/var'
)

$excludedTopLevelFiles = @(
    'auth.json',
    'cap_sid',
    '.codex-global-state.json',
    'installation_id',
    'logs_2.sqlite',
    'logs_2.sqlite-shm',
    'logs_2.sqlite-wal',
    'models_cache.json',
    'session_index.jsonl',
    'state_5.sqlite',
    'state_5.sqlite-shm',
    'state_5.sqlite-wal',
    '.personality_migration'
)

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$selectedSourceFiles = Get-ChildItem -LiteralPath $sourceRoot -File -ErrorAction SilentlyContinue |
    Where-Object {
        $matchesManagedPattern = $false
        foreach ($glob in $managedFileGlobs) {
            if ($_.Name -like $glob) {
                $matchesManagedPattern = $true
                break
            }
        }
        $matchesManagedPattern
    }
    Where-Object { $excludedTopLevelFiles -notcontains $_.Name } |
    Sort-Object FullName -Unique

$managedDestinationFiles = Get-ChildItem -LiteralPath $backupRoot -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne '_backup_notes.txt' } |
    Sort-Object FullName -Unique

$selectedFileNames = @($selectedSourceFiles | ForEach-Object Name)
foreach ($destinationFile in $managedDestinationFiles) {
    if ($selectedFileNames -notcontains $destinationFile.Name) {
        Remove-Item -LiteralPath $destinationFile.FullName -Force
    }
}

foreach ($sourceFile in $selectedSourceFiles) {
    Copy-Item -LiteralPath $sourceFile.FullName -Destination (Join-Path $backupRoot $sourceFile.Name) -Force
}

$copiedDirectories = 0
foreach ($directoryName in $managedDirectories) {
    $sourceDirectory = Join-Path $sourceRoot $directoryName
    $backupDirectory = Assert-WithinRoot -Path (Join-Path $backupRoot $directoryName) -Root $backupRoot -Label "Backup directory '$directoryName'"

    if (Test-Path -LiteralPath $backupDirectory -PathType Container) {
        Remove-Item -LiteralPath $backupDirectory -Recurse -Force
    }

    if (Test-Path -LiteralPath $sourceDirectory -PathType Container) {
        Copy-Item -LiteralPath $sourceDirectory -Destination $backupDirectory -Recurse -Force
        $copiedDirectories++
    }
}

foreach ($transientDirectoryName in $transientDirectoryNames) {
    Get-ChildItem -LiteralPath $backupRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $transientDirectoryName } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

foreach ($fileGlob in $transientFileGlobs) {
    Get-ChildItem -LiteralPath $backupRoot -Recurse -File -Force -Filter $fileGlob -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

foreach ($relativePath in $transientRelativePaths) {
    $transientPath = Assert-WithinRoot -Path (Join-Path $backupRoot $relativePath) -Root $backupRoot -Label "Transient path '$relativePath'"
    if (Test-Path -LiteralPath $transientPath) {
        Remove-Item -LiteralPath $transientPath -Recurse -Force
    }
}

$directorySummary = foreach ($directoryName in $managedDirectories) {
    $sourceDirectory = Join-Path $sourceRoot $directoryName
    if (Test-Path -LiteralPath $sourceDirectory -PathType Container) {
        $fileCount = @(Get-ChildItem -LiteralPath $sourceDirectory -Recurse -File -Force -ErrorAction SilentlyContinue).Count
        [PSCustomObject]@{
            Name = $directoryName
            Files = $fileCount
        }
    }
}

Write-Host "Synced $($selectedSourceFiles.Count) top-level files and $copiedDirectories directories into $backupRoot"
if ($directorySummary) {
    $directorySummary | Format-Table -AutoSize | Out-String | Write-Host
}
