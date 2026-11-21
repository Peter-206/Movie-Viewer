"use strict";

// Input: Electron runtime. Output: Lifecycle, window, protocol, and session APIs.
// Goal: Provide a private desktop player. Description: These APIs run in the main process.
const { app, BrowserWindow, dialog, ipcMain, protocol, session } = require("electron");
// Input: Node runtime. Output: Asynchronous file reader. Goal: Load trusted files.
// Description: The reader loads app assets, the trusted certificate, and the token.
const { readFile, writeFile, mkdir, readdir, stat, open } = require("node:fs/promises");
// Input: Node runtime. Output: Process launcher. Goal: Start the host and certificate helper. Description: Child output stays in the host window.
const { spawn } = require("node:child_process");
// Input: Node runtime. Output: Host addresses. Goal: Show a reachable address. Description: Private IPv4 interfaces are preferred.
const { networkInterfaces } = require("node:os");
// Input: Node runtime. Output: Credential digest. Goal: Convert a user password to a fixed bearer value. Description: SHA-256 uses the exact UTF-8 password bytes.
const { createHash } = require("node:crypto");
// Input: Node runtime. Output: HTTPS API. Goal: Authenticate requests privately.
// Description: The HTTPS client validates the configured source certificate and hostname.
const https = require("node:https");
// Input: Node runtime. Output: Readable API. Goal: Stream response bodies.
// Description: The adapter exposes the Node response to Electron with backpressure.
const { Readable } = require("node:stream");
// Input: Node runtime. Output: Path join function. Goal: Locate bundled assets.
// Description: Each local path is chosen from the fixed asset table below.
const { join, extname, basename, dirname, isAbsolute } = require("node:path");
// Input: Node runtime. Output: Readable file stream. Goal: Stream local movies directly. Description: No TCP connection is used.
const { createReadStream, mkdirSync } = require("node:fs");

if (process.env.MOVIE_SHELF_PROFILE) {
  mkdirSync(process.env.MOVIE_SHELF_PROFILE, { recursive: true });
  app.setPath("userData", process.env.MOVIE_SHELF_PROFILE);
}

// Input: None. Output: App origin. Goal: Limit requests to a single private origin.
// Description: The custom protocol is registered only in the player's session.
const playerOrigin = "shelfplay://player";
// Input: Bundled static assets. Output: Route-to-file map. Goal: Serve the trusted UI.
// Description: Explicit paths prevent callers from selecting arbitrary files.
const appAssets = new Map([
  [`${playerOrigin}/`, ["index.html", "text/html; charset=utf-8"]],
  [`${playerOrigin}/renderer.js`, ["renderer.js", "text/javascript; charset=utf-8"]],
  [`${playerOrigin}/style.css`, ["style.css", "text/css; charset=utf-8"]],
  [`${playerOrigin}/host.html`, ["host.html", "text/html; charset=utf-8"]],
  [`${playerOrigin}/host.js`, ["host.js", "text/javascript; charset=utf-8"]],
]);

protocol.registerSchemesAsPrivileged([{
  scheme: "shelfplay",
  privileges: { standard: true, secure: true, stream: true, supportFetchAPI: true },
}]);

// Input: App data directory. Output: Source settings path. Goal: Persist setup between launches. Description: Electron selects the current Windows user's directory.
const settingsPath = () => join(app.getPath("userData"), "sources.json");
// Input: App runtime. Output: Active source records. Goal: Route catalogs without restarting. Description: Credentials remain in this process.
let sources = [];
// Input: App runtime. Output: Indexed local files. Goal: Resolve local media IDs. Description: Rebuilt when local folders are added.
let localCatalogs = new Map();
// Input: App runtime. Output: Host child process or null. Goal: Stop sharing on exit. Description: Only the host window starts this process.
let hostProcess = null;

// Input: Saved settings file. Output: Valid source records. Goal: Restore previous hosts and local folders. Description: Invalid entries are ignored individually.
async function readSources() {
  // Input: Windows app data. Output: Parsed source array. Goal: Resume setup. Description: A missing file means first run.
  let definitions = [];
  try { definitions = JSON.parse((await readFile(settingsPath(), "utf8")).replace(/^\uFEFF/, "")); } catch { return []; }
  if (!Array.isArray(definitions)) return [];
  // Input: Saved definitions. Output: Limited validated sources. Goal: Bound work and avoid arbitrary routes. Description: At most 32 sources can be configured.
  const restored = [];
  // definition. Input: Saved array. Output: One source record. Goal: Validate independent entries. Description: One damaged source does not erase the others.
  for (const definition of definitions.slice(0, 32)) {
    try {
      if (definition.type === "local") {
        // Input: Saved path. Output: Local source. Goal: Preserve folders while a drive is offline. Description: The catalog route reports unavailability until the path returns.
        if (typeof definition.folder === "string" && isAbsolute(definition.folder)) restored.push({ type: "local", name: String(definition.name).slice(0, 80), folder: definition.folder });
      } else if (definition.type === "remote") {
        // Input: Saved address. Output: Validated HTTPS origin. Goal: Prevent arbitrary upstream paths. Description: A source is one LAN host.
        const sourceUrl = new URL(definition.url);
        if (sourceUrl.protocol !== "https:" || sourceUrl.pathname !== "/" || sourceUrl.search || sourceUrl.hash || sourceUrl.username || sourceUrl.password) continue;
        if (!/^[0-9a-f]{64}$/.test(definition.token)) continue;
        restored.push({ type: "remote", name: String(definition.name).slice(0, 80), sourceUrl, certificate: Buffer.from(definition.certificate, "base64"), token: definition.token });
      }
    } catch { /* A removed drive or invalid entry is skipped. */ }
  }
  return restored;
}

