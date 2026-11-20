"""Smoke-test the Windows package and its batch entry points in isolated roots."""

import ctypes
from ctypes import wintypes
from pathlib import Path
from shutil import copyfile
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from PIL import Image
from psutil import NoSuchProcess, Process


# Input: This file's path and the Windows User32 library.
# Output: The source directory and typed window API handles.
# Goal: Keep package verification independent from the launch working directory.
# Description: User32 inspection identifies windows without touching unrelated processes.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
# Input: The Windows runtime.
# Output: The loaded User32 API.
# Goal: Find and close only the window launched by this smoke check.
# Description: Signatures preserve native handle widths on 64-bit systems.
WINDOWS_API = ctypes.WinDLL("user32", use_last_error=True)
WINDOWS_API.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
WINDOWS_API.FindWindowExW.restype = wintypes.HWND
WINDOWS_API.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
WINDOWS_API.GetWindowThreadProcessId.restype = wintypes.DWORD
WINDOWS_API.IsWindowVisible.argtypes = [wintypes.HWND]
WINDOWS_API.IsWindowVisible.restype = wintypes.BOOL
WINDOWS_API.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
WINDOWS_API.PostMessageW.restype = wintypes.BOOL

# Input: The Win32 window message definition.
# Output: The registered numeric close message.
# Goal: Ask the selected native window to close cleanly.
# Description: Triggers the app's own shutdown handler.
CLOSE_WINDOW = 0x0010


# Input: A process launched by the smoke check.
# Output: The matching application's native window handle, or None.
# Goal: Wait until the GUI is instantiated under the expected process tree.
# Description: PyInstaller one-file apps create their visible window in a child process.
# Parameter process. Input: Subprocess instance. Output: Process ID and status. Goal: Scope lookup. Description: Owns the executable or launcher process tree.
def find_movie_shelf_window(process):
    try:
        # Input: The subprocess started by this test.
        # Output: The process inspection object.
        # Goal: Identify the bootloader's descendants as well as the launch process.
        # Description: The batch launcher adds one more level to the same tree.
        launch_process = Process(process.pid)
        # Input: The launch process and its descendants.
        # Output: IDs allowed to own the smoke window.
        # Goal: Restrict native operations to the isolated package launch.
        # Description: Matches an ID before returning its window handle.
        # Parameter child_process. Input: Descendant processes. Output: One process ID. Goal: Identify ownership. Description: Includes the one-file executable's child.
        allowed_process_ids = {process.pid, *(child_process.pid for child_process in launch_process.children(recursive=True))}
    except NoSuchProcess:
        return None

    # Input: Visible top-level windows named Movie Shelf.
    # Output: The candidate handle currently being inspected.
    # Goal: Enumerate matching captions until the test launch is found.
    # Description: FindWindowExW starts at the first window with a null handle.
    candidate_window = WINDOWS_API.FindWindowExW(None, None, None, "Movie Shelf")
    # Input: Each candidate's native handle.
    # Output: The Windows process ID owning that handle.
    # Goal: Distinguish the fixture from any existing Movie Shelf window.
    # Description: Is overwritten by User32 for each candidate.
    owner_process_id = wintypes.DWORD()
    while candidate_window:
        WINDOWS_API.GetWindowThreadProcessId(candidate_window, ctypes.byref(owner_process_id))
        if owner_process_id.value in allowed_process_ids and WINDOWS_API.IsWindowVisible(candidate_window):
            return candidate_window
        candidate_window = WINDOWS_API.FindWindowExW(None, candidate_window, None, "Movie Shelf")
    return None


