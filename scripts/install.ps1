$ErrorActionPreference = 'Stop'
$repo = 'fjzhangZzzzzz/okit'
$okitHome = if ($env:OKIT_HOME) { $env:OKIT_HOME } else { Join-Path $HOME '.okit' }
$installDir = if ($env:OKIT_INSTALL_DIR) { $env:OKIT_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\okit\bin' }
$requestedVersion = $env:OKIT_VERSION
$releaseRoot = if ($env:OKIT_RELEASE_BASE_URL) { $env:OKIT_RELEASE_BASE_URL.TrimEnd('/') } else { "https://github.com/$repo/releases" }

function Assert-SafeFilename([string]$Name, [string]$Kind) {
    if (-not $Name -or $Name -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$' -or [IO.Path]::GetFileName($Name) -ne $Name) {
        throw "Invalid $Kind filename in release manifest: $Name"
    }
}

if (-not [Environment]::Is64BitOperatingSystem) { throw 'okit requires a 64-bit Windows system' }
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
if ($requestedVersion -and $requestedVersion -notmatch '^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') { throw "Invalid OKIT_VERSION: $requestedVersion" }

$manifestURL = if ($requestedVersion) {
    "$releaseRoot/download/$requestedVersion/release-manifest.json"
} else {
    "$releaseRoot/latest/download/release-manifest.json"
}
$manifest = Invoke-RestMethod -Uri $manifestURL
if ($manifest.schema -ne 1) { throw "Unsupported release manifest schema: $($manifest.schema)" }
$version = [string]$manifest.version
if ($version -notmatch '^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') { throw "Invalid version in release manifest: $version" }
if ($requestedVersion -and $version -ne $requestedVersion) { throw "Release manifest version $version does not match requested version $requestedVersion" }
$target = "windows-$arch"
$assetProperty = $manifest.assets.PSObject.Properties[$target]
if (-not $assetProperty -or -not $assetProperty.Value) { throw "Release manifest has no asset for $target" }
$asset = [string]$assetProperty.Value
$checksumsName = [string]$manifest.checksums
Assert-SafeFilename $asset 'asset'
Assert-SafeFilename $checksumsName 'checksums'

$base = "$releaseRoot/download/$version"
$temp = Join-Path ([IO.Path]::GetTempPath()) ("okit-install-" + [guid]::NewGuid())
$metadataTemp = $null
$binaryTemp = $null
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $archive = Join-Path $temp $asset
    $checksums = Join-Path $temp $checksumsName
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile $archive
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$checksumsName" -OutFile $checksums
    $line = Get-Content -LiteralPath $checksums | Where-Object { $_ -match "\s\*?$([regex]::Escape($asset))$" } | Select-Object -First 1
    if (-not $line) { throw "Checksum for $asset is missing" }
    $expected = ($line -split '\s+')[0]
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
    if ($actual -ne $expected) { throw "Checksum mismatch for $asset" }

    Expand-Archive -LiteralPath $archive -DestinationPath $temp -Force
    $source = Join-Path $temp 'okit.exe'
    if (-not (Test-Path -LiteralPath $source)) { throw 'okit.exe is missing from release archive' }
    New-Item -ItemType Directory -Force -Path $installDir, $okitHome | Out-Null
    $executable = Join-Path $installDir 'okit.exe'
    $binaryTemp = Join-Path $installDir ('.okit-install-' + [guid]::NewGuid() + '.exe')
    $backup = "$executable.okit-old"
    Copy-Item -LiteralPath $source -Destination $binaryTemp
    try {
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        if (Test-Path -LiteralPath $executable) { Move-Item -LiteralPath $executable -Destination $backup }
        Move-Item -LiteralPath $binaryTemp -Destination $executable
        $binaryTemp = $null
    }
    catch {
        if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $executable)) { Move-Item -LiteralPath $backup -Destination $executable }
        throw
    }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    $addedPath = $false
    if (-not ($entries | Where-Object { $_.TrimEnd('\') -ieq $installDir.TrimEnd('\') })) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $installDir) -join ';'), 'User')
        $addedPath = $true
    }
    $metadata = [ordered]@{
        method = 'official'; version = $version; channel = 'stable'
        executable = $executable
        path_entries = @()
        managed_files = @()
    }
    if ($addedPath) { $metadata.path_entries = [string[]]@($installDir) }
    $metadataJSON = $metadata | ConvertTo-Json
    $metadataTemp = Join-Path $okitHome ('.install-' + [guid]::NewGuid() + '.tmp')
    [IO.File]::WriteAllText($metadataTemp, $metadataJSON, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $metadataTemp -Destination (Join-Path $okitHome 'install.json') -Force
    $metadataTemp = $null
    Write-Output "okit $version installed to $executable"
    if ($addedPath) { Write-Output 'Open a new terminal to use okit.' }
}
finally {
    if ($binaryTemp) { Remove-Item -LiteralPath $binaryTemp -Force -ErrorAction SilentlyContinue }
    if ($metadataTemp) { Remove-Item -LiteralPath $metadataTemp -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
