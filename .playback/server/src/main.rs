use std::{
    convert::Infallible,
    hash::{Hash, Hasher},
    io,
    net::SocketAddr,
    path::PathBuf,
    sync::Arc,
    time::Duration,
};

use bytes::Bytes;
use futures_util::TryStreamExt;
use http_body_util::{BodyExt, Empty, Full, StreamBody, combinators::UnsyncBoxBody};
use hyper::{
    Method, Request, Response, StatusCode,
    body::{Frame, Incoming},
    header::{self, HeaderValue},
    server::conn::http1,
    service::service_fn,
};
use hyper_util::rt::{TokioIo, TokioTimer};
use subtle::ConstantTimeEq;
use tokio::{
    fs::File,
    io::{AsyncReadExt, AsyncSeekExt},
    net::{TcpListener, TcpStream},
    sync::{OwnedSemaphorePermit, Semaphore},
    time::timeout,
};
use tokio_rustls::{
    TlsAcceptor,
    rustls::{
        ServerConfig,
        pki_types::{CertificateDer, PrivateKeyDer, pem::PemObject},
    },
};
use tokio_util::io::ReaderStream;

type PlaybackBody = UnsyncBoxBody<Bytes, io::Error>;
type StartupError = Box<dyn std::error::Error>;

struct PlaybackSettings {
    // Input: --bind or loopback default. Output: IP and port. Goal: Limit exposure. Description: Local TCP bind address.
    bind_address: SocketAddr,
    // Input: --cert. Output: PEM path. Goal: Present the paired peer identity. Description: Public TLS certificate.
    certificate_path: PathBuf,
    // Input: --key. Output: PEM path. Goal: Prove TLS identity. Description: Local private key.
    private_key_path: PathBuf,
    // Input: --token-file. Output: Text path. Goal: Keep the secret off the command line. Description: File containing one token.
    token_path: PathBuf,
    // Input: Repeated --library arguments. Output: Library roots. Goal: Share a complete catalog. Description: Each root is scanned recursively at startup.
    library_paths: Vec<PathBuf>,
}

struct SharedMedia {
    // Input: Startup arguments. Output: Canonical path. Goal: Open independent streams. Description: One registered movie file.
    path: PathBuf,
    // Input: Artwork files next to the movie. Output: Optional JPEG path. Goal: Show existing folder covers. Description: cover.jpg is preferred and thumb.jpg is the fallback.
    poster_path: Option<PathBuf>,
    // Input: Fixture extension. Output: MIME type. Goal: Tell the player the container. Description: Response Content-Type.
    mime_type: &'static str,
    // Input: Token file. Output: Header bytes. Goal: Authorize all media requests. Description: Complete expected Bearer header.
    authorization: Vec<u8>,
    // Input: Initial file metadata. Output: Byte count. Goal: Compare subsequent opens. Description: Snapshot length in bytes.
    length: u64,
    // Input: Initial file metadata. Output: Modification time. Goal: Detect movie replacement. Description: Snapshot timestamp.
    modified: std::time::SystemTime,
    // Input: Initial file metadata. Output: HTTP field. Goal: Describe the movie version. Description: Weak ETag based on size and modification time.
    etag: HeaderValue,
}

struct SharedCatalog {
    // Input: Registered media files. Output: Indexed assets. Goal: Resolve opaque media routes. Description: Each index identifies one scanned file.
    entries: Vec<SharedMedia>,
    // Input: Catalog entries. Output: UTF-8 JSON bytes. Goal: Browse without movie bytes. Description: Serialized once at startup.
    json: Bytes,
    // Input: Registered file metadata. Output: Catalog fingerprint. Goal: Reject stale media IDs after a changed scan. Description: Stable across restarts with matching files.
    version: u64,
}

