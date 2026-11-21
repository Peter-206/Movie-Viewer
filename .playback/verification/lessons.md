# Verification lessons

## CI-001. 2026-11-21

Tags. GitHub Actions, packaging, verification limits

The offline Cargo metadata defect was reproduced and fixed locally, but that did not establish that the hosted workflow was repaired. The user reported continued failures and requested removal of Actions. Removed both workflows and changed the documentation to manual builds and releases. Hosted failure diagnosis remains unresolved. Local reproduction proves a specific defect, not the cause of every hosted failure.

## OCCLUSION-001. 2026-11-21

The automation desktop reported a focused viewer as hidden, blocking fullscreen and sometimes playback. Page.bringToFront alone did not resolve it. Test launches now disable native window occlusion calculations and occluded-window backgrounding. These flags apply only to the test process. Two extracted-package tests passed, including synthetic artwork, with the existing fullscreen element and monitor-size assertions intact.

## FULLSCREEN-001. 2026-11-20

Tags. Electron, fullscreen, native controls, permissions

Removing the custom fullscreen button exposed blanket permission denial in the Electron session. I delivered the change after stopping a stalled verification instead of resolving it. Allow fullscreen for the trusted viewer main frame in both permission handlers and bound the test wait. The packaged setup-flow test passed with native fullscreen entry, monitor-sized bounds, exit, and playback. Always verify the retained native interaction before removing a working fallback. Wait for packaging and helper copies to finish before launching the package test.

## SHELL-QUOTES-001. 2026-11-20

Tags. PowerShell, quoting, smart apostrophes

A documentation replacement command failed to parse because PowerShell treats a typographic apostrophe inside a single-quoted string as a delimiter. Rephrasing the replacement without the apostrophe fixed the command. Verified by successful execution of the replacement. Use plain wording or correctly escaped delimiters for shell string literals.
