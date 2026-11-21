"use strict";

// Input: Node process and HTTP APIs. Output: Launch and CDP tools. Goal: Exercise the packaged first-run flow. Description: The script runs entirely on loopback.
const { spawn } = require("node:child_process");
// Input: Node file API. Output: Temporary test directory. Goal: Isolate app settings. Description: No real viewer settings are changed.
const { mkdtemp, mkdir, copyFile, rm, readFile, writeFile } = require("node:fs/promises");
// Input: Node OS API. Output: Temporary directory root. Goal: Store disposable identities. Description: Deleted after the test.
const { tmpdir } = require("node:os");
// Input: Node path API. Output: Joined paths. Goal: Locate package and fixture. Description: Command line supplies the package root.
const { join, dirname } = require("node:path");
// Input: Node timers. Output: Poll delays. Goal: Wait for UI readiness. Description: Every wait has a bounded retry count.
const { setTimeout: delay } = require("node:timers/promises");

// Input: Executable path, isolated profile, and debug port. Output: Running Electron process. Goal: Launch a role. Description: Child output is retained for diagnostics.
// executable. Input: Package path. Output: Process file. Goal: Choose host or viewer. Description: The executable name selects its role.
// profile. Input: Temporary folder. Output: APPDATA override. Goal: Avoid real settings. Description: Each role gets a separate profile.
// port. Input: Test port. Output: CDP endpoint. Goal: Drive the actual renderer. Description: Only loopback is used.
function launch(executable, profile, port) {
  // Input: Executable and Chromium flags. Output: Child process. Goal: Test the packaged app. Description: A temporary profile isolates settings. Test-only occlusion flags keep decoding and fullscreen active when the automation desktop covers the viewer.
  const child = spawn(executable, [`--remote-debugging-port=${port}`, "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows"], { env: { ...process.env, MOVIE_SHELF_PROFILE: profile }, windowsHide: false });
  child.on("error", (error) => { child.testError = error; });
  child.stderr.on("data", (chunk) => { child.testLog = (child.testLog || "") + chunk.toString(); });
  return child;
}

// Input: CDP port. Output: Page WebSocket URL. Goal: Attach to the app page. Description: The initial blank page may be replaced during startup.
// port. Input: Launch choice. Output: Debugger endpoint port. Goal: Find the renderer. Description: Polls up to ten seconds.
async function pageSocket(port) {
  // attempt. Input: Retry budget. Output: Poll number. Goal: Bound startup waiting. Description: One hundred short checks are allowed.
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      // Input: Local CDP endpoint. Output: Page descriptors. Goal: Find the committed app page. Description: The custom origin identifies it.
      const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      // Input: Page descriptors. Output: App page. Goal: Skip about:blank. Description: The host and viewer share the private origin.
      const page = pages.find((item) => item.type === "page" && item.url.startsWith("shelfplay://player/"));
      if (page) return new WebSocket(page.webSocketDebuggerUrl);
    } catch { /* CDP may still be starting. */ }
    await delay(100);
  }
  throw new Error(`No app renderer on port ${port}`);
}

// Input: Open CDP socket and expression. Output: JavaScript value. Goal: Assert visible UI behavior. Description: Each command waits for its matching reply.
// socket. Input: Connected WebSocket. Output: CDP transport. Goal: Evaluate in the app renderer. Description: The caller serializes requests.
// expression. Input: Test expression. Output: Returned value. Goal: Drive setup. Description: Promise results are awaited.
async function evaluate(socket, expression) {
  return new Promise((resolve, reject) => {
    // Input: CDP message. Output: One command response. Goal: Read the exact result. Description: Errors fail the test.
    // event. Input: WebSocket message. Output: Parsed response. Goal: Complete evaluation. Description: Event notifications are ignored.
    function receive(event) {
      // Input: JSON CDP frame. Output: Response object. Goal: Match command 1. Description: Tests send one command at a time.
      const message = JSON.parse(event.data);
      if (message.id !== 1) return;
      socket.removeEventListener("message", receive);
      if (message.error || message.result?.exceptionDetails) reject(new Error(JSON.stringify(message.error || message.result.exceptionDetails)));
      else resolve(message.result.result.value);
    }
    socket.addEventListener("message", receive);
    socket.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression, awaitPromise: true, returnByValue: true, userGesture: true } }));
  });
}