// Input: Host command line. Output: Bound TLS server or startup error. Goal: Share movie folders. Description: Loads credentials and runs the connection loop.
#[tokio::main]
async fn main() -> Result<(), StartupError> {
    // Input: Process command line. Output: Validated option paths and address. Goal: Select inputs. Description: Required credentials and libraries.
    let settings = read_settings()?;
    // Input: Certificate path. Output: Certificate list. Goal: Present peer identity. Description: PEM certificate chain ordered leaf first.
    let certificates =
        CertificateDer::pem_file_iter(settings.certificate_path)?.collect::<Result<Vec<_>, _>>()?;
    // Input: Private key path. Output: TLS key. Goal: Prove peer identity. Description: First supported key in the PEM file.
    let private_key = PrivateKeyDer::from_pem_file(settings.private_key_path)?;
    // Input: Certificate chain and private key. Output: Shared TLS acceptor. Goal: Encrypt connections. Description: Bearer authorization occurs at the HTTP layer.
    let tls_acceptor = TlsAcceptor::from(Arc::new(
        ServerConfig::builder()
            .with_no_client_auth()
            .with_single_cert(certificates, private_key)?,
    ));
    // Input: Token text file. Output: UTF-8 credential. Goal: Read authorization secret. Description: Line endings are removed before validation.
    let token_text = std::fs::read_to_string(settings.token_path)?;
    // Input: UTF-8 credential. Output: Trimmed bearer token. Goal: Accept a normal one-line file. Description: Must use RFC 6750 token characters.
    let token = token_text.trim_end_matches(['\r', '\n']);
    // Input: Token characters. Output: Unpadded credential. Goal: Validate RFC 6750 syntax. Description: Padding may appear only at the end.
    let token_body = token.trim_end_matches('=');
    if !(32..=256).contains(&token.len())
        || token_body.is_empty()
        || !token_body.bytes().all(is_bearer_character)
    {
        return Err("Token file must contain one 32 to 256 character bearer token.".into());
    }
    // Input: Library roots. Output: Ordered canonical files. Goal: Index local movies. Description: Only scanned files can be requested.
    let mut paths = Vec::new();
    // library_path. Input: Repeated --library arguments. Output: One root to scan. Goal: Include every registered drive. Description: Each root remains local to this host.
    for library_path in &settings.library_paths {
        collect_movies(library_path, &mut paths)?;
    }
    paths.sort();
    paths.dedup();
    if paths.is_empty() {
        return Err("No supported nonempty movies found in the registered libraries.".into());
    }
    // Input: Registered file paths. Output: Media records. Goal: Serve only scanned assets. Description: Each record snapshots its file length and modification time.
    let mut entries = Vec::new();
    // path. Input: Canonical registered paths. Output: One movie file. Goal: Build a catalog entry. Description: Client URLs never supply a filesystem path.
    for path in paths {
        // Input: File extension. Output: HTTP media type. Goal: Tell Chromium the container. Description: Unknown extensions are excluded.
        let mime_type = match path
            .extension()
            .and_then(std::ffi::OsStr::to_str)
            .map(str::to_ascii_lowercase)
            .as_deref()
        {
            Some("mp4" | "m4v") => "video/mp4",
            Some("mkv") => "video/x-matroska",
            Some("webm") => "video/webm",
            _ => continue,
        };
        // Input: Registered path. Output: Read-only guard. Goal: Keep a stable asset open. Description: Missing and inaccessible files are skipped.
        let Ok(fixture_guard) = open_movie(&path).await else {
            continue;
        };
        // Input: Read-only guard. Output: File metadata. Goal: Reject empty or unavailable assets. Description: Only regular files enter the catalog.
        let Ok(metadata) = fixture_guard.metadata().await else {
            continue;
        };
        if !metadata.is_file() || metadata.len() == 0 {
            continue;
        }
        // Input: File metadata. Output: Timestamp. Goal: Detect replacement during streaming. Description: Compared on every request.
        let modified = metadata.modified()?;
        // Input: Timestamp. Output: Nanoseconds after epoch. Goal: Build a version validator. Description: Pre-epoch times use zero.
        let modified_since_epoch = modified
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default();
        // Input: Registered movie directory. Output: First available JPEG path. Goal: Reuse the library's existing artwork. Description: A missing cover leaves the poster blank.
        let poster_path = ["cover.jpg", "thumb.jpg"]
            .iter()
            .map(|name| path.parent().unwrap().join(name))
            .find(|candidate| candidate.is_file());
        entries.push(SharedMedia {
            path,
            poster_path,
            mime_type,
            authorization: format!("Bearer {token}").into_bytes(),
            length: metadata.len(),
            modified,
            etag: HeaderValue::from_str(&format!(
                "W/\"{:x}-{:x}\"",
                metadata.len(),
                modified_since_epoch.as_nanos()
            ))?,
        });
    }
    if entries.is_empty() {
        return Err("No readable nonempty movies found.".into());
    }
    // Input: Registered file identities. Output: Catalog fingerprint. Goal: Bind IDs to this exact scan. Description: Metadata hashing avoids reading movie bytes.
    let mut version_hasher = std::collections::hash_map::DefaultHasher::new();
    // entry. Input: Startup media records. Output: Fingerprint fields. Goal: Detect catalog changes. Description: Hashes path, size, and modification time in sorted order.
    for entry in &entries {
        entry.path.hash(&mut version_hasher);
        entry.length.hash(&mut version_hasher);
        entry.modified.hash(&mut version_hasher);
    }
    // Input: Hashed catalog metadata. Output: Version number. Goal: Tag media routes. Description: Changed snapshots produce different IDs with high probability.
    let version = version_hasher.finish();
    // Input: Snapshot entries and version. Output: Catalog JSON. Goal: Send titles without video bytes. Description: IDs include the scan fingerprint.
    let json = catalog_json(&entries, version);
    // Input: Media records and JSON. Output: Shared catalog. Goal: Serve concurrent readers. Description: Both fields remain immutable until restart.
    let catalog = Arc::new(SharedCatalog {
        entries,
        json: Bytes::from(json),
        version,
    });
    // Input: Selected bind address. Output: TCP listener. Goal: Receive playback requests. Description: An explicit non-loopback address enables LAN use.
    let listener = TcpListener::bind(settings.bind_address).await?;
    // Input: Fixed connection budget. Output: Shared semaphore. Goal: Bound concurrent HTTP and handshake work. Description: Each connection holds one slot.
    let connection_slots = Arc::new(Semaphore::new(32));
    println!("Listening on https://{}", listener.local_addr()?);
    loop {
        // Input: TCP listener. Output: Newly accepted socket. Goal: Route one peer. Description: Peer IP is ignored and never serves as authorization.
        let (socket, _) = listener.accept().await?;
        // Input: Connection semaphore. Output: Slot guard. Goal: Enforce the connection budget. Description: A saturated listener immediately drops new sockets.
        let Ok(slot) = Arc::clone(&connection_slots).try_acquire_owned() else {
            continue;
        };
        tokio::spawn(serve_connection(
            socket,
            tls_acceptor.clone(),
            Arc::clone(&catalog),
            slot,
        ));
    }
}

