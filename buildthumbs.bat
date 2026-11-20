@echo off
setlocal
if exist "%~dp0movie_shelf.exe" goto use_executable
where python >nul 2>&1
if not errorlevel 1 goto use_python
where py >nul 2>&1
if not errorlevel 1 goto use_launcher
echo Python 3 is required to build Movie Shelf thumbnails.
pause
exit /b 1

:use_executable
"%~dp0movie_shelf.exe" --build-thumbs %*
goto check_result

:use_python
call python "%~dp0movie_shelf.py" --build-thumbs %*
goto check_result

:use_launcher
call py -3 "%~dp0movie_shelf.py" --build-thumbs %*

:check_result
set "movie_shelf_exit=%errorlevel%"
if not "%movie_shelf_exit%"=="0" (
    echo Thumbnail build failed. Check the library folder and app files.
    pause
)
exit /b %movie_shelf_exit%
