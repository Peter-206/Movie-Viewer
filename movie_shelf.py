"""Browse movies stored in separate folders.

Put this script beside your movie folders, or pass --root with their parent folder.
On startup and Rescan, the main video in each movie folder is renamed to movie
with its original extension. The movie title still comes from the folder name.
If there are several videos, an existing movie file is preferred; otherwise the
largest video is used. Other videos keep their names. Existing files are never
replaced. Nested videos stay in their original subfolder.
"""

import os
import argparse
import difflib
import json
import re
import sqlite3
import sys
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Optional, List

from PIL import Image, ImageTk

from movie_shelf_ui import MovieShelfPresentation

MOVIE_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm"}
IMG_EXTS = {".jpg", ".jpeg", ".png"}

# Input: The projection booth palette. Output: Main indigo background. Goal: Reduce glare around posters. Description: Colors the root surface.
NAVY_BG = "#171d2b"
# Input: The projection booth palette. Output: Panel background. Goal: Maintain consistent surfaces. Description: Matches the root.
PANEL_BG = "#171d2b"
# Input: The projection booth palette. Output: Lifted slate background. Goal: Group movie content. Description: Colors cards and input fields.
TILE_BG = "#222c3e"
# Input: The projection booth palette. Output: Hover background. Goal: Show interactive state. Description: Lifts the slate tone.
HOVER_BG = "#303e53"
# Input: The projection booth palette. Output: Primary ivory text. Goal: Keep titles readable. Description: Main foreground color.
TEXT_FG = "#f3f0e8"
# Input: The projection booth palette. Output: Secondary cool text. Goal: Separate supporting information. Description: Muted readable foreground.
MUTED_FG = "#b9c6d7"
# Input: The projection booth palette. Output: Brass action color. Goal: Identify primary actions. Description: Main accent surface.
ACCENT = "#e4bb70"
# Input: The projection booth palette. Output: Active brass color. Goal: Show action hover. Description: Lightens primary buttons.
ACCENT_HOVER = "#f0ce90"
# Input: The projection booth palette. Output: Slate border color. Goal: Delineate controls. Description: Quiet structural boundary.
SUBTLE_BORDER = "#52627a"
# Input: The projection booth palette. Output: Teal focus color. Goal: Highlight selection. Description: Signals an interactive poster.
HOVER_BORDER = "#86c9be"


THUMB_NAME = "thumb.jpg"
IMDB_SUGGEST_URL = "https://v2.sg.media-imdb.com/suggestion/x/{query}.json"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MovieShelf/1.0",
    "Accept": "application/json,image/avif,image/webp,image/jpeg,*/*",
}


def normalize_path(path: Optional[str]) -> Optional[str]:
    """Collapse repeated separators and dot segments in a filesystem path."""
    if not path:
        return path
    # Windows keeps the leading pair of slashes needed for network shares.
    return os.path.normpath(os.path.expanduser(path))


@dataclass(frozen=True)
class MovieItem:
    id: int
    title: str
    folder: str
    video_path: Optional[str]
    cover_path: Optional[str]
    thumb_path: Optional[str]
    year: Optional[int] = None
    studio: str = ""
    presentation: str = ""
    genres: tuple[str, ...] = ()
    watch_count: int = 0


class MovieCatalog:
    """Persistent metadata layered over the folders on disk."""

    def __init__(self, path: str):
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                folder_path TEXT NOT NULL UNIQUE,
                video_path TEXT,
                cover_path TEXT,
                thumb_path TEXT,
                year INTEGER,
                studio TEXT NOT NULL DEFAULT '',
                presentation TEXT NOT NULL DEFAULT ''
                    CHECK (presentation IN ('', 'Animation', 'Live action', 'Hybrid'))
            );
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE
            );
            CREATE TABLE IF NOT EXISTS movie_genres (
                movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
                PRIMARY KEY (movie_id, genre_id)
            );
            CREATE INDEX IF NOT EXISTS idx_movies_studio ON movies(studio);
            CREATE INDEX IF NOT EXISTS idx_movies_presentation ON movies(presentation);
            """
        )
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(movies)")}
        if "watch_count" not in columns:
            self.connection.execute(
                "ALTER TABLE movies ADD COLUMN watch_count INTEGER NOT NULL DEFAULT 0"
            )
        self.connection.commit()

    # Input: Movie folders found under the active library root.
    # Output: Updated paths and metadata associations in the catalog.
    # Goal: Keep edited metadata attached when the drive letter changes.
    # Description: Reuses an unambiguous historical row for each folder.
    def sync(self, scanned: List[MovieItem]) -> None:
        # Input: Existing movie rows and their genre names.
        # Output: A snapshot used to compare historical metadata.
        # Goal: Detect matching folders without relying on absolute paths.
        # Description: Reads the catalog before any path updates.
        stored_rows = self.connection.execute(
            """
            SELECT m.id, m.folder_path, m.title, m.year, m.studio,
                   m.presentation, m.watch_count,
                   COALESCE(group_concat(g.name, '|'), '')
            FROM movies m
            LEFT JOIN movie_genres mg ON mg.movie_id = m.id
            LEFT JOIN genres g ON g.id = mg.genre_id
            GROUP BY m.id
            """
        ).fetchall()
        with self.connection:
            # Input: Scanned movie folders.
            # Output: One movie to synchronize per iteration.
            # Goal: Relate the current folder to its catalog metadata.
            # Description: Processes each folder independently.
            for item in scanned:
                # Input: The scanned folder name.
                # Output: A display title and optional release year.
                # Goal: Establish the default metadata for comparison.
                # Description: Removes release tags from the folder name.
                clean_title, detected_year = movie_name_and_year(item.title)
                # Input: The scanned folder path.
                # Output: A normalized folder path.
                # Goal: Use a consistent active location.
                # Description: Normalizes separators and dot segments.
                folder = normalize_path(item.folder)
                # Input: The scanned video path.
                # Output: A normalized video path or None.
                # Goal: Keep playback pointing at the active drive.
                # Description: Normalizes the selected video's location.
                video = normalize_path(item.video_path)
                # Input: The scanned cover path.
                # Output: A normalized cover path or None.
                # Goal: Keep artwork pointing at the active drive.
                # Description: Normalizes the cover location.
                cover = normalize_path(item.cover_path)
                # Input: The scanned thumbnail path.
                # Output: A normalized thumbnail path or None.
                # Goal: Keep artwork pointing at the active drive.
                # Description: Normalizes the thumbnail location.
                thumb = normalize_path(item.thumb_path)
                # Input: The scanned folder path.
                # Output: A case-insensitive folder name.
                # Goal: Find historical entries after a drive move.
                # Description: Uses the folder name as a portable identity.
                folder_name = os.path.basename(folder).casefold()
                # Input: Historical rows and the active folder name.
                # Output: Rows with the same movie folder name.
                # Goal: Find possible metadata sources.
                # Description: Includes old absolute paths and drive-relative paths.
                matching_rows = [
                    stored_movie for stored_movie in stored_rows
                    if os.path.basename(os.path.normpath(stored_movie[1])).casefold() == folder_name
                ]
                # Input: Matching historical rows and the active path.
                # Output: The existing active row or None.
                # Goal: Preserve metadata already saved at this location.
                # Description: Compares normalized paths without case differences.
                current_row = next(
                    (stored_movie for stored_movie in matching_rows
                     if os.path.normcase(normalize_path(stored_movie[1])) == os.path.normcase(folder)),
                    None,
                )
                # Input: Defaults parsed from the current folder.
                # Output: The metadata tuple for an untouched entry.
                # Goal: Distinguish edited records from scanned defaults.
                # Description: Matches the selected fields from stored rows.
                default_metadata = (clean_title, detected_year, "", "", 0, "")
                # Input: Historical rows for this folder.
                # Output: Unique edited metadata tuples, excluding watch counts.
                # Goal: Avoid choosing between conflicting old edits.
                # Description: Watch counts may grow on different drive letters.
                edited_metadata = {
                    stored_movie[2:6] + (stored_movie[7],) for stored_movie in matching_rows
                    if stored_movie[2:6] + (stored_movie[7],)
                    != default_metadata[:4] + (default_metadata[5],)
                }
                # Input: Watch counts on historical copies of this movie.
                # Output: The largest recorded count.
                # Goal: Preserve recorded plays without double counting copies.
                # Description: A copied catalog may gain plays at another path.
                watch_count = max((stored_movie[6] for stored_movie in matching_rows), default=0)
                # Input: Historical rows and their edited metadata.
                # Output: One safe source row or None.
                # Goal: Reattach metadata only when its identity is clear.
                # Description: Prefers the oldest matching edited row when edits agree.
                source_row = None
                if len(edited_metadata) == 1:
                    source_row = min(
                        (stored_movie for stored_movie in matching_rows
                         if stored_movie[2:6] + (stored_movie[7],) in edited_metadata),
                        key=lambda stored_movie: stored_movie[0],
                    )
                elif not edited_metadata and matching_rows:
                    source_row = min(matching_rows, key=lambda stored_movie: stored_movie[0])

                if current_row is None and source_row is not None:
                    self.connection.execute(
                        """UPDATE movies SET folder_path=?, video_path=?, cover_path=?,
                                  thumb_path=?, watch_count=? WHERE id=?""",
                        (folder, video, cover, thumb, watch_count, source_row[0]),
                    )
                    continue

                if (current_row is not None
                        and current_row[2:6] + (current_row[7],)
                        == default_metadata[:4] + (default_metadata[5],)
                        and source_row is not None and source_row[0] != current_row[0]
                        and edited_metadata):
                    self.connection.execute(
                        """UPDATE movies SET title=?, year=?, studio=?, presentation=?,
                                  watch_count=? WHERE id=?""",
                        (*source_row[2:6], watch_count, current_row[0]),
                    )
                    self.connection.execute(
                        """INSERT OR IGNORE INTO movie_genres(movie_id, genre_id)
                           SELECT ?, genre_id FROM movie_genres WHERE movie_id=?""",
                        (current_row[0], source_row[0]),
                    )
                elif current_row is not None and current_row[6] < watch_count:
                    self.connection.execute(
                        "UPDATE movies SET watch_count=? WHERE id=?",
                        (watch_count, current_row[0]),
                    )
                self.connection.execute(
                    """
                    INSERT INTO movies
                        (title, folder_path, video_path, cover_path, thumb_path, year)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(folder_path) DO UPDATE SET
                        video_path=excluded.video_path,
                        cover_path=excluded.cover_path,
                        thumb_path=excluded.thumb_path
                    """,
                    (clean_title, folder, video, cover, thumb, detected_year),
                )

    def load(self, root_dir: Optional[str] = None) -> List[MovieItem]:
        rows = self.connection.execute(
            """
            SELECT m.id, m.title, m.folder_path, m.video_path, m.cover_path,
                   m.thumb_path, m.year, m.studio, m.presentation,
                   COALESCE(group_concat(g.name, '|'), ''), m.watch_count
            FROM movies m
            LEFT JOIN movie_genres mg ON mg.movie_id = m.id
            LEFT JOIN genres g ON g.id = mg.genre_id
            GROUP BY m.id
            """
        ).fetchall()
        root = os.path.normcase(os.path.abspath(normalize_path(root_dir))) if root_dir else None

        def belongs_to_root(folder: str) -> bool:
            if not os.path.isdir(folder):
                return False
            if root is None:
                return True
            try:
                return os.path.commonpath(
                    (root, os.path.normcase(os.path.abspath(folder)))
                ) == root
            except (OSError, ValueError):
                # Different Windows drives cannot be compared with commonpath.
                return False

        return [
            MovieItem(
                id=row[0], title=row[1], folder=normalize_path(row[2]),
                video_path=normalize_path(row[3]), cover_path=normalize_path(row[4]),
                thumb_path=normalize_path(row[5]), year=row[6], studio=row[7],
                presentation=row[8], genres=tuple(filter(None, row[9].split("|"))),
                watch_count=row[10],
            )
            for row in rows
            if belongs_to_root(normalize_path(row[2]))
        ]

    def save_metadata(self, movie_id: int, title: str, year: Optional[int],
                      studio: str, presentation: str, genres: List[str]) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE movies SET title=?, year=?, studio=?, presentation=? WHERE id=?",
                (title, year, studio, presentation, movie_id),
            )
            self.connection.execute("DELETE FROM movie_genres WHERE movie_id=?", (movie_id,))
            for genre in sorted({g.strip() for g in genres if g.strip()}, key=str.casefold):
                self.connection.execute("INSERT OR IGNORE INTO genres(name) VALUES (?)", (genre,))
                genre_id = self.connection.execute(
                    "SELECT id FROM genres WHERE name=? COLLATE NOCASE", (genre,)
                ).fetchone()[0]
                self.connection.execute(
                    "INSERT INTO movie_genres(movie_id, genre_id) VALUES (?, ?)",
                    (movie_id, genre_id),
                )

    def increment_watch_count(self, movie_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE movies SET watch_count = watch_count + 1 WHERE id=?", (movie_id,)
            )

    def update_video_path(self, movie_id: int, video_path: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE movies SET video_path=? WHERE id=?", (video_path, movie_id)
            )

    def choices(self, column: str) -> List[str]:
        if column == "genre":
            rows = self.connection.execute("SELECT name FROM genres ORDER BY name COLLATE NOCASE")
        elif column in {"studio", "presentation"}:
            rows = self.connection.execute(
                f"SELECT DISTINCT {column} FROM movies WHERE {column} <> '' ORDER BY {column} COLLATE NOCASE"
            )
        else:
            raise ValueError(f"Unsupported choice column: {column}")
        return [row[0] for row in rows]

    def close(self) -> None:
        self.connection.close()


def find_cover(folder: str) -> Optional[str]:
    # Prefer canonical names first
    for name in ("cover.jpg", "cover.jpeg", "cover.png"):
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            return p

    # Then any cover*.{jpg,jpeg,png}
    try:
        for fn in os.listdir(folder):
            low = fn.lower()
            if low.startswith("cover") and os.path.splitext(low)[1] in IMG_EXTS:
                return os.path.join(folder, fn)
    except OSError:
        return None

    return None


def find_video(folder: str) -> Optional[str]:
    """Find the main video inside this movie's folder only."""
    candidates = []
    folder = os.path.abspath(normalize_path(folder))
    for current, dirs, files in os.walk(folder):
        # Do not follow links into a different movie or another disk.
        dirs[:] = sorted(name for name in dirs
                         if not name.startswith((".", "__"))
                         and not os.path.islink(os.path.join(current, name)))
        for name in sorted(files):
            stem, extension = os.path.splitext(name)
            if extension.lower() not in MOVIE_EXTS:
                continue
            path = os.path.normpath(os.path.join(current, name))
            if os.path.islink(path):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            # A movie file takes priority over trailers and other bonus videos.
            named_movie = stem.casefold() == "movie"
            priority = 2 if named_movie and current == folder else int(named_movie)
            candidates.append((priority, size, path))
    return max(candidates)[2] if candidates else None