// Input: Process arguments. Output: Server settings. Goal: Accept library and credentials. Description: Parses named options and disallows duplicate flags.
fn read_settings() -> Result<PlaybackSettings, StartupError> {
    // Input: OS process arguments. Output: Iterator over options and values. Goal: Preserve Unicode paths. Description: The executable name is skipped.
    let mut arguments = std::env::args_os().skip(1);
    // Input: --bind. Output: Optional address text. Goal: Accept one explicit socket address. Description: Loopback is used if absent.
    let mut bind_address = None;
    // Input: --cert. Output: Optional certificate path. Goal: Accept one certificate. Description: Public TLS certificate in PEM format.
    let mut certificate_path = None;
    // Input: --key. Output: Optional private key path. Goal: Accept one TLS key. Description: Server private key in PEM format.
    let mut private_key_path = None;
    // Input: --token-file. Output: Optional bearer token path. Goal: Read one secret. Description: Required text credential file.
    let mut token_path = None;
    // Input: Repeated --library flags. Output: Paths to scan. Goal: Register multiple roots. Description: The scanner does not modify their contents.
    let mut library_paths = Vec::new();
    // Input: Argument iterator. Output: One option name. Goal: Select the receiving field. Description: Every flag consumes a value.
    while let Some(option) = arguments.next() {
        // Input: Argument iterator. Output: Option value. Goal: Preserve the native path representation. Description: The item immediately after the option.
        let value = arguments
            .next()
            .ok_or("Missing value for playback host option.")?;
        if option == "--library" {
            library_paths.push(PathBuf::from(value));
            continue;
        }
        // Input: Option name. Output: Mutable option field. Goal: Detect duplicates. Description: The matching vacant setting is filled once.
        let destination = match option.to_str() {
            Some("--bind") => &mut bind_address,
            Some("--cert") => &mut certificate_path,
            Some("--key") => &mut private_key_path,
            Some("--token-file") => &mut token_path,
            _ => return Err("Usage: movie-playback-host [--bind IP:PORT] --cert CERT --key KEY --token-file TOKEN --library FOLDER [--library FOLDER ...]".into()),
        };
        if destination.replace(value).is_some() {
            return Err("Playback host options may only be supplied once.".into());
        }
    }
    Ok(PlaybackSettings {
        bind_address: bind_address
            .as_deref()
            .unwrap_or(std::ffi::OsStr::new("127.0.0.1:8443"))
            .to_str()
            .ok_or("Bind address must be an IP and port.")?
            .parse()?,
        certificate_path: certificate_path.ok_or("Missing --cert.")?.into(),
        private_key_path: private_key_path.ok_or("Missing --key.")?.into(),
        token_path: token_path.ok_or("Missing --token-file.")?.into(),
        library_paths,
    })
}

// Input: One credential byte. Output: Whether it is an unpadded RFC 6750 token character. Goal: Validate file syntax. Description: ASCII alphanumeric or permitted punctuation.
// byte. Input: Token byte. Output: Byte to classify. Goal: Exclude whitespace and controls. Description: A single UTF-8 code unit.
fn is_bearer_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || b"-._~+/".contains(&byte)
}

