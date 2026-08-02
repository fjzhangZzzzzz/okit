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

if ($Version -notmatch '^v\d+\.\d+\.\d+(?:-rc\.[1-9][0-9]*)?$') { Fail "版本号无效：$Version" }
if ($Mode -eq 'binary' -and -not $Binary) { Fail 'binary 模式需要 -Binary PATH' }

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
    if (-not (Test-Path -LiteralPath $Binary -PathType Leaf)) { Fail "二进制文件不存在：$Binary" }
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
    Write-Phase '验证已安装版本'
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
    Write-Host "二进制：$executable"
    Write-Host "期望：okit $Version"
    Write-Host "实际输出："
    $actual | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) { Fail "版本命令退出码为 $exitCode" }
    if (-not ((($actual -join "`n") -split "`r?`n") -contains "okit $Version")) {
        Fail "已安装版本与 tag $Version 不一致"
    }
}

try {
    Write-Phase "准备 $Version 的 $Mode 冒烟测试"
    if ($Mode -eq 'binary') {
        Stage-Binary
    }
    else {
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail 'release 模式需要 gh' }
        $releases = gh api "repos/$Repository/releases" | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { Fail "无法列出 $Repository 的 Release" }
        $previous = $releases | Where-Object { -not $_.draft -and -not $_.prerelease -and $_.tag_name -ne $Version } | Select-Object -First 1
        if ($previous) {
            Write-Phase "安装上一正式版本 $($previous.tag_name)"
            & (Join-Path $PSScriptRoot 'install.ps1') -Version $previous.tag_name
            $previousHelp = @(& $executable --help 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { Fail "无法读取升级源 $($previous.tag_name) 的命令列表" }
            if ($previousHelp -notmatch '(?m)^\s+upgrade\s') {
                Fail "$($previous.tag_name) 不支持 upgrade 命令，不能作为 $Version 的升级源"
            }
            Write-Phase "从 $($previous.tag_name) 升级到 $Version"
            & $executable upgrade --version $Version
            if ($LASTEXITCODE -ne 0) { Fail '升级失败' }
        }
        else {
            Write-Phase "安装首个版本 $Version"
            & (Join-Path $PSScriptRoot 'install.ps1') -Version $Version
        }
    }

    Assert-Version

    Write-Phase '运行已安装二进制的运行时冒烟测试'
    & (Join-Path $PSScriptRoot 'smoke-runtime-windows.ps1') -Executable $executable -Version $Version
    if ($LASTEXITCODE -ne 0) { Fail 'Windows 运行时冒烟测试失败' }
    & bash (Join-Path $PSScriptRoot 'smoke-runtime-windows-git-bash.sh') --executable $executable --version $Version
    if ($LASTEXITCODE -ne 0) { Fail 'Windows Git Bash 运行时冒烟测试失败' }

    Write-Phase '检查发布生命周期命令'
    & $executable upgrade --help
    if ($LASTEXITCODE -ne 0) { Fail '升级帮助冒烟检查失败' }

    Write-Phase '验证默认卸载保留用户数据'
    New-Item -ItemType Directory -Force -Path $okitHome | Out-Null
    New-Item -ItemType File -Force -Path (Join-Path $okitHome 'user-data') | Out-Null
    & $executable uninstall --dry-run
    if ($LASTEXITCODE -ne 0) { Fail 'uninstall dry-run 失败' }
    & $executable uninstall
    if ($LASTEXITCODE -ne 0) { Fail 'uninstall 失败' }
    for ($attempt = 0; $attempt -lt 20 -and (Test-Path -LiteralPath $executable); $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if (Test-Path -LiteralPath $executable) { Fail "未卸载可执行文件：$executable" }
    if (-not (Test-Path -LiteralPath (Join-Path $okitHome 'user-data'))) { Fail '默认卸载删除了用户数据' }

    Write-Phase '发布生命周期冒烟测试通过'
}
finally {
    if ($smokeRoot) { Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue }
    if ($null -eq $originalOKITHome) { Remove-Item Env:OKIT_HOME -ErrorAction SilentlyContinue } else { $env:OKIT_HOME = $originalOKITHome }
    if ($null -eq $originalInstallDir) { Remove-Item Env:OKIT_INSTALL_DIR -ErrorAction SilentlyContinue } else { $env:OKIT_INSTALL_DIR = $originalInstallDir }
}
