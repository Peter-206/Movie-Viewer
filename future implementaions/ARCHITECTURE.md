# Proposed architecture

Status is a design for the full system. The [.playback](../.playback/README.md) app now scans library roots at startup, serves authenticated catalogs and media, pairs hosts through an app screen, merges their catalogs, and reads local folders directly. Persistent catalogs, artwork, and cross-network access remain proposed.

## Computers and drives

Each computer runs a Rust media service. The service scans registered roots, keeps its own SQLite database, exposes catalog and artwork endpoints, and serves movie streams. Several drives on one computer share that service.

The Electron application connects to the local service and paired remote services. A local aggregate catalog supports searching across them. Local and direct operation needs no coordinator. Cross-network relay access needs an available relay. A movie remains available only while a computer serving a copy is reachable and its drive is connected.

One computer must provide the complete browse and playback experience by itself. The same installation can host its local drives and watch their movies, and can also watch movies served by paired computers. The initial prototype may use its authenticated loopback HTTP path for local playback. A future direct file path or local protocol is an optimization to measure after the core workflow works.

Do not share a writable SQLite database over the network. Each service owns its database. Synchronization happens through an API.

Media hosting remains on the Windows computers holding the drives. A relay may be needed for cross-network connections, but it must not store movie files. The Rust process runs independently of Electron. Closing the interface follows an explicit sharing preference rather than automatically stopping the server. A Windows service installation is not required for the first release. Startup at sign-in is optional later work.

The interface distinguishes service running, drive connected, and peer reachable. Windows sleep interrupts sharing. Preserve playback position and offer reconnection when the source returns.

## Launching from a batch file

The future release includes a Windows batch launcher, the Rust service binary, the packaged Electron app, and versioned configuration. End users should not need Python, Rust, or Node installed.

Launching from a drive registers the directory beside the launcher as a library root. The launcher contacts the existing local service or starts one if needed. It then opens or focuses the desktop app. Starting launchers from two drives on the same computer should register both roots without starting competing services or duplicate scans.

Store machine settings and pairing credentials in the user's application data directory. Store a small library identity file on each writable drive, with a local registration fallback for read-only drives. Keep drive-specific configuration separate from machine identity. Copying a launcher to another computer must not copy that computer's credentials.

Use a hidden application directory on writable drives for portable identity, versioned metadata records, and referenced custom artwork. Local databases remain the fast searchable catalogs. Portable exports provide synchronization and recovery when a drive moves to another computer, including when its previous computer is offline.

Identify roots through persistent library IDs and their current mounted locations. Do not make a drive letter or IP address the permanent identity. Detect cloned library identity files and offer a reidentification flow instead of silently treating two changing copies as one drive.

## Catalog ownership and synchronization

| Record | Proposed identity and owner |
| --- | --- |
| Computer | Persistent node ID and pairing identity owned by the local installation |
| Library | Persistent library ID that follows the drive |
| File | Stable asset ID within a library, with a relative path and media details |
| Movie | Logical movie record linked to one or more file copies |
| Artwork | Content hash plus size and format, served by an owning node |
| Metadata revision | Record ID, stable author node ID, revision ID, base revision, and operation |
| Playback progress | Profile, movie or edition, position, session ID, and revision |

Keep physical file identity separate from movie identity. Two copies of a movie can share a title while differing in edition, language, or quality. Preserve separate entries until an identity match is reliable. Do not deduplicate by title alone or read every full movie just to populate the initial catalog.

Keep three explicit identities. A movie ID identifies the logical movie, a file ID identifies a particular media asset, and a library ID identifies its physical source independently of the serving node. Preserve file IDs across renames where the match is reliable. Replacing a file can create a new asset linked to the existing movie. Use external movie identifiers and conservative matching, with manual linking for uncertain matches. Keep editions distinct and never silently substitute a different timeline.

Begin network catalog synchronization with a revision number per serving catalog and complete paged snapshots. Compare revisions on reconnect and refresh changed catalogs. Pages must belong to one consistent snapshot. Stage and apply a completed snapshot atomically. An interrupted refresh retains the previous catalog. Measure payload size and refresh time before adding an incremental event log, durable cursors, or replication machinery.

