"use strict";

// Input: Bundled markup. Output: Video element. Goal: Use Chromium playback and controls.
// Description: The element issues native byte-range requests through the private protocol.
const video = document.querySelector("video");
// Input: Bundled markup. Output: Status text element. Goal: Tell the user what the player is doing.
// Description: Assistive technology announces changes without moving focus.
const statusText = document.querySelector("#status");
// Input: Bundled markup. Output: Retry button. Goal: Reopen media at the saved position.
// Description: The button appears when playback fails.
const retryButton = document.querySelector("#retry");
// Input: Bundled markup. Output: File picker. Goal: Let the user choose an external subtitle file.
// Description: The renderer can read only the file explicitly chosen.
const subtitleInput = document.querySelector("#subtitles");
// Input: Bundled markup. Output: Subtitle status element. Goal: Keep subtitle diagnostics separate from playback.
// Description: Displays attachment and validation outcomes.
const subtitleStatus = document.querySelector("#subtitle-status");
// Input: Bundled controls. Output: Catalog elements. Goal: Browse several source libraries. Description: The main process keeps host credentials private.
const movieList = document.querySelector("#movies");
// Input: Bundled Discover view. Output: Featured movie list. Goal: Keep discovery separate from the full catalog. Description: It shows the first eight unique titles.
const discoverList = document.querySelector("#discover-movies");
// Input: Bundled page sections. Output: Page elements. Goal: Show one app destination at a time. Description: Sections stay mounted so prepared media survives navigation.
const pageViews = [...document.querySelectorAll(".page-view")];
// Input: Bundled navigation controls. Output: Page buttons. Goal: Expose Discover, Library, Sources, and player. Description: Current state is announced with aria-current.
const pageLinks = [...document.querySelectorAll("[data-page-link]")];
// Input: Bundled controls. Output: Search field. Goal: Filter the combined catalog. Description: Filtering does not fetch media.
const searchInput = document.querySelector("#search");
// Input: Bundled controls. Output: Refresh button. Goal: Retry offline catalogs. Description: Each source is requested independently.
const refreshButton = document.querySelector("#refresh");
// Input: Bundled controls. Output: Catalog status. Goal: Show reachable and unavailable sources. Description: No credentials are displayed.
const catalogStatus = document.querySelector("#catalog-status");
// Input: Bundled controls. Output: Selected title. Goal: Identify prepared media. Description: Text is inserted with textContent.
const selectedTitle = document.querySelector("#selected-title");
// Input: Selection panel. Output: Playback source picker. Goal: Keep duplicate copies under one movie. Description: Every available PC remains selectable.
const playbackSource = document.querySelector("#playback-source");
// Input: Setup markup. Output: First-run panel. Goal: Require a source before browsing. Description: Shown when no saved source exists.
const firstRun = document.querySelector("#first-run");
// Input: Setup markup. Output: Add-server dialog. Goal: Pair another PC. Description: The password is cleared after use.
const serverDialog = document.querySelector("#server-dialog");
// Input: Setup markup. Output: Server form. Goal: Gather connection details. Description: Main process validates the address and code.
const serverForm = document.querySelector("#server-form");
// Input: Setup markup. Output: Source count label. Goal: Confirm cached sources. Description: Counts local folders and remote PCs.
const sourcesStatus = document.querySelector("#sources-status");
// Input: Setup markup. Output: Source list. Goal: Show and remove saved sources. Description: Names and types only are exposed.
const sourcesList = document.querySelector("#sources-list");
// Input: Sources view. Output: Visible action result. Goal: Explain removal and connection failures. Description: The message never includes private connection settings.
const sourceActionStatus = document.querySelector("#source-action-status");
// Input: Catalog responses. Output: Combined movie rows. Goal: Search across hosts. Description: Each row remembers its source index.
let movies = [];
// Input: Selection. Output: Current movie or null. Goal: Route playback and health checks. Description: Selected media retains its server and asset IDs.
let selectedMovie = null;
// Input: Hover or focus. Output: Pending timer. Goal: Wait for a strong intention signal. Description: A changed target cancels the timer.
let anticipationTimer = null;
// Input: Selection. Output: Loaded movie key or null. Goal: Reuse prepared browser media. Description: Same source remains loaded when Play is pressed.
let preparedMovieKey = null;
// Input: Navigation actions. Output: Current page name. Goal: Return to the correct screen after setup changes. Description: Only one of the four known pages is active.
let currentPage = "discover";
// Input: Loaded source settings. Output: First-run gate state. Goal: Require a source before browsing. Description: Navigation opens Sources until a folder or server is saved.
let hasSavedSources = false;

