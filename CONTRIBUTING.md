# Contributing

Open an issue before a large change. Explain the problem and reproduce it with synthetic media rather than a private collection.

## Build and check

Use Windows 10 or 11, Node.js 24, npm, stable Rust with the MSVC build tools, and Git for Windows. The packager uses the OpenSSL executable, DLLs and license supplied by Git for Windows.

Run from the repository root

```powershell
npm ci --prefix .playback/player
rustup component add rust-docs
cargo test --locked --manifest-path .playback/server/Cargo.toml
powershell -NoProfile -ExecutionPolicy Bypass -File .playback/build-release.ps1
```

The build produces `.playback/delivery/MovieShelf-win64.zip`. Extract it to a temporary folder. With an MP4 fixture you own, run

```powershell
node .playback/verification/setup-flow.cjs "C:\Temp\MovieShelf" "C:\Temp\sample.mp4"
```

The package folder must contain both executables. The test uses loopback ports and disposable profiles and checks pairing, source persistence, navigation, local and remote playback, fullscreen, byte ranges and stale media IDs. Rust currently has no unit tests, so `cargo test` checks compilation but does not replace this package test.

GitHub Actions generates an original test-pattern clip with FFmpeg. That clip and FFmpeg are test tools, not shipped assets.

## Pull requests

- Describe the change and checks you actually ran
- Preserve existing comments and keep changes focused
- Keep media, artwork, catalogs, credentials, pairing codes and private paths out of commits and screenshots
- Only contribute material you have permission to share, under the project's MIT license

The root-folder exclusions in `.gitignore` protect the private collection in this workspace. Explicitly allow any legitimate new source folder. Review `git diff --cached --stat` before committing.