// Input: Registered path. Output: Independent read handle or I/O error. Goal: Stream a movie safely. Description: Uses read-only Windows sharing while streaming.
// path. Input: Canonical movie path. Output: File to open. Goal: Bind requests to a scanned resource. Description: Supplied only by the host operator.
async fn open_movie(path: &std::path::Path) -> io::Result<File> {
    // Input: Default Tokio options. Output: Read-only configuration. Goal: Set interoperable sharing. Description: Windows allows other reads only.
    let mut options = File::options();
    options.read(true);
    #[cfg(windows)]
    options.share_mode(1);
    options.open(path).await
}

// Input: Accepted socket, TLS config, media state, and slot. Output: None. Goal: Serve requests securely. Description: Applies deadlines to TLS and HTTP headers and streams until completion or disconnect.
// socket. Input: TCP listener. Output: Connected peer stream. Goal: Run a TLS handshake. Description: Untrusted socket.
// tls_acceptor. Input: Startup identity. Output: TLS server configuration. Goal: Encrypt the connection. Description: Shared rustls acceptor.
// media. Input: Startup registration. Output: Shared application state. Goal: Authorize and resolve requests. Description: Contains registered movies.
// _connection_slot. Input: Semaphore permit. Output: Retained connection slot. Goal: Bound active peers. Description: Releases capacity on task exit.
async fn serve_connection(
    socket: TcpStream,
    tls_acceptor: TlsAcceptor,
    catalog: Arc<SharedCatalog>,
    _connection_slot: OwnedSemaphorePermit,
) {
    // Input: Established TCP socket and TLS identity. Output: Encrypted stream. Goal: Reject plaintext and stalled handshakes. Description: Given eight seconds to finish.
    let Ok(Ok(tls_stream)) = timeout(Duration::from_secs(8), tls_acceptor.accept(socket)).await
    else {
        return;
    };
    // request. Input: Hyper HTTP request. Output: Incoming method, target, and headers. Goal: Evaluate every seek independently. Description: Hyper invokes the closure for each request.
    let service = service_fn(move |request| serve_media(request, Arc::clone(&catalog)));
    let _ = http1::Builder::new()
        .timer(TokioTimer::new())
        .header_read_timeout(Duration::from_secs(8))
        .keep_alive(false)
        .max_buf_size(16 * 1024)
        .serve_connection(TokioIo::new(tls_stream), service)
        .await;
}

// Input: Stream Body and status. Output: HTTP response. Goal: Set shared playback headers. Description: Adds private no-store caching and bounded response semantics.
// body. Input: Empty response or streaming file body. Output: HTTP payload to send. Goal: Keep the response generic over both paths. Description: Boxed Hyper body.
// status. Input: Request decision. Output: Response status. Goal: Distinguish authorization and range results. Description: Assigned without a client-controlled value.
fn playback_response(body: PlaybackBody, status: StatusCode) -> Response<PlaybackBody> {
    // Input: Body and status. Output: Owned HTTP response. Goal: Attach no-store semantics. Description: Further headers are set by the successful route.
    let mut response = Response::new(body);
    *response.status_mut() = status;
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        HeaderValue::from_static("private, no-store"),
    );
    response
}

// Input: None. Output: Empty boxed Hyper body. Goal: Return metadata or errors without a payload. Description: Adapts the infallible empty body to the common I/O error type.
fn empty_body() -> PlaybackBody {
    // never. Input: Infallible error type. Output: Unreachable case. Goal: Unify body errors. Description: Empty bodies cannot fail.
    Empty::<Bytes>::new()
        .map_err(|never| match never {})
        .boxed_unsync()
}

