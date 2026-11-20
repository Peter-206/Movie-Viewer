"""Regression checks for the portable movie library and its Tk browser."""

from dataclasses import replace
from operator import attrgetter
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from PIL import Image

import movie_shelf


class TemporaryLibraryTest(unittest.TestCase):
    # Input: A unittest test instance.
    # Output: An empty library in an isolated temporary directory.
    # Goal: Exercise application writes without touching the real library.
    # Description: Registers directory removal after catalog and window cleanup.
    # Parameter self. Input: Test instance. Output: Fixture state. Goal: Share paths. Description: Holds the temporary library.
    def setUp(self):
        # Input: The system temporary directory.
        # Output: A temporary directory manager retained by unittest cleanup registration.
        # Goal: Remove all generated movies and database files when the test ends.
        # Description: The library is nested so tests can simulate moving it between roots.
        temporary_directory = TemporaryDirectory(prefix="movie-shelf-test-")
        self.addCleanup(temporary_directory.cleanup)
        # Input: The temporary manager's name and a fixture subfolder name.
        # Output: The absolute path to the active fixture library.
        # Goal: Give the application an explicit root for every test.
        # Description: Contains only test movies and their catalog.
        self.library_root = Path(temporary_directory.name) / "Active Library"
        self.library_root.mkdir()

    # Input: A folder name and the active fixture root.
    # Output: The new movie directory, with a fake local video.
    # Goal: Provide minimal movie files for scanning and mocked playback.
    # Description: A canonical filename keeps startup idempotent.
    # Parameter self. Input: Test instance. Output: Fixture root. Goal: Isolate files. Description: Holds the active library path.
    # Parameter folder_name. Input: Text. Output: Folder basename. Goal: Label the movie. Description: Supplies the folder name before catalog parsing.
    def add_movie(self, folder_name):
        # Input: The fixture library and the new folder's name.
        # Output: A path inside the isolated library.
        # Goal: Keep every fixture write under the selected root.
        # Description: Stores the movie and optional fixture artwork or extras.
        movie_folder = self.library_root / folder_name
        movie_folder.mkdir()
        (movie_folder / "movie.mp4").write_bytes(b"fixture video")
        return movie_folder

    # Input: A database path in the test library.
    # Output: An open SQLite catalog registered for cleanup.
    # Goal: Ensure the connection closes before removing the temporary files.
    # Description: Uses the same database name as the running application.
    # Parameter self. Input: Test instance. Output: Cleanup registration. Goal: Manage database lifetime. Description: Owns the fixture root.
    def open_catalog(self):
        # Input: The active root and its conventional database filename.
        # Output: A MovieCatalog connected to a fixture database.
        # Goal: Use real catalog persistence without accessing live metadata.
        # Description: Supports loading, rescanning, and simulated relocation.
        catalog = movie_shelf.MovieCatalog(str(self.library_root / "movies.db"))
        self.addCleanup(catalog.close)
        return catalog


