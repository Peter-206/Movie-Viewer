param(
    # Input: Installed OpenSSL folder. Output: Helper path. Goal: Package certificate creation. Description: Git for Windows supplies the verified helper binaries.
    [string]$OpenSslBin = 'C:\Program Files\Git\mingw64\bin'
)

# Input: PowerShell runtime. Output: Terminating command errors. Goal: Stop on failed packaging steps. Description: Prevents a partial ZIP from being reported as complete.
$ErrorActionPreference = 'Stop'

# Input: Script location. Output: Playback project root. Goal: Keep all paths inside this project. Description: Resolve the script directory once.
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
# Input: Project root. Output: Rust host directory. Goal: Build the server. Description: Cargo uses its existing lockfile.
$serverFolder = Join-Path $projectRoot 'server'
# Input: Project root. Output: Electron source directory. Goal: Package the two desktop roles. Description: Both role executables share one resources folder.
$playerFolder = Join-Path $projectRoot 'player'
# Input: Electron build. Output: Package directory. Goal: Copy release resources. Description: Packager names this directory deterministically.
$appFolder = Join-Path $playerFolder 'dist\MovieShelfViewer-win32-x64'
# Input: Package directory. Output: Resource directory. Goal: Locate bundled helpers. Description: Electron exposes this as process.resourcesPath.
$resourceFolder = Join-Path $appFolder 'resources'
# Input: Project root. Output: Delivery directory. Goal: Store the ZIP. Description: Generated artifacts remain outside Git.
$deliveryFolder = Join-Path $projectRoot 'delivery'
# Input: Delivery directory. Output: Temporary package folder. Goal: Give the extracted ZIP one clear top folder. Description: Removed after archive verification.
$stagingFolder = Join-Path $deliveryFolder 'MovieShelf'
# Input: Delivery directory. Output: Final ZIP path. Goal: Share one package. Description: It contains the two named apps and README.
$zipPath = Join-Path $deliveryFolder 'MovieShelf-win64.zip'

& cargo build --release --offline --manifest-path (Join-Path $serverFolder 'Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw 'Rust host build failed' }
Push-Location $playerFolder
try {
    & npm run package:windows
    if ($LASTEXITCODE -ne 0) { throw 'Electron package failed' }
} finally { Pop-Location }

Copy-Item -LiteralPath (Join-Path $appFolder 'MovieShelfViewer.exe') -Destination (Join-Path $appFolder 'MovieShelfHost.exe') -Force
Copy-Item -LiteralPath (Join-Path $serverFolder 'target\release\movie-playback-host.exe') -Destination (Join-Path $resourceFolder 'movie-playback-host.exe') -Force
 # helperName. Input: Required helper list. Output: One filename. Goal: Copy every runtime dependency. Description: Each file comes from the chosen OpenSSL folder.
foreach ($helperName in @('openssl.exe', 'libcrypto-3-x64.dll', 'libssl-3-x64.dll')) {
    # Input: Helper file list. Output: One bundled executable or DLL. Goal: Make host setup independent of other installs. Description: Missing helpers stop the build.
    $helperPath = Join-Path $OpenSslBin $helperName
    Copy-Item -LiteralPath $helperPath -Destination (Join-Path $resourceFolder $helperName) -Force
}

New-Item -ItemType Directory -Path $deliveryFolder -Force | Out-Null
if (Test-Path -LiteralPath $stagingFolder) {
    # Input: Existing staging path. Output: Absolute path. Goal: Limit cleanup to the intended project folder. Description: Rejects unexpected path resolution.
    $resolvedStagingFolder = (Resolve-Path -LiteralPath $stagingFolder).Path
    # Input: Delivery path. Output: Absolute root. Goal: Verify cleanup scope. Description: Staging must be a direct child of delivery.
    $resolvedDeliveryFolder = (Resolve-Path -LiteralPath $deliveryFolder).Path
    if ($resolvedStagingFolder -ne (Join-Path $resolvedDeliveryFolder 'MovieShelf')) { throw 'Unsafe staging path' }
    Remove-Item -LiteralPath $resolvedStagingFolder -Recurse -Force
}
Copy-Item -LiteralPath $appFolder -Destination $stagingFolder -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $stagingFolder 'README.md') -Force
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
& tar.exe -a -c -f $zipPath -C $deliveryFolder 'MovieShelf'
if ($LASTEXITCODE -ne 0) { throw 'ZIP creation failed' }
& tar.exe -tf $zipPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'ZIP verification failed' }
# Input: Verified staging directory. Output: Removed temporary copy. Goal: Leave only the ZIP and build directory. Description: Scope was checked above.
$verifiedStagingFolder = (Resolve-Path -LiteralPath $stagingFolder).Path
if ($verifiedStagingFolder -ne (Join-Path (Resolve-Path -LiteralPath $deliveryFolder).Path 'MovieShelf')) { throw 'Unsafe staging cleanup path' }
Remove-Item -LiteralPath $verifiedStagingFolder -Recurse -Force
Write-Output $zipPath
