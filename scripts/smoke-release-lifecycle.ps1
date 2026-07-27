param(
    [ValidateSet('release', 'binary')]
    [string]$Mode = 'release',
    [string]$Version = $env:OKIT_VERSION,
    [string]$Binary,
    [string]$Repository = $(if ($env:OKIT_REPOSITORY) { $env:OKIT_REPOSITORY } else { 'fjzhangZzzzzz/okit' })
)

$ErrorActionPreference = 'Stop'

function Write-Phase([string]$Message) { Write-Host "`n==> $Message" }
function Fail([string]$Message) { throw $Message }

if ($Version -notmatch '^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') { Fail "invalid version: $Version" }
if ($Mode -eq 'binary' -and -not $Binary) { Fail 'binary mode requires -Binary PATH' }

$repoRoot = Split-Path -Parent $PSScriptRoot
$smokeRoot = $null
$originalOKITHome = $env:OKIT_HOME
$originalInstallDir = $env:OKIT_INSTALL_DIR
if (-not $env:OKIT_HOME -or -not $env:OKIT_INSTALL_DIR) {
    $smokeRoot = Join-Path ([IO.Path]::GetTempPath()) ('okit-smoke-' + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $smokeRoot | Out-Null
}
$okitHome = if ($env:OKIT_HOME) { $env:OKIT_HOME } else { Join-Path $smokeRoot 'okit-home' }
$installDir = if ($env:OKIT_INSTALL_DIR) { $env:OKIT_INSTALL_DIR } else { Join-Path $smokeRoot 'okit-bin' }
$executable = Join-Path $installDir 'okit.exe'
$env:OKIT_HOME = $okitHome
$env:OKIT_INSTALL_DIR = $installDir

function Stage-Binary {
    if (-not (Test-Path -LiteralPath $Binary -PathType Leaf)) { Fail "binary does not exist: $Binary" }
    New-Item -ItemType Directory -Force -Path $installDir, $okitHome | Out-Null
    Copy-Item -LiteralPath $Binary -Destination $executable -Force
    $metadata = [ordered]@{
        method = 'official'; version = $Version; channel = $(if ($Version -like '*-*') { 'prerelease' } else { 'stable' }); executable = $executable
        path_entries = @(); managed_files = @()
    }
    [IO.File]::WriteAllText(
        (Join-Path $okitHome 'install.json'),
        ($metadata | ConvertTo-Json),
        [Text.UTF8Encoding]::new($false)
    )
}

function Assert-Version {
    Write-Phase 'Verify installed version'
    $actual = @()
    $exitCode = 1
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (Test-Path -LiteralPath $executable) {
            $actual = @(& $executable --version 2>&1)
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0 -and (($actual -join "`n") -split "`r?`n") -contains "okit $Version") { break }
        }
        Start-Sleep -Milliseconds 250
    }
    Write-Host "binary: $executable"
    Write-Host "expected: okit $Version"
    Write-Host "actual output:"
    $actual | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) { Fail "version command exited with status $exitCode" }
    if (-not ((($actual -join "`n") -split "`r?`n") -contains "okit $Version")) {
        Fail "installed version does not match tag $Version"
    }
}

try {
    Write-Phase "Prepare $Mode smoke test for $Version"
    if ($Mode -eq 'binary') {
        Stage-Binary
    }
    else {
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail 'gh is required for release mode' }
        $releases = gh api "repos/$Repository/releases" | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { Fail "could not list releases for $Repository" }
        $previous = $releases | Where-Object { -not $_.draft -and -not $_.prerelease -and $_.tag_name -ne $Version } | Select-Object -First 1
        if ($previous) {
            Write-Phase "Install previous release $($previous.tag_name)"
            & (Join-Path $PSScriptRoot 'install.ps1') -Version $previous.tag_name
            Write-Phase "Update $($previous.tag_name) to $Version"
            & $executable upgrade --version $Version
	            if ($LASTEXITCODE -ne 0) { Fail '升级失败' }
        }
        else {
            Write-Phase "Install first release $Version"
            & (Join-Path $PSScriptRoot 'install.ps1') -Version $Version
        }
    }

    Assert-Version

    Write-Phase 'Run installed binary runtime smoke'
    & (Join-Path $PSScriptRoot 'smoke-runtime-windows.ps1') -Executable $executable -Version $Version
    if ($LASTEXITCODE -ne 0) { Fail 'Windows runtime smoke failed' }
    & bash (Join-Path $PSScriptRoot 'smoke-runtime-windows-git-bash.sh') --executable $executable --version $Version
    if ($LASTEXITCODE -ne 0) { Fail 'Windows Git Bash runtime smoke failed' }

    Write-Phase 'Run release lifecycle command checks'
    & $executable upgrade --help
    if ($LASTEXITCODE -ne 0) { Fail '升级帮助冒烟检查失败' }

    Write-Phase 'Verify uninstall preserves user data'
    New-Item -ItemType Directory -Force -Path $okitHome | Out-Null
    New-Item -ItemType File -Force -Path (Join-Path $okitHome 'user-data') | Out-Null
    & $executable uninstall --dry-run
    if ($LASTEXITCODE -ne 0) { Fail 'uninstall dry-run failed' }
    & $executable uninstall
    if ($LASTEXITCODE -ne 0) { Fail 'uninstall failed' }
    for ($attempt = 0; $attempt -lt 20 -and (Test-Path -LiteralPath $executable); $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if (Test-Path -LiteralPath $executable) { Fail "executable was not uninstalled: $executable" }
    if (-not (Test-Path -LiteralPath (Join-Path $okitHome 'user-data'))) { Fail 'default uninstall removed user data' }

    Write-Phase 'Release lifecycle smoke test passed'
}
finally {
    if ($smokeRoot) { Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue }
    if ($null -eq $originalOKITHome) { Remove-Item Env:OKIT_HOME -ErrorAction SilentlyContinue } else { $env:OKIT_HOME = $originalOKITHome }
    if ($null -eq $originalInstallDir) { Remove-Item Env:OKIT_INSTALL_DIR -ErrorAction SilentlyContinue } else { $env:OKIT_INSTALL_DIR = $originalInstallDir }
}
