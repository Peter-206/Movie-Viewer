"""Capture Movie Shelf on Windows using a temporary library and local posters."""

from pathlib import Path
from shutil import copyfile
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import tkinter as tk

from PIL import ImageGrab


# Input: This script's path inside the hidden test directory.
# Output: The path to the Movie Shelf source directory.
# Goal: Import the app and find local poster files from any working directory.
# Description: The capture script never scans or opens the main library catalog.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))

from movie_shelf import MovieBrowser, MovieCatalog, find_cover, scan_movies


# Input: The source directory containing the hidden review folder.
# Output: The destination path for desktop screenshots.
# Goal: Make current captures easy to find for visual review.
# Description: All screenshot files stay outside the movie collection.
CAPTURE_ROOT = SOURCE_ROOT / ".impeccable" / "review"

# Input: Selected movies with locally available cover art.
# Output: Fictional review catalog metadata keyed by the source folder name.
# Goal: Populate a variety of genres, card titles, art, and watch ranks.
# Description: Each entry stores a year, studio, presentation, genres, and watch count for the temporary catalog.
REVIEW_MOVIES = {
    "Arrival": (2016, "Paramount", "Live action", ["Drama", "Science fiction"], 4),
    "Finding Nemo": (2003, "Pixar", "Animation", ["Adventure", "Family"], 6),
    "Interstellar": (2014, "Paramount", "Live action", ["Adventure", "Science fiction"], 0),
    "La La Land": (2016, "Summit Entertainment", "Live action", ["Drama", "Musical"], 4),
    "Parasite": (2019, "CJ Entertainment", "Live action", ["Drama", "Thriller"], 3),
    "RRR": (2022, "DVV Entertainment", "Live action", ["Action", "Adventure"], 0),
    "Spirited Away": (2001, "Studio Ghibli", "Animation", ["Adventure", "Fantasy"], 7),
    "The Grand Budapest Hotel": (2014, "Fox Searchlight", "Live action", ["Comedy", "Drama"], 2),
    "The Iron Giant": (1999, "Warner Bros.", "Animation", ["Family", "Science fiction"], 3),
    "The Wild Robot": (2024, "DreamWorks", "Animation", ["Adventure", "Family"], 0),
    "Whiplash": (2014, "Blumhouse", "Live action", ["Drama", "Musical"], 1),
}


# Input: A new, disposable library path.
# Output: Fixture movie folders, copied posters, and a separate catalog.
# Goal: Exercise real image layouts without copying or touching actual videos or saved metadata.
# Description: Builds a catalog with fake videos and example metadata using the same APIs as the desktop app.
# Parameter library_root. Input: A Path to a new directory. Output: Fixture library. Goal: Isolate writes. Description: Uses a temporary parent directory.
def stage_library(library_root):
    library_root.mkdir()
    # Input: The fixture movie metadata keys.
    # Output: The next title to stage for review.
    # Goal: Create one folder for each fixture movie.
    # Description: The key matches the existing movie cover's directory name.
    for movie_title in REVIEW_MOVIES:
        # Input: The isolated library root and selected movie title.
        # Output: A writable folder inside the disposable library.
        # Goal: Separate fixture files from the main collection.
        # Description: Holds the mock video and any local cover copy.
        movie_folder = library_root / movie_title
        movie_folder.mkdir()
        (movie_folder / "movie.mp4").write_bytes(b"Movie Shelf review fixture")
        # Input: The real collection folder for the selected title.
        # Output: The path to an existing poster or None.
        # Goal: Use local poster artwork without downloading anything.
        # Description: Cover discovery reads only artwork paths.
        cover_path = find_cover(str(SOURCE_ROOT / movie_title))
        if cover_path:
            copyfile(cover_path, movie_folder / f"cover{Path(cover_path).suffix}")

    # Input: The fixture library's new catalog path.
    # Output: An open connection to a fresh database.
    # Goal: Populate realistic genres, watch counts, and titles for the screenshot.
    # Description: Stores example values beside the fake videos.
    catalog = MovieCatalog(str(library_root / "movies.db"))
    try:
        catalog.sync(scan_movies(str(library_root), (260, 380)))
        # Input: The populated fixture catalog.
        # Output: Each staged movie and its assigned catalog ID.
        # Goal: Write the review metadata to the correct movie.
        # Description: The sample title matches the folder and dictionary key.
        for movie in catalog.load(str(library_root)):
            # Parameter release_year. Input: Fixture metadata. Output: An integer year. Goal: Show release year. Description: Comes from the selected example.
            # Parameter studio. Input: Fixture metadata. Output: A studio name. Goal: Populate studio filter. Description: Uses the example's releasing studio.
            # Parameter presentation. Input: Fixture metadata. Output: The display type. Goal: Populate type filter. Description: Matches the catalog's permitted values.
            # Parameter genres. Input: Fixture metadata. Output: A list of genres. Goal: Populate collection rows. Description: Assigns the title to each displayed genre.
            # Parameter watch_count. Input: Fixture metadata. Output: The sample count. Goal: Populate Popular. Description: Controls relative ranking in the fixture.
            release_year, studio, presentation, genres, watch_count = REVIEW_MOVIES[movie.title]
            catalog.save_metadata(movie.id, movie.title, release_year, studio, presentation, genres)
            # Input: The desired example watch count.
            # Output: One iteration per registered watch.
            # Goal: Record representative play activity in the temporary catalog.
            # Description: This loop uses the same catalog update that Play calls.
            for recorded_watch in range(watch_count):
                catalog.increment_watch_count(movie.id)
    finally:
        catalog.close()