// Input: Current source records. Output: Private JSON settings file. Goal: Keep added servers across launches. Description: The file stays in the user's app data directory.
async function saveSources() {
  // source. Input: Runtime source list. Output: Serializable source. Goal: Store only validated fields. Description: URLs, pins, and tokens remain in app data.
  const saved = sources.map((source) => source.type === "local"
    ? { type: "local", name: source.name, folder: source.folder }
    : { type: "remote", name: source.name, url: source.sourceUrl.origin, certificate: source.certificate.toString("base64"), token: source.token });
  await mkdir(app.getPath("userData"), { recursive: true });
  await writeFile(settingsPath(), JSON.stringify(saved, null, 2), { mode: 0o600 });
}

// Input: Bridge request and trusted source. Output: Media Response promise.
// Goal: Forward native playback and seek requests. Description: GET and HEAD are the only allowed methods.
// bridgeRequest. Input: Electron Request. Output: Method, range headers, and cancellation signal.
// Goal: Honor the browser's media requests. Description: Only approved headers cross the bridge.
// source. Input: readSource result. Output: HTTPS URL, certificate, and bearer token.
// Goal: Authenticate one peer. Description: Configuration is kept in the main process.
function forwardMedia(bridgeRequest, source, upstreamPath) {
  // Input: Response resolver. Output: HTTPS request side effects. Goal: Adapt Node HTTPS to Electron.
  // Description: HTTP responses resolve at headers and stream on demand.
  // resolve. Input: Response. Output: Settled promise. Goal: Deliver one Electron response.
  // Description: Later resolution attempts after a stream error are ignored.
  function openSource(resolve) {
    // Input: The incoming range and launcher token. Output: Upstream request headers.
    // Goal: Preserve HTTP seeking and authorization. Description: All other caller headers are ignored.
    const requestHeaders = {
      authorization: `Bearer ${source.token}`,
      "accept-encoding": "identity",
    };
    for (/* Input: Allowed list. Output: Header key. Goal: Preserve range requests. Description: Only named headers pass. */
      const headerName of ["range", "if-range"]) {
      // Input: Browser headers. Output: Optional value. Goal: Forward available values.
      // Description: Missing headers remain absent.
      const headerValue = bridgeRequest.headers.get(headerName);
      if (headerValue !== null) requestHeaders[headerName] = headerValue;
    }

    // Input: Node response. Output: Electron response. Goal: Keep partial delivery and status semantics.
    // Description: Only media and validity headers cross back into the renderer.
    // sourceResponse. Input: HTTPS IncomingMessage. Output: Status, headers, and body.
    // Goal: Stream data on demand. Description: The body is reused as a bounded Web stream.
    function relayResponse(sourceResponse) {
      // Input: Upstream headers. Output: Renderer-safe header collection. Goal: Keep media metadata.
      // Description: Prevent cached probe results and media from carrying into a reconnect attempt.
      const responseHeaders = new Headers({ "Cache-Control": "no-store" });
      for (/* Input: Allowed list. Output: Header key. Goal: Preserve byte range semantics. Description: Only media headers pass. */
        const headerName of ["accept-ranges", "content-length", "content-range", "content-type", "etag", "last-modified"]) {
        // Input: Upstream headers. Output: A scalar value if present. Goal: Copy media metadata.
        // Description: Multi-value or missing values are ignored.
        const headerValue = sourceResponse.headers[headerName];
        if (typeof headerValue === "string") responseHeaders.set(headerName, headerValue);
      }

      // Input: IncomingMessage. Output: Numeric HTTP status. Goal: Handle partial and failed delivery.
      // Description: Node supplies the status on parsed responses.
      const status = sourceResponse.statusCode;
      if (status >= 300 && status < 400) {
        sourceResponse.destroy();
        resolve(new Response(null, { status: 502 }));
        return;
      }
      if (bridgeRequest.method === "HEAD" || status === 204 || status === 205) {
        sourceResponse.resume();
        resolve(new Response(null, { status, headers: responseHeaders }));
        return;
      }

      // Input: Optional adapter chunk. Output: Chunk length in bytes. Goal: Bound the adapter queue by bytes.
      // Description: The byte length counts real buffered payload instead of a count of chunks.
      // chunk. Input: Binary Node chunk. Output: Byte count. Goal: Apply stream backpressure.
      // Description: Each queued chunk contributes exactly its byte length.
      function countChunkBytes(chunk) { return chunk.byteLength; }

      resolve(new Response(Readable.toWeb(sourceResponse, {
        strategy: { highWaterMark: 65536, size: countChunkBytes },
      }), { status, headers: responseHeaders }));
    }

    // Input: Source settings, bridge request, and approved headers. Output: Node ClientRequest.
    // Goal: Protect each request including seeks. Description: TLS hostname checks stay enabled.
    const sourceRequest = https.request(new URL(upstreamPath, source.sourceUrl), {
      method: bridgeRequest.method,
      headers: requestHeaders,
      ca: source.certificate,
      rejectUnauthorized: true,
      signal: bridgeRequest.signal,
      highWaterMark: 65536,
      agent: false,
    }, relayResponse);

    // Input: HTTPS socket timeout. Output: Aborted request. Goal: Bound source failure detection.
    // Description: Idle upstream sockets time out instead of leaving the UI waiting forever.
    function abortIdleSource() { sourceRequest.destroy(); }
    // Input: HTTPS error. Output: Bad Gateway response if headers are pending. Goal: Report source loss.
    // Description: The source address, token, and certificate never appear in the renderer response.
    function reportSourceFailure() {
      resolve(new Response(null, { status: 502, headers: { "Cache-Control": "no-store" } }));
    }

    sourceRequest.setTimeout(8000, abortIdleSource);
    sourceRequest.once("error", reportSourceFailure);
    sourceRequest.end();
  }

  return new Promise(openSource);
}

