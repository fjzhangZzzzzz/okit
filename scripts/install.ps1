$ErrorActionPreference = 'Stop'
$repo = 'fjzhangZzzzzz/okit'
$okitHome = if ($env:OKIT_HOME) { $env:OKIT_HOME } else { Join-Path $HOME '.okit' }
$installDir = if ($env:OKIT_INSTALL_DIR) { $env:OKIT_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\okit\bin' }
$version = $env:OKIT_VERSION

if (-not [Environment]::Is64BitOperatingSystem) { throw 'okit requires a 64-bit Windows system' }
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
if (-not $version) {
    $version = (Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest").tag_name
}
if ($version -notmatch '^v\d+\.\d+\.\d+(?:[-+].+)?$') { throw "Invalid OKIT_VERSION: $version" }

$plainVersion = $version.TrimStart('v')
$asset = "okit_${plainVersion}_windows_${arch}.zip"
$base = "https://github.com/$repo/releases/download/$version"
$temp = Join-Path ([IO.Path]::GetTempPath()) ("okit-install-" + [guid]::NewGuid())
$metadataTemp = $null
$binaryTemp = $null
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $archive = Join-Path $temp $asset
    $checksums = Join-Path $temp 'checksums.txt'
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile $archive
    Invoke-WebRequest -UseBasicParsing -Uri "$base/checksums.txt" -OutFile $checksums
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
