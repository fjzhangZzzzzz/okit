param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw $Message }

$resolvedExecutable = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
$executableDir = Split-Path -Parent $resolvedExecutable
$smokeRoot = Join-Path ([IO.Path]::GetTempPath()) ('okit-runtime-windows-' + [guid]::NewGuid())
$originalPath = $env:PATH
$originalOKITHome = $env:OKIT_HOME

try {
    New-Item -ItemType Directory -Path $smokeRoot | Out-Null
    $env:PATH = $executableDir + [IO.Path]::PathSeparator + $env:PATH
    $env:OKIT_HOME = Join-Path $smokeRoot 'okit-home'

    $actual = @(& okit.exe --version)
    if ($LASTEXITCODE -ne 0) { Fail "version command exited with status $LASTEXITCODE" }
    if ($actual -notcontains "okit $Version") { Fail "version output does not contain okit $Version" }

    & okit.exe --help | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "--help exited with status $LASTEXITCODE" }

    & okit.exe upgrade --help | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "upgrade help exited with status $LASTEXITCODE" }
    & okit.exe uninstall --help | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "uninstall help exited with status $LASTEXITCODE" }

    Write-Host 'Windows runtime smoke test passed'
}
finally {
    $env:PATH = $originalPath
    if ($null -eq $originalOKITHome) { Remove-Item Env:OKIT_HOME -ErrorAction SilentlyContinue } else { $env:OKIT_HOME = $originalOKITHome }
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
}