class CatalogTests(TemporaryLibraryTest):
    # Input: A temporary movie with a larger feature and a smaller trailer.
    # Output: Assertions against both the first scan and a repeated scan.
    # Goal: Protect safe startup renaming and canonical video selection.
    # Description: Checks the nested path, extension casing, and unchanged extras.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify scans. Description: Owns the temporary movie files.
    def test_scan_renames_only_the_main_video_in_its_existing_subfolder(self):
        # Input: The fixture root and movie name.
        # Output: The movie folder holding the film and its extras.
        # Goal: Build a layout with the main video inside a child directory.
        # Description: The movie starts with a noncanonical filename.
        movie_folder = self.library_root / "Winter Signal (2004) [1080p]"
        (movie_folder / "Feature").mkdir(parents=True)
        (movie_folder / "Feature" / "Release.MKV").write_bytes(b"the complete feature")
        (movie_folder / "trailer.mp4").write_bytes(b"trailer")
        (self.library_root / ".build").mkdir()

        # Input: The first scan of the fixture library.
        # Output: The only movie found in the scan.
        # Goal: Read its selected playback path and verify hidden folders were skipped.
        # Description: Tuple unpacking also checks the scan returned one movie.
        scanned_movie, = movie_shelf.scan_movies(str(self.library_root), (80, 120))
        self.assertEqual(scanned_movie.video_path, str(movie_folder / "Feature" / "movie.MKV"))
        self.assertFalse((movie_folder / "Feature" / "Release.MKV").exists())
        self.assertEqual((movie_folder / "trailer.mp4").read_bytes(), b"trailer")
        (movie_folder / "trailer.mp4").write_bytes(b"long trailer " * 50)
        self.assertEqual(movie_shelf.scan_movies(str(self.library_root), (80, 120)), [scanned_movie])
        self.assertEqual((movie_folder / "Feature" / "movie.MKV").read_bytes(), b"the complete feature")

    # Input: The same movie folder name under two different library roots.
    # Output: Assertions on IDs, edited metadata, watch counts, and current paths.
    # Goal: Preserve the user's saved details when the portable library relocates.
    # Description: Reuses an unambiguous stored row and scopes loading to the active root.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify relocation. Description: Owns both fixture roots.
    def test_catalog_preserves_metadata_and_watch_count_across_library_roots(self):
        # Input: A sibling root inside the test directory.
        # Output: The previously selected library root on disk.
        # Goal: Generate a catalog row that has an older absolute path.
        # Description: The old library also has an unrelated movie that must stay scoped to it.
        previous_root = self.library_root.with_name("Previous Library")
        (previous_root / "Winter Signal (2004) [1080p]").mkdir(parents=True)

        # Input: The isolated test database path.
        # Output: An open SQLite catalog.
        # Goal: Save user metadata before scanning the new location.
        # Description: Both scans use this same database, as they would after moving a drive.
        catalog = self.open_catalog()
        catalog.sync(movie_shelf.scan_movies(str(previous_root), (80, 120)))
        # Input: The catalog results from the previous root.
        # Output: The matching movie record with its original database ID.
        # Goal: Simulate applying metadata to a previously scanned movie.
        # Description: The original title and year are parsed from its release folder name.
        original_movie, = catalog.load(str(previous_root))
        self.assertEqual((original_movie.title, original_movie.year), ("Winter Signal", 2004))
        catalog.save_metadata(original_movie.id, "Winter Radio", 2005, "North Studios", "Hybrid", ["Drama", " Mystery "])
        catalog.increment_watch_count(original_movie.id)
        catalog.increment_watch_count(original_movie.id)
        (previous_root / "Away From Home").mkdir()
        catalog.sync(movie_shelf.scan_movies(str(previous_root), (80, 120)))

        self.add_movie("Winter Signal (2004) [1080p]")
        catalog.sync(movie_shelf.scan_movies(str(self.library_root), (80, 120)))
        # Input: The catalog results restricted to the current fixture library.
        # Output: The relocated movie record.
        # Goal: Compare it against persisted metadata and its current playback target.
        # Description: Tuple unpacking confirms the unrelated movie did not appear in the new root.
        relocated_movie, = catalog.load(str(self.library_root))
        self.assertEqual(relocated_movie.id, original_movie.id)
        self.assertEqual((relocated_movie.title, relocated_movie.year), ("Winter Radio", 2005))
        self.assertEqual((relocated_movie.studio, relocated_movie.presentation), ("North Studios", "Hybrid"))
        self.assertEqual((relocated_movie.genres, relocated_movie.watch_count), (("Drama", "Mystery"), 2))
        self.assertEqual(relocated_movie.video_path, str(self.library_root / "Winter Signal (2004) [1080p]" / "movie.mp4"))
        self.assertEqual(catalog.choices("genre"), ["Drama", "Mystery"])
        self.assertEqual(catalog.choices("studio"), ["North Studios"])
        self.assertEqual(catalog.choices("presentation"), ["Hybrid"])

    # Input: An existing cover, a cached thumbnail, and a movie without artwork.
    # Output: Assertions on the generated thumbnail and repeat build.
    # Goal: Protect explicit thumbnail maintenance and allow missing artwork.
    # Description: Checks dimensions, canonical cover preference, and cached bytes.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify thumbnail building. Description: Owns the fixture posters and cache.
    def test_thumbnail_builder_preserves_existing_cache_and_skips_missing_covers(self):
        # Input: A new folder with a canonical movie file.
        # Output: The fixture folder for valid cover artwork.
        # Goal: Exercise thumbnail generation with a readable image.
        # Description: Supplies both canonical and fallback cover names.
        covered_movie = self.add_movie("Movie With A Cover")
        Image.new("RGB", (300, 450), "#684b27").save(covered_movie / "cover.jpg")
        (covered_movie / "cover-older.png").write_bytes(b"invalid fallback")

        # Input: A second fixture movie folder.
        # Output: A path to a movie with an existing cached thumbnail.
        # Goal: Seed a file the builder must keep intact.
        # Description: Protects the no-overwrite behavior on repeated maintenance.
        cached_movie = self.add_movie("Movie With A Cache")
        (cached_movie / "thumb.jpg").write_bytes(b"original cache")
        self.add_movie("Movie Without A Cover")

        self.assertEqual(movie_shelf.build_thumbnails(str(self.library_root), (80, 120)), 1)
        # Input: Thumbnail generated from the fixture's canonical cover.
        # Output: A decoded Pillow image with file access scoped to the context.
        # Goal: Verify the requested maximum dimensions and picture format.
        # Description: Reads image headers and closes the handle before fixture cleanup.
        with Image.open(covered_movie / "thumb.jpg") as thumbnail:
            self.assertEqual(thumbnail.size, (80, 120))
            self.assertEqual(thumbnail.format, "JPEG")
        self.assertEqual((cached_movie / "thumb.jpg").read_bytes(), b"original cache")
        self.assertFalse((self.library_root / "Movie Without A Cover" / "thumb.jpg").exists())
        self.assertEqual(movie_shelf.build_thumbnails(str(self.library_root), (80, 120)), 0)


