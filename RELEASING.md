# Publishing a Windows release

The default branch is `master`. A version tag runs the Windows build and packaged-app verification. After those pass, the workflow creates a draft pre-release with the tested Windows ZIP, source ZIP and SHA-256 checksums. It does not publish automatically.

## Repository setup

Enable GitHub Actions in Settings, then Actions, then General. Enable secret scanning, push protection, Dependabot alerts and private vulnerability reporting where your repository settings support them. Protect `master` with pull requests and the `verify` check after its first successful run.

Keep the repository description and About topics focused on the Windows Rust and Electron app. Avoid screenshots containing private movie collections or credentials.

## Create a release

1. Push `master` and wait for Verify Windows app to pass on GitHub
2. Update `CHANGELOG.md` with reviewed changes and the date, then commit and push it
3. Choose an unused version tag matching `.playback/player/package.json`, its lockfile and `.playback/server/Cargo.toml`. Update versions and lockfiles together for later releases
4. For the initial `0.1.0` version, run the following commands

```powershell
git tag -a v0.1.0 -m "Movie Shelf 0.1.0"
git push origin v0.1.0
```

Open Actions and wait for Prepare Windows release to finish. Open Releases and review the draft. Confirm it contains `MovieShelf-win64.zip`, `MovieShelf-source.zip` and `SHA256SUMS.txt`. Keep the first version marked as a pre-release while evaluating it, then publish when ready.

If the tag already exists, choose the next unused version and update app metadata first. Do not move a published tag. Fix failed checks before making another release.

## Package review

Extract the ZIP and keep its `MovieShelf` folder together. Both `MovieShelfHost.exe` and `MovieShelfViewer.exe` must be present. Confirm `PROJECT-LICENSE.txt`, Electron's `LICENSE`, `LICENSES.chromium.html`, OpenSSL's license and Rust dependency notices are included.

The build needs Git for Windows in its default location for the OpenSSL helper and license. A custom installation can be selected with `-OpenSslBin`. The expected license location is `../share/licenses/openssl/LICENSE` relative to that bin directory.

Check that the archive contains no movies, artwork, private settings, TLS keys, credentials, databases or developer dependency folders. Test the extracted package using [CONTRIBUTING.md](CONTRIBUTING.md). End users need neither Rust nor Node.js installed.

Release builds are currently unsigned. Code signing and automatic updates are not configured.