// Input: Library root and output path list. Output: Canonical movie paths. Goal: Discover all movies on registered roots. Description: Directory links are skipped to avoid loops and leaving the root.
// root. Input: Operator-selected folder. Output: Files below that folder. Goal: Restrict catalog ownership. Description: Must exist and be a directory.
// paths. Input: Existing registered files. Output: Appended canonical movie files. Goal: Combine several roots. Description: Duplicate paths are removed later.
fn collect_movies(root: &std::path::Path, paths: &mut Vec<PathBuf>) -> io::Result<()> {
    // Input: Requested root. Output: Canonical directory. Goal: Anchor traversal. Description: A missing root is a setup error.
    let canonical_root = root.canonicalize()?;
    if !canonical_root.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "Library root must be a directory",
        ));
    }
    // Input: Root directory. Output: Pending directories. Goal: Visit nested movie folders. Description: Iterative traversal avoids call stack growth.
    let mut pending = vec![canonical_root];
    // directory. Input: Pending directories. Output: Current directory. Goal: Read its entries. Description: Directory links are not followed.
    while let Some(directory) = pending.pop() {
        // Input: Current directory. Output: Directory iterator. Goal: Discover files. Description: Unreadable subfolders are skipped.
        let Ok(entries) = std::fs::read_dir(&directory) else {
            continue;
        };
        // entry. Input: Directory iterator. Output: One filesystem child. Goal: Classify the child. Description: Failed individual entries are skipped.
        for entry in entries.flatten() {
            // Input: Child path. Output: Link metadata. Goal: Avoid following junctions and symlinks. Description: They can escape the selected root or form cycles.
            let Ok(metadata) = entry.path().symlink_metadata() else {
                continue;
            };
            if metadata.file_type().is_symlink() {
                continue;
            }
            if metadata.is_dir() {
                // Input: Directory name. Output: Hidden-workspace decision. Goal: Exclude local build and test fixtures from a movie root. Description: Dot-prefixed folders are skipped unless explicitly registered as the root.
                let hidden_workspace = entry.file_name().to_string_lossy().starts_with('.');
                if !hidden_workspace {
                    pending.push(entry.path());
                }
                continue;
            }
            if !metadata.is_file() || metadata.len() == 0 {
                continue;
            }
            // Input: Filename extension. Output: Supported-container decision. Goal: Keep nonmovie files out of the catalog. Description: Case insensitive comparison.
            let supported = entry
                .path()
                .extension()
                .and_then(std::ffi::OsStr::to_str)
                .is_some_and(|extension| {
                    ["mp4", "m4v", "mkv", "webm"]
                        .iter()
                        .any(|candidate| extension.eq_ignore_ascii_case(candidate))
                });
            if supported {
                if let Ok(path) = entry.path().canonicalize() {
                    paths.push(path);
                }
            }
        }
    }
    Ok(())
}

// Input: Arbitrary title text. Output: JSON string contents. Goal: Encode filenames safely. Description: Escapes quotes, backslashes, and control characters.
// title. Input: Filename stem. Output: Encoded text without surrounding quotes. Goal: Preserve Unicode titles. Description: JSON control escapes use four hex digits.
fn escape_json(title: &str) -> String {
    // Input: Title length. Output: Encoded string. Goal: Build a response once at startup. Description: Capacity is a hint only.
    let mut escaped = String::with_capacity(title.len());
    // character. Input: Title characters. Output: One encoded character. Goal: Produce valid JSON. Description: Normal Unicode is retained.
    for character in title.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            character if character < ' ' => {
                escaped.push_str(&format!("\\u{:04x}", character as u32))
            }
            character => escaped.push(character),
        }
    }
    escaped
}

// Input: Registered movie entries and catalog version. Output: JSON catalog bytes. Goal: Browse without requesting media. Description: IDs invalidate when the scanned assets change.
// entries. Input: Startup media snapshot. Output: One row per movie file. Goal: Include full registered libraries. Description: Duplicate titles remain separate entries.
// version. Input: Hashed catalog metadata. Output: Media ID prefix. Goal: Detect stale selections after rescan. Description: Stable when the same files are registered again.
fn catalog_json(entries: &[SharedMedia], version: u64) -> String {
    // Input: Entry list. Output: JSON array text. Goal: Return a compact metadata response. Description: No local paths or credentials leave the host.
    let mut json = String::from("{\"movies\":[");
    // index. Input: Entry order. Output: Opaque route suffix. Goal: Resolve the selected file. Description: Assigned only on this host.
    // entry. Input: Media record. Output: Title and byte length. Goal: Populate the viewer. Description: The filename stem supplies the provisional title.
    for (index, entry) in entries.iter().enumerate() {
        if index > 0 {
            json.push(',');
        }
        // Input: Filename stem. Output: Display title. Goal: Avoid exposing local folder paths. Description: Falls back to Movie when Unicode conversion fails.
        let file_stem = entry
            .path
            .file_stem()
            .and_then(std::ffi::OsStr::to_str)
            .unwrap_or("Movie");
        // Input: Generic media filename or descriptive stem. Output: Display title. Goal: Show useful library names. Description: movie.mkv takes its enclosing folder name.
        let title = if file_stem.eq_ignore_ascii_case("movie") {
            entry
                .path
                .parent()
                .and_then(std::path::Path::file_name)
                .and_then(std::ffi::OsStr::to_str)
                .unwrap_or(file_stem)
        } else {
            file_stem
        };
        json.push_str(&format!(
            "{{\"id\":\"{version}-{index}\",\"title\":\"{}\",\"bytes\":{},\"poster\":{}}}",
            escape_json(title),
            entry.length,
            entry.poster_path.is_some()
        ));
    }
    json.push_str("]}");
    json
}

