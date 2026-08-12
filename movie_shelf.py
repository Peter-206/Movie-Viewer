import os
import argparse
import difflib
import json
import re
import sqlite3
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Optional, List

from PIL import Image, ImageTk

MOVIE_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm"}
IMG_EXTS = {".jpg", ".jpeg", ".png"}

NAVY_BG = "#0b1220"      # deep navy
TILE_BG = "#0f1a2e"      # slightly lighter navy for tiles
HOVER_BG = "#142445"     # hover highlight
TEXT_FG = "#ffffff"
SUBTLE_BORDER = "#1c2e52"
HOVER_BORDER = "#4c6fff"


THUMB_NAME = "thumb.jpg"
IMDB_SUGGEST_URL = "https://v2.sg.media-imdb.com/suggestion/x/{query}.json"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MovieShelf/1.0",
    "Accept": "application/json,image/avif,image/webp,image/jpeg,*/*",
}


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

    def sync(self, scanned: List[MovieItem]) -> None:
        with self.connection:
            for item in scanned:
                clean_title, detected_year = movie_name_and_year(item.title)
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
                    (clean_title, item.folder, item.video_path, item.cover_path,
                     item.thumb_path, detected_year),
                )

    def load(self) -> List[MovieItem]:
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
        return [
            MovieItem(
                id=row[0], title=row[1], folder=row[2], video_path=row[3],
                cover_path=row[4], thumb_path=row[5], year=row[6], studio=row[7],
                presentation=row[8], genres=tuple(filter(None, row[9].split("|"))),
                watch_count=row[10],
            )
            for row in rows if os.path.isdir(row[2])
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
    # Pick the largest video file in the folder (usually the actual movie)
    best = None
    best_size = -1

    try:
        for fn in os.listdir(folder):
            ext = os.path.splitext(fn)[1].lower()
            if ext in MOVIE_EXTS:
                p = os.path.join(folder, fn)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if size > best_size:
                    best_size = size
                    best = p
    except OSError:
        return None

    return best


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
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"Not a directory: {root_dir}")

    items: List[MovieItem] = []
    for name in sorted(os.listdir(root_dir), key=str.lower):
        if name.startswith((".", "__")):
            continue
        folder = os.path.join(root_dir, name)
        if not os.path.isdir(folder):
            continue

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
                video_path=find_video(folder),
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