// Input: Library directory. Output: Sorted movie records. Goal: Browse local files without network traffic. Description: Hidden folders and symbolic links are skipped.
// folder. Input: User-selected folder path. Output: Recursive file list. Goal: Index this PC. Description: Only supported containers enter the catalog.
async function scanLocalFolder(folder) {
  // Input: Folder walk. Output: Discovered movie paths. Goal: Build a stable catalog. Description: The scan reads names and metadata, not video bytes.
  const paths = [];
  // Input: One directory. Output: Added file records. Goal: Visit nested movie folders. Description: Symlinks are never followed.
  // currentFolder. Input: Library root or child. Output: Entries appended to paths. Goal: Recurse safely. Description: A removed child is ignored.
  async function visit(currentFolder) {
    // entry. Input: Directory listing. Output: Child to inspect. Goal: Find supported movies. Description: Hidden names are omitted.
    for (const entry of await readdir(currentFolder, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.isSymbolicLink()) continue;
      // Input: Parent and name. Output: Child path. Goal: Locate the entry. Description: It remains private to the main process.
      const path = join(currentFolder, entry.name);
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile() && /\.(mp4|m4v|mkv|webm)$/i.test(entry.name)) paths.push(path);
    }
  }
  await visit(folder);
  paths.sort();
  // Input: Ordered paths. Output: Catalog rows. Goal: Avoid loading movies during browse. Description: IDs are scoped to this scan.
  const entries = [];
  // path. Input: Supported file paths. Output: One movie record. Goal: Record metadata. Description: Missing and empty files are skipped.
  for (const path of paths) {
    try {
      // Input: File path. Output: Size and modified time. Goal: Reject stale reads. Description: Metadata is checked again on streaming.
      const metadata = await stat(path);
      if (!metadata.isFile() || !metadata.size) continue;
      // Input: File name. Output: Display name. Goal: Show folder titles for generic movie files. Description: Paths never enter the renderer.
      const stem = basename(path, extname(path));
      // Input: Movie folder. Output: Optional registered poster. Goal: Use the library's cover convention. Description: cover.jpg wins over thumb.jpg, and neither is required.
      let posterPath = null;
      // Input: Preferred artwork names. Output: First readable image. Goal: Keep missing posters blank. Description: Only fixed names beside the movie are considered.
      for (const artworkName of ["cover.jpg", "thumb.jpg"]) {
        // Input: Movie directory and artwork name. Output: Candidate path. Goal: Check only local artwork. Description: The renderer never receives this path.
        const candidatePath = join(dirname(path), artworkName);
        try { if ((await stat(candidatePath)).isFile()) { posterPath = candidatePath; break; } } catch { /* Artwork is optional. */ }
      }
      entries.push({ path, size: metadata.size, modified: metadata.mtimeMs, posterPath,
        title: stem.toLowerCase() === "movie" ? basename(dirname(path)) : stem });
    } catch { /* Files may disappear during a scan. */ }
  }
  return entries;
}

