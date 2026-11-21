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

& cargo build --release --locked --manifest-path (Join-Path $serverFolder 'Cargo.toml')
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
# Input: Project root. Output: Repository root. Goal: Include project licensing. Description: The playback folder is directly below the repository.
$repositoryRoot = Split-Path -Parent $projectRoot
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'LICENSE') -Destination (Join-Path $stagingFolder 'PROJECT-LICENSE.txt') -Force
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'THIRD-PARTY-NOTICES.md') -Destination $stagingFolder -Force
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'DATA-AND-RIGHTS.md') -Destination $stagingFolder -Force
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'SECURITY.md') -Destination $stagingFolder -Force
# Input: Staging root. Output: Dependency notice directory. Goal: Preserve upstream licenses. Description: Electron's own LICENSE and Chromium notices stay at the package root.
$noticeFolder = Join-Path $stagingFolder 'third-party-notices'
New-Item -ItemType Directory -Path $noticeFolder -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $OpenSslBin '..\share\licenses\openssl\LICENSE') -Destination (Join-Path $noticeFolder 'OpenSSL-LICENSE.txt') -Force
# Input: Active Rust compiler. Output: Toolchain root. Goal: Preserve standard-library notices. Description: The rust-docs component supplies the library copyright inventory and license texts.
$rustToolchainRoot = & rustc --print sysroot
if ($LASTEXITCODE -ne 0) { throw 'Rust toolchain lookup failed' }
# Input: Toolchain location. Output: Distributed notice directory. Goal: Include statically linked runtime terms. Description: Install rust-docs if this directory is missing.
$rustNoticeRoot = Join-Path $rustToolchainRoot 'share\doc\rust'
Copy-Item -LiteralPath (Join-Path $rustNoticeRoot 'COPYRIGHT-library.html') -Destination (Join-Path $noticeFolder 'Rust-standard-library-COPYRIGHT.html') -Force
Copy-Item -LiteralPath (Join-Path $rustNoticeRoot 'licenses') -Destination (Join-Path $noticeFolder 'Rust-runtime-licenses') -Recurse -Force
# Input: Locked dependency graph. Output: Cargo package metadata. Goal: Identify bundled Rust libraries. Description: Fetching is complete after the release build.
$cargoMetadata = & cargo metadata --locked --offline --format-version 1 --manifest-path (Join-Path $serverFolder 'Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw 'Rust dependency inventory failed' }
# Input: Metadata JSON. Output: Parsed package list. Goal: Copy actual dependency notices. Description: The local project is covered by PROJECT-LICENSE.txt.
$dependencyGraph = $cargoMetadata | ConvertFrom-Json
# dependency. Input: Cargo package list. Output: One dependency. Goal: Preserve notices. Description: Registry packages have non-null sources.
foreach ($dependency in $dependencyGraph.packages | Where-Object { $_.source }) {
    # Input: Crate manifest location. Output: Crate directory. Goal: Find distributed license files. Description: Cargo stores the downloaded originals here.
    $crateFolder = Split-Path -Parent $dependency.manifest_path
    # Input: Crate root. Output: License and attribution files. Goal: Keep upstream terms. Description: Matches conventional license, notice and copyright names.
    $licenseFiles = @(Get-ChildItem -LiteralPath $crateFolder | Where-Object { $_.Name -match '^(LICENSE|LICENCE|COPYING|NOTICE|COPYRIGHT)' })
    if ($licenseFiles.Count -eq 0) { throw "No license text found for $($dependency.name). Review this dependency before releasing." }
    # Input: Dependency identity. Output: Unique notice subdirectory. Goal: Avoid overwriting different versions. Description: Names come from Cargo metadata.
    $crateNoticeFolder = Join-Path $noticeFolder "$($dependency.name)-$($dependency.version)"
    New-Item -ItemType Directory -Path $crateNoticeFolder -Force | Out-Null
    $licenseFiles | Copy-Item -Destination $crateNoticeFolder -Recurse -Force
}
$dependencyGraph.packages | Select-Object name, version, license, source | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $noticeFolder 'rust-dependencies.json') -Encoding utf8
if (!(Test-Path -LiteralPath (Join-Path $stagingFolder 'LICENSES.chromium.html'))) { throw 'Electron Chromium notices are missing' }
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
