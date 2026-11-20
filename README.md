# Movie Shelf

Movie Shelf browses a local movie collection and opens movies in the Windows default player. Keep the application beside the collection's movie folders and `movies.db`

## Run

Double-click `run.bat` or `movie_shelf.exe`. The launcher prefers the executable. To run from source, install Pillow and use the following command

```powershell
python movie_shelf.py
```

Source delivery needs both `movie_shelf.py` and `movie_shelf_ui.py`. The standalone executable includes both modules

Use an explicit root to open a different collection

```powershell
python movie_shelf.py --root "E:\Movies"
```

The default collection is beside the source script or executable, regardless of the current working directory. Keep `movies.db` with the collection when moving it to another drive

## Library

- Discover presents recommendations, popular movies and genre shelves
- Library combines search, genre, studio and type filters with six sort orders
- Select a poster to open details, play the movie, edit metadata or open its folder
- Right-click a library poster to edit metadata
- Rescan finds folder changes and refreshes the catalog
- Press F1 for the complete keyboard guide

Startup and Rescan normalize the selected main video's name to `movie` with its existing extension. Other videos remain in place and existing destination files are preserved. Test a new setup against a copy of your collection when evaluating that behavior

## Artwork tools

`buildthumbs.bat` creates missing thumbnails from local covers. Existing thumbnails remain intact. The executable and source also accept maintenance flags directly

```powershell
.\movie_shelf.exe --build-thumbs
.\movie_shelf.exe --fetch-covers
```

Cover fetching uses the existing IMDb matching flow and needs internet access. Existing covers remain intact

## Build and verify

The source uses Python, Tkinter and Pillow. Building the Windows executable also requires PyInstaller

```powershell
python -B -m unittest discover -s .tests -v
python -m PyInstaller --noconfirm --distpath .build-ui\dist --workpath .build-ui\work movie_shelf.spec
```

Tests use temporary libraries. Build output stays in a hidden folder because ordinary top-level folders are interpreted as movie entries

The rebuild's behavior checklist is in `REBUILD-CONTRACT.md`. Product context, design decisions and agent responsibilities are recorded in `PRODUCT.md`, `DESIGN.md` and `REBUILD-PROGRESS.md`