def movie_name_and_year(folder_name: str) -> tuple[str, Optional[int]]:
    """Turn common release-folder names into an IMDb search title and optional year."""
    name = re.sub(r"[._]+", " ", folder_name).strip()
    years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", name)
    year = int(years[-1]) if years else None
    if year:
        name = name[:name.rfind(str(year))]

    # Remove common release metadata when there is no year to act as a boundary.
    name = re.split(
        r"\b(?:2160p|1080p|720p|480p|bluray|blu-ray|brrip|webrip|web-dl|dvdrip|x26[45]|hevc)\b",
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


class MovieBrowser(tk.Tk):
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

        style.configure("Nav.TFrame", background=NAVY_BG)
        style.configure("TileHover.TFrame", background=HOVER_BG)
        style.configure("Status.TLabel", background=NAVY_BG, foreground=TEXT_FG, font=("Segoe UI", 11))

        # Tile/card styles
        style.configure("Tile.TFrame")
        style.configure("TitleHover.TLabel", background=HOVER_BG, foreground=TEXT_FG, font=("Segoe UI", 13, "bold"))
        style.configure("Title.TLabel", foreground=TEXT_FG, font=("Segoe UI", 13, "bold"))

        self.title("Movie Browser")

        self.root_dir = root_dir
        self.cols = cols
        self.rows = rows
        self.page_size = cols * rows
        self.thumb_size = (thumb_w, thumb_h)

        self.catalog = MovieCatalog(os.path.join(root_dir, "movies.db"))
        scanned = scan_movies(root_dir, self.thumb_size, build_thumbs=build_thumbs_on_scan)
        self.catalog.sync(scanned)
        self.all_items = self.catalog.load()
        self.filtered = list(self.all_items)

        self.page = 0
        self.thumb_cache: dict[str, ImageTk.PhotoImage] = {}
        self.loading_job: Optional[str] = None

        self.placeholder = ImageTk.PhotoImage(Image.new("RGB", self.thumb_size, (30, 30, 30)))

        self._build_ui()
        self._render_page()
        self.protocol("WM_DELETE_WINDOW", self._close)

        # Keyboard paging
        self.bind("<Left>", lambda _e: self._prev_page())
        self.bind("<Right>", lambda _e: self._next_page())

    def _close(self):
        self.catalog.close()
        self.destroy()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Folder:").pack(side="left")
        ttk.Label(top, text=self.root_dir).pack(side="left", padx=(6, 18))

        ttk.Label(top, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.search_var, width=35)
        ent.pack(side="left", padx=(6, 8))
        ent.bind("<KeyRelease>", lambda _e: self._apply_filter())

        ttk.Button(top, text="Rescan", command=self._rescan).pack(side="left", padx=6)

        filters = ttk.Frame(self, padding=(10, 0, 10, 8))
        filters.pack(fill="x")
        self.genre_var = tk.StringVar(value="All genres")
        self.studio_var = tk.StringVar(value="All studios")
        self.presentation_var = tk.StringVar(value="All types")
        self.sort_var = tk.StringVar(value="Title (A-Z)")

        ttk.Label(filters, text="Genre:").pack(side="left")
        self.genre_combo = ttk.Combobox(filters, textvariable=self.genre_var, state="readonly", width=16)
        self.genre_combo.pack(side="left", padx=(5, 12))
        ttk.Label(filters, text="Studio/brand:").pack(side="left")
        self.studio_combo = ttk.Combobox(filters, textvariable=self.studio_var, state="readonly", width=16)
        self.studio_combo.pack(side="left", padx=(5, 12))
        ttk.Label(filters, text="Type:").pack(side="left")
        self.presentation_combo = ttk.Combobox(
            filters, textvariable=self.presentation_var, state="readonly", width=13
        )
        self.presentation_combo.pack(side="left", padx=(5, 12))
        ttk.Label(filters, text="Sort:").pack(side="left")
        self.sort_combo = ttk.Combobox(
            filters, textvariable=self.sort_var, state="readonly", width=15,
            values=(
                "Title (A-Z)", "Title (Z-A)", "Year (newest)", "Year (oldest)",
                "Most watched", "Least watched",
            ),
        )
        self.sort_combo.pack(side="left", padx=(5, 0))
        for combo in (self.genre_combo, self.studio_combo, self.presentation_combo, self.sort_combo):
            combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        self._refresh_filter_choices()

        nav = ttk.Frame(self, padding=(10, 0, 10, 10))
        nav.pack(fill="x")

        self.prev_btn = ttk.Button(nav, text="◀ Prev", command=self._prev_page)
        self.prev_btn.pack(side="left")

        self.page_label = ttk.Label(nav, text="")
        self.page_label.pack(side="left", padx=12)

        self.next_btn = ttk.Button(nav, text="Next ▶", command=self._next_page)
        self.next_btn.pack(side="left")

        self.status = ttk.Label(self, text="", anchor="w", style="Status.TLabel")
        self.status.pack(fill="x", padx=10, pady=(0, 6))

        self.grid = ttk.Frame(self, padding=10)
        self.grid.pack(fill="both", expand=True)


        # Create fixed slots once; reuse them per page
        self.slots: list[tuple[tk.Label, ttk.Label]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                card = ttk.Frame(self.grid, padding=6, style="Title.TFrame")
                card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")

                poster = tk.Label(
                        card,
                        image=self.placeholder,
                        cursor="hand2",
                        bd=0,
                        bg=TILE_BG,
                        activebackground=TILE_BG,
                        highlightthickness=1,
                        highlightbackground=SUBTLE_BORDER,
                        highlightcolor=SUBTLE_BORDER,
                )
                poster.grid(row=0, column=0, sticky="nsew")

                title = ttk.Label(card, text="", wraplength=self.thumb_size[0], justify="center",
                                  cursor="hand2", style="Title.TLabel")
                title.grid(row=1, column=0, sticky="ew", pady=(6, 0))

                card.grid_columnconfigure(0, weight=1)
                card.grid_rowconfigure(0, weight=1)
                card.grid_rowconfigure(1, weight=0)

                self.slots.append((poster, title))

                def on_enter(_e, c=card, p=poster, t=title):
                    c.configure(style="TileHover.TFrame")
                    t.configure(style="TitleHover.TLabel")
                    self._apply_hover(c, p, True)

                def on_leave(_e, c=card, p=poster, t=title):
                    c.configure(style="Tile.TFrame")
                    t.configure(style="Title.TLabel")
                    self._apply_hover(c, p, False)

                # Hover triggers if mouse enters poster OR title OR card
                poster.bind("<Enter>", on_enter)
                poster.bind("<Leave>", on_leave)
                title.bind("<Enter>", on_enter)
                title.bind("<Leave>", on_leave)
                card.bind("<Enter>", on_enter)
                card.bind("<Leave>", on_leave)

        for c in range(self.cols):
            self.grid.grid_columnconfigure(c, weight=1, uniform="gridcol")
        for r in range(self.rows):
            self.grid.grid_rowconfigure(r, weight=1, uniform="gridrow")

    def _apply_filter(self):
        q = self.search_var.get().strip().lower()
        genre = self.genre_var.get()
        studio = self.studio_var.get()
        presentation = self.presentation_var.get()
        self.filtered = [
            m for m in self.all_items
            if (not q or q in m.title.lower())
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
            self.all_items = self.catalog.load()
        except Exception as e:
            messagebox.showerror("Rescan failed", str(e))
            return

        self.thumb_cache.clear()
        self._refresh_filter_choices()
        self._apply_filter()

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
            self.all_items = self.catalog.load()
            self._refresh_filter_choices()
            self._apply_filter()
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

    def _play(self, item: MovieItem):
        if not item.video_path or not os.path.isfile(item.video_path):
            messagebox.showwarning("No video found", f"No playable video file found in:\n{item.folder}")
            return
        try:
            os.startfile(item.video_path)
            self.catalog.increment_watch_count(item.id)
            self.all_items = self.catalog.load()
            self._apply_filter()
        except Exception as e:
            messagebox.showerror("Could not open video", str(e))

    def _open_folder(self, item: MovieItem):
        try:
            os.startfile(item.folder)
        except Exception as e:
            messagebox.showerror("Could not open folder", str(e))

    def _apply_hover(self, card: ttk.Frame, poster: tk.Label, on: bool):
        # Card background via style swap
        card_style = "TileHover.TFrame" if on else "Tile.TFrame"
        card.configure(style=card_style)

        # Poster border “glow”
        if on:
            poster.configure(highlightthickness=2, highlightbackground=HOVER_BORDER, highlightcolor=HOVER_BORDER)
        else:
            poster.configure(highlightthickness=1, highlightbackground=SUBTLE_BORDER, highlightcolor=SUBTLE_BORDER)

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
        for i, (poster, title) in enumerate(self.slots):
            if i < len(page_items):
                item = page_items[i]
                poster.config(image=self.placeholder)
                poster.image = self.placeholder
                title.config(text=item.title)

                poster.bind("<Button-1>", lambda e, it=item: self._play(it))
                title.bind("<Button-1>", lambda e, it=item: self._play(it))
                poster.bind("<Button-3>", lambda e, it=item: self._edit_metadata(it))
                title.bind("<Button-3>", lambda e, it=item: self._edit_metadata(it))
            else:
                poster.config(image=self.placeholder)
                poster.image = self.placeholder
                title.config(text="")
                poster.unbind("<Button-1>")
                title.unbind("<Button-1>")
                poster.unbind("<Button-3>")
                title.unbind("<Button-3>")

        self._lazy_load(page_items, 0)

    def _lazy_load(self, items: List[MovieItem], i: int):
        if i >= len(items):
            self.loading_job = None
            return

        item = items[i]
        poster, _title = self.slots[i]

        img = self._load_thumb(item)
        poster.config(image=img)
        poster.image = img

        # tiny delay keeps UI responsive
        self.loading_job = self.after(10, lambda: self._lazy_load(items, i + 1))


def main():
    default_root = os.environ.get("MOVIES_ROOT")
    if not default_root:
        default_root = os.path.abspath(os.path.dirname(__file__))

    parser = argparse.ArgumentParser(description="Movie Browser")
    parser.add_argument("--root", default=default_root, help="Root movies folder")
    parser.add_argument("--cols", type=int, default=6, help="Columns in grid")
    parser.add_argument("--rows", type=int, default=2, help="Rows in grid")
    parser.add_argument("--thumb-w", type=int, default=260, help="Thumbnail width")
    parser.add_argument("--thumb-h", type=int, default=380, help="Thumbnail height")
    parser.add_argument("--build-thumbs", action="store_true", help="Build thumb.jpg in each folder then exit")
    parser.add_argument("--fetch-covers", action="store_true", help="Download IMDb primary posters for folders that do not already have a cover",
    )
    args = parser.parse_args()

    root = args.root
    thumb_size = (args.thumb_w, args.thumb_h)

    if args.fetch_covers:
        if not os.path.isdir(root):
            raise SystemExit(f"Not a directory: {root}")
        downloaded, skipped, failed = fetch_missing_covers(root)
        print(f"Done: {downloaded} downloaded, {skipped} already had covers, {failed} not downloaded")
        return

    if args.build_thumbs:
        if not os.path.isdir(root):
            raise SystemExit(f"Not a directory: {root}")
        made = build_thumbnails(root, thumb_size)
        print(f"Built {made} thumbnails ({THUMB_NAME})")
        return

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
    main()