# Input: A mapped Tk window and an output filename.
# Output: A PNG of the actual desktop window.
# Goal: Inspect poster sizing and layout after Tk processes resize and thumbnail work.
# Description: Waits briefly in Tk's own event loop and grabs the target window by native handle.
# Parameter window. Input: A Tk or Toplevel. Output: Native capture target. Goal: Read actual window pixels. Description: Identifies the client surface.
# Parameter filename. Input: A PNG filename. Output: Screenshot path. Goal: Identify view and size. Description: Saved beneath the review directory.
def capture_window(window, filename):
    window.update()
    window.lift()
    # Input: The Tk interpreter for the current window.
    # Output: A signal updated after pending poster and geometry work.
    # Goal: Give the asynchronous loader a bounded time to finish.
    # Description: Waiting on the flag keeps Tk's event loop active.
    capture_ready = tk.BooleanVar(window, value=False)
    window.after(300, capture_ready.set, True)
    window.wait_variable(capture_ready)
    if isinstance(window, MovieBrowser) and window.browser_view.winfo_ismapped():
        # Input: The current monotonic clock reading and an eight-second allowance.
        # Output: The latest time for outstanding layout work to complete.
        # Goal: Fail clearly if the application cannot finish rendering the page.
        # Description: The deadline formula adds the time allowance to the start time.
        loading_deadline = monotonic() + 8
        while window.loading_job is not None or window.resize_job is not None:
            if monotonic() >= loading_deadline:
                raise RuntimeError(f"Poster loading did not finish before capturing {filename}")
            window.update()
            sleep(0.02)
        window.update_idletasks()
    # Input: The window's hexadecimal Windows handle.
    # Output: A numeric window identifier for Pillow.
    # Goal: Capture only the targeted Tk surface.
    # Description: Reads the native frame handle after the window is created.
    window_handle = int(window.wm_frame(), 16)
    # Input: Screen pixels belonging to the target window.
    # Output: A context-managed image saved to the review directory.
    # Goal: Preserve what the real window rendered at the selected size.
    # Description: Releases the image when the PNG write completes.
    with ImageGrab.grab(window=window_handle) as screenshot:
        screenshot.save(CAPTURE_ROOT / filename)
        print(f"{filename} {screenshot.width}x{screenshot.height}")


# Input: Local poster files and a fresh temporary directory.
# Output: Compact and wide captures of Discover, Library, and Details, plus the editor and empty state.
# Goal: Compare composition and control visibility at different window sizes.
# Description: Creates and closes the Tk windows without using the live database or launching a video.
def main():
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    # Input: The system temporary directory.
    # Output: An isolated path removed after both fixture windows close.
    # Goal: Keep review videos and databases away from the user's library.
    # Description: Only PNG captures persist after the script finishes.
    with TemporaryDirectory(prefix="movie-shelf-review-") as fixture_directory:
        # Input: The temporary directory and populated fixture name.
        # Output: A path for the review movies and metadata.
        # Goal: Point browser startup to the disposable collection.
        # Description: Uses a space in the folder name to mirror portable use.
        library_root = Path(fixture_directory) / "Review Library"
        stage_library(library_root)
        # Input: The new fixture library and standard library grid settings.
        # Output: The main browser used for all populated view captures.
        # Goal: Render normal Discover and Library operations with local artwork.
        # Description: Uses the CLI's default six columns and two rows.
        browser = MovieBrowser(str(library_root), cols=6, rows=2)
        try:
            # Input: The fixture catalog's movie records.
            # Output: A known, richly populated record for the Details screenshot.
            # Goal: Compare the same artwork and facts in both viewports.
            # Description: All data comes from the temporary catalog.
            # Parameter movie. Input: Fixture records. Output: A candidate record. Goal: Match the detail title. Description: Contains stored metadata and test paths.
            detail_movie, = (movie for movie in browser.all_items if movie.title == "Spirited Away")
            # Input: Two desktop client sizes in Tk geometry notation.
            # Output: One size string per capture group.
            # Goal: Review compact and wide layouts with identical content.
            # Description: Also identifies captures by size in their filenames.
            for window_size in ("980x680", "1440x900"):
                browser.geometry(f"{window_size}+35+35")
                browser._show_home()
                browser.home_canvas.yview_moveto(0)
                capture_window(browser, f"discover-{window_size}.png")
                browser._open_library()
                capture_window(browser, f"library-{window_size}.png")
                browser._show_details(detail_movie)
                capture_window(browser, f"details-{window_size}.png")

            browser.detail_edit.invoke()
            # Input: The toplevels owned by the browser.
            # Output: The native metadata editor dialog.
            # Goal: Review original values and action placement in the modal.
            # Description: The browser has only one open modal during capture.
            # Parameter child. Input: Browser descendants. Output: Candidate modal. Goal: Match editor window. Description: Uses exact toplevel identity.
            editor, = (child for child in browser.winfo_children() if type(child) is tk.Toplevel)
            capture_window(editor, "metadata-editor.png")
            editor.destroy()
        finally:
            browser._close()

        # Input: A second path under the same temporary parent.
        # Output: An empty collection root distinct from the populated one.
        # Goal: Exercise normal startup with no records without clearing the other fixture.
        # Description: The empty app creates its own isolated database.
        empty_library = Path(fixture_directory) / "Empty Library"
        empty_library.mkdir()
        # Input: The empty folder and standard grid settings.
        # Output: A second mapped window for empty-state capture.
        # Goal: Verify empty Discover and Library composition visually.
        # Description: Closes before the temporary parent is removed.
        empty_browser = MovieBrowser(str(empty_library), cols=6, rows=2)
        try:
            empty_browser.geometry("980x680+35+35")
            capture_window(empty_browser, "discover-empty-980x680.png")
            empty_browser._open_library()
            capture_window(empty_browser, "library-empty-980x680.png")
        finally:
            empty_browser._close()


if __name__ == "__main__":
    main()
