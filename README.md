# Movie Shelf

Movie Shelf is a Windows movie viewer with a separate host app for sharing a movie folder from another PC. The viewer combines the servers and local folders you add. Local folders are read directly from disk.

## Get started

Download or build the ZIP in `.playback/delivery/MovieShelf-win64.zip`, extract it, and open `MovieShelfViewer.exe`. To share a folder from another PC, run `MovieShelfHost.exe` on that PC. The host window shows the address and pairing code needed by the viewer.

For simple step by step setup, including passwords, local folders, and multiple PCs, read the [setup guide](.playback/README.md).

## Build from source

The current app uses Rust for the host service and Electron for the desktop apps. Build and package it with `.playback/build-release.ps1`. The ZIP contains both Windows executables and their required helper files. Python is not used by the app or its build.