// Input: Connected DevTools socket and output path. Output: PNG screenshot. Goal: Inspect the packaged viewer's real page layout. Description: The caller enables screenshots with a test-only environment variable.
// socket. Input: Renderer DevTools connection. Output: Captured page pixels. Goal: Read Chromium's rendered view. Description: Commands run after setup actions finish.
// screenshotPath. Input: Local PNG destination. Output: Written image. Goal: Review a named page. Description: The path is supplied by the test caller.
async function captureScreenshot(socket, screenshotPath) {
  // Input: One CDP response. Output: Base64 image bytes. Goal: Write the requested screenshot. Description: Command ID 2 is reserved for page captures.
  const screenshotBytes = await new Promise((resolve, reject) => {
    // event. Input: CDP message. Output: Matching capture result. Goal: Ignore unrelated events. Description: The listener is removed after response ID 2.
    function receive(event) {
      // Input: WebSocket payload. Output: Parsed CDP result. Goal: Detect capture errors. Description: The image is returned as base64.
      const message = JSON.parse(event.data);
      if (message.id !== 2) return;
      socket.removeEventListener("message", receive);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(Buffer.from(message.result.data, "base64"));
    }
    socket.addEventListener("message", receive);
    socket.send(JSON.stringify({ id: 2, method: "Page.captureScreenshot", params: { format: "png" } }));
  });
  await writeFile(screenshotPath, screenshotBytes);
}

// Input: App renderer and required selector. Output: Ready page. Goal: Avoid racing the first navigation. Description: Preload and DOM must both exist before setup actions.
// socket. Input: Connected CDP socket. Output: Evaluation transport. Goal: Inspect readiness. Description: One page per test role.
// selector. Input: Host or viewer element. Output: Presence check. Goal: Identify the loaded role. Description: Polls for up to ten seconds.
async function waitReady(socket, selector) {
  // attempt. Input: Retry budget. Output: Poll count. Goal: Bound startup wait. Description: One hundred short checks are allowed.
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try { if (await evaluate(socket, `Boolean(window.shelfAPI && document.querySelector(${JSON.stringify(selector)}))`)) return; }
    catch { /* The first execution context can be replaced during navigation. */ }
    await delay(100);
  }
  throw new Error(`Renderer did not load ${selector}`);
}