An unreachable computer or missing drive means unavailable, not deleted. Keep its cached records and covers. Confirm removals through a successful scan or an explicit removal action.

Movie-level edits belong to the user's logical catalog, not exclusively to a drive or serving computer. File paths, stream details, and availability belong to file copies and their serving nodes. Progress belongs to a profile. Scanned metadata must not overwrite user edits.

Treat portable metadata exchange and network availability synchronization as separate mechanisms. Import portable revisions when a drive connects. Commit a local metadata edit and its pending export record in the same SQLite transaction, then export using atomic file replacement. Retry interrupted exports idempotently. Export referenced custom artwork as well as its metadata so poster corrections survive a drive move.

Allow local edits while a drive or peer is absent or read-only. Clearly mark edits as pending until they reach a writable registered drive containing the associated movie or an explicitly supported peer metadata destination. Never imply that a local save is already portable. Retain pending edits across restarts.

Use record revisions, base revisions, and stable author node IDs to detect competing edits. Preserve both conflicting values and offer explicit resolution in the first version. Do not resolve conflicts using wall-clock time alone. Record explicit deletion revisions so imports cannot resurrect removed metadata. No ownership handoff is required when a drive moves. Define the portable record schema and conflict examples before implementing exchange.

Initially keep viewing progress on the watching desktop. Cross-device progress synchronization is a later milestone with explicit conflict rules. Do not merge watch counts by blindly adding totals from different catalogs.

## Metadata and covers

Return paged catalog data quickly and fetch thumbnails as they become visible. Download full covers on demand. Cache artwork by content hash so unchanged images are reused across sessions and refreshed when the source changes.

Use a lightweight event connection or polling to signal catalog changes. Large images and movie bytes travel through ordinary HTTP requests, separately from catalog notifications. Limit scan and artwork work so browsing and playback remain responsive.

## Playback and preloading

1. Browsing loads catalog records and visible artwork without requesting movie bytes. A brief hover, keyboard focus, or selection can signal likely playback
2. The service verifies the asset is available and compares its media streams with the client's supported capabilities
3. The app receives a session ID, playback method, duration, and authorized stream location
4. When a prediction is strong enough, the player begins a small bounded buffer for that movie. The details screen shows preparing, ready, or an actionable error
5. Pressing Play opens the player inside the app using the prepared session
6. Seeking requests data around the new position. Moving to another movie or closing the viewer cancels unnecessary preparation
7. Progress saves periodically and when playback pauses or ends

Anticipatory preloading starts only after a strong interaction signal, such as sustained hover, keyboard focus, or opening details. Catalog synchronization and scrolling do not fetch movie bytes. Keep at most one predicted movie prepared per viewer, cap buffered bytes and time, and cancel stale work when attention moves elsewhere. Play must work even when no preload happened. Browser preload settings alone do not guarantee a particular buffer size. Measure actual buffering behavior and bound any custom cache. If autoplay is wanted on movie selection, that can become a setting.

Prepare only the predicted or selected movie and cancel stale work on attention changes. Defer expensive conversion until Play. Capability checks guide playback selection but actual playback can still fail. Show whether direct playback is supported, an alternative engine or conversion is needed, or compatibility remains unverified.