// Input: HTTP request and movie registration. Output: HTTP response. Goal: Authorize every request and stream only the selected movie. Description: Resolves full, partial, and metadata-only requests.
// request. Input: Hyper request. Output: Method, target, and headers. Goal: Match and authorize the operation. Description: Request bodies are unused.
// media. Input: Startup registration. Output: Shared movie records and expected token. Goal: Prevent user-controlled path resolution. Description: Peers request opaque media IDs.
async fn serve_media(
    request: Request<Incoming>,
    catalog: Arc<SharedCatalog>,
) -> Result<Response<PlaybackBody>, Infallible> {
    // Input: Request target. Output: Catalog or media route. Goal: Reject unknown paths. Description: Media IDs include the current catalog version and index.
    let route = request.uri().path();
    // Input: Media route suffix. Output: Optional catalog index. Goal: Resolve only current registered assets. Description: IDs include the current catalog version.
    let media_index = route
        .strip_prefix("/media/")
        .or_else(|| route.strip_prefix("/poster/"))
        .and_then(|value| value.split_once('-'))
        .and_then(|(version_text, index_text)| {
            if version_text.parse::<u64>().ok() == Some(catalog.version) {
                index_text.parse::<usize>().ok()
            } else {
                None
            }
        });
    if request.uri().query().is_some()
        || (route != "/catalog"
            && media_index
                .and_then(|index| catalog.entries.get(index))
                .is_none())
    {
        return Ok(playback_response(empty_body(), StatusCode::NOT_FOUND));
    }
    // Input: Authorization field. Output: Header iterator. Goal: Reject duplicates as ambiguous. Description: A request must contain exactly one bearer credential.
    let mut authorization_fields = request.headers().get_all(header::AUTHORIZATION).iter();
    // Input: Authorization header and configured token. Output: Authentication decision. Goal: Compare the credential without early byte mismatches. Description: Constant-time for inputs of the same length.
    // credential. Input: First Authorization value. Output: Raw credential bytes. Goal: Compare the entire value. Description: Includes scheme and token.
    let authorized = authorization_fields.next().is_some_and(|credential| {
        bool::from(
            credential
                .as_bytes()
                .ct_eq(&catalog.entries[0].authorization),
        )
    }) && authorization_fields.next().is_none();
    if !authorized {
        // Input: Invalid or absent token. Output: Authentication challenge. Goal: Tell the application which authorization scheme is required. Description: The response carries no media.
        let mut response = playback_response(empty_body(), StatusCode::UNAUTHORIZED);
        response
            .headers_mut()
            .insert(header::WWW_AUTHENTICATE, HeaderValue::from_static("Bearer"));
        return Ok(response);
    }
    // Input: HTTP method. Output: Metadata-only flag. Goal: Honor standard HEAD semantics. Description: HEAD returns full metadata without media bytes.
    let is_head = request.method() == Method::HEAD;
    if !is_head && request.method() != Method::GET {
        // Input: Unsupported method. Output: Method error and Allow field. Goal: Advertise the permitted operations. Description: Only read operations are supported.
        let mut response = playback_response(empty_body(), StatusCode::METHOD_NOT_ALLOWED);
        response
            .headers_mut()
            .insert(header::ALLOW, HeaderValue::from_static("GET, HEAD"));
        return Ok(response);
    }
    if route == "/catalog" {
        // Input: Catalog snapshot. Output: JSON or empty HEAD response. Goal: Load movie names without media bytes. Description: Authenticated and private like streams.
        let body = if is_head {
            empty_body()
        } else {
            Full::new(catalog.json.clone())
                .map_err(|never| match never {})
                .boxed_unsync()
        };
        let mut response = playback_response(body, StatusCode::OK);
        response.headers_mut().insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/json; charset=utf-8"),
        );
        response.headers_mut().insert(
            header::CONTENT_LENGTH,
            HeaderValue::from(catalog.json.len()),
        );
        return Ok(response);
    }
    // Input: Validated media index. Output: Registered file. Goal: Reuse the secure byte-range path. Description: No user filesystem path is accepted.
    let media = &catalog.entries[media_index.unwrap()];
    if route.starts_with("/poster/") {
        // Input: Registered artwork path. Output: Optional bounded JPEG bytes. Goal: Send posters separately from catalog and movie streams. Description: Missing or oversized images stay blank.
        let poster_bytes = match &media.poster_path {
            Some(poster_path) => match tokio::fs::metadata(poster_path).await {
                Ok(poster_metadata) if poster_metadata.is_file() && poster_metadata.len() <= 10 * 1024 * 1024 => tokio::fs::read(poster_path).await.ok(),
                _ => None,
            },
            None => None,
        };
        let Some(poster_bytes) = poster_bytes else { return Ok(playback_response(empty_body(), StatusCode::NOT_FOUND)); };
        // Input: Image bytes. Output: JPEG response. Goal: Display existing cover art. Description: HEAD reports size without a body.
        let mut poster_response = playback_response(if is_head { empty_body() } else { Full::new(Bytes::from(poster_bytes.clone())).map_err(|never| match never {}).boxed_unsync() }, StatusCode::OK);
        poster_response.headers_mut().insert(header::CONTENT_TYPE, HeaderValue::from_static("image/jpeg"));
        poster_response.headers_mut().insert(header::CONTENT_LENGTH, HeaderValue::from(poster_bytes.len()));
        return Ok(poster_response);
    }
    // Input: The registered path. Output: Request-owned file stream. Goal: Seek and cancel independently. Description: Failed open means the source is unavailable.
    let Ok(mut file) = open_movie(&media.path).await else {
        return Ok(playback_response(
            empty_body(),
            StatusCode::SERVICE_UNAVAILABLE,
        ));
    };
    // Input: Newly opened file. Output: Current metadata. Goal: Detect unavailable or changed movies. Description: Compares the file with the registration.
    let Ok(metadata) = file.metadata().await else {
        return Ok(playback_response(
            empty_body(),
            StatusCode::SERVICE_UNAVAILABLE,
        ));
    };
    if !metadata.is_file()
        || metadata.len() != media.length
        || metadata.modified().ok() != Some(media.modified)
    {
        return Ok(playback_response(
            empty_body(),
            StatusCode::SERVICE_UNAVAILABLE,
        ));
    }

    // Input: HTTP Range fields. Output: Iterator over the values. Goal: Apply at most one range. Description: Range applies to GET only.
    let mut range_fields = request.headers().get_all(header::RANGE).iter();
    // Input: Range and If-Range fields. Output: Optional inclusive byte span. Goal: Plan the transfer. Description: The weak validator cannot satisfy If-Range, so conditional range requests receive the full representation.
    // range_header. Input: First Range field. Output: Proposed HTTP byte range. Goal: Parse the client's requested span. Description: Multiple ranges are rejected.
    let range = if is_head || request.headers().contains_key(header::IF_RANGE) {
        None
    } else if let Some(range_header) = range_fields.next() {
        // Input: Range field, fixture length, and second Range field. Output: Valid single range outcome. Goal: Reject malformed or unsatisfiable requests. Description: Duplicate fields are treated as unsupported multiple ranges.
        // range_text. Input: ASCII Range field value. Output: Text passed to the range parser. Goal: Apply a single range. Description: A non-ASCII header is rejected before parsing.
        let parsed_range = range_header
            .to_str()
            .ok()
            .and_then(|range_text| parse_range(range_text, media.length))
            .filter(|_| range_fields.next().is_none());
        if parsed_range.is_none() {
            // Input: Rejected range and sample length. Output: Unsatisfiable-range response. Goal: Advertise the current representation length. Description: No fixture bytes are sent.
            let mut response = playback_response(empty_body(), StatusCode::RANGE_NOT_SATISFIABLE);
            response.headers_mut().insert(
                header::CONTENT_RANGE,
                HeaderValue::from_str(&format!("bytes */{}", media.length)).unwrap(),
            );
            response
                .headers_mut()
                .insert(header::ACCEPT_RANGES, HeaderValue::from_static("bytes"));
            return Ok(response);
        }
        parsed_range
    } else {
        None
    };

    // start_offset. Input: Optional requested span. Output: Start byte. Goal: Position the file for streaming. Description: A complete response starts at zero.
    // response_length. Input: Optional requested span and file length. Output: Bytes to transfer. Goal: Read exactly the requested bytes. Description: Inclusive byte count, a descriptive formula, is end minus start plus one because both endpoints are sent.
    let (start_offset, response_length) = match range {
        // start. Input: First included byte. Output: File seek offset. Goal: Begin the requested span. Description: Zero-based byte position.
        // end. Input: Last included byte. Output: Inclusive span endpoint. Goal: Count bytes to transfer. Description: Already clamped to the fixture.
        Some((start, end)) => (start, end - start + 1),
        None => (0, media.length),
    };
    // Input: Method and open file. Output: Empty or streamed body. Goal: Return metadata or requested bytes. Description: Reads at most 64 KiB per chunk on demand until HTTP completes or cancels.
    let body = if is_head {
        empty_body()
    } else {
        if file.seek(io::SeekFrom::Start(start_offset)).await.is_err() {
            return Ok(playback_response(
                empty_body(),
                StatusCode::SERVICE_UNAVAILABLE,
            ));
        }
        StreamBody::new(
            ReaderStream::with_capacity(file.take(response_length), 64 * 1024).map_ok(Frame::data),
        )
        .boxed_unsync()
    };
    // Input: Presence of a range. Output: 200 or 206 status. Goal: Tell the player whether the response is partial. Description: HEAD uses the full response status.
    let status = if range.is_some() {
        StatusCode::PARTIAL_CONTENT
    } else {
        StatusCode::OK
    };
    // Input: Stream body and metadata. Output: HTTP response. Goal: Send enough information for playback and seeking. Description: Includes exact byte length and the source's weak ETag.
    let mut response = playback_response(body, status);
    // Input: HTTP response. Output: Mutable header map. Goal: Set range and playback metadata. Description: Common headers are shared by GET and HEAD.
    let headers = response.headers_mut();
    headers.insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static(media.mime_type),
    );
    headers.insert(header::ACCEPT_RANGES, HeaderValue::from_static("bytes"));
    headers.insert(header::CONTENT_LENGTH, HeaderValue::from(response_length));
    headers.insert(header::ETAG, media.etag.clone());
    // first_byte. Input: Optional parsed range. Output: Start position. Goal: Advertise the start of the partial span. Description: Inclusive zero-based byte position.
    // last_byte. Input: Optional parsed range. Output: End position. Goal: Advertise the end of the partial span. Description: Inclusive zero-based byte position.
    if let Some((first_byte, last_byte)) = range {
        headers.insert(
            header::CONTENT_RANGE,
            HeaderValue::from_str(&format!("bytes {first_byte}-{last_byte}/{}", media.length))
                .unwrap(),
        );
    }
    Ok(response)
}