// Input: A known page name. Output: One visible view and current navigation state. Goal: Keep the app from becoming one long scroller. Description: Navigation does not unload prepared playback.
// pageName. Input: Discover, Library, Sources, or player. Output: Visible destination. Goal: Route navigation. Description: Unknown values fall back to Discover.
function showPage(pageName) {
  currentPage = !hasSavedSources ? "sources" : (["discover", "library", "sources", "player"].includes(pageName) ? pageName : "discover");
  // pageView. Input: Mounted page sections. Output: One visible section. Goal: Hide other destinations. Description: Hidden sections remain available to the renderer.
  for (const pageView of pageViews) pageView.hidden = pageView.dataset.page !== currentPage;
  // pageLink. Input: Navigation buttons. Output: Current page marker. Goal: Keep navigation understandable. Description: The active button gets aria-current.
  for (const pageLink of pageLinks) {
    if (pageLink.dataset.pageLink === currentPage) pageLink.setAttribute("aria-current", "page");
    else pageLink.removeAttribute("aria-current");
  }
  document.querySelector(".viewer-content").scrollTop = 0;
}

// Input: Movie record. Output: Private protocol path. Goal: Request only registered media. Description: Source and asset identifiers are numeric.
// movie. Input: Catalog row. Output: Relative media path. Goal: Keep host URLs outside the renderer. Description: IDs come from validated catalog data.
function moviePath(movie) { return `/media/${movie.sourceIndex}/${movie.id}`; }
// Input: Catalog movie. Output: Private poster route. Goal: Fetch artwork separately from movie bytes. Description: Missing artwork yields an empty poster slot.
// movie. Input: Indexed catalog row. Output: Poster URL. Goal: Display its registered JPEG. Description: Only numeric source and asset IDs enter the URL.
function posterPath(movie) { return `/poster/${movie.sourceIndex}/${movie.id}`; }

// Input: Display title. Output: Stable comparison key. Goal: Merge copies with harmless punctuation differences. Description: Year and edition text remain significant.
// title. Input: Catalog title. Output: Lowercase normalized title. Goal: Group the same movie from several PCs. Description: Unicode letters and digits are retained.
function movieTitleKey(title) { return title.normalize("NFKD").toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim(); }

// Input: Selected movie and all catalog rows. Output: Source choices. Goal: Switch copies without duplicate cards. Description: Matching titles share a picker.
// movie. Input: Current selection. Output: Its matching copies. Goal: Show every playback source. Description: The source name identifies the PC.
function showPlaybackSources(movie) {
  playbackSource.replaceChildren();
  if (!movie) return;
  // Input: Selected title. Output: Normalized key. Goal: Find the same movie. Description: Title identity is provisional until richer metadata is added.
  const selectedKey = movieTitleKey(movie.title);
  // sourceMovie. Input: Combined catalog. Output: One matching copy. Goal: Make its source selectable. Description: Each option keeps its media ID.
  for (const sourceMovie of movies.filter((item) => movieTitleKey(item.title) === selectedKey)) {
    // Input: Matching movie. Output: Source option. Goal: Identify the serving PC. Description: The value is an index in the current catalog.
    const option = document.createElement("option");
    option.value = String(movies.indexOf(sourceMovie));
    option.textContent = sourceMovie.sourceName;
    option.selected = sourceMovie === movie;
    playbackSource.append(option);
  }
}