// Input: Local media request and indexed file. Output: HTTP response. Goal: Support direct playback and seeking. Description: Node streams the selected file without TCP.
// bridgeRequest. Input: Electron request. Output: Method and Range field. Goal: Honor Chromium's media requests. Description: Only GET and HEAD reach this function.
// entry. Input: Indexed movie. Output: File path and snapshot. Goal: Prevent arbitrary file access. Description: Renderer IDs never contain paths.
async function serveLocalMedia(bridgeRequest, entry) {
  if (!entry) return new Response(null, { status: 404 });
  // Input: Indexed path. Output: Current file metadata. Goal: Reject changed files. Description: Refresh rescans the library.
  let metadata;
  try { metadata = await stat(entry.path); } catch { return new Response(null, { status: 503 }); }
  if (metadata.size !== entry.size || metadata.mtimeMs !== entry.modified) return new Response(null, { status: 503 });
  // Input: File suffix. Output: Media type. Goal: Let Chromium select a decoder. Description: Only scanned formats are possible.
  const mimeType = { ".mp4": "video/mp4", ".m4v": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm" }[extname(entry.path).toLowerCase()];
  // Input: Range header. Output: Inclusive byte interval. Goal: Seek locally. Description: One standard bytes range is supported.
  const range = bridgeRequest.headers.get("range");
  // Input: Range syntax. Output: Captured endpoints. Goal: Avoid malformed file reads. Description: Suffix ranges are included.
  const match = range && /^bytes=(\d*)-(\d*)$/.exec(range);
  if (range && !match) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${entry.size}` } });
  // Input: Range endpoints and file size. Output: First byte offset. Goal: Start the exact requested span. Description: Full requests begin at zero.
  const first = !match ? 0 : match[1] ? Number(match[1]) : Math.max(0, entry.size - Number(match[2]));
  // Input: Range endpoints and file size. Output: Last inclusive offset. Goal: End the exact span. Description: Open-ended requests end at the file boundary.
  const last = !match ? entry.size - 1 : match[1] && match[2] ? Math.min(Number(match[2]), entry.size - 1) : entry.size - 1;
  if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || first > last || first >= entry.size) {
    return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${entry.size}` } });
  }
  // Input: Selected offsets. Output: Standard response headers. Goal: Support seek and metadata preload. Description: No local path is exposed.
  const headers = { "Content-Type": mimeType, "Content-Length": String(last - first + 1), "Accept-Ranges": "bytes", "Cache-Control": "no-store" };
  if (match) headers["Content-Range"] = `bytes ${first}-${last}/${entry.size}`;
  if (bridgeRequest.method === "HEAD") return new Response(null, { status: match ? 206 : 200, headers });
  // Input: Indexed path and offsets. Output: Byte stream. Goal: Send only the requested part. Description: Browser cancellation stops the stream.
  const stream = createReadStream(entry.path, { start: first, end: last, highWaterMark: 65536 });
  bridgeRequest.signal.addEventListener("abort", () => stream.destroy(), { once: true });
  return new Response(Readable.toWeb(stream), { status: match ? 206 : 200, headers });
}

// Input: User password. Output: Lowercase SHA-256 text. Goal: Use a fixed bearer token without storing the plain password. Description: The same password on the viewer computes the same token.
// password. Input: Password field. Output: Digest string. Goal: Authenticate a host. Description: A minimum of twelve characters is required by setup.
function passwordToken(password) { return createHash("sha256").update(password, "utf8").digest("hex"); }

// Input: Peer certificate. Output: Short pairing code. Goal: Let users verify the host identity. Description: The code is the first twelve uppercase hex characters of SHA-256 of the DER certificate.
// certificate. Input: TLS peer raw DER bytes. Output: Display code. Goal: Compare two screens. Description: The full certificate remains pinned after pairing.
function pairingCode(certificate) { return createHash("sha256").update(certificate).digest("hex").slice(0, 12).toUpperCase(); }

// Input: Host address. Output: TLS certificate bytes. Goal: Inspect identity before sending a password. Description: This first handshake sends no HTTP request or credential.
// address. Input: IPv4 string. Output: DER certificate. Goal: Pin this host. Description: The address is validated before connection.
async function inspectHost(address) {
  return new Promise((resolve, reject) => {
    // Input: TCP address and port. Output: TLS socket. Goal: Read the presented identity. Description: Certificate validation occurs after the user compares the pairing code.
    const socket = require("node:tls").connect({ host: address, port: 8443, rejectUnauthorized: false, timeout: 5000 }, () => {
      // Input: TLS socket. Output: Peer certificate. Goal: Compute the pairing code. Description: The full DER bytes are saved for later verified connections.
      const peer = socket.getPeerCertificate(true);
      socket.end();
      if (!peer.raw) reject(new Error("The host did not present a certificate."));
      else resolve(peer.raw);
    });
    socket.once("timeout", () => socket.destroy(new Error("The host did not answer.")));
    socket.once("error", reject);
  });
}

// Input: Executable and arguments. Output: Exit status. Goal: Generate a local TLS identity. Description: OpenSSL is bundled alongside the host executable.
// executable. Input: Packaged helper path. Output: Child process. Goal: Run certificate creation. Description: No shell parses the arguments.
// arguments. Input: Identity paths and IP. Output: OpenSSL flags. Goal: Include the selected IP in the certificate. Description: Password never enters these arguments.
async function runHelper(executable, arguments_) {
  return new Promise((resolve, reject) => {
    // Input: Process path and flags. Output: Helper child. Goal: Complete setup. Description: Standard error is captured for a safe failure message.
    const child = spawn(executable, arguments_, { windowsHide: true });
    // Input: Helper error stream. Output: Diagnostic text. Goal: Explain certificate failures. Description: Capped to avoid unbounded memory use.
    let errorText = "";
    child.stderr.on("data", (chunk) => { errorText = (errorText + chunk.toString()).slice(-1000); });
    child.once("error", reject);
    child.once("exit", (code) => code === 0 ? resolve() : reject(new Error(`Certificate setup failed. ${errorText}`)));
  });
}

// Input: Network interfaces. Output: Private IPv4 options. Goal: Show the address another PC should enter. Description: Loopback is offered for same-PC testing.
function hostAddresses() {
  // Input: Windows adapters. Output: Deduplicated IPv4 addresses. Goal: Avoid manual command line inspection. Description: Internal and link-local addresses are omitted.
  const addresses = new Set();
  // adapter. Input: Network interface list. Output: Address records. Goal: Visit every interface. Description: VPN addresses may appear and can be ignored by the user.
  for (const adapter of Object.values(networkInterfaces())) {
    // item. Input: One adapter address. Output: Candidate IPv4. Goal: Offer reachable addresses. Description: The UI names the selected address.
    for (const item of adapter || []) if (item.family === "IPv4" && !item.internal && !item.address.startsWith("169.254.")) addresses.add(item.address);
  }
  return [...addresses, "127.0.0.1"];
}

