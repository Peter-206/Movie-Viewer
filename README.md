# Movie Shelf

[![Windows checks](https://github.com/Peter-206/Movie-Viewer/actions/workflows/verify.yml/badge.svg)](https://github.com/Peter-206/Movie-Viewer/actions/workflows/verify.yml)

Movie Shelf is a Windows movie viewer with a separate host app for sharing a movie folder from another PC. The viewer combines the servers and local folders you add. Local folders are read directly from disk.

## Get started

Download `MovieShelf-win64.zip` from [Releases](https://github.com/Peter-206/Movie-Viewer/releases), extract it, and open `MovieShelfViewer.exe`. If no release has been published yet, build the ZIP using the instructions below. To share a folder from another PC, run `MovieShelfHost.exe` on that PC. The host window shows the address and pairing code needed by the viewer.

For simple step by step setup, including passwords, local folders, and multiple PCs, read the [setup guide](.playback/README.md).

## Build from source

The current app uses Rust for the host service and Electron for the desktop apps. Build and package it with `.playback/build-release.ps1`. The ZIP contains both Windows executables and their required helper files. Python is not used by the app or its build.

See [CONTRIBUTING.md](CONTRIBUTING.md) for prerequisites and exact build and test commands. See [RELEASING.md](RELEASING.md) for version tags and draft releases.

## License and data

Original code is licensed under [MIT](LICENSE), copyright Peter-206. Commercial use is allowed with the required copyright and license notices preserved. Bundled dependencies have their own [notices](THIRD-PARTY-NOTICES.md).

Movies, artwork, private settings and databases are excluded from Git and release packages. The app reads local artwork and does not include an online cover downloader. Read [data and rights](DATA-AND-RIGHTS.md) and [security guidance](SECURITY.md) before sharing a library. Use a trusted private network. The current Windows package is unsigned.