class CommandLineTests(TemporaryLibraryTest):
    # Input: A simulated script and executable beside a fixture library.
    # Output: Checks the root path and grid options passed to the browser.
    # Goal: Protect startup from another directory, including when the library moves.
    # Description: Replaces the window with a mock to exercise normal CLI dispatch.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify portable startup. Description: Owns the fixture root.
    def test_main_defaults_to_application_folder_for_script_and_executable(self):
        # Input: The browser constructor in the CLI module.
        # Output: A mock constructor that records its selected root and options.
        # Goal: Exercise startup without opening a second window.
        # Description: Both script and frozen paths should resolve to the same library.
        with patch.object(movie_shelf, "MovieBrowser") as browser_factory:
            with patch.object(movie_shelf, "__file__", str(self.library_root / "movie_shelf.py")):
                with patch.object(sys, "argv", ["movie_shelf.py"]):
                    movie_shelf.main()
            browser_factory.assert_called_once_with(
                root_dir=str(self.library_root), cols=6, rows=2,
                thumb_w=260, thumb_h=380, build_thumbs_on_scan=False,
            )
            browser_factory.return_value.mainloop.assert_called_once_with()
            browser_factory.reset_mock()

            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", str(self.library_root / "movie_shelf.exe")):
                    with patch.object(sys, "argv", ["movie_shelf.exe", "--cols", "3", "--rows", "1"]):
                        movie_shelf.main()
            browser_factory.assert_called_once_with(
                root_dir=str(self.library_root), cols=3, rows=1,
                thumb_w=260, thumb_h=380, build_thumbs_on_scan=False,
            )
            browser_factory.return_value.mainloop.assert_called_once_with()

    # Input: The maintenance flags and a disposable library root.
    # Output: Checks each dispatched maintenance action and its precedence.
    # Goal: Keep maintenance independent from GUI startup, network, and video renaming.
    # Description: Stubs the invoked action and records the root and dimensions.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify CLI routing. Description: Provides a valid library path.
    def test_main_dispatches_maintenance_and_prioritizes_cover_fetching(self):
        # Input: Standard CLI options and the isolated fixture root.
        # Output: Arguments selecting a specific library and thumbnail size.
        # Goal: Reuse the common arguments across maintenance cases.
        # Description: Each call adds the maintenance flags being exercised.
        arguments = ["movie_shelf.py", "--root", str(self.library_root), "--thumb-w", "80", "--thumb-h", "120"]
        # Input: The original browser constructor.
        # Output: A mock recording any attempted GUI startup.
        # Goal: Prove neither maintenance path opens a window.
        # Description: Spans both CLI calls so the same check covers both.
        with patch.object(movie_shelf, "MovieBrowser") as browser_factory:
            # Input: The thumbnail builder in the CLI module.
            # Output: A predetermined creation count and call record.
            # Goal: Verify the thumbnail action receives the supplied options once.
            # Description: The core thumbnail test covers real filesystem behavior.
            with patch.object(movie_shelf, "build_thumbnails", return_value=3) as build_thumbnails:
                # Input: The cover fetcher in the CLI module.
                # Output: Predetermined download, skip, and failure counts.
                # Goal: Verify maintenance precedence without making a network request.
                # Description: Receives only the explicit fixture root.
                with patch.object(movie_shelf, "fetch_missing_covers", return_value=(1, 2, 3)) as fetch_covers:
                    with patch.object(sys, "argv", [*arguments, "--build-thumbs"]):
                        movie_shelf.main()
                    build_thumbnails.assert_called_once_with(str(self.library_root), (80, 120))
                    fetch_covers.assert_not_called()
                    build_thumbnails.reset_mock()

                    with patch.object(sys, "argv", [*arguments, "--build-thumbs", "--fetch-covers"]):
                        movie_shelf.main()
                    fetch_covers.assert_called_once_with(str(self.library_root))
                    build_thumbnails.assert_not_called()
            browser_factory.assert_not_called()