def rename_main_video(folder: str) -> Optional[str]:
    """Rename the main video to movie.ext and return its actual path."""
    source = find_video(folder)
    if source is None:
        return None

    # Keep the exact original extension, including its letter case.
    extension = os.path.splitext(source)[1]
    destination = os.path.join(os.path.dirname(source), "movie" + extension)
    if source == destination:
        return source

    if os.path.lexists(destination):
        # On Windows, Movie.mp4 and movie.mp4 can refer to the same file.
        # Rename that file too so its displayed name matches the convention.
        if os.path.samefile(source, destination):
            os.rename(source, destination)
            return destination
        raise FileExistsError(f"Cannot rename {source}: {destination} already exists.")

    os.rename(source, destination)
    print(f"Renamed: {source} -> {destination}")
    return destination


def ensure_thumb(folder: str, cover_path: Optional[str], thumb_size: tuple[int, int]) -> Optional[str]:
    """
    Create thumb.jpg once per folder if possible; return its path if it exists/created.
    """
    thumb_path = os.path.join(folder, THUMB_NAME)
    if os.path.isfile(thumb_path):
        return thumb_path

    if not cover_path or not os.path.isfile(cover_path):
        return None

    try:
        im = Image.open(cover_path)
        im.thumbnail(thumb_size)
        im.save(thumb_path, format="JPEG", quality=85, optimize=True, progressive=True)
        return thumb_path
    except Exception:
        return None


def scan_movies(root_dir: str, thumb_size: tuple[int, int], build_thumbs: bool = False) -> List[MovieItem]:
    root_dir = os.path.abspath(normalize_path(root_dir))
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"Not a directory: {root_dir}")

    items: List[MovieItem] = []
    for name in sorted(os.listdir(root_dir), key=str.lower):
        if name.startswith((".", "__")):
            continue
        folder = os.path.join(root_dir, name)
        if not os.path.isdir(folder) or os.path.islink(folder):
            continue

        # Renaming happens before saving the paths in movies.db.
        # Running another scan is safe: movie.ext already has the right name.
        video_path = rename_main_video(folder)

        cover = find_cover(folder)
        thumb = os.path.join(folder, THUMB_NAME)
        thumb_path = thumb if os.path.isfile(thumb) else None

        if build_thumbs and not thumb_path:
            thumb_path = ensure_thumb(folder, cover, thumb_size)

        items.append(
            MovieItem(
                id=0,
                title=name,
                folder=folder,
                video_path=video_path,
                cover_path=cover,
                thumb_path=thumb_path,
            )
        )

    return items


def build_thumbnails(root_dir: str, thumb_size: tuple[int, int]) -> int:
    count = 0
    for name in os.listdir(root_dir):
        if name.startswith((".", "__")):
            continue
        folder = os.path.join(root_dir, name)
        if not os.path.isdir(folder):
            continue

        thumb_path = os.path.join(folder, THUMB_NAME)
        if os.path.isfile(thumb_path):
            continue

        cover = find_cover(folder)
        if not cover:
            continue

        created = ensure_thumb(folder, cover, thumb_size)
        if created:
            count += 1

    return count