Begin with direct playback over HTTP byte ranges for formats the chosen player supports. Correct seeking requires range handling, including partial responses, unsatisfiable ranges, cancellation, and stable file validators. See [MDN's HTTP range guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests).

Explore remuxing and native playback before committing to comprehensive video transcoding. Remuxing changes the container without re-encoding compatible streams. Audio conversion and video transcoding are separate workloads. Add only paths justified by measured compatibility results. Jellyfin documents these distinctions in its [transcoding overview](https://jellyfin.org/docs/general/post-install/transcoding/). FFmpeg is a candidate for these jobs, with concurrency limits, cancellation, temporary file cleanup, and a separate packaging review before distribution.

Electron does not guarantee playback of every local movie format. Test actual video, audio, containers, and subtitles on the packaged app. Jellyfin's [codec support documentation](https://jellyfin.org/docs/general/clients/codec-support/) explains why client capabilities and subtitles affect playback choices. Investigate an embedded native player if the web player requires too much conversion. Keep that decision open until the experiment produces evidence.

If a source disconnects during playback, show the failure and retain the position. Another copy is only a safe seamless replacement when it has matching content and timeline. Different editions should require a new playback session.

## Pairing and application boundaries

Start with manually entered local network addresses and a visible pairing flow. Discovery can suggest computers later, but discovering a computer must not automatically authorize it. Keep the current single-file host as a test fixture. Do not expose it broadly or treat its shared token as the finished pairing system.

Each installation needs its own persistent key and a user-approved pairing step that verifies the other computer's identity. A short-lived pairing code may help users confirm the connection, but it must not become the permanent access secret. Grant each paired computer its own revocable credential and display its name and last connection in sharing settings. Removing a computer must stop its future catalog and media access without changing every other pairing. Never use a reusable human password as a URL parameter or as the credential on every media request.

Encrypt every catalog, artwork, control, and media request. Verify the peer identity on every connection, including reconnections and relay paths. Protect local private keys and pairing credentials using Windows Credential Manager or user-scoped DPAPI, keep them out of drive metadata and release packages, and never log them. If a password is offered to unlock local sharing, store only a salted password verifier and limit failed attempts. See [Microsoft's credential storage guidance](https://learn.microsoft.com/en-us/windows/win32/SecBP/handling-passwords) and [NIST's authenticator guidance](https://pages.nist.gov/800-63-4/sp800-63b/authenticators/).

Treat transport and authorization separately. Use a local path for the same computer, a direct connection where permitted, and an outbound-established relay path where direct reachability fails. Encrypt peer-to-peer traffic end to end through any relay, so the relay cannot read media or grant access by itself. Check the rules of managed networks before using an overlay or relay there. The interface must show whether a source is local, direct, or relayed and allow sharing to be stopped. Do not enable internet-facing direct access by default.

Limit failed authentication and pairing attempts, concurrent streams, and request rates. Apply the same authorization to byte ranges and retries as to the first media request. Keep a minimal connection audit without secrets. Test unpaired clients, revoked peers, expired credentials, changed certificates, and relay reconnection before a wider release.

Each service has a persistent cryptographic identity. Prove authenticated media delivery in the first playback experiment, including peer certificate trust and authorization on seek requests. A normal video element cannot conveniently attach arbitrary authorization headers to every request. Evaluate an Electron-controlled custom protocol or a restricted local proxy. Any bridge must authorize callers and target only paired services, without becoming an arbitrary forwarding endpoint. Do not bypass certificate validation or disable renderer security to make the experiment work.

Authorize catalog, artwork, and playback requests. Resolve opaque asset IDs to registered files on the server. Never expose an endpoint that serves arbitrary client-supplied filesystem paths. Handle junctions, symlinks, and path traversal when enforcing root boundaries.

Keep Electron's renderer sandboxed with context isolation and no Node integration. Use a narrow preload bridge for desktop actions. Validate IPC senders and arguments. The launcher starts the independent Rust process if needed, and Electron attaches to it. Expose explicit sharing controls through an authenticated local interface. See Electron's [process model](https://www.electronjs.org/docs/latest/tutorial/process-model) and [security guidance](https://www.electronjs.org/docs/latest/tutorial/security).

## Migration

Read a copy of the existing `movies.db` and map legacy IDs using both source library identity and old row ID. Import existing metadata and genres, associate covers, and resolve file paths relative to each registered root. Produce an import report for missing files and ambiguous matches.

Make import repeatable without duplicating records or watch counts. Keep original files and databases unchanged during migration. The future scanner should discover media without automatically renaming it. Existing Python filename normalization is behavior to review deliberately rather than carry over by accident.