class BrowserTests(TemporaryLibraryTest):
    # Input: The temporary library root and a compact test viewport.
    # Output: A mapped MovieBrowser registered for cleanup.
    # Goal: Exercise Tk callbacks and geometry using the same class as normal startup.
    # Description: Uses fake videos only. Tests that need playback patch Windows dispatch.
    # Parameter self. Input: Test instance. Output: Fixture and cleanup registration. Goal: Manage the browser window. Description: Owns its library root.
    def open_browser(self):
        # Input: The temporary root, one row, and two requested columns.
        # Output: A browser using the fixture catalog.
        # Goal: Make a small collection span multiple pages during the paging test.
        # Description: Requested artwork and geometry fit a compact desktop viewport.
        browser = movie_shelf.MovieBrowser(str(self.library_root), cols=2, rows=1, thumb_w=100, thumb_h=150)
        self.addCleanup(browser._close)
        browser.geometry("1200x760+25+25")
        browser.update()
        return browser

    # Input: Three movies with different years, play counts, studios, types, and genres.
    # Output: Assertions on keyboard paging, result filtering, and every sort choice.
    # Goal: Protect the existing behavior through the rebuilt Library controls.
    # Description: Combines a mixed-case metadata query with all three facets.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify library controls. Description: Owns the temporary catalog.
    def test_library_combines_filters_and_sorts_with_keyboard_paging(self):
        self.add_movie("Early Road (2002)")
        self.add_movie("New Trail (2021)")
        self.add_movie("Unknown Destination")
        # Input: The fixture database and the three scanned movie folders.
        # Output: An initialized catalog used to seed expected ranking and filter values.
        # Goal: Give each sort mode and facet distinct test data.
        # Description: Test data is saved through the real catalog API.
        catalog = self.open_catalog()
        catalog.sync(movie_shelf.scan_movies(str(self.library_root), (100, 150)))
        # Input: The catalog after scanning the three named movie folders.
        # Output: A list of all fixture records before editing.
        # Goal: Build the title mapping from one consistent catalog read.
        # Description: Contains both year-tagged movies and the unknown-year one.
        loaded_movies = catalog.load()
        # Input: The catalog after scanning the three named movie folders.
        # Output: A mapping from parsed title to current record.
        # Goal: Select records without relying on database order.
        # Description: Each title uniquely names one fixture movie.
        movies = dict(zip(map(attrgetter("title"), loaded_movies), loaded_movies))
        catalog.save_metadata(movies["Early Road"].id, "Zebra Road", 2002, "Cedar Pictures", "Live action", ["Drama"])
        catalog.save_metadata(movies["New Trail"].id, "Mountain Trail", 2021, "Orchid Film", "Animation", ["Adventure"])
        catalog.increment_watch_count(movies["Early Road"].id)
        catalog.increment_watch_count(movies["Early Road"].id)
        catalog.increment_watch_count(movies["New Trail"].id)

        # Input: The seeded temporary library.
        # Output: A mapped browser initially displaying Discover.
        # Goal: Exercise the keyboard command that opens Library.
        # Description: Queues native Tk key events and processes them synchronously.
        browser = self.open_browser()
        browser.focus_force()
        browser.event_generate("<Control-b>")
        browser.update()
        self.assertTrue(browser.browser_view.winfo_ismapped())
        self.assertEqual(list(map(attrgetter("title"), browser.filtered)),
                         ["Mountain Trail", "Unknown Destination", "Zebra Road"])
        browser.event_generate("<Right>")
        self.assertEqual(browser.page, 1)
        self.assertIn("disabled", browser.next_btn.state())
        browser.event_generate("<Home>")
        self.assertEqual(browser.page, 0)
        self.assertIn("disabled", browser.prev_btn.state())

        # Input: The six existing sort menu choices.
        # Output: Each choice paired with the expected title list.
        # Goal: Check year gaps and ascending and descending ordering.
        # Description: The catalog contains one missing year and three distinct watch counts.
        sort_expectations = {
            "Title (A-Z)": ["Mountain Trail", "Unknown Destination", "Zebra Road"],
            "Title (Z-A)": ["Zebra Road", "Unknown Destination", "Mountain Trail"],
            "Year (newest)": ["Mountain Trail", "Zebra Road", "Unknown Destination"],
            "Year (oldest)": ["Zebra Road", "Mountain Trail", "Unknown Destination"],
            "Most watched": ["Zebra Road", "Mountain Trail", "Unknown Destination"],
            "Least watched": ["Unknown Destination", "Mountain Trail", "Zebra Road"],
        }
        # Parameter sort_mode. Input: Sort expectations. Output: One menu choice. Goal: Select the sort. Description: Uses the visible choice's exact value.
        # Parameter expected_titles. Input: Sort expectations. Output: The predicted order. Goal: Verify sorting. Description: Contains all three fixture titles.
        for sort_mode, expected_titles in sort_expectations.items():
            with self.subTest(sort_mode=sort_mode):
                browser._next_page()
                browser.sort_var.set(sort_mode)
                browser._apply_filter()
                self.assertEqual(list(map(attrgetter("title"), browser.filtered)), expected_titles)
                self.assertEqual(browser.page, 0)

        browser.library_search_entry.focus_force()
        browser.library_search_entry.delete(0, "end")
        browser.library_search_entry.insert(0, "  oRcHiD  ")
        browser.library_search_entry.event_generate("<Return>")
        browser.genre_var.set("Adventure")
        browser.studio_var.set("Orchid Film")
        browser.presentation_var.set("Animation")
        browser._apply_filter()
        self.assertEqual(list(map(attrgetter("title"), browser.filtered)), ["Mountain Trail"])
        browser.studio_var.set("Cedar Pictures")
        browser._apply_filter()
        self.assertEqual(browser.filtered, [])
        self.assertIn("disabled", browser.next_btn.state())

    # Input: A temporary library with three posterless movie records.
    # Output: Assertions on discovery rotation, startup view, and disabled playback.
    # Goal: Verify graceful placeholders and stable recommendation layout.
    # Description: Generates a native arrow event and opens a movie without a video.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify discovery navigation. Description: Owns the temporary media.
    def test_discover_rotation_reuses_widgets_and_details_returns_home(self):
        self.add_movie("Evening Tide")
        self.add_movie("Harbor Light")
        (self.library_root / "No Video Here").mkdir()
        (self.library_root / "Harbor Light" / "cover.jpg").write_bytes(b"corrupt image")
        # Input: The fixture database and the scanned movie folders.
        # Output: A real catalog with several genre sections in Discover.
        # Goal: Make the viewport scrollable for the descendant wheel check.
        # Description: One fixture movie belongs to every seeded genre.
        catalog = self.open_catalog()
        catalog.sync(movie_shelf.scan_movies(str(self.library_root), (100, 150)))
        # Input: The scanned catalog records.
        # Output: The first fixture movie in title order.
        # Goal: Add genres without relying on a database row order.
        # Description: Its metadata produces several separate Discover rows.
        grouped_movie = min(catalog.load(), key=attrgetter("title"))
        catalog.save_metadata(grouped_movie.id, grouped_movie.title, None, "", "", ["Drama", "Family", "Mystery"])
        # Input: A temporary library with missing and unreadable artwork.
        # Output: A mapped browser initially displaying Discover.
        # Goal: Exercise rotation and placeholder rendering in a running window.
        # Description: Startup must continue despite corrupt artwork.
        browser = self.open_browser()
        self.assertTrue(browser.home_view.winfo_ismapped())
        # Input: The persistent hero widgets before rotation.
        # Output: Widget references for the initial recommendation panel.
        # Goal: Verify a recommendation change preserves panel layout and widget identity.
        # Description: Includes the poster, position, title, and genre labels.
        feature_widgets = browser.feature_widgets
        # Input: The current hero selection before the key press.
        # Output: The starting recommendation index.
        # Goal: Check that Left or Right advances to a different recommendation.
        # Description: The temporary library supplies multiple recommendations.
        starting_pick = browser.feature_index
        # Input: The initial Discover scroll position.
        # Output: Fraction marking the top of the visible canvas.
        # Goal: Detect a full step from two partial mouse-wheel events.
        # Description: Captures the canvas before input over a nested poster widget.
        starting_scroll = browser.home_canvas.yview()[0]
        feature_widgets[0].event_generate("<MouseWheel>", delta=-60)
        self.assertEqual(browser.home_canvas.yview()[0], starting_scroll)
        feature_widgets[0].event_generate("<MouseWheel>", delta=-60)
        self.assertGreater(browser.home_canvas.yview()[0], starting_scroll)
        browser.update()
        # Input: The canvas configure operation during scrolling. Output: A recording wrapper. Goal: Detect redundant layout invalidation. Description: Scrolling should move existing controls without rewriting the scroll region.
        with patch.object(browser.home_canvas, "configure", wraps=browser.home_canvas.configure) as canvas_configuration:
            # Input: Repeated scroll input. Output: One wheel step per iteration. Goal: Exercise native descendant movement. Description: Drives both directions without rebuilding the content.
            for scroll_step in range(12):
                feature_widgets[0].event_generate("<MouseWheel>", delta=-120 if scroll_step < 6 else 120)
                browser.update()
            self.assertEqual(canvas_configuration.call_count, 0)
        self.assertEqual(browser.feature_widgets, feature_widgets)
        browser.focus_force()
        browser.event_generate("<Right>")
        browser.update()
        self.assertNotEqual(browser.feature_index, starting_pick)
        self.assertEqual(browser.feature_widgets, feature_widgets)

        # Input: The three fixture records loaded from the catalog.
        # Output: The record for the only movie without video.
        # Goal: Check unavailable playback while still rendering details.
        # Description: The movie folder exists but has no playable file.
        movie_without_video = max(browser.all_items, key=attrgetter("title"))
        self.assertEqual(movie_without_video.title, "No Video Here")
        browser._show_details(movie_without_video)
        browser.update()
        self.assertTrue(browser.detail_view.winfo_ismapped())
        self.assertIn("disabled", browser.detail_play.state())
        browser.event_generate("<Escape>")
        browser.update()
        self.assertTrue(browser.home_view.winfo_ismapped())

    # Input: An empty library root.
    # Output: Checks that navigation and rescan remain usable with no collection.
    # Goal: Protect empty states and add a movie from the normal keyboard command.
    # Description: Starts with a blank catalog and introduces a fixture movie after startup.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify empty startup and rescan. Description: Owns the initially empty fixture root.
    def test_empty_library_accepts_movie_added_before_rescan(self):
        # Input: The empty temporary root.
        # Output: A mapped browser with no movie records.
        # Goal: Check the empty state through the normal startup and Library shortcut.
        # Description: Does not seed files until after confirming the empty result.
        browser = self.open_browser()
        self.assertEqual(browser.all_items, [])
        browser.focus_force()
        browser.event_generate("<Control-b>")
        browser.update()
        self.assertTrue(browser.browser_view.winfo_ismapped())
        self.assertIn("disabled", browser.prev_btn.state())
        self.assertIn("disabled", browser.next_btn.state())
        self.add_movie("First Arrival (2024)")
        browser.event_generate("<F5>")
        browser.update()
        self.assertEqual(list(map(attrgetter("title"), browser.filtered)), ["First Arrival"])

    # Input: Two movies with identical canonical filenames and one stale catalog path.
    # Output: Assertions on folder-scoped resolution and the successful watch counter.
    # Goal: Keep Play and Open folder attached to the selected movie after relocation.
    # Description: Mocks Windows dispatch and then removes the selected fixture video.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify playback safety. Description: Owns both fake movies.
    def test_play_repairs_the_selected_file_and_never_uses_another_title(self):
        self.add_movie("Active Title")
        self.add_movie("Another Title")
        # Input: The fixture root containing the two same-named video files.
        # Output: A browser and its current movie records.
        # Goal: Verify the normal details actions and local watch updates.
        # Description: The default player and Explorer are mocked in this test.
        browser = self.open_browser()
        # Input: The two movie records in the fixture catalog.
        # Output: The record for the alphabetically first title.
        # Goal: Choose a fixed playback subject and use the other as a decoy.
        # Description: Uses the title rather than relying on the database row order.
        active_movie = min(browser.all_items, key=attrgetter("title"))
        self.assertEqual(active_movie.title, "Active Title")
        # Input: The adjacent movie's canonical video path.
        # Output: A valid path belonging to a different movie.
        # Goal: Check that stale video paths cannot trigger the wrong movie.
        # Description: Both paths end in movie.mp4.
        neighboring_video = str(self.library_root / "Another Title" / "movie.mp4")
        browser.catalog.update_video_path(active_movie.id, neighboring_video)
        browser._show_details(replace(active_movie, video_path=neighboring_video))
        browser.update()

        # Input: The Windows file opening function.
        # Output: A mock whose calls record the movie folder and chosen video.
        # Goal: Check OS dispatch without starting Explorer or a media player.
        # Description: The browser runs its actual catalog repair and watch update logic.
        with patch.object(movie_shelf.os, "startfile", create=True) as open_file:
            browser.detail_folder.invoke()
            open_file.assert_called_once_with(active_movie.folder)
            open_file.reset_mock()
            browser.detail_play.invoke()
            open_file.assert_called_once_with(active_movie.video_path)
            self.assertIn("1", browser.detail_facts.cget("text"))
            open_file.reset_mock()
            Path(active_movie.video_path).unlink()
            # Input: The desktop warning function.
            # Output: A mock recording the warning for missing media.
            # Goal: Keep the test from blocking on a modal dialog.
            # Description: The neighboring movie remains present throughout this check.
            with patch.object(movie_shelf.messagebox, "showwarning") as warning:
                browser._play(active_movie)
                warning.assert_called_once()
            open_file.assert_not_called()

        # Input: The catalog after opening the selected title.
        # Output: The persisted copy of the active movie record.
        # Goal: Verify one play and removal of the stale path from the catalog.
        # Description: Reads through the normal catalog API to check persistence.
        updated_movie = min(browser.catalog.load(), key=attrgetter("title"))
        self.assertEqual(updated_movie.watch_count, 1)
        self.assertEqual(updated_movie.video_path, active_movie.video_path)

    # Input: A parent widget and a Tk class to match exactly.
    # Output: Matching widgets in the order their controls are created.
    # Goal: Locate native metadata fields regardless of presentation containers.
    # Description: Exact class checks keep Combobox controls out of Entry results.
    # Parameter self. Input: Test instance. Output: Recursive lookup method. Goal: Search widget levels. Description: Traverses the dialog tree.
    # Parameter parent_widget. Input: A Tk widget. Output: Child collection. Goal: Walk controls. Description: Marks the current tree root.
    # Parameter widget_type. Input: A Tk widget class. Output: Exact class filter. Goal: Identify controls. Description: Avoids collecting subclasses.
    def controls_of_type(self, parent_widget, widget_type):
        # Input: Children of the current widget tree root.
        # Output: The next descendant being checked for a class match.
        # Goal: Search control layouts recursively.
        # Description: Child frames may contain insets and action areas.
        for child_widget in parent_widget.winfo_children():
            if type(child_widget) is widget_type:
                yield child_widget
            yield from self.controls_of_type(child_widget, widget_type)

    # Input: One movie shown in Details after entering from Discover.
    # Output: Checks an invalid year and a valid save through the native editor.
    # Goal: Protect validation, display refresh, and the original Back destination.
    # Description: Edits temporary data and uses Escape to return to Discover.
    # Parameter self. Input: Test instance. Output: Test assertions. Goal: Verify metadata editing. Description: Owns the fixture catalog and Tk window.
    def test_edit_metadata_keeps_origin_and_updates_visible_details(self):
        self.add_movie("Forest Road (2011)")
        # Input: The fixture library containing the one editable movie.
        # Output: A mapped browser window starting in Discover.
        # Goal: Enter Details from the same surface that Back should restore.
        # Description: The original saved title and year are parsed from the folder name.
        browser = self.open_browser()
        browser._show_details(browser.all_items[0])
        browser.update()
        browser.detail_edit.invoke()
        browser.update()

        # Input: The browser's descendant windows.
        # Output: The visible metadata editor dialog.
        # Goal: Scope native field discovery to the modal.
        # Description: The fixture opens one toplevel at a time.
        editor, = self.controls_of_type(browser, tk.Toplevel)
        # Parameter title_field. Input: Metadata editor entries. Output: Title control. Goal: Edit name. Description: Starts with the parsed title.
        # Parameter year_field. Input: Metadata editor entries. Output: Year control. Goal: Check validation. Description: Accepts blank or four digits.
        # Parameter studio_field. Input: Metadata editor entries. Output: Studio control. Goal: Edit studio. Description: Starts blank for the fixture.
        # Parameter genre_field. Input: Metadata editor entries. Output: Genres control. Goal: Edit categories. Description: Accepts comma-separated names.
        title_field, year_field, studio_field, genre_field = self.controls_of_type(editor, ttk.Entry)
        # Input: The metadata editor's exact Combobox control.
        # Output: The presentation dropdown widget.
        # Goal: Edit the presentation without matching a plain Entry.
        # Description: The fixture uses the existing Hybrid selection.
        presentation_field, = self.controls_of_type(editor, ttk.Combobox)
        # Input: The editor's action buttons and their visible text.
        # Output: A mapping from action captions to buttons.
        # Goal: Invoke Save through the actual modal control.
        # Description: Locates the action without relying on its layout frame or index.
        # Parameter editor_button. Input: Editor descendants. Output: One native button. Goal: Read caption. Description: Supplies a clickable command.
        editor_actions = {
            editor_button.cget("text"): editor_button
            for editor_button in self.controls_of_type(editor, ttk.Button)
        }

        year_field.delete(0, "end")
        year_field.insert(0, "11")
        # Input: The desktop error function used by the modal.
        # Output: A mock recording the validation error.
        # Goal: Check that a short year leaves the modal open.
        # Description: Prevents a real error dialog from blocking the test.
        with patch.object(movie_shelf.messagebox, "showerror") as show_error:
            editor_actions["Save"].invoke()
            show_error.assert_called_once()
            self.assertTrue(editor.winfo_exists())
        year_field.delete(0, "end")
        year_field.insert(0, "2012")
        title_field.delete(0, "end")
        title_field.insert(0, "Forest River")
        studio_field.insert(0, "Hawthorn Films")
        genre_field.insert(0, "Drama, Adventure")
        presentation_field.set("Hybrid")
        editor_actions["Save"].invoke()
        browser.update()
        self.assertFalse(editor.winfo_exists())
        self.assertEqual(browser.detail_title.cget("text"), "Forest River")
        self.assertIn("Hawthorn Films", browser.detail_facts.cget("text"))
        self.assertIn("Adventure", browser.detail_genres.cget("text"))
        self.assertIn("Adventure", browser.genre_combo["values"])

        browser.focus_force()
        browser.event_generate("<Escape>")
        browser.update()
        self.assertTrue(browser.home_view.winfo_ismapped())