// Input: HTTP Range text and sample length. Output: Satisfiable inclusive zero-based start and end. Goal: Support closed, open-ended, and suffix byte ranges. Description: Rejects malformed, multipart, reversed, and out-of-file ranges.
// range_text. Input: Incoming Range text. Output: HTTP byte range expression. Goal: Determine the requested segment. Description: Must use a single bytes range.
// file_length. Input: Fixture size. Output: Available byte count. Goal: Clamp the range. Description: The last byte index is byte count minus one because offsets start at zero.
fn parse_range(range_text: &str, file_length: u64) -> Option<(u64, u64)> {
    // Input: File length. Output: Last valid offset. Goal: Clamp and validate the span. Description: Zero-based last index, a descriptive formula, subtracts one from the count because the first offset is zero.
    let last_offset = file_length.checked_sub(1)?;
    // unit. Input: Range field. Output: Unit text. Goal: Require the bytes range unit. Description: The portion preceding the equals sign.
    // expression. Input: Range field. Output: The requested span. Goal: Separate unit from byte positions. Description: The portion after the equals sign.
    let (unit, expression) = range_text.split_once('=')?;
    if !unit.eq_ignore_ascii_case("bytes") {
        return None;
    }
    // start_text. Input: Range expression. Output: Text before the hyphen. Goal: Distinguish closed, open-ended, and suffix forms. Description: An empty first component marks a suffix.
    // end_text. Input: Range expression. Output: Text after the hyphen. Goal: Parse the end position or suffix length. Description: An empty last component marks an open-ended range.
    let (start_text, end_text) = expression.split_once('-')?;
    if start_text.is_empty() {
        // Input: Requested suffix length. Output: Positive requested byte count. Goal: Reject an empty suffix. Description: A suffix larger than the file returns the entire file.
        // count. Input: Parsed unsigned suffix length. Output: Candidate number of bytes. Goal: Reject zero-length slices. Description: Compared to zero before use.
        let suffix_length = parse_offset(end_text).filter(|count| *count > 0)?;
        // Descriptive formula: suffix start equals file length minus suffix count, saturated at zero so an oversized suffix selects the whole file.
        return Some((file_length.saturating_sub(suffix_length), last_offset));
    }
    // Input: Left side of the span. Output: First included byte. Goal: Locate the seek position. Description: Must be within the fixture.
    let start_offset = parse_offset(start_text)?;
    // Input: Right side of the span and last valid offset. Output: Last included byte. Goal: Stop at the requested or available end. Description: An omitted end means the final file byte.
    let end_offset = if end_text.is_empty() {
        last_offset
    } else {
        parse_offset(end_text)?.min(last_offset)
    };
    (start_offset <= end_offset).then_some((start_offset, end_offset))
}

// Input: Offset text. Output: Nonnegative integer or none. Goal: Enforce HTTP decimal digit syntax. Description: Rejects signs, punctuation, empty text, and numeric overflow.
// offset_text. Input: Byte offset or count. Output: ASCII digits to parse. Goal: Accept only valid byte positions. Description: A substring from one range field.
fn parse_offset(offset_text: &str) -> Option<u64> {
    if offset_text.is_empty() || !offset_text.as_bytes().iter().all(u8::is_ascii_digit) {
        return None;
    }
    offset_text.parse().ok()
}
