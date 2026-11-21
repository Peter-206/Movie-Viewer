# Third-party notices

Movie Shelf's original code is licensed under MIT. The Windows package also contains third-party software with its own terms.

| Component | Included notices |
| --- | --- |
| Electron and its Node.js runtime | Package-root `LICENSE` |
| Chromium and its components, including media libraries | Package-root `LICENSES.chromium.html` |
| OpenSSL executable and DLLs from Git for Windows | `third-party-notices/OpenSSL-LICENSE.txt` |
| Rust host dependencies | Per-crate license files under `third-party-notices` and `rust-dependencies.json` |
| Rust standard library | `third-party-notices/Rust-standard-library-COPYRIGHT.html` and `Rust-runtime-licenses` |
| Movie Shelf | `PROJECT-LICENSE.txt` |

The build script copies notices from the actual installed dependencies. A missing crate license file or Chromium notice stops packaging. Keep these files with the application when redistributing it. Source manifests and lockfiles identify build dependencies, including Electron Packager, which is not installed for end users.

This inventory does not grant rights to movies, artwork or trademarks. Codec patent and other distribution requirements can depend on your use and jurisdiction. Review the exact release contents before distributing modified builds.