// Input: Host setup form. Output: Running host and pairing details. Goal: Start sharing without terminal commands. Description: Files and credentials remain in user app data.
// settings. Input: Address, folder, and password. Output: Host state. Goal: Apply user choices. Description: Rejects invalid inputs before creating credentials.
async function startHost(settings) {
  if (hostProcess) throw new Error("Sharing is already running.");
  if (!hostAddresses().includes(settings.address)) throw new Error("Choose an address shown in the list.");
  if (typeof settings.password !== "string" || settings.password.length < 12) throw new Error("Use a password of at least twelve characters.");
  // Input: Chosen folder. Output: Folder metadata. Goal: Require an existing library. Description: An empty library can still be shared until movies are added.
  const folder = await stat(settings.folder);
  if (!folder.isDirectory()) throw new Error("Choose a movie folder.");
  if (!(await scanLocalFolder(settings.folder)).length) throw new Error("This folder has no supported movies yet. Choose a folder with MP4, M4V, MKV, or WebM files.");
  // Input: User data directory. Output: Host identity folder. Goal: Keep private key outside the ZIP. Description: Windows user profile controls access.
  const identityFolder = join(app.getPath("userData"), "host");
  await mkdir(identityFolder, { recursive: true });
  // Input: Chosen IP. Output: Certificate and key paths. Goal: Bind TLS to the address displayed. Description: A new address gets a new identity.
  const certificatePath = join(identityFolder, `${settings.address}.pem`);
  // Input: Chosen IP. Output: Private key path. Goal: Prove host identity. Description: Only this PC keeps the key.
  const keyPath = join(identityFolder, `${settings.address}.key`);
  // Input: Packaged resources. Output: OpenSSL executable. Goal: Avoid an external install. Description: The build copies its DLLs beside it.
  const opensslPath = join(process.resourcesPath, "openssl.exe");
  try { await stat(certificatePath); await stat(keyPath); }
  catch { await runHelper(opensslPath, ["req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes", "-days", "3650", "-config", "NUL", "-subj", "/CN=Movie Shelf Host", "-addext", `subjectAltName=IP:${settings.address}`, "-addext", "extendedKeyUsage=serverAuth", "-keyout", keyPath, "-out", certificatePath]); }
  // Input: Password field. Output: Token text file. Goal: Authenticate catalog and media. Description: Plain password is never written to disk.
  const tokenPath = join(identityFolder, "token.txt");
  await writeFile(tokenPath, passwordToken(settings.password), { mode: 0o600 });
  // Input: Packaged host binary and setup paths. Output: Running sharing process. Goal: Serve this library. Description: The UI owns the child lifecycle.
  const executable = join(process.resourcesPath, "movie-playback-host.exe");
  // Input: Host executable and validated paths. Output: Child process. Goal: Start LAN sharing. Description: The host binds the selected IP on port 8443.
  const child = spawn(executable, ["--bind", `${settings.address}:8443`, "--cert", certificatePath, "--key", keyPath, "--token-file", tokenPath, "--library", settings.folder], { windowsHide: true });
  hostProcess = child;
  child.once("exit", () => { if (hostProcess === child) hostProcess = null; });
  await new Promise((resolve, reject) => {
    // Input: Host stdout. Output: Readiness result. Goal: Report a working sharing process. Description: The host prints its listening address after binding.
    let output = "";
    // Input: Host startup timer. Output: Timeout error. Goal: Avoid a stuck setup screen. Description: Ten seconds covers a normal library scan.
    const timer = setTimeout(() => reject(new Error("Host startup timed out. Try a smaller folder or restart the app.")), 30000);
    child.stdout.on("data", (chunk) => { output += chunk.toString(); if (output.includes("Listening on ")) { clearTimeout(timer); resolve(); } });
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.once("exit", (code) => { clearTimeout(timer); reject(new Error(`Host stopped during setup, exit code ${code}. Check that port 8443 is available.`)); });
  });
  // Input: Certificate PEM. Output: DER bytes. Goal: Display an identity code. Description: OpenSSL PEM base64 is decoded locally.
  const certificateText = await readFile(certificatePath, "utf8");
  // Input: PEM body. Output: Certificate bytes. Goal: Match the viewer fingerprint. Description: Headers and whitespace are removed.
  const certificate = Buffer.from(certificateText.replace(/-----[^-]+-----/g, "").replace(/\s/g, ""), "base64");
  return { address: settings.address, folder: settings.folder, code: pairingCode(certificate) };
}

