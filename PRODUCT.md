# Movie Shelf

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop, using native Python and Tkinter. This platform is outside Impeccable's web and mobile platform enum

## Users

Alex browses and plays a personal collection of movies stored in folders on a portable drive

## Product Purpose

Find something to watch, play it with the operating system's associated player, and maintain useful local metadata

## Operating Context

The user confirmed a portable Windows desktop app with the same deliverables. The application, database, and movie folders travel together. Existing movie artwork is the primary visual asset

## Capabilities and Constraints

- Preserve discovery, recommendations, searchable paged browsing, genre, studio and presentation filters, and all existing sort orders
- Preserve detail pages, playback, folder opening, metadata editing, watch counts, keyboard shortcuts and fullscreen
- Preserve the SQLite catalog, IDs, metadata, portable path synchronization, existing movie folders and artwork
- Preserve all CLI options, cover fetching, thumbnail building, source entry point, Windows launchers and executable
- Rebuild the UI freely, with design choices delegated to the implementation team
- Test filesystem changes only against disposable libraries

## Brand Commitments

Movie Shelf remains the delivered application. No visual palette or typeface is pinned

## Evidence on Hand

movie_shelf.py, movie_shelf.spec, run.bat, buildthumbs.bat, movies.db and local cover images document the existing product

## Product Principles

- Preserve local ownership and portability
- Keep browsing and playback direct
- Make metadata and library maintenance discoverable
- Keep the application usable with a keyboard
