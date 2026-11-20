# Movie Shelf rebuild

## Objective

Rebuild the native Windows UI using Impeccable, preserving all existing features and deliverables. User confirmed the complete delivery target and delegated design selection

## Agent hierarchy

- Root owns product context, design direction, integration, package build and final acceptance
- Architecture lead uses gpt-6.2-astra at high reasoning for compatibility analysis and independent review
- UI implementation uses gpt-6.2-astra at high reasoning for the native view layer
- Verification uses gpt-6.2-sol at high reasoning for isolated regression and GUI acceptance checks

Each agent receives a bounded file ownership contract and the relevant source context. Findings return to root and are shared directly where dependencies cross roles

## Decisions

- Preserve the existing catalog and file handling implementation
- Replace views through a flat Python UI mixin to avoid circular imports and accidental movie folders
- Deliver movie_shelf.py, movie_shelf_ui.py, movie_shelf.exe and existing run.bat and buildthumbs.bat
- Use disposable catalogs and movie fixtures for all execution tests
- Keep existing working tree changes and comments
- Design selection is delegated by the user's explicit answer

## Current state

- Product contract recorded in PRODUCT.md
- Baseline screenshots captured with an isolated library by architecture
- Impeccable context loaded and direction seed resolved
- Compatibility contract completed in REBUILD-CONTRACT.md
- New native view layer integrated through MovieShelfPresentation and MovieShelfController
- Ten isolated regression checks pass, including native dialog editing and keyboard navigation
- Compact and wide Discover, Library and Details captured with local posters in .impeccable/review
- Metadata editor and empty states captured
- Real-window review corrected long-title truncation, poster resizing and stale filter selections
- PyInstaller built .build-ui/dist/movie_shelf.exe successfully
- The final UI module hash matched the packaged source
- Fresh finish reviewer scored both final requested fixes resolved, disposition ship
- Design documenter validated DESIGN.md and its schema v2 sidecar against the final UI source, with no dangling token references
- Standalone maintenance, relocated default startup, run.bat with quoted root and buildthumbs.bat with custom dimensions passed
- Validated executable installed as movie_shelf.exe and matched the staged build by SHA256
- Live movies.db size and modification timestamp remain at their pre-rebuild values. The locked file could not be hashed

## Remaining

- No implementation or delivery work remains. DESIGN.md and .impeccable/design.json are written, and the sidecar parses as JSON

## Final acceptance

- Source regression suite passed all 10 checks
- Final native review scored both requested fixes resolved with disposition ship
- Source and packaged thumbnail generation and existing-cover preservation passed
- Relocated executable startup used the executable-adjacent library from an unrelated working directory
- run.bat forwarded a quoted explicit root correctly
- buildthumbs.bat forwarded a quoted root and custom thumbnail dimensions correctly
- Installed movie_shelf.exe SHA256 is C4C56E9B5DC45D769957A2A25183111B9E783CE60A3A578985BFC96FB319838F
- The source UI SHA256 is 6AB239294EA130A6405609BA98B4270AF7579A60A7D7A11218262D5F2A0247D7
- Rollback source and executable remain in .build-title-cleanup as movie_shelf.before-ui-rebuild.py and movie_shelf.before-ui-rebuild.exe
- Package smoke verification is reproducible with python -B .tests/verify_movie_shelf_package.py .build-ui/dist/movie_shelf.exe
- Captures are reproducible with python -B .tests/capture_movie_shelf.py

## Lessons

Project setup and native widget corrections are recorded in REBUILD-LESSONS.md. The UI implementation agent also recorded the verified native label correction as TK-004 in the local lessons index

## Discover scrolling correction

The user reported severe tearing while scrolling Discover. Content position changes were rewriting the canvas scroll region on every wheel event. Dimension guards removed these redundant requests. An independent 120-event check measured zero writes versus 120 before, with resize bounds and final genre navigation intact. All 10 regression tests and the standalone executable smoke checks passed again. The updated executable is installed. Perceived tearing on the user's display remains unverified