// Input: Pairing form. Output: Saved remote source. Goal: Add another PC without moving files. Description: Certificate code is checked before the password-derived token is sent.
// settings. Input: IP, password, code, and optional name. Output: Source index. Goal: Pair with a host. Description: Only the selected HTTPS host is contacted.
async function addRemoteSource(settings) {
  if (sources.length >= 32) throw new Error("The viewer supports up to 32 sources.");
  // Input: Address field. Output: Valid IPv4 text. Goal: Constrain connections to a chosen PC. Description: Hostnames and URLs are not accepted here.
  const address = String(settings.address || "").trim();
  if (!/^(?:\d{1,3}\.){3}\d{1,3}$/.test(address) || address.split(".").some((part) => Number(part) > 255)) throw new Error("Enter the host's IPv4 address.");
  if (typeof settings.password !== "string" || settings.password.length < 12) throw new Error("Enter the host password.");
  // Input: TLS handshake. Output: Raw certificate. Goal: Verify the host shown on the other PC. Description: No password is transmitted during inspection.
  const certificate = await inspectHost(address);
  if (pairingCode(certificate) !== String(settings.code || "").replace(/\s/g, "").toUpperCase()) throw new Error("Pairing code does not match the host screen.");
  // Input: Address, pinned certificate, and password digest. Output: Remote source. Goal: Authenticate a catalog request. Description: Normal TLS verification remains enabled.
  // Input: Peer DER bytes. Output: PEM certificate. Goal: Use the host as the sole TLS trust anchor. Description: The displayed fingerprint still comes from the same DER bytes.
  const certificatePem = `-----BEGIN CERTIFICATE-----\n${certificate.toString("base64").match(/.{1,64}/g).join("\n")}\n-----END CERTIFICATE-----\n`;
  const source = { type: "remote", name: String(settings.name || address).trim().slice(0, 80), sourceUrl: new URL(`https://${address}:8443`), certificate: Buffer.from(certificatePem), token: passwordToken(settings.password) };
  // Input: Pinned host. Output: Catalog response. Goal: Prove password and connectivity before saving. Description: The response is read only for success.
  const result = await forwardMedia(new Request("https://local/catalog"), source, "/catalog");
  if (result.status !== 200) throw new Error("Could not open this host. Check the password and that sharing is running.");
  await result.body?.cancel();
  if (sources.some((existing) => existing.type === "remote" && existing.sourceUrl.origin === source.sourceUrl.origin)) throw new Error("This host is already added.");
  sources.push(source);
  await saveSources();
  return sources.length - 1;
}

// Input: Native picker and current source list. Output: Added local source. Goal: Give this PC a direct library. Description: The selected folder is scanned without using a server.
async function addLocalSource() {
  if (sources.length >= 32) throw new Error("The viewer supports up to 32 sources.");
  // Input: Desktop folder picker. Output: Selected path. Goal: Avoid typing file paths. Description: Cancellation makes no change.
  const choice = await dialog.showOpenDialog({ properties: ["openDirectory"], title: "Choose your movie folder" });
  if (choice.canceled) return false;
  // Input: Picker result. Output: Folder path. Goal: Register local movies. Description: Only the main process reads the folder.
  const folder = choice.filePaths[0];
  if (sources.some((source) => source.type === "local" && source.folder === folder)) throw new Error("This folder is already added.");
  sources.push({ type: "local", name: `This PC, ${basename(folder)}`, folder });
  await saveSources();
  return true;
}