// Input: Selected or predicted movie. Output: Loaded video metadata. Goal: Anticipate playback. Description: Native metadata preload starts after sustained hover, focus, or selection and remains usable by Play.
// movie. Input: Catalog row. Output: Prepared video source. Goal: Avoid movie transfer during browsing. Description: One candidate is loaded at a time.
function prepareMovie(movie) {
  if (!movie) return;
  // Input: Movie source and ID. Output: Unique key. Goal: Avoid repeating preparation. Description: Source index scopes server-local IDs.
  const movieKey = `${movie.sourceIndex}/${movie.id}`;
  if (preparedMovieKey === movieKey) return;
  activeProbe?.abort();
  activeProbe = null;
  video.pause();
  video.removeAttribute("src");
  video.load();
  savedPosition = 0;
  resumePlaying = false;
  playbackFailed = false;
  retryButton.hidden = true;
  preparedMovieKey = movieKey;
  selectedMovie = movie;
  selectedTitle.textContent = movie.title;
  showPlaybackSources(movie);
  statusText.textContent = "Preparing…";
  video.preload = "metadata";
  video.src = moviePath(movie);
  video.load();
}

// Input: Candidate movie. Output: Delayed preparation. Goal: Anticipate only sustained attention. Description: New focus cancels the previous prediction.
// movie. Input: Catalog row. Output: Timer target. Goal: Prepare likely playback. Description: The timer fires after 400 milliseconds.
function anticipateMovie(movie) {
  if (!video.paused) return;
  clearTimeout(anticipationTimer);
  anticipationTimer = setTimeout(() => prepareMovie(movie), 400);
}

// Input: Combined catalog and search text. Output: Visible movie buttons. Goal: Browse all hosts. Description: Rows contain metadata only.
function renderMovies() {
  movieList.replaceChildren();
  discoverList.replaceChildren();
  // Input: Current search field. Output: Lowercase query. Goal: Match titles and host names. Description: Whitespace is trimmed.
  const query = searchInput.value.trim().toLocaleLowerCase();
  // Input: Combined catalog. Output: One representative per normalized title. Goal: Avoid duplicate movie cards. Description: The selected source stays the representative when possible.
  const uniqueMovies = new Map();
  // movie. Input: Combined catalog. Output: One visible movie. Goal: Render matches. Description: Source names remain searchable.
  for (const movie of movies) {
    // Input: Movie title. Output: Group key. Goal: Group copies. Description: Punctuation does not split one movie into separate cards.
    const groupKey = movieTitleKey(movie.title);
    if (!uniqueMovies.has(groupKey) || movie === selectedMovie) uniqueMovies.set(groupKey, movie);
  }
  // Input: One unique catalog. Output: Search matches. Goal: Search across all copy locations. Description: A title appears when any serving PC matches.
  const filteredMovies = [...uniqueMovies.values()].filter((movie) => !query || movies.some((copy) => movieTitleKey(copy.title) === movieTitleKey(movie.title) && `${copy.title} ${copy.sourceName}`.toLocaleLowerCase().includes(query)));
  document.querySelector("#library-status").hidden = filteredMovies.length > 0;
  renderMovieCards(discoverList, [...uniqueMovies.values()].slice(0, 8));
  renderMovieCards(movieList, filteredMovies);
}

