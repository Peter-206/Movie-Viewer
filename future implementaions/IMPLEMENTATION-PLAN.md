# Implementation plan

Milestone 1 is underway in [.playback](../.playback/README.md). A startup-scanned combined catalog and anticipatory metadata preload now work in the prototype, including a two-host loopback check. The full milestones below remain incomplete. Persistent storage, pairing, artwork, and measured preload limits remain to be implemented.

## Milestone 1. Authenticated playback experiment

- Build an isolated Rust service and packaged Electron experiment with disposable media
- Prove encrypted, authenticated playback between two computers, including authorization on seek requests and peer certificate trust
- Record that the fixture's shared token and short-lived certificate are test credentials, not a public-access pairing design
- Evaluate an Electron custom protocol or restricted local proxy without disabling renderer security or certificate validation
- Verify play, pause, random seeking, cancellation, bounded buffering, and source disconnect errors with preserved position
- Test H.264 and AAC MP4, HEVC MKV, multiple audio tracks, embedded subtitles, external SRT, 4K HDR, and large high-bitrate samples where available
- Record measured compatibility, missing test cases, and capability-check failures
- Evaluate remuxing and native playback before committing to comprehensive transcoding

Done when a compatible movie streams and seeks inside packaged Electron over the authenticated connection, source loss preserves position, and a compatibility report supports the next player decision. No distributed catalog is needed yet.

## Milestone 2. Complete single-computer experience

- Add persistent identities, registered roots, configuration, and local SQLite storage
- Scan supported media without renaming files, reuse artwork, and extract stream details
- Import a copied Python catalog with legacy ID mapping and a reviewable report
- Build paged catalog, artwork, health, and streaming APIs
- Build library search, filters, details, metadata editing, and playback as one usable frontend path
- Include loading, empty, unsupported media, disconnected drive, and service unavailable states
- Add fullscreen, volume, seeking, keyboard controls, supported audio and subtitle selection, and local resume positions
- Run one independent Rust process per computer, with a launcher that attaches or starts it and an explicit sharing preference when Electron closes

Done when a sample drive can be scanned, browsed, edited, and played, repeated import creates no duplicates, and browsing stays responsive during scanning and playback.

## Milestone 3. Portable drives and metadata

- Define versioned portable records with movie, file, library, author node, revision, and base revision identities
- Keep movie edits in the logical catalog and file availability with the serving node
- Store portable identity, metadata, and referenced custom artwork in a hidden drive directory
- Import revisions on connection and preserve edits through drive letter changes
- Commit local edits and pending exports together, export atomically, and retry safely after interruptions
- Retain visibly pending edits for absent or read-only drives across restarts
- Detect conflicting revisions, preserve both values, and provide explicit resolution without ownership handoffs or clock-based winner selection
- Detect cloned library identities and offer reidentification
- Test multiple drives, renames, interrupted exports, repeated imports, explicit deletion revisions, and movement while the previous computer is offline

Done when metadata and poster corrections follow drives between computers, pending exports survive restart, conflicts remain recoverable, and repeated exchange creates no duplicates or inflated watch counts.

## Milestone 4. Two-computer library

- Replace the shared test token with approved pairing, a persistent identity for each installation, and a separate revocable credential for each peer
- Protect local keys and credentials with Windows user-scoped storage, keep them out of portable drives and logs, and support unpairing
- Support local, direct, and outbound-established relay connections so hosts can be reached across permitted networks without relying on inbound ports
- Keep the relay unable to authorize peers or read media, and show the active connection path in the interface
- Limit failed pairing and authentication attempts, request rates, and concurrent streams
- Add an aggregate catalog and artwork cache
- Load catalog records without media transfer. Predict likely playback from sustained hover, keyboard focus, or opening details, then prepare only one movie with a bounded buffer and cancel stale preparation
- Compare catalog revisions and refresh changed catalogs through consistent complete paged snapshots
- Apply completed snapshots atomically and retain previous records after interrupted refreshes
- Group movie copies only with strong identity evidence, preserve editions, and offer manual linking for uncertain matches
- Display source computer, drive, availability, and selectable copies
- Distinguish service running, drive connected, and peer reachable
- Preserve offline records and covers and select available compatible playback sources
- Keep metadata revision exchange separate from availability reporting
- Define peer metadata exchange and conflict semantics before treating a peer as a destination for pending edits
- Measure payload sizes and refresh times before introducing incremental replication

Done when two computers show one combined library, confidently matched copies share an entry, offline sources remain visible without false deletions, and either computer can stream from the other over an allowed direct or relay path. Unpaired and revoked computers must not receive catalog or media data.

## Milestone 5. Reliability and portable Windows release

- Verify reconnect recovery, Windows sleep, source disconnection, and preserved playback positions
- Restore discovery and remaining everyday browsing behavior from the existing product contract
- Add only remuxing, native playback, or conversion paths justified by the compatibility report
- Bound scanning, artwork, preparation, and conversion work with cancellation and temporary file cleanup
- Package Rust and Electron for clean Windows computers without development tools
- Resolve bundled media tool licensing and distribution requirements
- Test spaces, non-ASCII paths, repeated launcher clicks, multiple drive launchers, occupied ports, and clean shutdown
- Document sharing preferences, pairing, pending exports, conflicts, backups, logs, and updates
- Verify against copies of the existing library before migration

Done when the first-release scenario passes on two clean Windows computers using the distributed package.

## First-release acceptance scenario

Two Windows computers each have an external movie drive. Both applications display a combined library. Confidently identified copies are grouped, with editions kept distinct. Metadata and poster corrections persist when drives move while the previous computer is offline. Offline files remain visible and clearly unavailable. Either computer can stream a compatible movie from the other and seek without downloading the whole file. Source disconnection preserves position and offers a clear reconnection path. Pending edits and conflicts remain visible and recoverable.

## Later work

- Incremental synchronization if measurements justify it
- Automatic local network discovery after manual pairing works
- Cross-device progress and history with defined conflict rules
- Optional startup at sign-in and installed Windows service mode
- Wider internet access only after pairing, revocation, relay security, and managed-network policy checks pass
- Broader transcoding, hardware acceleration, bandwidth adaptation, and explicit offline downloads
- A standalone browser client after desktop playback and authentication are stable

## Decisions still open

| Question | Starting assumption |
| --- | --- |
| When are movie bytes fetched? | Browsing loads metadata and visible artwork. A strong playback signal may start a small bounded preload for one movie. Play works without a preload, and expensive conversion waits until Play |
| Must a computer remain on? | No coordinator is required. The selected source must be awake and reachable |
| What happens when Electron closes? | Follow an explicit sharing preference. The independent service can continue |
| Can I edit an offline library? | Save locally and visibly retain pending exports until a supported destination is available |
| Where do movie edits belong? | The logical catalog, with portable exports for synchronization and recovery |
| How are conflicts resolved? | Preserve competing values and request an explicit choice |
| Do movie files move automatically? | No, files stay on their drives |
| Which player should we use? | Test packaged Electron first, then evaluate remuxing and native playback from measured coverage |
| How do media requests authenticate? | Prove a custom protocol or restricted local proxy in milestone 1 |
| Is cloud hosting needed? | Media stays on the computers holding drives. Cross-network access may require an outbound-established relay when direct connections are blocked |
| Does this integrate with Jellyfin? | Jellyfin is a behavior reference. Integration is not requested |

## First implementation handoff

Read these notes and the current Rust and Electron app in `.playback`. Use the local agentic-coding and readable-code-math skills during implementation. Test filesystem operations against disposable roots and record measured results before expanding. Planning updates do not constitute completed implementation or verification.
