# Data and rights

## Code and media

Original project code uses the MIT License in the root LICENSE file. Commercial use is allowed without contacting the author. Copies and substantial portions must retain the copyright and license notices. MIT does not require a visible credit screen or endorsement.

This license does not grant rights to movies, artwork, trademarks or third-party data. Only share media and artwork when you have the necessary rights. Having a local file does not establish permission to distribute it.

## Stored information

The Electron viewer saves local folder paths, remote addresses, certificate pins and password-derived bearer credentials in `sources.json` under its user data directory. The host creates a local identity folder containing TLS certificates, private keys and a credential file. Treat these files as secrets. Password-derived credentials can authorize requests even though the plain password is not saved.

The app scans selected movie folders and reads local `cover.jpg` or `thumb.jpg` artwork. The host builds its catalog at startup. It does not use the legacy `movies.db` file or rename movie files. Existing private databases can stay on disk but are not included in Git or releases.

## Network behavior

Remote sources use HTTPS on port 8443. The viewer verifies the host using its pairing code and saved certificate. Configured hosts receive authenticated catalog, artwork and media requests. Local sources are read directly from disk.

The Rust and Electron app does not include the old IMDb cover downloader. Supply local artwork you have permission to use. Movie files, artwork, populated catalogs, pairing credentials and private settings do not belong in releases.

This document describes the current implementation. It does not certify legal compliance.