// Input: Target list and deduplicated movies. Output: Poster buttons. Goal: Share one card behavior across Discover and Library. Description: Choosing a card opens the separate player page.
// targetList. Input: Discover or Library list. Output: Appended cards. Goal: Render the intended shelf. Description: Poster loading follows visible row order.
// visibleMovies. Input: Unique movie records. Output: One card per title. Goal: Prevent duplicate copies. Description: Playback source choices remain in the player.
function renderMovieCards(targetList, visibleMovies) {
  // movie. Input: Deduplicated catalog. Output: Poster card. Goal: Browse a visual library. Description: Each card retains every source through the selection picker.
  for (const movie of visibleMovies) {
    // Input: Movie metadata. Output: Focusable button. Goal: Support pointer and keyboard selection. Description: Text is never interpreted as HTML.
    const button = document.createElement("button");
    button.type = "button";
    button.className = "movie-card";
    button.setAttribute("aria-current", selectedMovie && movieTitleKey(selectedMovie.title) === movieTitleKey(movie.title) ? "true" : "false");
    // Input: Catalog artwork flag. Output: Cover or blank poster frame. Goal: Respect absent artwork. Description: The image is loaded only for rows with a registered poster.
    const artwork = document.createElement("span");
    artwork.className = "movie-artwork";
    if (movie.poster) {
      // Input: Registered poster route. Output: Lazy image. Goal: Show movie covers without blocking the catalog. Description: Browser decodes only visible JPEGs.
      const posterImage = document.createElement("img");
      posterImage.src = posterPath(movie);
      posterImage.alt = "";
      posterImage.loading = targetList.childElementCount < 12 ? "eager" : "lazy";
      posterImage.addEventListener("error", () => posterImage.remove());
      artwork.append(posterImage);
    }
    // Input: Movie title. Output: Card caption. Goal: Match the folder's display name. Description: Text is never parsed as HTML.
    const titleLabel = document.createElement("strong");
    titleLabel.textContent = movie.title;
    button.append(artwork, titleLabel);
    // Input: Source name. Output: Secondary label. Goal: Identify the serving PC. Description: Duplicate titles remain distinct.
    const sourceLabel = document.createElement("small");
    // Input: Normalized movie title. Output: Number of available copies. Goal: Explain multiple sources. Description: Source choice appears after selection.
    const copyCount = movies.filter((item) => movieTitleKey(item.title) === movieTitleKey(movie.title)).length;
    sourceLabel.textContent = copyCount > 1 ? `${copyCount} sources` : movie.sourceName;
    button.append(sourceLabel);
    button.addEventListener("mouseenter", () => anticipateMovie(movie));
    button.addEventListener("focus", () => anticipateMovie(movie));
    button.addEventListener("mouseleave", () => clearTimeout(anticipationTimer));
    button.addEventListener("blur", () => clearTimeout(anticipationTimer));
    button.addEventListener("click", () => { clearTimeout(anticipationTimer); prepareMovie(movie); showPage("player"); renderMovies(); });
    // Input: Button. Output: List row. Goal: Group catalog results. Description: Native list markup supports assistive technology.
    const row = document.createElement("li");
    row.append(button);
    targetList.append(row);
  }
}

