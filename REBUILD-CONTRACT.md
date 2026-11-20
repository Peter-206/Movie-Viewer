# Movie Shelf rebuild compatibility

The baseline is the working copy of `movie_shelf.py`, `run.bat`, `buildthumbs.bat`, and `movie_shelf.spec` on November 19, 2026. The working copy includes portable catalog repair, safe video selection, cleaned display titles, the Discover screen, and executable-first launchers. The checklist below describes observable behavior to exercise against the rebuilt app.

## Library and metadata

- [ ] Open `movies.db` in the selected movie root. Read the existing `movies`, `genres`, and `movie_genres` tables and retain the existing migration that adds `watch_count` to older databases
- [ ] Preserve movie IDs and user edits, including title, optional year, studio, presentation, genre links, and watch count. The supported presentation values are blank, Animation, Live action, and Hybrid
- [ ] Startup and Rescan discover visible direct child folders, including folders that lack playable media. The scanner skips dot-prefixed names, names beginning with two underscores, and linked folders. An ordinary directory for application assets or tests would appear as a movie
- [ ] Search each eligible folder recursively for MKV, MP4, AVI, MOV, M4V, WMV, and WebM, case insensitively. Prefer a root-level video named `movie`, then a nested video named `movie`, then the largest eligible video. Keep the selected video's directory and exact extension case when normalizing its name. Preserve other files and refuse destination collisions
- [ ] Reuse the working copy's folder-title parser for default metadata. Retain numeric titles such as `1917` and preserve the title and release year in `Blade Runner 2049 (2017)`
- [ ] After a drive or library move, synchronize paths for the same folder basename, reattach unambiguous edited metadata, preserve the highest existing watch count, and retain historical rows with conflicting edits. Display existing folders under the active root
- [ ] Open the selected title in the Windows default player and its folder in Explorer. Resolve the current file within the selected movie folder or its relocated counterpart under the active root. A second title with the same video filename must never be substituted
- [ ] On a successful player launch, repair a stale video path and increment that movie's count once. Missing media and launch failures must leave its count intact

## Desktop interactions

- [ ] Start on Discover. Show up to five picks, with unwatched movies first. Within each group, use the existing watched-genre ranking and alphabetical title tie-break. Expose the current recommendation, its details, manual navigation, and eight-second rotation on the visible Discover view
- [ ] Show up to eight popular movies ordered by recorded plays, with title tie-breaks and visible counts. Show the active collection's genre sections, independent row paging, and a genre jump control
- [ ] Support vertical scrolling over content and its descendants, including partial wheel deltas. Keep the recommendation area and scroll position stable as picks change
- [ ] A submitted Discover search opens Library with that query. Library matches case-insensitive substrings across title, year, studio, presentation, and genres. Combine the query with genre, studio, and presentation filters
- [ ] Keep six sort choices covering ascending and descending title, newest and oldest year with missing years last, and highest and lowest watch count. A changed filter or sort returns to page one. Show page and result counts and disable paging at each limit
- [ ] A library poster or caption opens the correct details. Right-click opens its metadata editor. Show local art, title, year, type, studio, genres, and watch count where available. Handle empty libraries, empty search results, missing artwork, unreadable artwork, and missing video
- [ ] Keep Play, Edit metadata, Open folder, and Back reachable. Back restores the originating view after opening or editing a title. Reflect successful saves and plays in the current details, collection rows, and filtering choices
- [ ] Edit a nonblank title, blank or four-digit year, studio, comma-separated genres, and the supported type. Save atomically, retain the modal on validation errors, and discard edits on Cancel or Escape. The editor also offers Open folder
- [ ] Preserve keyboard help on F1 and from a visible control, F11 or Alt+Enter for fullscreen, Escape to leave fullscreen or return, Ctrl+F or Ctrl+L for search, Ctrl+B for Library, Alt+Home for Discover, Alt+Left for Back, and F5 or Ctrl+R for Rescan
- [ ] Within Library, Left or Page Up and Right or Page Down change page, and Home or End jumps to the first or last page. Within Discover, Left and Right rotate picks, Up and Down scroll, Page Up and Page Down scroll a screen, and Home and End scroll to the ends. Space plays from Details. Preserve Tab, Shift+Tab, focused button activation, and native editing or popup behavior

## Entry points and packaging

| Entry point | Acceptance check |
| --- | --- |
| `movie_shelf.py` and `movie_shelf.exe` | Default root is beside the script or executable, including launch from a different working directory. An explicit `--root` selects the supplied library |
| Grid and thumbnail options | Preserve `--cols`, `--rows`, `--thumb-w`, and `--thumb-h`. CLI defaults are 6, 2, 260, and 380 respectively. Reject values below one. Honor layout constraints and fit the actual display |
| `--build-thumbs` | Run independently of GUI startup and video renaming. Generate missing `thumb.jpg` files from available covers within the requested dimensions. Preserve existing thumbnails and report the number created |
| `--fetch-covers` | Run independently of GUI startup. Preserve existing covers, download confidently matched IMDb posters, verify the image and minimum dimensions of 500 by 700 pixels, clean failed temporary downloads, and report downloaded, skipped, and failed counts. When both maintenance flags are supplied, fetch covers takes precedence |
| Artwork discovery | Keep `cover.jpg`, `cover.jpeg`, `cover.png`, then other eligible `cover*` artwork in precedence order. Reuse local thumbnails, fall back to local covers, and display usable placeholders |
| `run.bat` and `buildthumbs.bat` | Preserve quoted paths relative to the launcher, arbitrary forwarded arguments, executable-first dispatch, and the `python` then `py -3` fallbacks. The thumbnail launcher supplies `--build-thumbs`. Preserve failure status and the existing failure message and pause |
| `movie_shelf.spec` | Build a windowed, single-file `movie_shelf.exe` with the existing Python entry point. Confirm the standalone executable includes its UI dependencies and uses the adjacent library after relocation |

## Implementation and verification

Keep catalog access, file scanning, poster maintenance, Windows playback resolution, and CLI dispatch in the existing module. Put the rebuilt view methods in a flat `movie_shelf_ui.py` mixin and keep `MovieBrowser` importable from `movie_shelf.py`. Pass selected movie IDs through view actions. Use the catalog's refreshed records after writes. Track the Details origin when entering Details and cancel scheduled UI callbacks at shutdown.

Use a disposable library for startup, Rescan, metadata, and playback checks because a normal scan can rename files and write catalog rows. Include distinct folders with identically named main videos, one nested video, edited catalog metadata, absent artwork, corrupt artwork, and a movie with no video. Check the source and the newly built executable through their normal entry points, including a launcher path with spaces. Exercise controls in the actual desktop window at both compact and wide sizes.

Three pre-rebuild window captures use synthetic posters and a temporary SQLite database. They show Discover, Library, and Details at a client size of 1200 by 760 pixels. The captures record the baseline appearance. The checkboxes describe rebuild acceptance and do not represent completed tests.
