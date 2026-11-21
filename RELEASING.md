# Publishing a Windows release

The default branch is `master`. Builds, verification and releases are manual. Pushing a version tag does not run checks or create a release.

## Repository setup

Enable secret scanning, push protection, Dependabot alerts and private vulnerability reporting where your repository settings support them. If branch protection requires the old `verify` check, remove that requirement because it no longer runs.

Keep the repository description and About topics focused on the Windows Rust and Electron app. Avoid screenshots containing private movie collections or credentials.

## Create a release

1. Update `CHANGELOG.md` with reviewed changes and the date
2. Choose an unused version tag matching `.playback/player/package.json`, its lockfile and `.playback/server/Cargo.toml`. Update versions and lockfiles together for later releases
3. Build and test locally using [CONTRIBUTING.md](CONTRIBUTING.md), then complete the package review below
4. Commit and push the tested changes to `master`, then tag that commit. For the initial `0.1.0` version, the commands are

```powershell
git tag -a v0.1.0 -m "Movie Shelf 0.1.0"
git push origin v0.1.0
```

Open Releases on GitHub and create a draft for the pushed tag. Attach the tested `.playback/delivery/MovieShelf-win64.zip`. GitHub provides source archives for the tag. Keep the first version marked as a pre-release while evaluating it, then publish when ready.

If the tag already exists, choose the next unused version and update app metadata first. Do not move a published tag. Fix failed checks before making another release.

## Package review

Extract the ZIP and keep its `MovieShelf` folder together. Both `MovieShelfHost.exe` and `MovieShelfViewer.exe` must be present. Confirm `PROJECT-LICENSE.txt`, Electron's `LICENSE`, `LICENSES.chromium.html`, OpenSSL's license and Rust dependency notices are included.

The build needs Git for Windows in its default location for the OpenSSL helper and license. A custom installation can be selected with `-OpenSslBin`. The expected license location is `../share/licenses/openssl/LICENSE` relative to that bin directory.

Check that the archive contains no movies, artwork, private settings, TLS keys, credentials, databases or developer dependency folders. Test the extracted package using [CONTRIBUTING.md](CONTRIBUTING.md). End users need neither Rust nor Node.js installed.

Release builds are currently unsigned. Code signing and automatic updates are not configured.
