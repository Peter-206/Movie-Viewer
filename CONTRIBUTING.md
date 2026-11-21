# Contributing

Open an issue before starting a large change. Explain the problem, expected behavior and how to reproduce it with a small synthetic library.

## Local checks

Use Windows and Python 3.13 with Tcl/Tk enabled. From the repository root, run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -B -m unittest discover -s .tests -v
.\.venv\Scripts\python -m PyInstaller --noconfirm --distpath .build-ui\dist --workpath .build-ui\work movie_shelf.spec
.\.venv\Scripts\python .tests\verify_movie_shelf_package.py .build-ui\dist\movie_shelf.exe
```

Use temporary fixtures rather than a real collection. Startup and Rescan can rename video files.

## Pull requests

- Describe the change and checks you actually ran
- Keep movie files, artwork, databases, secrets and personal paths out of commits and screenshots
- Preserve existing comments and keep changes focused
- Only contribute material you have permission to share

The root-folder exclusions in `.gitignore` protect the private collection in this workspace. Add an explicit exception when introducing a legitimate source folder. Review `git diff --cached --stat` before committing.