// Input: Packaged folder and sample movie. Output: Verified setup flow. Goal: Prove host and viewer work without terminal setup. Description: Tests first run, pairing, catalog, and media readiness.
async function main() {
  // Input: CLI. Output: Packaged app folder. Goal: Test the release candidate. Description: Must contain both named executables.
  const packageFolder = process.argv[2];
  // Input: CLI. Output: MP4 fixture. Goal: Give the host one movie. Description: The file is copied to a temporary library.
  const sample = process.argv[3];
  // Input: Optional CLI artwork path. Output: Cover fixture or undefined. Goal: Exercise the existing folder poster convention. Description: The test can still run with only a movie sample.
  const posterSample = process.argv[4];
  // Input: Optional test environment path. Output: Screenshot directory or undefined. Goal: Permit visual review of packaged pages. Description: Normal verification runs create no images.
  const screenshotFolder = process.env.MOVIE_SHELF_SCREENSHOTS;
  if (!packageFolder || !sample) throw new Error("Usage: node setup-flow.cjs PACKAGE_FOLDER SAMPLE_MP4");
  if (screenshotFolder) await mkdir(screenshotFolder, { recursive: true });
  // Input: OS temp root. Output: Isolated test directory. Goal: Avoid touching real settings. Description: Removed in finally.
  const workspace = await mkdtemp(join(tmpdir(), "movie-shelf-setup-"));
  // Input: Launch lifecycle. Output: Host child or null. Goal: Clean up. Description: Initialized before the try block.
  let host = null;
  // Input: Launch lifecycle. Output: Viewer child or null. Goal: Clean up. Description: Initialized before the try block.
  let viewer = null;
  // Input: Local-only launch lifecycle. Output: Viewer child or null. Goal: Clean up the direct-file check. Description: Initialized before the try block.
  let localViewer = null;
  // Input: Duplicate-source check. Output: Viewer child or null. Goal: Verify one movie card can offer two PCs. Description: This profile is disposable.
  let combinedViewer = null;
  try {
    // Input: Temporary workspace. Output: Movie folder. Goal: Supply the host. Description: Holds one disposable copy.
    const library = join(workspace, "library");
    await mkdir(library);
    await copyFile(sample, join(library, "sample.mp4"));
    if (posterSample) await copyFile(posterSample, join(library, "cover.jpg"));
    host = launch(join(packageFolder, "MovieShelfHost.exe"), join(workspace, "host-profile"), 18921);
    // Input: Host renderer. Output: CDP socket. Goal: Run the actual setup action. Description: Does not bypass main-process validation.
    const hostSocket = await pageSocket(18921);
    await new Promise((resolve) => hostSocket.addEventListener("open", resolve, { once: true }));
    await waitReady(hostSocket, "#host-form");
    // Input: Selected folder and loopback address. Output: Pairing details. Goal: Start the packaged Rust host. Description: Password is test-only.
    const sharing = await evaluate(hostSocket, `window.shelfAPI.setup("start-host", {folder:${JSON.stringify(library)},address:"127.0.0.1",password:"correct horse battery staple"})`);
    if (!/^[0-9A-F]{12}$/.test(sharing.code)) throw new Error("Host did not show a valid pairing code");
    viewer = launch(join(packageFolder, "MovieShelfViewer.exe"), join(workspace, "viewer-profile"), 18922);
    // Input: Viewer renderer. Output: CDP socket. Goal: Exercise first-run setup. Description: The viewer must start without saved hosts.
    const viewerSocket = await pageSocket(18922);
    await new Promise((resolve) => viewerSocket.addEventListener("open", resolve, { once: true }));
    await waitReady(viewerSocket, "#first-run");
    // attempt. Input: Initial catalog load. Output: Poll number. Goal: Wait for first-run state. Description: The renderer fetches its empty source list asynchronously.
    let firstRunShown = false;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      firstRunShown = await evaluate(viewerSocket, `document.querySelector("#first-run").hidden === false && document.querySelector("#movies").hidden === true`);
      if (firstRunShown) break;
      await delay(100);
    }
    if (!firstRunShown) throw new Error("First-run gate was not shown: " + JSON.stringify(await evaluate(viewerSocket, `({firstRun:document.querySelector("#first-run").hidden, movies:document.querySelector("#movies").hidden, status:document.querySelector("#catalog-status").textContent, sources:document.querySelector("#sources-status").textContent})`)));
    // Input: Incorrect pairing code. Output: Rejected add. Goal: Prove host identity is checked before saving. Description: The test password is never sent to the unverified peer.
    const wrongCodeRejected = await evaluate(viewerSocket, `window.shelfAPI.setup("add-remote", {name:"Wrong",address:"127.0.0.1",code:"000000000000",password:"correct horse battery staple"}).then(() => false, () => true)`);
    if (!wrongCodeRejected) throw new Error("Wrong pairing code was accepted");
    await evaluate(viewerSocket, `window.shelfAPI.setup("add-remote", {name:"Test host",address:"127.0.0.1",code:${JSON.stringify(sharing.code)},password:"correct horse battery staple"})`);
    await evaluate(viewerSocket, `loadCatalogs()`);
    if (!(await evaluate(viewerSocket, `document.querySelectorAll("#movies button").length === 1 && !document.querySelector("video").hasAttribute("src")`))) throw new Error("Catalog did not load without movie bytes");
    // Input: Saved host and navigation buttons. Output: One visible destination. Goal: Prove the viewer no longer shows every section in one scroller. Description: Discover opens after the first source is added.
    if (!(await evaluate(viewerSocket, `document.querySelector('[data-page="discover"]').hidden === false && [...document.querySelectorAll('.page-view')].filter((page) => !page.hidden).length === 1`))) throw new Error("Discover did not open as a separate page");
    if (screenshotFolder) await captureScreenshot(viewerSocket, join(screenshotFolder, "discover.png"));
    await evaluate(viewerSocket, `document.querySelector('[data-page-link="library"]').click()`);
    if (!(await evaluate(viewerSocket, `document.querySelector('[data-page="library"]').hidden === false && document.querySelector('[data-page="discover"]').hidden === true`))) throw new Error("Library navigation did not switch pages");
    if (screenshotFolder) await captureScreenshot(viewerSocket, join(screenshotFolder, "library.png"));
    if (posterSample) {
      // Input: Remote poster card. Output: Decoded JPEG dimensions. Goal: Prove the host artwork route and CSP work. Description: Waits for image load through the private bridge.
      const remotePosterLoaded = await evaluate(viewerSocket, `new Promise((resolve) => { const image = document.querySelector(".movie-artwork img"); if (!image) return resolve(false); if (image.complete) return resolve(image.naturalWidth > 0); image.onload = () => resolve(image.naturalWidth > 0); image.onerror = () => resolve(false); setTimeout(() => resolve(false), 10000); })`);
      if (!remotePosterLoaded) throw new Error("Remote poster did not load: " + JSON.stringify(await evaluate(viewerSocket, `({complete:document.querySelector(".movie-artwork img").complete,width:document.querySelector(".movie-artwork img").naturalWidth,loading:document.querySelector(".movie-artwork img").loading,poster:document.querySelector(".movie-artwork img").src,status:document.querySelector("#catalog-status").textContent})`)));
    }
    await evaluate(viewerSocket, `document.querySelector("#movies button").click()`);
    if (!(await evaluate(viewerSocket, `document.querySelector('[data-page="player"]').hidden === false && document.querySelector('[data-page="library"]').hidden === true`))) throw new Error("Movie selection did not open the player page");
    if (screenshotFolder) await captureScreenshot(viewerSocket, join(screenshotFolder, "player.png"));
    // Input: Native video element. Output: Metadata readiness. Goal: Prove the selected movie can stream. Description: Waits up to ten seconds.
    const loaded = await evaluate(viewerSocket, `new Promise((resolve) => { const movie = document.querySelector("video"); if (movie.readyState >= 1) return resolve(true); movie.addEventListener("loadedmetadata", () => resolve(true), {once:true}); setTimeout(() => resolve(false), 10000); })`);
    if (!loaded) throw new Error("Selected movie metadata did not load");
    // Input: Play button and sample movie. Output: Advancing video time. Goal: Prove remote playback beyond metadata. Description: The browser decodes a short part of the fixture.
    const played = await evaluate(viewerSocket, `new Promise(async (resolve) => { const movie = document.querySelector("video"); try { await movie.play(); } catch { return resolve(false); } const beginning = movie.currentTime; let attempts = 0; const check = () => { if (movie.currentTime > beginning + 0.2) { movie.pause(); return resolve(true); } if (++attempts >= 50) { movie.pause(); return resolve(false); } setTimeout(check, 100); }; check(); })`);
    if (!played) throw new Error("Remote playback did not advance");
    // Input: Viewer CDP connection. Output: Foreground viewer. Goal: Exercise fullscreen on a visible page. Description: Windows can leave a test launch occluded despite document focus.
    await new Promise((resolve, reject) => {
      // Input: CDP reply. Output: Completed foreground request. Goal: Wait for activation. Description: ID 3 is reserved for Page.bringToFront.
      // event. Input: Socket message. Output: Parsed reply. Goal: Select command response. Description: Unrelated messages are ignored.
      function receiveForeground(event) {
        // Input: Socket payload. Output: CDP response object. Goal: Check activation. Description: Errors fail the test before fullscreen.
        const foregroundReply = JSON.parse(event.data);
        if (foregroundReply.id !== 3) return;
        viewerSocket.removeEventListener("message", receiveForeground);
        if (foregroundReply.error) reject(new Error(JSON.stringify(foregroundReply.error)));
        else resolve();
      }
      viewerSocket.addEventListener("message", receiveForeground);
      viewerSocket.send(JSON.stringify({ id: 3, method: "Page.bringToFront" }));
    });
    // Input: Fullscreen button. Output: Fullscreen viewer and restored layout. Goal: Verify the reported playback control. Description: Uses the same UI action as a person.
    const fullscreenWorked = await evaluate(viewerSocket, `Promise.race([document.querySelector("video").requestFullscreen().then(() => document.fullscreenElement === document.querySelector("video") && document.querySelector("video").controls && !document.querySelector("#play, #fullscreen")), new Promise((resolve) => setTimeout(() => resolve(false), 5000))])`);
    if (!fullscreenWorked) throw new Error("Fullscreen button did not enter fullscreen: " + JSON.stringify(await evaluate(viewerSocket, `({fullscreen:document.fullscreenElement?.tagName, controls:document.querySelector("video").controls, extraControls:Boolean(document.querySelector("#play, #fullscreen")), focused:document.hasFocus(), visibility:document.visibilityState, width:innerWidth, height:innerHeight})`)));
    // Input: Asynchronous Windows fullscreen transition. Output: Full monitor bounds. Goal: Avoid checking before the window manager finishes resizing. Description: Polls for up to five seconds.
    const filledScreen = await evaluate(viewerSocket, `new Promise((resolve) => { let attempts = 0; const check = () => { if (window.innerWidth >= screen.availWidth - 2 && window.innerHeight >= screen.availHeight - 2) return resolve(true); if (++attempts >= 50) return resolve(false); setTimeout(check, 100); }; check(); })`);
    if (!filledScreen) throw new Error("Viewer window did not fill the screen: " + JSON.stringify(await evaluate(viewerSocket, `({innerWidth,innerHeight,availableWidth:screen.availWidth,availableHeight:screen.availHeight})`)));
    await evaluate(viewerSocket, `document.exitFullscreen()`);
    // Input: Remote pairing. Output: Saved settings location. Goal: Seed a separate local-only viewer. Description: The app decides its own user-data subfolder.
    // Input: Saved profile. Output: One source configuration file. Goal: Confirm persistence. Description: The isolated profile contains no real credentials.
    const savedSettingsPath = join(workspace, "viewer-profile", "sources.json");
    // Input: Pairing result. Output: Persisted source list. Goal: Verify the cache. Description: A later launch will restore this data.
    const savedSources = JSON.parse(await readFile(savedSettingsPath, "utf8"));
    if (savedSources.length !== 1 || savedSources[0].type !== "remote") throw new Error("Remote source was not cached");
    // Input: One remote source and the same local movie. Output: Combined profile. Goal: Reproduce two copies of one title. Description: Both entries point to disposable test files.
    const combinedSettingsPath = join(workspace, "combined-profile", "sources.json");
    await mkdir(dirname(combinedSettingsPath), { recursive: true });
    await writeFile(combinedSettingsPath, JSON.stringify([...savedSources, { type: "local", name: "This PC", folder: library }]));
    combinedViewer = launch(join(packageFolder, "MovieShelfViewer.exe"), join(workspace, "combined-profile"), 18924);
    // Input: Combined viewer. Output: Renderer connection. Goal: Inspect source grouping. Description: Pairing data came from the real setup flow.
    const combinedSocket = await pageSocket(18924);
    await new Promise((resolve) => combinedSocket.addEventListener("open", resolve, { once: true }));
    await waitReady(combinedSocket, "#movies");
    await evaluate(combinedSocket, `loadCatalogs()`);
    if (!(await evaluate(combinedSocket, `document.querySelectorAll("#movies .movie-card").length === 1`))) throw new Error("Duplicate movie sources were shown as separate cards");
    await evaluate(combinedSocket, `document.querySelector('[data-page-link="library"]').click()`);
    await evaluate(combinedSocket, `document.querySelector("#movies .movie-card").click()`);
    if (!(await evaluate(combinedSocket, `document.querySelector("#playback-source").options.length === 2`))) throw new Error("Both playback sources were not selectable");
    await evaluate(combinedSocket, `document.querySelector('[data-page-link="sources"]').click()`);
    if (!(await evaluate(combinedSocket, `document.querySelector('[data-page="sources"]').hidden === false && document.querySelectorAll('#sources-list li').length === 2`))) throw new Error("Sources page did not show both saved sources");
    if (screenshotFolder) await captureScreenshot(combinedSocket, join(screenshotFolder, "sources.png"));
    await evaluate(combinedSocket, `document.querySelector('#sources-list button').click()`);
    // Input: One remote and one local source. Output: The local source remains after remote removal. Goal: Verify the correct row is removed. Description: The viewer must also update its saved settings.
    let retainedLocalSource = false;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      retainedLocalSource = await evaluate(combinedSocket, `document.querySelectorAll('#sources-list li').length === 1 && document.querySelector('#sources-list').textContent.includes('This PC')`);
      if (retainedLocalSource) break;
      await delay(100);
    }
    if (!retainedLocalSource) throw new Error("Removing a server did not keep the local source");
    // Input: Test profile settings. Output: One persisted local source. Goal: Confirm the server stays removed after restart. Description: The saved file is read only in the disposable test profile.
    const remainingSources = JSON.parse(await readFile(combinedSettingsPath, "utf8"));
    if (remainingSources.length !== 1 || remainingSources[0].type !== "local") throw new Error("Server removal was not saved");
    combinedSocket.close();
    await evaluate(viewerSocket, `document.querySelector('[data-page-link="sources"]').click()`);
    await evaluate(viewerSocket, `document.querySelector("#sources-list button").click()`);
    // Input: Remove action. Output: First-run state. Goal: Confirm a mistaken source can be removed. Description: Movie files are untouched.
    let removedSource = false;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      removedSource = await evaluate(viewerSocket, `document.querySelector("#first-run").hidden === false && document.querySelector("#sources-list").children.length === 0 && document.querySelector('[data-page="sources"]').hidden === false`);
      if (removedSource) break;
      await delay(100);
    }
    if (!removedSource) throw new Error("Removing the saved source did not return to setup");
    // Input: Separate profile. Output: Direct local configuration. Goal: Test the local route without a picker automation hack. Description: The picker itself is native Electron UI.
    const localSettingsPath = join(workspace, "local-profile", "sources.json");
    await mkdir(dirname(localSettingsPath), { recursive: true });
    await writeFile(localSettingsPath, JSON.stringify([{ type: "local", name: "This PC", folder: library }]));
    localViewer = launch(join(packageFolder, "MovieShelfViewer.exe"), join(workspace, "local-profile"), 18923);
    // Input: Local viewer renderer. Output: CDP socket. Goal: Verify direct catalog and playback. Description: No host source is configured in this profile.
    const localSocket = await pageSocket(18923);
    await new Promise((resolve) => localSocket.addEventListener("open", resolve, { once: true }));
    await waitReady(localSocket, "#first-run");
    await evaluate(localSocket, `loadCatalogs()`);
    if (!(await evaluate(localSocket, `document.querySelectorAll("#movies button").length === 1 && document.querySelector("#first-run").hidden`))) throw new Error("Local catalog did not load");
    await evaluate(localSocket, `document.querySelector('[data-page-link="library"]').click()`);
    if (posterSample) {
      // Input: Local poster card. Output: Decoded JPEG dimensions. Goal: Prove direct artwork access works. Description: No host is configured in this viewer.
      const localPosterLoaded = await evaluate(localSocket, `new Promise((resolve) => { const image = document.querySelector(".movie-artwork img"); if (!image) return resolve(false); if (image.complete) return resolve(image.naturalWidth > 0); image.onload = () => resolve(image.naturalWidth > 0); image.onerror = () => resolve(false); setTimeout(() => resolve(false), 10000); })`);
      if (!localPosterLoaded) throw new Error("Local poster did not load");
    }
    await evaluate(localSocket, `document.querySelector("#movies button").click()`);
    // Input: Direct file source. Output: Metadata readiness. Goal: Prove local playback. Description: The configured source has no network URL.
    const localLoaded = await evaluate(localSocket, `new Promise((resolve) => { const movie = document.querySelector("video"); if (movie.readyState >= 1) return resolve(true); movie.addEventListener("loadedmetadata", () => resolve(true), {once:true}); setTimeout(() => resolve(false), 10000); })`);
    if (!localLoaded) throw new Error("Direct local movie metadata did not load");
    // Input: Direct local movie. Output: Advancing time. Goal: Prove the no-TCP path actually plays. Description: Pauses after one second.
    const localPlayed = await evaluate(localSocket, `new Promise(async (resolve) => { const movie = document.querySelector("video"); try { await movie.play(); } catch { return resolve(false); } const beginning = movie.currentTime; setTimeout(() => { movie.pause(); resolve(movie.currentTime > beginning + 0.2); }, 1000); })`);
    if (!localPlayed) throw new Error("Direct local playback did not advance");
    // Input: Local movie route. Output: Partial file response. Goal: Verify direct seek support. Description: The app protocol reads the local file without a host.
    const partialBytes = await evaluate(localSocket, `fetch(document.querySelector("video").src, {headers:{Range:"bytes=0-15"}}).then(async (response) => ({status:response.status,length:(await response.arrayBuffer()).byteLength}))`);
    if (partialBytes.status !== 206 || partialBytes.length !== 16) throw new Error("Local byte-range response failed");
    // Input: Selected local movie. Output: Original media URL. Goal: Check stale IDs after refresh. Description: A later scan must not silently retarget it.
    const oldMediaUrl = await evaluate(localSocket, `document.querySelector("video").src`);
    await copyFile(sample, join(library, "extra.mp4"));
    await evaluate(localSocket, `loadCatalogs()`);
    // Input: Changed local catalog. Output: Old route status. Goal: Prevent a stale selection from opening a different movie. Description: Versioned IDs reject changed scans.
    const staleStatus = await evaluate(localSocket, `fetch(${JSON.stringify(oldMediaUrl)}).then((response) => response.status)`);
    if (staleStatus !== 404) throw new Error("Changed local catalog accepted a stale movie ID");
    console.log("PASS: separate pages, persisted server removal, setup, posters, fullscreen, grouped sources, remote and local playback, byte ranges, stale-ID rejection");
    hostSocket.close();
    viewerSocket.close();
    localSocket.close();
  } catch (error) {
    console.error("Host log", host?.testLog || "");
    console.error("Viewer log", viewer?.testLog || "");
    throw error;
  } finally {
    viewer?.kill();
    localViewer?.kill();
    combinedViewer?.kill();
    host?.kill();
    await delay(500);
    await rm(workspace, { recursive: true, force: true });
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