// Input: Trusted source names and authenticated catalogs. Output: Combined rows. Goal: Browse all reachable PCs. Description: A failed host does not hide other catalogs.
async function loadCatalogs() {
  catalogStatus.textContent = "Loading libraries…";
  try {
    // Input: Private local route. Output: Configured source names. Goal: Label merged entries. Description: Tokens and URLs stay in the main process.
    const sources = await (await fetch("/sources", { cache: "no-store" })).json();
    // Input: Saved source metadata. Output: Source controls. Goal: Let the user remove a stale host or folder. Description: The UI never sees credentials.
    const savedSources = await window.shelfAPI.setup("list");
    sourcesList.replaceChildren();
    // index. Input: Saved source order. Output: Numeric source index. Goal: Remove the intended source. Description: Matches the current catalog route.
    // source. Input: Source list. Output: Visible label. Goal: Identify one saved source. Description: Names are safe text.
    for (const [index, source] of savedSources.entries()) {
      // Input: Source name and type. Output: List item. Goal: Make setup reviewable. Description: Text is inserted safely.
      const row = document.createElement("li");
      row.textContent = `${source.name} (${source.type === "local" ? "local folder" : "server"})`;
      // Input: Source index. Output: Remove button. Goal: Correct setup mistakes. Description: Removal also clears the selected movie.
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.textContent = "Remove";
      removeButton.setAttribute("aria-label", `Remove ${source.name}`);
      removeButton.addEventListener("click", async () => {
        removeButton.disabled = true;
        sourceActionStatus.textContent = `Removing ${source.name}…`;
        try {
          await window.shelfAPI.setup("remove", index);
          video.pause(); video.removeAttribute("src"); video.load();
          selectedMovie = null; preparedMovieKey = null; showPlaybackSources(null);
          selectedTitle.textContent = "Select a movie";
          await loadCatalogs();
          sourceActionStatus.textContent = `${source.name} removed. Movie files were not deleted.`;
        } catch (error) {
          removeButton.disabled = false;
          sourceActionStatus.textContent = `Could not remove ${source.name}. ${error.message}`;
        }
      });
      row.append(removeButton); sourcesList.append(row);
    }
    // Input: Earlier source state. Output: First-run transition flag. Goal: Open Discover after the first source is saved. Description: Later source edits stay on Sources.
    const wasFirstRun = !hasSavedSources;
    hasSavedSources = sources.length > 0;
    firstRun.hidden = hasSavedSources;
    sourcesStatus.textContent = `${sources.length} source${sources.length === 1 ? "" : "s"} saved`;
    document.querySelector(".library-controls").hidden = sources.length === 0;
    movieList.hidden = sources.length === 0;
    document.querySelector(".selection").hidden = sources.length === 0;
    video.hidden = sources.length === 0;
    document.querySelector(".details").hidden = sources.length === 0;
    if (!hasSavedSources) { movies = []; renderMovies(); showPage("sources"); catalogStatus.textContent = "Add a server or a local folder to begin."; return; }
    // Input: Configured sources. Output: Per-source catalog results. Goal: Keep reachable hosts usable. Description: Requests happen concurrently.
    const results = await Promise.allSettled(sources.map(async (sourceName, sourceIndex) => {
      // Input: Source index. Output: Authenticated catalog response. Goal: Fetch metadata only. Description: No media path is requested.
      const response = await fetch(`/catalog/${sourceIndex}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Catalog unavailable");
      // Input: JSON body. Output: Validated rows. Goal: Reject malformed host data. Description: IDs contain a decimal catalog version and index.
      const catalog = await response.json();
      if (!Array.isArray(catalog.movies)) throw new Error("Invalid catalog");
      return catalog.movies.filter((movie) => typeof movie.title === "string" && /^\d+-\d+$/.test(movie.id))
        .map((movie) => ({ title: movie.title, id: movie.id, poster: movie.poster === true, sourceIndex, sourceName }));
    }));
    movies = results.flatMap((result) => result.status === "fulfilled" ? result.value : []);
    // Input: Per-source results. Output: Offline count. Goal: Show partial reachability. Description: A rejected catalog counts as unavailable.
    const unavailableCount = results.filter((result) => result.status === "rejected").length;
    catalogStatus.textContent = `${new Set(movies.map((movie) => movieTitleKey(movie.title))).size} movies from ${sources.length - unavailableCount} sources${unavailableCount ? `, ${unavailableCount} unavailable` : ""}`;
    renderMovies();
    if (wasFirstRun) showPage("discover");
  } catch {
    catalogStatus.textContent = "Could not load source settings. Check the player configuration.";
    sourceActionStatus.textContent = "Could not load sources. Select Refresh on Discover to try again.";
  }
}

// Input: Add-server button. Output: Pairing form. Goal: Add another PC at any time. Description: Native dialog keeps focus in setup.
function showServerDialog() { document.querySelector("#server-error").textContent = ""; serverDialog.showModal(); }

// Input: Server form submit. Output: Saved source and fresh catalog. Goal: Connect to a host. Description: The host code is verified before sending the password token.
// event. Input: Submit event. Output: Prevented navigation. Goal: Keep the viewer open. Description: The request is asynchronous.
async function saveServer(event) {
  event.preventDefault();
  // Input: Form fields. Output: Pairing settings. Goal: Add one host. Description: The main process retains the certificate and token.
  const settings = { name: document.querySelector("#server-name").value, address: document.querySelector("#server-address").value,
    code: document.querySelector("#server-code").value, password: document.querySelector("#server-password").value };
  document.querySelector("#save-server").disabled = true;
  try {
    await window.shelfAPI.setup("add-remote", settings);
    serverForm.reset();
    serverDialog.close();
    await loadCatalogs();
    sourceActionStatus.textContent = "Server added.";
  } catch (error) { document.querySelector("#server-error").textContent = error.message; }
  finally { document.querySelector("#save-server").disabled = false; document.querySelector("#server-password").value = ""; }
}

// Input: Local button click. Output: Saved folder and catalog. Goal: Use this PC without a network host. Description: Native folder picker chooses the path.
async function addLocal() {
  try {
    if (await window.shelfAPI.setup("add-local")) {
      await loadCatalogs();
      sourceActionStatus.textContent = "Local folder added.";
    }
  } catch (error) { sourceActionStatus.textContent = error.message; }
}

// Input: Player events. Output: Last valid position in seconds. Goal: Preserve progress through a disconnect.
// Description: Captured separately because a replacement media load resets currentTime.
let savedPosition = 0;
// Input: The last playback state. Output: Boolean play intent. Goal: Restore paused or playing state after retry.
// Description: Capture this before unloading the failed source.
let resumePlaying = false;
// Input: Source load and recovery events. Output: Boolean failure state. Goal: Avoid overwriting a saved position.
// Description: Position events are ignored while the failed source is unloaded.
let playbackFailed = false;
// Input: Retry request. Output: Boolean restoration state. Goal: Guard against position events during a reload.
// Description: Remains set until media metadata permits restoring the seek position.
let restoringPosition = false;
// Input: Health check lifecycle. Output: Probe controller or null. Goal: Avoid overlapping probes.
// Description: Retry and fail states cancel the previous probe.
let activeProbe = null;
// Input: Subtitle file selection. Output: Current blob URL or null. Goal: Release the previous subtitle resource.
// Description: The browser loads a WebVTT blob through a native track element.
let subtitleUrl = null;

// Input: Native video position. Output: Updated saved position. Goal: Preserve valid progress for retry.
// Description: Capture both playback updates and explicit seeks while the current source is valid.
function savePosition() {
  if (!playbackFailed && !restoringPosition && Number.isFinite(video.currentTime)) {
    savedPosition = video.currentTime;
  }
}

// Input: Active source status. Output: Paused and unloaded source. Goal: Recover without losing position.
// Description: Unloading cancels outstanding media streams while the user waits to retry.
// failureMessage. Input: Safe status text. Output: Visible failure message. Goal: Explain the recovery action.
// Description: Contains no URL or credential information.
function failPlayback(failureMessage) {
  if (playbackFailed) return;
  savePosition();
  playbackFailed = true;
  restoringPosition = false;
  activeProbe?.abort();
  activeProbe = null;
  statusText.textContent = failureMessage;
  retryButton.hidden = false;
  video.removeAttribute("src");
  video.load();
}

// Input: Native media events. Output: Failure state. Goal: Handle decode and source errors.
// Description: Error codes 3 and 4 include unsupported or undecodable media.
function handleMediaError() {
  if (video.error?.code >= 3) {
    failPlayback("The movie could not be opened. Check the source and media format, then retry.");
  } else {
    failPlayback("The source became unavailable. Retry when it returns.");
  }
}

// Input: Native playing event. Output: Saved play intent and visible status. Goal: Indicate playback.
// Description: Retry restores the last play intent.
function markPlaying() {
  resumePlaying = true;
  statusText.textContent = "Playing";
}

// Input: Native pause event. Output: Saved pause intent and visible status. Goal: Preserve intentional pauses.
// Description: Ignore pauses caused by errors, source unload, or restoration.
function markPaused() {
  if (playbackFailed || restoringPosition || video.error) return;
  savePosition();
  resumePlaying = false;
  statusText.textContent = "Paused";
}

// Input: Media metadata event. Output: Restored position and play state. Goal: Resume the selected movie.
// Description: Restores after Chromium knows the new duration.
function handleMetadata() {
  if (restoringPosition) {
    video.currentTime = Math.min(savedPosition, video.duration);
    restoringPosition = false;
    if (resumePlaying) video.play().catch(markPaused);
  }
  statusText.textContent = "Ready";
}

// Input: Retry button click. Output: Fresh source load. Goal: Recheck TLS, authentication, and availability.
// Description: A new load reads the selected movie through the authenticated bridge.
function retryPlayback() {
  if (!selectedMovie) return;
  playbackFailed = false;
  restoringPosition = true;
  retryButton.hidden = true;
  statusText.textContent = "Reconnecting…";
  video.src = moviePath(selectedMovie);
}

// Input: Periodic timer. Output: Source liveness check. Goal: Detect disconnects during buffered playback.
// Description: A HEAD request checks the source with no media payload and shares the trusted route.
async function checkSource() {
  if (!selectedMovie || playbackFailed || activeProbe || !preparedMovieKey) return;

  // Input: Probe attempt. Output: Abort controller. Goal: Cancel this request when the source is reset.
  // Description: Its identity also guards against responses from earlier attempts.
  const probe = new AbortController();
  activeProbe = probe;
  try {
    // Input: Trusted media route. Output: HEAD response. Goal: Detect unavailable or unauthorized peers.
    // Description: The main process forwards with the same TLS and authorization checks as GET.
    const response = await fetch(moviePath(selectedMovie), {
      method: "HEAD",
      cache: "no-store",
      signal: probe.signal,
    });
    if (!response.ok && activeProbe === probe) {
      failPlayback("The source is unavailable. Retry when it returns.");
    }
  } catch {
    if (activeProbe === probe) failPlayback("The source is unavailable. Retry when it returns.");
  } finally {
    if (activeProbe === probe) activeProbe = null;
  }
}

// Input: Selected subtitle file. Output: Native WebVTT track. Goal: Support external SRT and WebVTT.
// Description: SRT timestamps use commas for milliseconds, so convert each timing line to WebVTT syntax.
async function attachSubtitles() {
  // Input: File picker selection. Output: Optional File object. Goal: Access user-selected subtitles.
  // Description: The file is read locally in the sandboxed renderer.
  const selectedFile = subtitleInput.files[0];
  if (!selectedFile) return;
  if (selectedFile.size > 1024 * 1024) {
    subtitleStatus.textContent = "Choose a subtitle file smaller than 1 MiB.";
    return;
  }

  try {
    // Input: Selected file bytes. Output: Normalized subtitle text. Goal: Read UTF-8 in either line ending convention.
    // Description: Remove an optional BOM and normalize line endings.
    const subtitleText = (await selectedFile.text()).replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");
    if (subtitleInput.files[0] !== selectedFile) return;

    // Input: File extension and text. Output: WebVTT document. Goal: Match Chromium's supported track format.
    // Description: Pass existing WebVTT or convert SRT timing lines conservatively.
    const webVttText = /\.srt$/i.test(selectedFile.name)
      ? "WEBVTT\n\n" + subtitleText.replace(/^(\d{2,}:\d{2}:\d{2}),(\d{3})\s+-->\s+(\d{2,}:\d{2}:\d{2}),(\d{3}).*$/gm, "$1.$2 --> $3.$4")
      : subtitleText;
    if (!/^WEBVTT(?:\s|$)/.test(webVttText) || !/\d\.\d{3}\s+-->\s+\d/.test(webVttText)) {
      subtitleStatus.textContent = "Choose a WebVTT or UTF-8 SRT file with valid cue times.";
      return;
    }

    video.querySelector("track")?.remove();
    if (subtitleUrl) URL.revokeObjectURL(subtitleUrl);
    subtitleUrl = URL.createObjectURL(new Blob([webVttText], { type: "text/vtt" }));

    // Input: Validated subtitle blob. Output: Track element. Goal: Render cues in Chromium.
    // Description: The track is visible immediately and available in native controls.
    const track = document.createElement("track");
    track.kind = "subtitles";
    track.label = selectedFile.name;
    track.src = subtitleUrl;
    video.append(track);
    track.track.mode = "showing";
    subtitleStatus.textContent = `Showing ${selectedFile.name}.`;
  } catch {
    subtitleStatus.textContent = "Could not read the selected subtitle file.";
  }
}

video.addEventListener("timeupdate", savePosition);
video.addEventListener("seeking", savePosition);
video.addEventListener("playing", markPlaying);
video.addEventListener("pause", markPaused);
video.addEventListener("error", handleMediaError);
video.addEventListener("loadedmetadata", handleMetadata);
retryButton.addEventListener("click", retryPlayback);
subtitleInput.addEventListener("change", attachSubtitles);
searchInput.addEventListener("input", renderMovies);
refreshButton.addEventListener("click", loadCatalogs);
// pageLink. Input: Navigation buttons. Output: Click route. Goal: Keep each destination on its own page. Description: The first-run gate is enforced by showPage.
for (const pageLink of pageLinks) pageLink.addEventListener("click", () => showPage(pageLink.dataset.pageLink));
document.querySelector("#back-to-library").addEventListener("click", () => showPage("library"));
document.querySelector("#add-server").addEventListener("click", showServerDialog);
document.querySelector("#cancel-server").addEventListener("click", () => serverDialog.close());
document.querySelector("#add-local").addEventListener("click", addLocal);
playbackSource.addEventListener("change", () => { prepareMovie(movies[Number(playbackSource.value)]); renderMovies(); });
serverForm.addEventListener("submit", saveServer);
loadCatalogs();
setInterval(checkSource, 2000);