// Input: URI and method from the isolated player session. Output: Local asset, media stream, or error.
// Goal: Restrict the custom protocol to the bundled UI and one upstream route.
// Description: The full request URL must match a known route before a request is acted on.
// bridgeRequest. Input: Electron Request. Output: URL and HTTP method.
// Goal: Dispatch player requests. Description: All other origins and paths get a local error.
// source. Input: Launcher configuration. Output: Trusted source for the one media route.
// Goal: Bind the bridge to configured sources. Description: Renderer cannot alter peer credentials.
async function routePlayerRequest(bridgeRequest) {
  if (bridgeRequest.method !== "GET" && bridgeRequest.method !== "HEAD") {
    return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  // Input: Trusted local URL. Output: Source index and optional media ID. Goal: Restrict the bridge to configured hosts. Description: Numeric IDs are server catalog indexes.
  const route = new URL(bridgeRequest.url);
  // Input: Local pathname. Output: Catalog or media route pieces. Goal: Reject arbitrary forwarding. Description: Versioned numeric IDs exclude traversal and stale selections.
  const match = route.search || route.hash ? null : /^\/(catalog|media|poster)\/(\d+)(?:\/(\d+-\d+))?$/.exec(route.pathname);
  if (match && ((match[1] === "catalog" && match[3] === undefined) ||
      ((match[1] === "media" || match[1] === "poster") && match[3] !== undefined))) {
    // Input: Route index. Output: Configured host. Goal: Resolve one source. Description: Missing indexes return 404.
    const source = sources[Number(match[2])];
    if (!source) return new Response(null, { status: 404 });
    if (source.type === "remote") return forwardMedia(bridgeRequest, source, match[1] === "catalog" ? "/catalog" : `/${match[1]}/${match[3]}`);
    // Input: Local source and folder contents. Output: Current scan. Goal: Refresh direct local catalog. Description: Media bytes are untouched until selection.
    let snapshot = localCatalogs.get(Number(match[2]));
    if (match[1] === "catalog") {
      // Input: Local folder. Output: Current movie records. Goal: Refresh the source. Description: Only metadata is scanned.
      let entries;
      try { entries = await scanLocalFolder(source.folder); } catch { return new Response(null, { status: 503 }); }
      // Input: Paths, sizes, and modification times. Output: Decimal catalog version. Goal: Reject stale local movie IDs after a changed scan. Description: SHA-256 changes when the registered files change.
      const version = BigInt("0x" + createHash("sha256").update(JSON.stringify(entries.map((entry) => [entry.path, entry.size, entry.modified]))).digest("hex").slice(0, 12)).toString();
      snapshot = { entries, version };
      localCatalogs.set(Number(match[2]), snapshot);
      return new Response(JSON.stringify({ movies: entries.map((entry, index) => ({ id: `${version}-${index}`, title: entry.title, bytes: entry.size, poster: Boolean(entry.posterPath) })) }),
        { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
    }
    if (!snapshot || !match[3].startsWith(`${snapshot.version}-`)) return new Response(null, { status: 404 });
    // Input: Versioned asset ID. Output: Registered movie. Goal: Serve only scanned poster or video files. Description: Numeric IDs cannot select arbitrary paths.
    const indexedEntry = snapshot.entries[Number(match[3].split("-")[1])];
    if (match[1] === "media") return serveLocalMedia(bridgeRequest, indexedEntry);
    if (!indexedEntry?.posterPath) return new Response(null, { status: 404 });
    try {
      // Input: Fixed artwork path. Output: Small image bytes. Goal: Show local posters. Description: Oversized or changed artwork is rejected.
      const posterMetadata = await stat(indexedEntry.posterPath);
      if (!posterMetadata.isFile() || posterMetadata.size > 10 * 1024 * 1024) return new Response(null, { status: 404 });
      return new Response(bridgeRequest.method === "HEAD" ? null : await readFile(indexedEntry.posterPath), { headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store" } });
    } catch { return new Response(null, { status: 404 }); }
  }
  if (bridgeRequest.url === `${playerOrigin}/sources`) {
    return new Response(JSON.stringify(sources.map((source) => source.name)), {
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  // Input: Requested URL. Output: Bundled filename and MIME type, if allowed.
  // Goal: Match only static app routes. Description: The URL never becomes a filesystem path.
  const asset = appAssets.get(bridgeRequest.url);
  if (!asset) return new Response(null, { status: 404 });
  return new Response(bridgeRequest.method === "HEAD" ? null : await readFile(join(__dirname, asset[0])), {
    headers: {
      "Content-Type": asset[1],
      "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

// Input: Electron readiness and launch configuration. Output: One sandboxed BrowserWindow.
// Goal: Start the app securely. Description: The private in-memory session owns the URL handler.
async function openPlayer() {
  // Input: Launcher environment. Output: Validated source configuration. Goal: Constrain upstream requests.
  // Description: This object is only read by the main process.
  sources = await readSources();
  // Input: Packaged executable name or development argument. Output: Role flag. Goal: Open the correct setup screen. Description: The ZIP ships two clearly named executables.
  const hostMode = /MovieShelfHost/i.test(process.execPath) || process.argv.includes("--host");
  // Input: Trusted renderer action. Output: IPC result. Goal: Keep filesystem and credentials in the main process. Description: Only the app origin may request these operations.
  // action. Input: Preload API command. Output: Named operation. Goal: Dispatch setup tasks. Description: Unrecognized commands are rejected.
  // payload. Input: Form values. Output: Setup data. Goal: Pass user choices. Description: Paths are obtained from native pickers where possible.
  async function handleSetup(event, action, payload) {
    if (event.senderFrame?.url !== `${playerOrigin}/` && event.senderFrame?.url !== `${playerOrigin}/host.html`) throw new Error("Invalid setup request.");
    if (action === "list") return sources.map((source) => ({ name: source.name, type: source.type }));
    if (action === "fullscreen" && !hostMode) {
      // Input: Viewer request and current window. Output: Fullscreen state. Goal: Make fullscreen work even when native video controls do not. Description: Only the trusted viewer can change its window.
      const viewerWindow = BrowserWindow.fromWebContents(event.sender);
      if (!viewerWindow) throw new Error("Viewer window is unavailable.");
      if (payload) { viewerWindow.show(); viewerWindow.focus(); }
      viewerWindow.setKiosk(Boolean(payload));
      return viewerWindow.isKiosk();
    }
    if (action === "remove" && !hostMode) {
      if (!Number.isSafeInteger(payload) || payload < 0 || payload >= sources.length) throw new Error("Choose a saved source.");
      // Input: Valid saved-source index. Output: Removed source record. Goal: Restore the list if persistence fails. Description: Movie files remain untouched.
      const removedSource = sources.splice(payload, 1)[0];
      try { await saveSources(); }
      catch (error) { sources.splice(payload, 0, removedSource); throw error; }
      localCatalogs = new Map();
      return true;
    }
    if (action === "add-local" && !hostMode) return addLocalSource();
    if (action === "add-remote" && !hostMode) return addRemoteSource(payload);
    if (action === "addresses" && hostMode) return hostAddresses();
    if (action === "pick-folder" && hostMode) {
      // Input: Native folder dialog. Output: Selected directory or null. Goal: Avoid manual path typing. Description: Cancellation keeps the current form.
      const choice = await dialog.showOpenDialog({ properties: ["openDirectory"], title: "Choose the movie folder to share" });
      return choice.canceled ? null : choice.filePaths[0];
    }
    if (action === "start-host" && hostMode) return startHost(payload);
    if (action === "stop-host" && hostMode) { hostProcess?.kill(); hostProcess = null; return true; }
    throw new Error("This action is unavailable.");
  }
  ipcMain.handle("shelf:setup", handleSetup);
  // Input: Private partition name. Output: Non-persistent session. Goal: Isolate the app scheme.
  // Description: The handler is never registered on the default session.
  const playerSession = session.fromPartition("movie-shelf", { cache: false });

  // Input: Session request. Output: Response promise. Goal: Dispatch against fixed configuration.
  // Description: The closure allows only this isolated session to reach the media route.
  // bridgeRequest. Input: Electron Request. Output: Route inputs. Goal: Route a request.
  // Description: Method and URL are validated before the route can use source credentials.
  function handlePlayerRequest(bridgeRequest) { return routePlayerRequest(bridgeRequest); }
  // Input: Permission check callback arguments. Output: False. Goal: Deny renderer privileges.
  // Description: Playback only needs web media capabilities and a user-driven file input.
  function denyPermissionCheck() { return false; }
  // Input: Permission check. Output: Boolean decision. Goal: Permit native fullscreen only. Description: Requires the trusted viewer main frame.
  // requestingContents. Input: Web contents. Output: Page URL. Goal: Validate viewer. Description: Null contents are denied.
  // permission. Input: Permission name. Output: Fullscreen match. Goal: Limit privileges. Description: Other permissions remain denied.
  // requestingOrigin. Input: Frame origin. Output: Origin match. Goal: Validate source. Description: Must match the private app origin.
  // details. Input: Frame details. Output: Main frame check. Goal: Exclude embedded pages. Description: Requires the viewer main frame.
  function checkViewerPermission(requestingContents, permission, requestingOrigin, details) {
    return !hostMode && permission === "fullscreen" && requestingContents?.getURL() === `${playerOrigin}/` && details.isMainFrame && (requestingOrigin === playerOrigin || requestingOrigin === `${playerOrigin}/`);
  }
  // Input: Electron permission request. Output: Callback with false. Goal: Deny permission requests.
  // Description: No permission prompts are necessary for the prototype.
  // _webContents. Input: Requesting WebContents. Output: None. Goal: Accept Electron's signature. Description: Ignored.
  // _permission. Input: Permission name. Output: None. Goal: Accept Electron's signature. Description: Ignored.
  // reply. Input: Permission callback. Output: False decision. Goal: Deny the request. Description: Completes the interaction.
  function denyPermissionRequest(_webContents, _permission, reply) { reply(false); }

  // Input: Browser permission request. Output: Permission decision. Goal: Enable native video fullscreen. Description: Only the trusted viewer main frame may request fullscreen.
  // requestingContents. Input: Requesting web contents. Output: Current page URL. Goal: Verify the viewer. Description: Missing contents are rejected.
  // permission. Input: Permission name. Output: Fullscreen match. Goal: Keep other privileges denied. Description: Automatic fullscreen is excluded.
  // reply. Input: Electron callback. Output: Boolean decision. Goal: Complete the request. Description: Called once.
  // details. Input: Request frame metadata. Output: Trusted frame check. Goal: Reject subframes and other pages. Description: Requires the bundled viewer URL.
  function handleViewerPermission(requestingContents, permission, reply, details) {
    reply(!hostMode && permission === "fullscreen" && requestingContents?.getURL() === `${playerOrigin}/` && details.isMainFrame && details.requestingUrl === `${playerOrigin}/`);
  }

  playerSession.protocol.handle("shelfplay", handlePlayerRequest);
  playerSession.setPermissionCheckHandler(checkViewerPermission);
  playerSession.setPermissionRequestHandler(handleViewerPermission);

  // Input: Player session. Output: BrowserWindow. Goal: Display only the bundled trusted UI.
  // Description: Chromium security, context isolation, and sandboxing remain enabled.
  const playerWindow = new BrowserWindow({
    width: 1000,
    height: 760,
    webPreferences: { session: playerSession, contextIsolation: true, sandbox: true, nodeIntegration: false, preload: join(__dirname, "preload.cjs") },
  });

  // Input: Window-open request. Output: Deny action. Goal: Keep untrusted pages out of the player session.
  // Description: Setup uses a dialog inside the existing window.
  function denyNewWindow() { return { action: "deny" }; }
  // Input: Renderer navigation. Output: Canceled navigation. Goal: Keep credentials bound to the trusted app.
  // Description: Electron's main-process loadURL is not affected by will-navigate.
  // navigationEvent. Input: Electron navigation event. Output: Canceled event.
  // Goal: Block renderer navigation. Description: The listener cancels every renderer-initiated page navigation.
  function denyNavigation(navigationEvent) { navigationEvent.preventDefault(); }

  playerWindow.webContents.setWindowOpenHandler(denyNewWindow);
  playerWindow.webContents.on("will-navigate", denyNavigation);
  await playerWindow.loadURL(hostMode ? `${playerOrigin}/host.html` : `${playerOrigin}/`);
}

// Input: Startup failure. Output: Safe launch instructions and exit. Goal: Make missing configuration actionable.
// Description: The error object is never printed because configuration may contain secrets.
function reportStartupFailure() {
  dialog.showErrorBox("Movie Shelf could not start", "Close the app and try again. If this keeps happening, remove its saved settings in your Windows AppData folder.");
  app.exit(1);
}

// Input: All windows closed. Output: App quits. Goal: Release all media requests.
// Description: The server runs independently of the desktop player.
function closePlayer() { hostProcess?.kill(); app.quit(); }

app.whenReady().then(openPlayer).catch(reportStartupFailure);
app.on("window-all-closed", closePlayer);