# Input: A package or batch command, a foreign working directory, and a test video path.
# Output: Successful startup, a renamed fixture video, and a clean native close.
# Goal: Verify source-independent package loading and correct root selection.
# Description: Waits for the target window, verifies writes, and sends a close message only to its handle.
# Parameter command. Input: Argument list or quoted cmd command. Output: Launch request. Goal: Test a normal entry point. Description: Selects explicit or adjacent library roots.
# Parameter working_directory. Input: Temporary Path. Output: Working directory. Goal: Exercise launch from elsewhere. Description: Must remain free of catalog writes.
# Parameter movie_folder. Input: Folder in fixture library. Output: Expected mutation target. Goal: Verify root selection. Description: Starts with a noncanonical video name.
def verify_window_launch(command, working_directory, movie_folder):
    # Input: The selected native entry point and unrelated working directory.
    # Output: The process this test owns.
    # Goal: Search its descendants and wait for graceful exit.
    # Description: Hides a batch command prompt while leaving the Tk window visible.
    process = subprocess.Popen(command, cwd=working_directory, creationflags=subprocess.CREATE_NO_WINDOW)
    # Input: The launch time and a 20-second allowance.
    # Output: A deadline for package initialization.
    # Goal: Bound the wait for PyInstaller extraction and Tk startup.
    # Description: The deadline formula adds the allowed time to the monotonic clock.
    startup_deadline = monotonic() + 20
    # Input: The package process tree.
    # Output: A handle only after the smoke window is found.
    # Goal: Close only a verified fixture window if assertions fail.
    # Description: Keeps the expected handle independent from other desktop windows.
    application_window = None
    try:
        while application_window is None and process.poll() is None and monotonic() < startup_deadline:
            application_window = find_movie_shelf_window(process)
            if application_window is None:
                sleep(0.10)
        assert application_window, f"Movie Shelf did not open for {command}"
        assert (movie_folder.parent / "movies.db").is_file()
        assert (movie_folder / "movie.MP4").is_file()
        assert not (working_directory / "movies.db").exists()
    finally:
        if application_window:
            if not WINDOWS_API.PostMessageW(application_window, CLOSE_WINDOW, 0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
    assert process.wait(timeout=20) == 0


# Input: A disposable fixture movie path.
# Output: A new movie folder holding an intentionally noncanonical video.
# Goal: Observe which root startup selected and whether maintenance skipped renaming.
# Description: Uses a small fake video with a case-sensitive extension check.
# Parameter movie_folder. Input: Fixture Path. Output: New movie location. Goal: Isolate writes. Description: Parent is unique to this verification process.
def create_movie_fixture(movie_folder):
    movie_folder.mkdir(parents=True)
    (movie_folder / "Feature Release.MP4").write_bytes(b"Movie Shelf smoke fixture")


# Input: A source or packaged command and a temporary movie with a cover.
# Output: A generated thumbnail, unchanged cover, and unchanged video name.
# Goal: Exercise both maintenance flags without opening a GUI or fetching from the network.
# Description: Every movie has a valid cover before the cover command runs.
# Parameter command. Input: Executable and optional script argument. Output: Maintenance prefix. Goal: Choose source or package. Description: Followed by the same CLI flags in either case.
# Parameter movie_folder. Input: Test Path. Output: Maintenance fixture. Goal: Isolate I/O. Description: Contains a known image and video after setup.
# Parameter working_directory. Input: Temporary Path. Output: Unrelated current directory. Goal: Exercise root selection. Description: Both commands explicitly receive the fixture root.
def verify_maintenance(command, movie_folder, working_directory):
    create_movie_fixture(movie_folder)
    # Input: Generated test artwork.
    # Output: The path to a valid local cover.
    # Goal: Exercise poster discovery and the cover-fetch skip branch.
    # Description: The existing cover prevents any network request.
    cover_path = movie_folder / "cover.jpg"
    Image.new("RGB", (300, 450), "#674e5c").save(cover_path)
    # Input: The fixture poster on disk.
    # Output: Original cover bytes for an exact preservation check.
    # Goal: Verify that maintenance leaves a present cover intact.
    # Description: Compared after the executable and thumbnail writer run.
    cover_bytes = cover_path.read_bytes()
    subprocess.run(
        [*command, "--root", str(movie_folder.parent), "--build-thumbs", "--thumb-w", "80", "--thumb-h", "120"],
        cwd=working_directory, timeout=30, check=True,
    )
    # Input: The thumbnail written by the maintenance command.
    # Output: The decoded image header.
    # Goal: Verify the package's Pillow data and argument forwarding.
    # Description: The handle closes before the temporary library is removed.
    with Image.open(movie_folder / "thumb.jpg") as thumbnail:
        assert thumbnail.size == (80, 120)
    subprocess.run(
        [*command, "--root", str(movie_folder.parent), "--fetch-covers"],
        cwd=working_directory, timeout=30, check=True,
    )
    assert cover_path.read_bytes() == cover_bytes
    assert (movie_folder / "Feature Release.MP4").is_file()
    assert not (movie_folder.parent / "movies.db").exists()


# Input: The newly built executable path supplied as the only script argument.
# Output: Smoke-check results for CLI maintenance, default portable startup, and run.bat.
# Goal: Verify the exact new package without launching against the live library.
# Description: All launches run from a distinct working directory with disposable media.
def main():
    # Input: The staged package path from the command line.
    # Output: The absolute executable path to copy into the fixture.
    # Goal: Test the selected build rather than any installed counterpart.
    # Description: Fails before staging if the path does not exist.
    executable_source = Path(sys.argv[1]).resolve(strict=True)
    # Input: The system temporary directory.
    # Output: A fresh directory for all portable launch and maintenance fixtures.
    # Goal: Keep realistic space-containing paths and isolate app writes.
    # Description: Removed only after package and batch processes exit.
    with TemporaryDirectory(prefix="movie-shelf-package-") as fixture_directory:
        # Input: The temporary directory and a foreign working folder name.
        # Output: An empty directory distinct from the library and executable.
        # Goal: Verify the application does not use the current working directory as its root.
        # Description: All source and package launches receive this same working directory.
        working_directory = Path(fixture_directory) / "Unrelated Working Directory"
        working_directory.mkdir()
        # Input: The fixture directory and the portable folder name.
        # Output: The new executable and default library location.
        # Goal: Reproduce moving the package to another directory.
        # Description: The batch launcher sits beside the staged executable.
        package_directory = Path(fixture_directory) / "Portable Movies"
        package_directory.mkdir()
        # Input: The built executable and a new destination beside default-root media.
        # Output: The copied executable that the smoke test will launch.
        # Goal: Keep package verification independent from the source directory.
        # Description: Its adjacent folders contain only fixture movies.
        package_path = package_directory / "movie_shelf.exe"
        copyfile(executable_source, package_path)

        verify_maintenance([sys.executable, "-B", str(SOURCE_ROOT / "movie_shelf.py")],
                           Path(fixture_directory) / "Source Maintenance" / "Source Poster", working_directory)
        print("Source thumbnail build and cover skip passed")
        verify_maintenance([str(package_path)],
                           Path(fixture_directory) / "Package Maintenance" / "Package Poster", working_directory)
        print("Packaged thumbnail build and cover skip passed")

        # Input: A new movie adjacent to the staged executable.
        # Output: The fixture that default startup should discover and rename.
        # Goal: Confirm that frozen default root uses the executable directory.
        # Description: The launch passes no root option and runs from elsewhere.
        default_movie = package_directory / "Default Root Movie"
        create_movie_fixture(default_movie)
        verify_window_launch([str(package_path)], working_directory, default_movie)
        print("Packaged window opened and closed with its adjacent default library")

        # Input: The real batch launcher and a staged path beside the executable.
        # Output: An isolated copy of the launcher.
        # Goal: Exercise executable-first dispatch without running the live library's copy.
        # Description: Both the launcher and its root argument contain spaces.
        launcher_path = package_directory / "run.bat"
        copyfile(SOURCE_ROOT / "run.bat", launcher_path)
        # Input: A library root outside the package directory.
        # Output: The fixture for the launcher's explicit root argument.
        # Goal: Prove root forwarding overrides the executable-adjacent default.
        # Description: The resulting catalog and rename must occur in this separate location.
        explicit_movie = Path(fixture_directory) / "Explicit Library" / "Explicit Root Movie"
        create_movie_fixture(explicit_movie)
        verify_window_launch(
            f'cmd.exe /d /s /c ""{launcher_path}" --root "{explicit_movie.parent}""',
            working_directory, explicit_movie,
        )
        print("run.bat opened the packaged window using its forwarded quoted root")

        # Input: The original thumbnail launcher and the portable test directory.
        # Output: A copy of buildthumbs.bat beside the staged executable.
        # Goal: Exercise thumbnail batch dispatch and quoting with no GUI startup.
        # Description: Uses the same executable as the run.bat check.
        thumbnail_launcher = package_directory / "buildthumbs.bat"
        copyfile(SOURCE_ROOT / "buildthumbs.bat", thumbnail_launcher)
        # Input: A separate thumbnail fixture directory path.
        # Output: A cover and fake video for the batch maintenance command.
        # Goal: Verify that batch startup passes dimensions and bypasses normal scans.
        # Description: Defaults would produce different dimensions than this test requests.
        thumbnail_movie = Path(fixture_directory) / "Batch Maintenance" / "Batch Poster"
        create_movie_fixture(thumbnail_movie)
        Image.new("RGB", (300, 450), "#674e5c").save(thumbnail_movie / "cover.jpg")
        subprocess.run(
            f'cmd.exe /d /s /c ""{thumbnail_launcher}" --root "{thumbnail_movie.parent}" --thumb-w 80 --thumb-h 120"',
            cwd=working_directory, timeout=30, check=True,
        )
        # Input: The thumbnail produced by the relocated batch file.
        # Output: The image header showing the forwarded dimensions.
        # Goal: Confirm the maintenance action ran through the batch file.
        # Description: Closes after checking size to permit Windows cleanup.
        with Image.open(thumbnail_movie / "thumb.jpg") as thumbnail:
            assert thumbnail.size == (80, 120)
        assert (thumbnail_movie / "Feature Release.MP4").is_file()
        assert not (thumbnail_movie.parent / "movies.db").exists()
        print("buildthumbs.bat generated a thumbnail with its forwarded quoted root and dimensions")


if __name__ == "__main__":
    main()
