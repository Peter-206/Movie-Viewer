# Future Movie Shelf

Started November 19, 2026. This directory holds planning notes for a future Rust and Electron version. The [.playback](../.playback/README.md) app now pairs hosts through a guided setup, combines their catalogs, and reads local folders directly. The larger architecture below remains in development.

## What I want

I want to run a batch file on different computers with different movie drives and see everything in one app. Each computer should share its movie metadata and covers. When I select a movie, the app should start preparing and buffering it so I can watch it inside the app, similar to Jellyfin.

The movies should stay on their original drives. Browsing the library should not download whole movies.

## Starting direction

- Rust handles scanning, catalog storage, networking, and streaming
- Electron hosts the web interface and the player. Its shell and frontend still use JavaScript or TypeScript
- One Rust service runs per computer and can manage several movie drives
- The service runs independently of Electron, with explicit background sharing controls
- Each drive has a persistent library identity that survives a drive letter change
- Movie edits belong to the logical catalog, with portable metadata and custom artwork exports on writable drives
- Offline edits remain visibly pending and competing revisions are preserved for explicit resolution
- Every desktop app combines the catalogs of its paired computers
- Metadata and covers are cached locally so browsing stays useful when a computer is offline
- Movie bytes stream directly from the computer holding the selected file
- The first version works on the local network with explicit pairing and manual addresses
- Catalog exchange starts with revision checks and complete snapshots. Incremental synchronization waits for measured need

These are proposed implementation choices. The requested Rust backend, Electron app, distributed libraries, batch launch, buffering, and playback inside the app define the goal.

## Notes in this directory

- [Architecture](ARCHITECTURE.md) describes services, identities, synchronization, launch behavior, and playback
- [Implementation plan](IMPLEMENTATION-PLAN.md) breaks the work into milestones with checks and open decisions

## Current project context

The current app is the Rust and Electron package in [.playback](../.playback/README.md). It combines catalogs from paired hosts and direct local folders. The old Python app and its launchers have been removed. The existing `movies.db` and movie artwork remain as user data for a future migration. Work from copies when building an importer. Separate drives may contain the same old numeric database IDs.

## Next concrete step

Build a playback experiment using disposable media. Prove authenticated encrypted playback, buffering, seeking, and source disconnect handling between Rust and packaged Electron on different computers. Resolve media request authorization and certificate trust during this experiment. Test representative formats before choosing the player and any conversion paths.

Then build the single-computer browse-to-play experience, portable drive metadata, the combined two-computer library, and release reliability. The first release must preserve corrections when drives move, group confidently matched copies, retain offline catalogs, and stream compatible movies between two Windows computers. The implementation plan defines the full acceptance scenario.