# Input: A movie folder or saved title.
# Output: A readable title and an optional release year.
# Goal: Remove release tags while retaining numbers in movie titles.
# Description: Uses a trailing year as metadata only when a title precedes it.
# Parameter folder_name. Input: Text. Output: Source title. Goal: Parse movie names. Description: The original folder or title.
def movie_name_and_year(folder_name: str) -> tuple[str, Optional[int]]:
    """Turn common release-folder names into an IMDb search title and optional year."""
    # Input: Original text. Output: Title text. Goal: Remove release prefixes. Description: Strips a leading distributor URL and release separators.
    name = re.sub(r"^www\.[^\s]+\s*-\s*", "", folder_name, flags=re.I)
    name = re.sub(r"[._]+", " ", name).strip()
    # Input: Normalized text. Output: Trailing year match. Goal: Preserve titles like 1917 and 2001. Description: Requires nonempty title text before a release year.
    release_year = next(reversed(list(re.finditer(r"(?<=\S)\s+\(?((?:19|20)\d{2})\)?(?=\s|$|\[)", name))), None)
    # Input: Year match. Output: Optional integer year. Goal: Store release metadata separately. Description: Title numbers alone are not release years.
    year = int(release_year.group(1)) if release_year else None
    if release_year:
        name = name[:release_year.start()]

    # Remove common release metadata when there is no year to act as a boundary.
    name = re.split(
        r"\b(?:2160p|1080p|720p|480p|bluray|blu-ray|brrip|webrip|web-dl|dvdrip|x26[45]|hevc)\b|\[[^\]]*\]",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    name = re.sub(r"\s+", " ", name).strip(" -()[]")
    return name or folder_name, year


def _normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def find_imdb_poster(folder_name: str, timeout: int = 15) -> Optional[tuple[str, str]]:
    """Return (IMDb id, primary poster URL) for a confident movie-title match."""
    title, wanted_year = movie_name_and_year(folder_name)
    query = urllib.parse.quote(title.lower())
    request = urllib.request.Request(IMDB_SUGGEST_URL.format(query=query), headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

    wanted = _normalized_title(title)
    best: Optional[tuple[float, dict]] = None
    for result in payload.get("d", []):
        imdb_id = result.get("id", "")
        result_title = result.get("l", "")
        poster = result.get("i", {}).get("imageUrl")
        result_type = str(result.get("qid", "")).lower()
        if not imdb_id.startswith("tt") or not result_title or not poster:
            continue
        if result_type and result_type not in {"movie", "tvshort", "tv movie"}:
            continue

        similarity = difflib.SequenceMatcher(None, wanted, _normalized_title(result_title)).ratio()
        result_year = result.get("y")
        if wanted_year and result_year:
            if abs(int(result_year) - wanted_year) > 1:
                continue
            similarity += 0.08 if int(result_year) == wanted_year else 0.03
        if best is None or similarity > best[0]:
            best = (similarity, result)

    if best is None or best[0] < (0.90 if wanted_year else 0.94):
        return None

    result = best[1]
    poster_url = result["i"]["imageUrl"]
    # Strip IMDb's thumbnail/crop instructions while retaining the stable image id.
    poster_url = re.sub(r"\._V1_.*?(?=\.(?:jpg|jpeg|png)(?:\?|$))", "._V1_", poster_url, flags=re.I)
    return result["id"], poster_url


def fetch_missing_covers(root_dir: str, timeout: int = 20) -> tuple[int, int, int]:
    """Download IMDb primary posters only for movie folders lacking a cover."""
    downloaded = skipped = failed = 0
    for folder_name in sorted(os.listdir(root_dir), key=str.lower):
        if folder_name.startswith((".", "__")):
            continue
        folder = os.path.join(root_dir, folder_name)
        if not os.path.isdir(folder):
            continue
        if find_cover(folder):
            skipped += 1
            continue

        destination = os.path.join(folder, "cover.jpg")
        temporary = destination + ".download"
        try:
            match = find_imdb_poster(folder_name, timeout=timeout)
            if not match:
                print(f"NO MATCH  {folder_name}")
                failed += 1
                continue
            imdb_id, poster_url = match
            request = urllib.request.Request(poster_url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response, open(temporary, "wb") as output:
                output.write(response.read())

            # Reject HTML error pages and corrupt/tiny images before installing the cover.
            with Image.open(temporary) as image:
                image.verify()
            with Image.open(temporary) as image:
                width, height = image.size
            if width < 500 or height < 700:
                raise ValueError(f"poster was unexpectedly small ({width}x{height})")
            os.replace(temporary, destination)
            downloaded += 1
            print(f"SAVED     {folder_name} <- https://www.imdb.com/title/{imdb_id}/ ({width}x{height})")
        except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
            failed += 1
            print(f"FAILED    {folder_name}: {exc}")
            try:
                if os.path.isfile(temporary):
                    os.remove(temporary)
            except OSError:
                pass
    return downloaded, skipped, failed


class MovieShelfController(tk.Tk):
    def __init__(
        self,
        root_dir: str,
        cols: int = 3,
        rows: int = 6,
        thumb_w: int = 260,
        thumb_h: int = 380,
        build_thumbs_on_scan: bool = False,
    ):
        super().__init__()
        self.configure(bg=NAVY_BG)

        style = ttk.Style(self)
        # Pick a theme that respects styling a bit more consistently
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=NAVY_BG)
        style.configure("TLabel", background=NAVY_BG, foreground=TEXT_FG)
        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("Tile.TFrame", background=TILE_BG)
        style.configure("TileHover.TFrame", background=HOVER_BG)
        style.configure("Status.TLabel", foreground=MUTED_FG, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=TILE_BG, foreground=TEXT_FG, font=("Segoe UI Semibold", 12))
        style.configure("TitleHover.TLabel", background=HOVER_BG, foreground=TEXT_FG, font=("Segoe UI Semibold", 12))
        style.configure("Meta.TLabel", background=TILE_BG, foreground=MUTED_FG, font=("Segoe UI", 9))
        style.configure("MetaHover.TLabel", background=HOVER_BG, foreground=TEXT_FG, font=("Segoe UI", 9))
        style.configure("HeroTitle.TLabel", foreground=TEXT_FG, font=("Segoe UI Semibold", 34))
        style.configure("Eyebrow.TLabel", foreground=ACCENT, font=("Segoe UI Semibold", 10))
        style.configure("Body.TLabel", foreground=TEXT_FG, font=("Segoe UI", 12))
        style.configure("FeatureTitle.TLabel", background=TILE_BG, foreground=TEXT_FG,
                        font=("Segoe UI Semibold", 34))
        style.configure("FeatureEyebrow.TLabel", background=TILE_BG, foreground=SUBTLE_BORDER,
                        font=("Segoe UI Semibold", 10))
        style.configure("FeatureBody.TLabel", background=TILE_BG, foreground=TEXT_FG,
                        font=("Segoe UI", 12))
        style.configure("RowNav.TButton", background=TILE_BG, foreground=TEXT_FG,
                        borderwidth=0, font=("Segoe UI Semibold", 10), padding=(9, 5))
        style.map("RowNav.TButton", background=[("active", HOVER_BG), ("disabled", TILE_BG)],
                  foreground=[("disabled", MUTED_FG)])
        style.configure("TButton", background=SUBTLE_BORDER, foreground=NAVY_BG, borderwidth=0,
                        font=("Segoe UI Semibold", 10), padding=(14, 9))
        style.map("TButton", background=[("active", TEXT_FG), ("disabled", TILE_BG)])
        style.configure("Accent.TButton", background=ACCENT, foreground=TEXT_FG, padding=(20, 11))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", TILE_BG)])
        style.configure("TEntry", fieldbackground=TILE_BG, foreground=TEXT_FG, insertcolor=TEXT_FG,
                        bordercolor=SUBTLE_BORDER, padding=8)
        style.configure("Search.TEntry", fieldbackground=TILE_BG, foreground=TEXT_FG,
                        insertcolor=TEXT_FG, bordercolor=SUBTLE_BORDER,
                        font=("Segoe UI", 16), padding=(14, 12))
        style.configure("TCombobox", fieldbackground=TILE_BG, background=TILE_BG,
                        foreground=TEXT_FG, arrowcolor=MUTED_FG, bordercolor=SUBTLE_BORDER, padding=6)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", TILE_BG)],
            background=[("readonly", TILE_BG), ("active", HOVER_BG)],
            foreground=[("readonly", TEXT_FG)],
            arrowcolor=[("readonly", TEXT_FG)],
        )
        # The popup is a native Tk listbox. Only set its basic colors; selection
        # and focus remain under Tk's control so mouse and keyboard input work.
        self.option_add("*TCombobox*Listbox.background", TILE_BG)
        self.option_add("*TCombobox*Listbox.foreground", TEXT_FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT_FG)

        self.title("Movie Library")
        self.minsize(980, 680)

        self.root_dir = os.path.abspath(normalize_path(root_dir))
        # Input: Screen dimensions and requested grid size.
        # Output: A column count that fits the display.
        # Goal: Keep library pages inside the visible window.
        # Description: Reserves room for card spacing and the window border.
        self.cols = min(cols, max(2, (self.winfo_screenwidth() - 100) // 170))
        # Input: Requested row count and available screen height.
        # Output: A row count that fits the display.
        # Goal: Avoid a clipped second or third row.
        # Description: Uses the usable height after navigation and filters.
        self.rows = min(rows, max(1, (self.winfo_screenheight() - 330) // 260))
        # Input: Visible rows and columns.
        # Output: The number of titles per library page.
        # Goal: Keep paging consistent with the rendered grid.
        # Description: Uses the screen-sized grid capacity.
        self.page_size = self.cols * self.rows
        # Input: Requested art size and available card space.
        # Output: Thumbnail dimensions in pixels.
        # Goal: Fit posters without clipping page controls.
        # Description: Caps art to the grid's screen-sized cells.
        self.thumb_size = (min(thumb_w, max(110, (self.winfo_screenwidth() - 120) // self.cols - 24)),
                           min(thumb_h, max(150, (self.winfo_screenheight() - 330) // self.rows - 58)))

        self.catalog = MovieCatalog(os.path.join(self.root_dir, "movies.db"))
        scanned = scan_movies(self.root_dir, self.thumb_size, build_thumbs=build_thumbs_on_scan)
        self.catalog.sync(scanned)
        self.all_items = self.catalog.load(self.root_dir)
        self.filtered = list(self.all_items)

        self.page = 0
        self.thumb_cache: dict[str, ImageTk.PhotoImage] = {}
        self.detail_image: Optional[ImageTk.PhotoImage] = None
        self.loading_job: Optional[str] = None

        self.placeholder = ImageTk.PhotoImage(Image.new("RGB", self.thumb_size, TILE_BG))

        self._build_modern_ui()
        self._build_home_ui()
        self._render_page()
        self._show_home()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._bind_shortcuts()

    # Input: The main application window.
    # Output: Keyboard bindings on this window and its descendants.
    # Goal: Make common navigation available without a mouse.
    # Description: Routes keys through one dispatcher with input-field protection.
    def _bind_shortcuts(self):
        # Input: Supported Tk key sequences.
        # Output: One sequence per iteration.
        # Goal: Register consistent shortcuts.
        # Description: Native Tab, Shift+Tab, Return, and Alt+F4 remain available.
        for sequence in ("<F11>", "<Alt-Return>", "<Escape>", "<F1>", "<Control-f>",
                         "<Control-l>", "<Control-r>", "<F5>", "<Alt-Left>", "<Alt-Home>",
                         "<Control-b>", "<Left>", "<Right>", "<Up>", "<Down>",
                         "<Prior>", "<Next>", "<Home>", "<End>", "<space>", "<Return>"):
            self.bind(sequence, self._keyboard_action)

    # Input: event supplies the pressed key, modifiers, and focused widget.
    # Output: A navigation action or normal native key handling.
    # Goal: Support familiar shortcuts without interfering with text editing.
    # Description: Global actions run first. Navigation skips input fields and popups.
    # Parameter event. Input: Tk key event. Output: Action selection. Goal: Read key. Description: Includes keysym and state.
    def _keyboard_action(self, event):
        if self.grab_current() is not None:
            return
        # Input: Tk key symbol.
        # Output: Normalized key name.
        # Goal: Match shortcut names consistently.
        # Description: Lowercases letters and special key names.
        key = event.keysym.lower()
        if key == "f11" or (key == "return" and event.state & 0x20000):
            self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        elif key == "escape":
            if self.attributes("-fullscreen"):
                self.attributes("-fullscreen", False)
            elif self.detail_view.winfo_ismapped():
                self._show_browser()
            elif self.browser_view.winfo_ismapped():
                self._show_home()
            else:
                self.focus_set()
        elif key == "f1":
            self._shortcut_help()
        elif event.state & 0x4 and key in ("f", "l"):
            if self.detail_view.winfo_ismapped():
                self._open_library()
            if self.home_view.winfo_ismapped():
                self.home_search_entry.focus_set()
                self.home_search_entry.selection_range(0, "end")
            else:
                self.library_search_entry.focus_set()
                self.library_search_entry.selection_range(0, "end")
        elif key == "f5" or (event.state & 0x4 and key == "r"):
            self._rescan()
        elif event.state & 0x4 and key == "b":
            self._open_library()
        elif event.state & 0x20000 and key == "home":
            self._show_home()
        elif event.state & 0x20000 and key == "left":
            self._show_browser() if self.detail_view.winfo_ismapped() else self._show_home()
        elif key == "return" and isinstance(event.widget, ttk.Button):
            event.widget.invoke()
        elif isinstance(event.widget, (ttk.Entry, tk.Entry, ttk.Combobox, tk.Text, ttk.Spinbox)):
            return
        elif self.browser_view.winfo_ismapped():
            if key in ("left", "prior"):
                self._prev_page()
            elif key in ("right", "next"):
                self._next_page()
            elif key in ("home", "end"):
                self.page = 0 if key == "home" else self._max_page()
                self._render_page()
            else:
                return
        elif self.home_view.winfo_ismapped():
            if key in ("left", "right"):
                self._rotate_feature(-1 if key == "left" else 1)
            elif key in ("up", "down", "prior", "next"):
                self.home_canvas.yview_scroll(-1 if key in ("up", "prior") else 1,
                                             "pages" if key in ("prior", "next") else "units")
            elif key in ("home", "end"):
                self.home_canvas.yview_moveto(0 if key == "home" else 1)
            else:
                return
        elif self.detail_view.winfo_ismapped() and key == "space" and not isinstance(event.widget, ttk.Button):
            self.detail_play.invoke()
        else:
            return
        return "break"

    # Input: Main window.
    # Output: A dismissible keyboard reference dialog.
    # Goal: Make shortcuts discoverable from F1 and the visible help button.
    # Description: Describes the view-specific keys and standard native controls.
    def _shortcut_help(self):
        messagebox.showinfo("Keyboard shortcuts",
            "F11 or Alt+Enter    Toggle fullscreen\n"
            "Esc    Exit fullscreen, go back, or leave search\n"
            "Ctrl+F or Ctrl+L    Focus search\n"
            "Ctrl+B    Browse the library\n"
            "Alt+Home    Open Discover\n"
            "Alt+Left    Go back\n"
            "F5 or Ctrl+R    Rescan library\n\n"
            "Library\nLeft / Right or Page Up / Page Down    Previous / next page\n"
            "Home / End    First / last page\n\n"
            "Discover\nUp / Down    Scroll\nPage Up / Page Down    Scroll one screen\n"
            "Home / End    Top / bottom\nLeft / Right    Previous / next recommendation\n\n"
            "Movie details\nSpace    Play movie\n\n"
            "Tab / Shift+Tab    Move between controls\nEnter or Space    Activate focused button\n"
            "Enter in search    Search library\nAlt+F4    Close window\nF1    Show this guide",
            parent=self)

    # Input: The active window and any pending thumbnail load callback.
    # Output: A closed catalog and destroyed window.
    # Goal: Exit without leaving a scheduled callback against a destroyed widget.
    # Description: Cancels lazy loading before closing the database and Tk window.
    def _close(self):
        if self.loading_job is not None:
            self.after_cancel(self.loading_job)
            self.loading_job = None
        self.catalog.close()
        self.destroy()

    def _build_modern_ui(self):
        self.browser_view = ttk.Frame(self)
        self.browser_view.pack(fill="both", expand=True)

        header = ttk.Frame(self.browser_view, padding=(26, 18, 26, 12))
        header.pack(fill="x")

        left_group = ttk.Frame(header)
        left_group.grid(row=0, column=0, sticky="w")
        ttk.Button(left_group, text="← Discover", command=self._show_home).pack(anchor="w")
        ttk.Label(left_group, text="THE LIBRARY",
                  font=("Segoe UI Semibold", 24)).pack(anchor="w", pady=(0, 10))

        filters = ttk.Frame(left_group)
        filters.pack(anchor="w")
        self.genre_var = tk.StringVar(value="All genres")
        self.studio_var = tk.StringVar(value="All studios")
        self.presentation_var = tk.StringVar(value="All types")
        self.sort_var = tk.StringVar(value="Title (A-Z)")
        ttk.Label(filters, text="Genre", style="Status.TLabel").pack(side="left", padx=(0, 5))
        self.genre_combo = ttk.Combobox(filters, textvariable=self.genre_var, state="readonly", width=16)
        self.genre_combo.pack(side="left", padx=(0, 14))
        ttk.Label(filters, text="Studio", style="Status.TLabel").pack(side="left", padx=(0, 5))
        self.studio_combo = ttk.Combobox(filters, textvariable=self.studio_var, state="readonly", width=16)
        self.studio_combo.pack(side="left", padx=(0, 14))
        ttk.Label(filters, text="Type", style="Status.TLabel").pack(side="left", padx=(0, 5))
        self.presentation_combo = ttk.Combobox(filters, textvariable=self.presentation_var, state="readonly", width=13)
        self.presentation_combo.pack(side="left")

        self.search_var = tk.StringVar()
        search_group = ttk.Frame(header)
        search_group.grid(row=0, column=1, padx=30)
        ttk.Label(search_group, text="Search library", foreground=MUTED_FG,
                  font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(0, 6))
        search = ttk.Entry(search_group, textvariable=self.search_var, width=42,
                           style="Search.TEntry")
        search.pack()
        # Input: Library search widget. Output: Entry reference. Goal: Focus search by shortcut. Description: Retains the existing control.
        self.library_search_entry = search
        search.bind("<KeyRelease>", lambda _e: self._apply_filter())

        right_group = ttk.Frame(header)
        right_group.grid(row=0, column=2, sticky="e")
        ttk.Button(right_group, text="Rescan library", command=self._rescan).pack(anchor="e", pady=(0, 16))
        sort_row = ttk.Frame(right_group)
        sort_row.pack(anchor="e")
        self.sort_combo = ttk.Combobox(
            sort_row, textvariable=self.sort_var, state="readonly", width=15,
            values=("Title (A-Z)", "Title (Z-A)", "Year (newest)", "Year (oldest)",
                    "Most watched", "Least watched"),
        )
        self.sort_combo.pack(side="right")
        ttk.Label(sort_row, text="Sort by", foreground=MUTED_FG).pack(side="right", padx=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=1)
        for combo in (self.genre_combo, self.studio_combo, self.presentation_combo, self.sort_combo):
            combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        self._refresh_filter_choices()

        summary = ttk.Frame(self.browser_view, padding=(26, 0, 26, 2))
        summary.pack(fill="x")
        self.status = ttk.Label(summary, anchor="w", style="Status.TLabel")
        self.status.pack(side="left")
        self.page_label = ttk.Label(summary, style="Status.TLabel")
        self.page_label.pack(side="right")

        self.grid = ttk.Frame(self.browser_view, padding=(20, 5, 20, 5))
        self.grid.pack(fill="both", expand=True)
        self.slots: list[tuple[tk.Label, ttk.Label, ttk.Label]] = []
        for row in range(self.rows):
            for column in range(self.cols):
                card = ttk.Frame(self.grid, padding=7, style="Tile.TFrame", cursor="hand2")
                card.grid(row=row, column=column, padx=7, pady=7, sticky="nsew")
                poster = tk.Label(card, image=self.placeholder, cursor="hand2", bd=0, bg=TILE_BG,
                                  highlightthickness=0)
                poster.grid(row=0, column=0, sticky="nsew")
                title = ttk.Label(card, wraplength=self.thumb_size[0], justify="center",
                                  cursor="hand2", style="Title.TLabel")
                title.grid(row=1, column=0, sticky="ew", pady=(8, 0))
                meta = ttk.Label(card, anchor="center", cursor="hand2", style="Meta.TLabel")
                meta.grid(row=2, column=0, sticky="ew", pady=(3, 2))
                card.grid_columnconfigure(0, weight=1)
                card.grid_rowconfigure(0, weight=1)
                self.slots.append((poster, title, meta))

                def enter(_e, c=card, p=poster, t=title, m=meta):
                    c.configure(style="TileHover.TFrame")
                    t.configure(style="TitleHover.TLabel")
                    m.configure(style="MetaHover.TLabel")
                    self._apply_hover(c, p, True)

                def leave(_e, c=card, p=poster, t=title, m=meta):
                    c.configure(style="Tile.TFrame")
                    t.configure(style="Title.TLabel")
                    m.configure(style="Meta.TLabel")
                    self._apply_hover(c, p, False)

                for widget in (card, poster, title, meta):
                    widget.bind("<Enter>", enter)
                    widget.bind("<Leave>", leave)
        for column in range(self.cols):
            self.grid.grid_columnconfigure(column, weight=1, uniform="gridcol")
        for row in range(self.rows):
            self.grid.grid_rowconfigure(row, weight=1, uniform="gridrow")

        nav = ttk.Frame(self.browser_view, padding=(26, 7, 26, 18))
        nav.pack(fill="x")
        self.prev_btn = ttk.Button(nav, text="Previous", command=self._prev_page)
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(nav, text="Next", command=self._next_page)
        self.next_btn.pack(side="right")

        self.detail_view = ttk.Frame(self)
        self._build_detail_view()

    # Input: Active movies and their recorded watch counts.
    # Output: Five recommended movies.
    # Goal: Feature unwatched titles related to viewing history.
    # Description: Scores genre overlap using recorded plays and fills empty history with library titles.
    def _featured_movies(self):
        # Input: Watched titles in the active library.
        # Output: A score for each watched genre.
        # Goal: Represent the viewer's genre interests.
        # Description: The weighted genre frequency formula sums watch counts for each genre because repeat plays indicate stronger interest.
        genre_scores = {}
        # Input: Active library titles.
        # Output: One title per iteration.
        # Goal: Build genre scores from actual watches.
        # Description: Ignores unwatched titles while measuring preferences.
        for movie in self.all_items:
            if movie.watch_count:
                # Input: Genres on the current watched title.
                # Output: One genre per iteration.
                # Goal: Credit each matching genre.
                # Description: Adds this title's play count to each genre score.
                for genre in movie.genres:
                    genre_scores[genre] = genre_scores.get(genre, 0) + movie.watch_count
        # Input: Active titles and watched genre scores.
        # Output: Five ranked titles.
        # Goal: Prioritize fresh titles that match viewing history.
        # Description: The genre overlap score sums the watched genre frequencies on each unwatched movie.
        recommended = sorted(self.all_items, key=lambda movie: (
            movie.watch_count > 0,
            -sum(genre_scores.get(genre, 0) for genre in movie.genres),
            movie.title.casefold(),
        ))
        return recommended[:5]

    # Input: The current catalog and window.
    # Output: A scrollable discovery screen.
    # Goal: Present featured, popular, and genre collections.
    # Description: Builds a compact dashboard with direct routes to the searchable library.
    def _build_home_ui(self):
        self.home_view = ttk.Frame(self)
        self.home_view.pack(fill="both", expand=True)
        top = ttk.Frame(self.home_view, padding=(32, 18))
        top.pack(fill="x")
        ttk.Label(top, text="FRAME", font=("Segoe UI Semibold", 24)).pack(side="left")
        ttk.Button(top, text="Keys · F1", command=self._shortcut_help).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Browse all  →", command=self._open_library).pack(side="right")
        ttk.Button(top, text="Rescan", command=self._rescan).pack(side="right", padx=10)
        self.home_search = tk.StringVar()
        search = ttk.Entry(top, textvariable=self.home_search, width=26, style="Search.TEntry")
        search.pack(side="right", padx=10)
        # Input: Home search widget. Output: Entry reference. Goal: Focus search by shortcut. Description: Retains the existing control.
        self.home_search_entry = search
        search.insert(0, "Search movies")
        search.bind("<FocusIn>", lambda event: search.delete(0, "end") if search.get() == "Search movies" else None)
        search.bind("<Return>", self._search_from_home)
        self.home_canvas = tk.Canvas(self.home_view, bg=NAVY_BG, highlightthickness=0, yscrollincrement=24)
        scrollbar = ttk.Scrollbar(self.home_view, orient="vertical", command=self.home_canvas.yview)
        self.home_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.home_canvas.pack(fill="both", expand=True)
        self.home_content = ttk.Frame(self.home_canvas, padding=(32, 4, 32, 32))
        self.home_window = self.home_canvas.create_window((0, 0), window=self.home_content, anchor="nw")
        self.home_content.bind("<Configure>", lambda event: self.home_canvas.configure(scrollregion=self.home_canvas.bbox("all")))
        self.home_canvas.bind("<Configure>", lambda event: self.home_canvas.itemconfigure(self.home_window, width=event.width))
        self.bind("<MouseWheel>", self._scroll_home, add="+")
        self.feature_index = 0
        self.home_images = []
        self._refresh_home()
        self._schedule_feature()

    # Input: event contains the wheel delta and originating widget.
    # Output: The discovery canvas moves, or the event continues normally.
    # Goal: Scroll when the pointer is over cards, labels, or the canvas.
    # Description: Toplevel bindings receive descendant events. Restricts handling
    # to canvas descendants and preserves partial touchpad deltas between events.
    # Parameter event. Input: Tk wheel event. Output: Scroll input. Goal: Read motion. Description: Supplies widget and delta.
    def _scroll_home(self, event):
        if not self.home_view.winfo_ismapped():
            return
        if str(event.widget) != str(self.home_canvas) and not str(event.widget).startswith(str(self.home_canvas) + "."):
            return
        # Input: Previous wheel remainder and current Windows wheel delta.
        # Output: Accumulated wheel motion.
        # Goal: Support high resolution wheels without losing small events.
        # Description: Retains deltas smaller than one native wheel step.
        self.home_wheel_delta = getattr(self, "home_wheel_delta", 0) + event.delta
        # Input: Accumulated wheel motion.
        # Output: Signed count of complete wheel steps.
        # Goal: Move in predictable 24 pixel units.
        # Description: Native wheel step conversion divides by 120 delta units per step.
        steps = int(self.home_wheel_delta / 120)
        if steps:
            self.home_canvas.yview_scroll(-steps, "units")
            self.home_wheel_delta -= steps * 120
        return "break"

    # Input: Home search text.
    # Output: Filtered library view.
    # Goal: Make search available from the first screen.
    # Description: Transfers the entered query into the existing search and paging flow.
    def _search_from_home(self, _event=None):
        self.search_var.set("" if self.home_search.get() == "Search movies" else self.home_search.get())
        self._apply_filter()
        self._open_library()

    # Input: Current navigation state.
    # Output: The library screen.
    # Goal: Expose all existing filters and proper paging.
    # Description: Hides discovery and opens the searchable grid.
    def _open_library(self):
        self.home_view.pack_forget()
        self.detail_view.pack_forget()
        self.browser_view.pack(fill="both", expand=True)

    # Input: Current navigation state.
    # Output: The discovery screen.
    # Goal: Restore the main screen.
    # Description: Hides details and library while preserving their state.
    def _show_home(self):
        self.browser_view.pack_forget()
        self.detail_view.pack_forget()
        self.home_view.pack(fill="both", expand=True)

    # Input: A movie and card parent.
    # Output: A clickable poster card.
    # Goal: Give every row a consistent visual layout.
    # Description: Loads local artwork and opens movie details when clicked.
    # Input: parent is the card container, movie supplies artwork and metadata.
    # Output: A card widget with optional captions and watch count.
    # Goal: Reuse row cards and a clean hero poster.
    # Description: poster_only hides captions, show_watch_count enables Popular metadata.
    # Parameter parent. Input: Tk container. Output: Parent reference. Goal: Place card. Description: Owns widgets.
    # Parameter movie. Input: MovieItem. Output: Metadata source. Goal: Identify title. Description: Supplies card content.
    # Parameter poster_only. Input: Boolean. Output: Caption visibility. Goal: Simplify hero. Description: Hides row text.
    # Parameter show_watch_count. Input: Boolean. Output: Count visibility. Goal: Explain ranking. Description: Adds local watches.
    def _home_card(self, parent, movie, poster_only=False, show_watch_count=False):
        card = ttk.Frame(parent, style="Tile.TFrame", padding=8, cursor="hand2")
        source = movie.thumb_path if movie.thumb_path and os.path.isfile(movie.thumb_path) else movie.cover_path
        try:
            image = Image.open(source).convert("RGB")
            image.thumbnail((155, 205))
            artwork = ImageTk.PhotoImage(image)
        except Exception:
            artwork = ImageTk.PhotoImage(Image.new("RGB", (135, 190), TILE_BG))
        self.home_images.append(artwork)
        poster = tk.Label(card, image=artwork, bg=TILE_BG, bd=0, cursor="hand2")
        poster.pack()
        card.bind("<Button-1>", lambda event: self._show_details(movie))
        poster.bind("<Button-1>", lambda event: self._show_details(movie))
        if not poster_only:
            ttk.Label(card, text=movie.title, style="Title.TLabel", wraplength=155,
                      justify="center").pack(pady=(8, 2))
            ttk.Label(card, text=str(movie.year or ""), style="Meta.TLabel").pack()
            if show_watch_count:
                ttk.Label(card, text=f"{movie.watch_count} {'watch' if movie.watch_count == 1 else 'watches'}",
                          style="Meta.TLabel").pack(pady=(2, 0))
            # Input: Caption widgets on this card.
            # Output: One child per iteration.
            # Goal: Make captions open the same movie.
            # Description: Binds the entire card content to details.
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda event: self._show_details(movie))
        return card

    # Input: The active library after startup or an edit.
    # Output: Updated featured and collection rows.
    # Goal: Keep discovery synchronized with watches and metadata.
    # Description: Rebuilds popularity from play counts and rows from stored genres.
    def _refresh_home(self):
        for child in self.home_content.winfo_children():
            child.destroy()
        self.home_images.clear()
        self.featured = self._featured_movies()
        self.feature_index = 0
        self.feature_panel = ttk.Frame(self.home_content, style="Tile.TFrame", padding=22, height=340)
        self.feature_panel.pack(fill="x", pady=(0, 22))
        self.feature_panel.pack_propagate(False)
        # Input: Newly rebuilt feature panel.
        # Output: Reset persistent hero widgets.
        # Goal: Recreate widgets only during a full home refresh.
        # Description: Rotation updates widgets in place to avoid flashing and layout churn.
        self.feature_widgets = None
        self._draw_feature()
        popular = sorted(self.all_items, key=lambda movie: (-movie.watch_count, movie.title.casefold()))
        self._home_row("POPULAR IN YOUR LIBRARY", "Ranked by recorded watches", popular[:8], show_watch_count=True)
        genres = sorted({genre for movie in self.all_items for genre in movie.genres})
        # Input: Active genre names.
        # Output: Genre-to-section mapping.
        # Goal: Resolve picker destinations after every refresh.
        # Description: Stores the actual rendered row widgets.
        self.genre_sections = {}
        # Input: Home content container.
        # Output: Genre navigation toolbar.
        # Goal: Offer a direct route through long collections.
        # Description: Places a labeled native picker above genre rows.
        genre_navigation = ttk.Frame(self.home_content)
        genre_navigation.pack(fill="x", pady=(0, 20))
        ttk.Label(genre_navigation, text="Explore by genre", font=("Segoe UI Semibold", 17)).pack(side="left", padx=(0, 18))
        # Input: Fresh genre choices.
        # Output: Current picker selection.
        # Goal: Start with an obvious prompt.
        # Description: This selection is independent of the library filter.
        self.home_genre_var = tk.StringVar(value="Jump to genre")
        ttk.Combobox(genre_navigation, textvariable=self.home_genre_var, values=genres,
                     state="readonly" if genres else "disabled", width=24).pack(side="left")
        genre_navigation.winfo_children()[-1].bind("<<ComboboxSelected>>", self._jump_to_genre)
        if not genres:
            ttk.Label(self.home_content, text="No genres added yet", style="Status.TLabel").pack(anchor="w")
        for genre in genres:
            movies = [movie for movie in self.all_items if genre in movie.genres]
            self.genre_sections[genre] = self._home_row(genre.upper(), f"{len(movies)} titles", movies)

    # Input: event is the native picker selection notification.
    # Output: Canvas scroll position updated to the selected genre.
    # Goal: Reveal a genre heading without changing filters or row pages.
    # Description: Uses the section offset divided by content height to locate the row.
    # Parameter event. Input: Optional Tk event. Output: None. Goal: Accept binding. Description: Selection notification.
    def _jump_to_genre(self, event=None):
        self.update_idletasks()
        # Input: Current picker selection and rendered mapping.
        # Output: Target row or None.
        # Goal: Ignore stale or empty selections.
        # Description: Looks up the current section widget.
        section = self.genre_sections.get(self.home_genre_var.get())
        if section is not None:
            # Descriptive offset fraction formula. Offset / content height maps pixels
            # to Canvas yview units so the selected heading aligns with the viewport.
            self.home_canvas.yview_moveto(max(0, section.winfo_y() - 12) / max(1, self.home_content.winfo_height()))

    # Input: A section title, description, and movies.
    # Output: A horizontally paged movie section.
    # Goal: Organize the library by theme without overflowing the screen.
    # Description: Four cards appear at once with section-local page controls.
    # Parameter show_watch_count. Input: Boolean. Output: Card presentation option.
    # Goal: Explain Popular ranking. Description: Passed explicitly to row cards.
    def _home_row(self, heading, description, movies, show_watch_count=False):
        section = ttk.Frame(self.home_content)
        section.pack(fill="x", pady=(0, 25))
        heading_row = ttk.Frame(section)
        heading_row.pack(fill="x", pady=(0, 10))
        ttk.Label(heading_row, text=heading, font=("Segoe UI Semibold", 17)).pack(side="left")
        ttk.Label(heading_row, text=f"  {description}", style="Status.TLabel").pack(side="left")
        cards = ttk.Frame(section)
        cards.pack(fill="x")
        # Input: Screen width.
        # Output: Cards that fit in a section page.
        # Goal: Keep row paging usable on narrower displays.
        # Description: Uses available width after page padding.
        visible_count = min(4, max(2, (self.winfo_screenwidth() - 100) // 185))
        page = [0]
        def draw():
            for child in cards.winfo_children():
                child.destroy()
            for movie in movies[page[0] * visible_count:(page[0] + 1) * visible_count]:
                self._home_card(cards, movie, show_watch_count=show_watch_count).pack(side="left", fill="x", expand=True, padx=(0, 12))
            previous.configure(state="normal" if page[0] else "disabled")
            following.configure(state="normal" if (page[0] + 1) * visible_count < len(movies) else "disabled")
        def change(amount):
            page[0] += amount
            draw()
        following = ttk.Button(heading_row, text="Next  ›", width=8,
                               style="RowNav.TButton", command=lambda: change(1))
        following.pack(side="right", padx=(6, 0))
        previous = ttk.Button(heading_row, text="‹  Prev", width=8,
                              style="RowNav.TButton", command=lambda: change(-1))
        previous.pack(side="right")
        draw()
        return section

    # Input: The current featured index.
    # Output: Updated hero artwork, text, and controls.
    # Goal: Show one of five recommendations prominently.
    # Description: Replaces the hero content while retaining image references.
    def _draw_feature(self):
        if self.feature_widgets is not None:
            self._update_feature_content()
            return
        for child in self.feature_panel.winfo_children():
            child.destroy()
        if not self.featured:
            ttk.Label(self.feature_panel, text="Add movies to start discovering.").pack()
            return
        movie = self.featured[self.feature_index]
        artwork = self._home_card(self.feature_panel, movie, poster_only=True)
        artwork.pack(side="left", padx=(0, 28))
        copy = ttk.Frame(self.feature_panel, style="Tile.TFrame")
        copy.pack(side="left", fill="both", expand=True)
        # Input: Current feature position.
        # Output: Persistent recommendation position label.
        # Goal: Advance the counter without rebuilding the panel.
        # Description: Reuses the feature eyebrow style.
        feature_position = ttk.Label(copy, text="PICKED FOR YOU  •  %s / %s" % (self.feature_index + 1, len(self.featured)),
                                     style="FeatureEyebrow.TLabel")
        feature_position.pack(anchor="w", pady=(8, 12))
        # Input: Featured movie text.
        # Output: A heading widget with responsive wrapping.
        # Goal: Keep long titles within the feature width.
        # Description: Wrap length follows the allocated text column.
        feature_title = ttk.Label(copy, text=movie.title, style="FeatureTitle.TLabel", wraplength=500)
        feature_title.pack(anchor="w")
        # Input: Featured movie genres.
        # Output: Supporting text with responsive wrapping.
        # Goal: Keep genre text inside the hero.
        # Description: Shares the heading's available width.
        feature_genres = ttk.Label(copy, text="  /  ".join(movie.genres) or "From your library",
                                   style="FeatureBody.TLabel", wraplength=500)
        feature_genres.pack(anchor="w", pady=(12, 20))
        copy.bind("<Configure>", lambda event: (feature_title.configure(wraplength=max(200, event.width - 12)),
                                                feature_genres.configure(wraplength=max(200, event.width - 12))))
        ttk.Button(copy, text="View movie", style="Accent.TButton",
                   command=lambda: self._show_details(self.featured[self.feature_index])).pack(side="left")
        ttk.Button(copy, text="Next pick  →", command=lambda: self._rotate_feature(1)).pack(side="left", padx=10)
        # Input: Hero widgets created above.
        # Output: References for subsequent in-place updates.
        # Goal: Avoid destroying visible widgets on every rotation.
        # Description: Stores poster, counter, title, and genre labels.
        self.feature_widgets = (artwork.winfo_children()[0], feature_position, feature_title, feature_genres)

    # Input: The current recommendation index and persistent hero widgets.
    # Output: Updated text and artwork without rebuilding the widget tree.
    # Goal: Prevent redraw flashes and page jumps during rotation.
    # Description: Loads the new poster before updating visible content.
    def _update_feature_content(self):
        # Input: Current featured index.
        # Output: Selected movie.
        # Goal: Keep artwork and actions synchronized.
        # Description: Uses the same selection as the View movie action.
        movie = self.featured[self.feature_index]
        # Input: Selected artwork paths.
        # Output: Source path for the poster.
        # Goal: Load local art.
        # Description: Prefers the thumbnail when it exists.
        source = movie.thumb_path if movie.thumb_path and os.path.isfile(movie.thumb_path) else movie.cover_path
        try:
            # Input: Local source image.
            # Output: RGB poster image.
            # Goal: Prepare the replacement before drawing.
            # Description: Matches the existing hero poster dimensions.
            image = Image.open(source).convert("RGB")
            image.thumbnail((155, 205))
        except Exception:
            image = Image.new("RGB", (135, 190), TILE_BG)
        # Input: Prepared poster.
        # Output: Tk image retained on the label.
        # Goal: Prevent image garbage collection.
        # Description: Replaces the prior reference when rotation completes.
        artwork = ImageTk.PhotoImage(image)
        self.feature_widgets[0].configure(image=artwork)
        self.feature_widgets[0].image = artwork
        self.feature_widgets[0].bind("<Button-1>", lambda event: self._show_details(self.featured[self.feature_index]))
        self.feature_widgets[0].master.bind("<Button-1>", lambda event: self._show_details(self.featured[self.feature_index]))
        self.feature_widgets[1].configure(text=f"PICKED FOR YOU  •  {self.feature_index + 1} / {len(self.featured)}")
        self.feature_widgets[2].configure(text=movie.title)
        self.feature_widgets[3].configure(text="  /  ".join(movie.genres) or "From your library")

    # Input: A direction of one featured slot.
    # Output: A newly visible recommendation.
    # Goal: Let viewers control the rotation.
    # Description: Wraps the index across the available five picks.
    def _rotate_feature(self, direction):
        if self.featured and self.home_view.winfo_ismapped():
            self.feature_index = (self.feature_index + direction) % len(self.featured)
            self._draw_feature()

    # Input: Tk's timer.
    # Output: A scheduled featured advance.
    # Goal: Rotate recommendations automatically.
    # Description: Advances every eight seconds while the window exists.
    def _schedule_feature(self):
        if self.winfo_exists():
            self._rotate_feature(1)
            self.after(8000, self._schedule_feature)

    def _build_detail_view(self):
        top = ttk.Frame(self.detail_view, padding=(26, 20, 26, 12))
        top.pack(fill="x")
        ttk.Button(top, text="Back", command=self._show_browser).pack(side="left")
        ttk.Label(top, text="FRAME", font=("Segoe UI Semibold", 15)).pack(side="right")
        body = ttk.Frame(self.detail_view, padding=(42, 22, 42, 38))
        body.pack(fill="both", expand=True)
        self.detail_poster = tk.Label(body, bg=PANEL_BG, bd=0, highlightthickness=1,
                                      highlightbackground=SUBTLE_BORDER)
        self.detail_poster.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 46))
        info = ttk.Frame(body)
        info.grid(row=0, column=1, sticky="nsew")
        self.detail_eyebrow = ttk.Label(info, style="Eyebrow.TLabel")
        self.detail_eyebrow.pack(anchor="w", pady=(8, 8))
        self.detail_title = ttk.Label(info, style="HeroTitle.TLabel", wraplength=680)
        self.detail_title.pack(anchor="w")
        self.detail_facts = ttk.Label(info, style="Body.TLabel", wraplength=680)
        self.detail_facts.pack(anchor="w", pady=(15, 8))
        self.detail_genres = ttk.Label(info, style="Body.TLabel", wraplength=680)
        self.detail_genres.pack(anchor="w", pady=(0, 22))
        self.detail_play = ttk.Button(info, text="Play movie", style="Accent.TButton")
        self.detail_play.pack(anchor="w", pady=(0, 16))
        actions = ttk.Frame(info)
        actions.pack(anchor="w")
        self.detail_edit = ttk.Button(actions, text="Edit metadata")
        self.detail_edit.pack(side="left", padx=(0, 8))
        self.detail_folder = ttk.Button(actions, text="Open folder")
        self.detail_folder.pack(side="left")
        ttk.Label(info, text="Tip: press Esc anytime to return to your library.",
                  style="Status.TLabel").pack(anchor="w", pady=(28, 0))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

    def _apply_filter(self):
        q = self.search_var.get().strip().lower()
        genre = self.genre_var.get()
        studio = self.studio_var.get()
        presentation = self.presentation_var.get()
        self.filtered = [
            m for m in self.all_items
            if (not q or q in " ".join((m.title, str(m.year or ""), m.studio,
                                         m.presentation, *m.genres)).lower())
            and (genre == "All genres" or genre in m.genres)
            and (studio == "All studios" or studio == m.studio)
            and (presentation == "All types" or presentation == m.presentation)
        ]
        sort = self.sort_var.get()
        if sort == "Title (Z-A)":
            self.filtered.sort(key=lambda m: m.title.casefold(), reverse=True)
        elif sort == "Year (newest)":
            self.filtered.sort(key=lambda m: (m.year is not None, m.year or 0, m.title.casefold()), reverse=True)
        elif sort == "Year (oldest)":
            self.filtered.sort(key=lambda m: (m.year is None, m.year or 0, m.title.casefold()))
        elif sort == "Most watched":
            self.filtered.sort(key=lambda m: (-m.watch_count, m.title.casefold()))
        elif sort == "Least watched":
            self.filtered.sort(key=lambda m: (m.watch_count, m.title.casefold()))
        else:
            self.filtered.sort(key=lambda m: m.title.casefold())
        self.page = 0
        self._render_page()

    def _refresh_filter_choices(self):
        self.genre_combo["values"] = ("All genres", *self.catalog.choices("genre"))
        self.studio_combo["values"] = ("All studios", *self.catalog.choices("studio"))
        self.presentation_combo["values"] = ("All types", *self.catalog.choices("presentation"))

    def _rescan(self):
        try:
            scanned = scan_movies(self.root_dir, self.thumb_size, build_thumbs=False)
            self.catalog.sync(scanned)
            self.all_items = self.catalog.load(self.root_dir)
        except Exception as e:
            messagebox.showerror("Rescan failed", str(e))
            return

        self.thumb_cache.clear()
        self._refresh_filter_choices()
        self._apply_filter()
        self._refresh_home()

    def _edit_metadata(self, item: MovieItem):
        dialog = tk.Toplevel(self)
        dialog.title(f"Edit metadata - {item.title}")
        dialog.transient(self)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)

        fields = {}
        values = {
            "Title": item.title,
            "Year": str(item.year or ""),
            "Studio/brand": item.studio,
            "Genres (comma-separated)": ", ".join(item.genres),
        }
        for row, (label, value) in enumerate(values.items()):
            ttk.Label(body, text=label + ":").grid(row=row, column=0, sticky="w", pady=4)
            variable = tk.StringVar(value=value)
            ttk.Entry(body, textvariable=variable, width=48).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
            fields[label] = variable

        ttk.Label(body, text="Type:").grid(row=4, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=item.presentation)
        ttk.Combobox(
            body, textvariable=type_var, state="readonly", width=45,
            values=("", "Animation", "Live action", "Hybrid"),
        ).grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=4)
        ttk.Label(
            body,
            text=(f"Watched: {item.watch_count} time(s). Use the most specific studio/brand: "
                  "Marvel instead of Disney for Marvel movies."),
            wraplength=430,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 12))

        def save():
            year_text = fields["Year"].get().strip()
            if year_text and (not year_text.isdigit() or len(year_text) != 4):
                messagebox.showerror("Invalid year", "Year must be four digits or blank.", parent=dialog)
                return
            title = fields["Title"].get().strip()
            if not title:
                messagebox.showerror("Invalid title", "Title cannot be blank.", parent=dialog)
                return
            genres = fields["Genres (comma-separated)"].get().split(",")
            self.catalog.save_metadata(
                item.id, title, int(year_text) if year_text else None,
                fields["Studio/brand"].get().strip(), type_var.get(), genres,
            )
            self.all_items = self.catalog.load(self.root_dir)
            if self.detail_view.winfo_ismapped():
                # Input: Reloaded catalog items and the edited movie ID.
                # Output: The refreshed movie or None.
                # Goal: Keep the visible detail panel in sync after saving.
                # Description: Finds the edited movie in the reloaded catalog.
                updated_item = next((movie for movie in self.all_items if movie.id == item.id), None)
                if updated_item is not None:
                    self._show_details(updated_item)
            self._refresh_filter_choices()
            self._apply_filter()
            self._refresh_home()
            dialog.destroy()

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Open folder", command=lambda: self._open_folder(item)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=4)
        body.grid_columnconfigure(1, weight=1)
        dialog.bind("<Return>", lambda _e: save())
        dialog.bind("<Escape>", lambda _e: dialog.destroy())

    def _max_page(self) -> int:
        if not self.filtered:
            return 0
        return max(0, (len(self.filtered) - 1) // self.page_size)

    def _prev_page(self):
        if self.page > 0:
            self.page -= 1
            self._render_page()

    def _next_page(self):
        if self.page < self._max_page():
            self.page += 1
            self._render_page()

    def _resolve_video_path(self, item: MovieItem) -> Optional[str]:
        """Resolve the movie against the active library root, not a stale DB path."""
        root = os.path.normcase(os.path.abspath(normalize_path(self.root_dir)))

        def is_in_root(path: str) -> bool:
            try:
                return os.path.commonpath(
                    (root, os.path.normcase(os.path.abspath(path)))
                ) == root
            except (OSError, ValueError):
                return False

        # Always rescan the current folder first. This also repairs a stored path
        # when the movie file was moved after the catalog was last refreshed.
        if item.folder and is_in_root(item.folder) and os.path.isdir(item.folder):
            current_path = find_video(item.folder)
            if current_path:
                return current_path

        # If the database has an old root (for example F:\Title), try the same
        # movie folder beneath the currently selected root (F:\Movies\Title).
        folder_name = os.path.basename(os.path.normpath(item.folder))
        relocated_folder = os.path.join(self.root_dir, folder_name)
        if os.path.isdir(relocated_folder):
            current_path = find_video(relocated_folder)
            if current_path:
                return current_path

        # Every movie may be named movie.mp4. Searching other movie folders by
        # filename could play the wrong title, so stop here if this one is missing.
        return None

    def _play(self, item: MovieItem):
        video_path = self._resolve_video_path(item)
        if not video_path:
            messagebox.showwarning(
                "No video found",
                f"No playable video file found for {item.title} under:\n{self.root_dir}",
            )
            return
        try:
            os.startfile(video_path)
            if video_path != item.video_path:
                self.catalog.update_video_path(item.id, video_path)
            self.catalog.increment_watch_count(item.id)
            self.all_items = self.catalog.load(self.root_dir)
            self._apply_filter()
            self._refresh_home()
        except Exception as e:
            messagebox.showerror("Could not open video", str(e))

    def _open_folder(self, item: MovieItem):
        try:
            os.startfile(item.folder)
        except Exception as e:
            messagebox.showerror("Could not open folder", str(e))

    def _show_details(self, item: MovieItem):
        # Input: The currently visible browser view.
        # Output: The view to restore after details.
        # Goal: Keep home and library navigation predictable.
        # Description: Remembers the source screen before hiding it.
        self.return_view = "home" if self.home_view.winfo_ismapped() else "library"
        self.home_view.pack_forget()
        self.browser_view.pack_forget()
        self.detail_view.pack(fill="both", expand=True)
        self.detail_title.configure(text=item.title)
        self.detail_eyebrow.configure(text="NOW IN YOUR LIBRARY")
        facts = [str(item.year) if item.year else "Year unknown"]
        if item.presentation:
            facts.append(item.presentation)
        if item.studio:
            facts.append(item.studio)
        facts.append(f"Watched {item.watch_count} time{'s' if item.watch_count != 1 else ''}")
        self.detail_facts.configure(text="  •  ".join(facts))
        self.detail_genres.configure(
            text="  /  ".join(item.genres) if item.genres else "No genres added yet"
        )
        self.detail_play.configure(
            command=lambda it=item: self._play(it),
            state=("normal" if self._resolve_video_path(item) else "disabled"),
        )
        self.detail_edit.configure(command=lambda it=item: self._edit_metadata(it))
        self.detail_folder.configure(command=lambda it=item: self._open_folder(it))
        source = item.cover_path if item.cover_path and os.path.isfile(item.cover_path) else item.thumb_path
        try:
            if not source:
                raise OSError("No poster")
            image = Image.open(source).convert("RGB")
            image.thumbnail((360, 520))
            self.detail_image = ImageTk.PhotoImage(image)
        except Exception:
            self.detail_image = ImageTk.PhotoImage(Image.new("RGB", (340, 500), TILE_BG))
        self.detail_poster.configure(image=self.detail_image)
        self.detail_poster.image = self.detail_image

    def _show_browser(self):
        self.detail_view.pack_forget()
        if getattr(self, "return_view", "library") == "home":
            self._show_home()
        else:
            self.browser_view.pack(fill="both", expand=True)

    def _apply_hover(self, card: ttk.Frame, poster: tk.Label, on: bool):
        # Card background via style swap
        card_style = "TileHover.TFrame" if on else "Tile.TFrame"
        card.configure(style=card_style)

        # Poster border “glow”
        if on:
            poster.configure(highlightthickness=2, highlightbackground=HOVER_BORDER, highlightcolor=HOVER_BORDER)
        else:
            poster.configure(highlightthickness=0, highlightbackground=SUBTLE_BORDER, highlightcolor=SUBTLE_BORDER)

    def _load_thumb(self, item: MovieItem) -> ImageTk.PhotoImage:
        # Prefer thumb.jpg, then cover.*
        path = item.thumb_path if item.thumb_path and os.path.isfile(item.thumb_path) else None
        if not path and item.cover_path and os.path.isfile(item.cover_path):
            path = item.cover_path

        if not path:
            return self.placeholder

        if path in self.thumb_cache:
            return self.thumb_cache[path]

        try:
            im = Image.open(path)
            im.thumbnail(self.thumb_size)
            img = ImageTk.PhotoImage(im)
            self.thumb_cache[path] = img
            return img
        except Exception:
            return self.placeholder

    def _render_page(self):
        # cancel ongoing lazy load
        if self.loading_job is not None:
            try:
                self.after_cancel(self.loading_job)
            except Exception:
                pass
            self.loading_job = None

        total = len(self.filtered)
        maxp = self._max_page()

        start = self.page * self.page_size
        end = min(start + self.page_size, total)
        page_items = self.filtered[start:end]

        self.page_label.config(text=f"Page {self.page + 1} / {maxp + 1 if total else 1}")
        self.status.config(text=f"{total} movies (showing {start + 1 if total else 0}-{end})")
        self.prev_btn.config(state=("disabled" if self.page == 0 else "normal"))
        self.next_btn.config(state=("disabled" if self.page >= maxp else "normal"))

        # Fill slots quickly with placeholder, then lazy-load images
        for i, (poster, title, meta) in enumerate(self.slots):
            if i < len(page_items):
                item = page_items[i]
                poster.config(image=self.placeholder)
                poster.image = self.placeholder
                title.config(text=item.title)
                details = [str(item.year) if item.year else "Unknown year"]
                if item.presentation:
                    details.append(item.presentation)
                meta.config(text="  •  ".join(details))

                for widget in (poster, title, meta):
                    widget.bind("<Button-1>", lambda e, it=item: self._show_details(it))
                    widget.bind("<Button-3>", lambda e, it=item: self._edit_metadata(it))
            else:
                poster.config(image=self.placeholder)
                poster.image = self.placeholder
                title.config(text="")
                meta.config(text="")
                for widget in (poster, title, meta):
                    widget.unbind("<Button-1>")
                    widget.unbind("<Button-3>")

        self._lazy_load(page_items, 0)

    def _lazy_load(self, items: List[MovieItem], i: int):
        if i >= len(items):
            self.loading_job = None
            return

        item = items[i]
        poster, _title, _meta = self.slots[i]

        img = self._load_thumb(item)
        poster.config(image=img)
        poster.image = img

        # tiny delay keeps UI responsive
        self.loading_job = self.after(10, lambda: self._lazy_load(items, i + 1))


# Input: The presentation mixin and existing controller.
# Output: A native movie browser with the rebuilt views.
# Goal: Preserve catalog and command behavior while replacing the UI.
# Description: Presentation methods take precedence over legacy view builders.
class MovieBrowser(MovieShelfPresentation, MovieShelfController):
    pass


# Input: Command line arguments and the script or packaged executable location.
# Output: Opens the movie browser or completes the requested maintenance command.
# Goal: Select and validate the requested movie library operation.
# Description: Parses options, checks the root and dimensions, then dispatches.
def main():
    # Input: sys.executable for a packaged app, or __file__ for a Python script.
    # Output: The folder containing the executable or script.
    # Goal: Find the library beside the app after moving it to another computer.
    # Description: Ignores the current directory and old environment overrides.
    default_root = os.path.dirname(
        os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
    )

    # Input: The movie browser command line options.
    # Output: An argument parser with the supported options.
    # Goal: Interpret the selected operation and its settings.
    # Description: Defines the command line interface.
    parser = argparse.ArgumentParser(description="Movie Browser")
    parser.add_argument("--root", default=default_root, help="Root movies folder")
    parser.add_argument("--cols", type=int, default=6, help="Columns in grid")
    parser.add_argument("--rows", type=int, default=2, help="Rows in grid")
    parser.add_argument("--thumb-w", type=int, default=260, help="Thumbnail width")
    parser.add_argument("--thumb-h", type=int, default=380, help="Thumbnail height")
    parser.add_argument("--build-thumbs", action="store_true", help="Build thumb.jpg in each folder then exit")
    parser.add_argument("--fetch-covers", action="store_true", help="Download IMDb primary posters for folders that do not already have a cover",
    )
    # Input: Command line arguments parsed by parser.
    # Output: The selected options and values.
    # Goal: Use the requested settings.
    # Description: Holds the parsed command line namespace.
    args = parser.parse_args()

    # Input: The root argument.
    # Output: An absolute, normalized movie library path.
    # Goal: Use one consistent root path throughout the operation.
    # Description: Expands and normalizes the selected library folder.
    root = os.path.abspath(normalize_path(args.root))
    # Input: The requested thumbnail width and height in pixels.
    # Output: A width and height tuple in pixels.
    # Goal: Pass thumbnail dimensions to maintenance commands.
    # Description: Groups the two dimensions expected by thumbnail helpers.
    thumb_size = (args.thumb_w, args.thumb_h)

    if not os.path.isdir(root):
        raise FileNotFoundError(f"Movie folder does not exist: {root}")
    if min(args.cols, args.rows, args.thumb_w, args.thumb_h) < 1:
        parser.error("Columns, rows, and thumbnail dimensions must be at least 1.")

    if args.fetch_covers:
        # Input: Cover download results for the selected root.
        # Output: Downloaded, skipped, and failed folder counts.
        # Goal: Report the maintenance result.
        # Description: Holds the three counts returned by the cover fetcher.
        downloaded, skipped, failed = fetch_missing_covers(root)
        print(f"Done: {downloaded} downloaded, {skipped} already had covers, {failed} not downloaded")
        return

    if args.build_thumbs:
        # Input: Thumbnail generation results for the selected root.
        # Output: The number of thumbnails created.
        # Goal: Report the maintenance result.
        # Description: Holds the count returned by the thumbnail builder.
        made = build_thumbnails(root, thumb_size)
        print(f"Built {made} thumbnails ({THUMB_NAME})")
        return

    # Input: The validated root and browser layout options.
    # Output: The movie browser window.
    # Goal: Display the selected library.
    # Description: Holds the application until its event loop exits.
    app = MovieBrowser(
        root_dir=root,
        cols=args.cols,
        rows=args.rows,
        thumb_w=args.thumb_w,
        thumb_h=args.thumb_h,
        build_thumbs_on_scan=False,
    )
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except (OSError, sqlite3.Error) as error:
        # Keep the error visible when the script was opened by double-clicking.
        messagebox.showerror("Movie Shelf could not finish", str(error))
        raise SystemExit(1) from error
