import os
import argparse
import difflib
import json
import re
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
    title: str
    folder: str
    video_path: Optional[str]
    cover_path: Optional[str]
    thumb_path: Optional[str]


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
        if name.startswith("."):
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
        if name.startswith("."):
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
        if folder_name.startswith("."):
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

        self.all_items = scan_movies(root_dir, self.thumb_size, build_thumbs=build_thumbs_on_scan)
        self.filtered = list(self.all_items)

        self.page = 0
        self.thumb_cache: dict[str, ImageTk.PhotoImage] = {}
        self.loading_job: Optional[str] = None

        self.placeholder = ImageTk.PhotoImage(Image.new("RGB", self.thumb_size, (30, 30, 30)))

        self._build_ui()
        self._render_page()

        # Keyboard paging
        self.bind("<Left>", lambda _e: self._prev_page())
        self.bind("<Right>", lambda _e: self._next_page())

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
        if not q:
            self.filtered = list(self.all_items)
        else:
            self.filtered = [m for m in self.all_items if q in m.title.lower()]
        self.page = 0
        self._render_page()

    def _rescan(self):
        try:
            self.all_items = scan_movies(self.root_dir, self.thumb_size, build_thumbs=False)
        except Exception as e:
            messagebox.showerror("Rescan failed", str(e))
            return

        self.thumb_cache.clear()
        self._apply_filter()

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
                poster.bind("<Button-3>", lambda e, it=item: self._open_folder(it))
                title.bind("<Button-3>", lambda e, it=item: self._open_folder(it))
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
