# Movie Shelf conversation checkpoint

Recorded November 21, 2026 on branch `Server-setup`. This is a durable conversation summary with the user's key requests, not a verbatim export of every assistant response or tool result.

## Project history discussed

- August 12, 2026. Commit `5b6eee7` introduced the existing Python app, packaging specification, and batch launchers to Git
- August 12. Commit `01715da` expanded database-backed organization and sorting. Commit `11d6e0b` continued application development, followed by the styling branch merge
- November 19. Library cleanup reconciled displayed titles, folder names, artwork, and database paths. Backups and a rename map remain local user data
- November 19. Commit `791b15d` recorded the native Python UI rebuild with regression and package verification records
- November 19. Commit `4ecceaf` merged master and styling history while keeping the styling contents
- November 20 and 21 working tree. Rust and Electron replaced the Python entry points. The current host shares a startup-scanned catalog and media. The viewer combines remote hosts and direct local folders and plays inside the app

The historical review inspected Git, source, documentation, and saved verification notes. It did not rerun application tests. Earlier verification claims belong to their recorded runs.

## Three futures discussed

1. A dependable home movie app. Prioritize packaged two-PC playback, seeking, reconnect behavior, persistent catalogs, offline visibility, and durable resume positions
2. A collection that travels with drives. Add stable movie, asset, and library identities, portable metadata and artwork, recoverable pending exports, and explicit conflict handling
3. A broader personal streaming platform. Add supported cross-network access, revocable peer credentials, wider format support, more clients, and synchronized progress

The assistant recommended a reliable home-network release first, portable collection features next, and wider networking only when actual use justifies it. This was advice, not authorization to implement every future.

## User requests and hardware

The user asked for a project history map and three projected futures, with time taken to think through them.

The user then said, "i was thinking of making a non public iphone app so i can run it on my phone and making a apk for my tcl tv to sideload".

The user clarified, "its a new tcl google tv". The exact model is not yet known.

The user has no Mac and asked whether Claude or a GitHub repository would let us try iPhone development anyway.

The user requested conservative usage until 3:02 a.m. Eastern, stating that their usage limit resets at 3:01 a.m. The assistant cannot verify account quota or guarantee reset timing. This was a session-specific timing preference.

## Proposed phone and TV direction

- Keep movie files on the existing Windows hosts and drives
- Add a remote-friendly Android TV client for the TCL Google TV, delivered as a sideloadable APK
- Add a private iPhone viewer with touch navigation
- Reuse host catalog and streaming concepts, but replace Electron-specific connection and playback integration on each platform
- Prove host connection, authentication, certificate trust, and playback of a compatible movie on each physical device before expanding features
- Initial proposed controls are browsing, search, play, pause, seeking, source selection, and subtitles
- Home-network-only operation was proposed but has not been explicitly confirmed by the user

No phone or TV client has been implemented during this conversation. No final framework or Apple distribution method has been selected.

## iPhone options researched

Claude is not required. Changing coding assistants does not remove Apple build or signing requirements. A personally owned Mac is not required when using an appropriate cloud build workflow.

| Option | Purpose | Limitation |
| --- | --- | --- |
| Expo Go | Try a React Native prototype on a physical iPhone while developing on Windows | Runs within Expo Go and does not support arbitrary custom native integrations |
| Expo EAS Build | Build an installable iPhone app in the cloud | Its physical-device development build workflow requires an Apple Developer Program membership |
| SideStore | Install and refresh an existing IPA, with initial setup possible from Windows | Does not compile the Movie Shelf app. An IPA must first be built |
| TestFlight | Private testing without a public App Store listing | Requires the relevant developer membership and replacement builds because builds expire after 90 days |

Free Apple personal-team provisioning was also discussed. Its seven-day expiry makes maintenance part of that route. Do not confuse installation tools with compilation tools.

The assistant proposed Expo Go as an initial phone experiment. The existing host's authentication and certificate handling still need an early compatibility check. This is not a verified working integration.

References checked during the conversation

- [Expo Windows development FAQ](https://docs.expo.dev/faq/)
- [Expo physical iOS device cloud builds](https://docs.expo.dev/tutorial/eas/ios-development-build-for-devices/)
- [SideStore repository](https://github.com/SideStore/SideStore)
- [SideStore prerequisites](https://docs.sidestore.io/docs/installation/prerequisites.html)
- [Apple developer account guidance](https://developer.apple.com/help/account/basics/about-your-developer-account)
- [TestFlight overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/)
- [TCL Google TV platform explanation](https://support.tcl.com/en_CA/what-is-the-difference-between-android-tv-and-google-tv)

## Current limitations and next decisions

The current viewer groups copies by normalized titles. The planned architecture calls for stronger identities and preservation of distinct editions. The host scans at startup, and offline hosts currently disappear from the displayed collection. Persistent catalogs, portable edits, and separately revocable peer credentials remain further work.

Some roadmap text trails the implementation. Basic guided setup and artwork support exist even where older milestone text lists them as pending. Those basic features do not establish completion of the broader architecture.

Before expanding the clients, confirm the exact TV model, iPhone and iOS version, whether home-network-only playback is sufficient, and the preferred Apple installation route. Preserve the existing movie files and databases.

## Branch handoff

The user's final instruction was, "okay lets commit the local branch make sure this convo is saved, then im gonna make this branch the main branch or rebase or whatever".

The authorized action is a local checkpoint commit of the existing project changes and this record. The user intends to handle making this branch the main branch or integrating it afterward. No push, merge, rebase, branch rename, or force push was requested.
