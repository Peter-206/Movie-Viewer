---
name: Movie Shelf
description: A portable Windows movie library framed around local cover artwork.
colors:
  brass: "#e4bb70"
  brass-hover: "#f2cd88"
  brass-disabled: "#384150"
  teal: "#86c9be"
  selected-slate: "#2f454d"
  shell: "#171d2b"
  panel: "#222c3e"
  well: "#111823"
  ink: "#f3f0e8"
  muted: "#b9c6d7"
  rule: "#415066"
  control: "#314057"
  control-hover: "#3e4f68"
  control-pressed: "#425771"
  control-disabled-text: "#8492a6"
  pager-disabled-text: "#8996a8"
typography:
  display:
    fontFamily: "Segoe UI Semibold"
    fontSize: "27pt"
    fontWeight: 600
  headline:
    fontFamily: "Segoe UI Semibold"
    fontSize: "20pt"
    fontWeight: 600
  brand:
    fontFamily: "Segoe UI Semibold"
    fontSize: "17pt"
    fontWeight: 600
  shelf:
    fontFamily: "Segoe UI Semibold"
    fontSize: "16pt"
    fontWeight: 600
  search:
    fontFamily: "Segoe UI"
    fontSize: "16pt"
    fontWeight: 400
  title:
    fontFamily: "Segoe UI Semibold"
    fontSize: "11pt"
    fontWeight: 600
  body:
    fontFamily: "Segoe UI"
    fontSize: "10pt"
    fontWeight: 400
  control:
    fontFamily: "Segoe UI Semibold"
    fontSize: "10pt"
    fontWeight: 600
  label:
    fontFamily: "Segoe UI"
    fontSize: "9pt"
    fontWeight: 400
rounded:
  square: "0px"
spacing:
  poster-outline: "2px"
  grid-row-inset: "4px"
  caption-gap: "5px"
  shelf-card-gap: "10px"
  detail-panel-inset: "18px"
  library-page-inset: "22px"
  page-inset: "24px"
components:
  button-primary:
    backgroundColor: "{colors.brass}"
    textColor: "{colors.well}"
    typography: "{typography.control}"
    rounded: "{rounded.square}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.brass-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.brass-disabled}"
    textColor: "{colors.muted}"
  button-standard:
    backgroundColor: "{colors.control}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.square}"
    padding: "7px 12px"
  button-standard-hover:
    backgroundColor: "{colors.control-hover}"
  button-standard-pressed:
    backgroundColor: "{colors.control-pressed}"
  button-standard-disabled:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.control-disabled-text}"
  button-pager:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.muted}"
    typography: "{typography.control}"
    rounded: "{rounded.square}"
    padding: "4px 9px"
  button-pager-disabled:
    backgroundColor: "{colors.shell}"
    textColor: "{colors.pager-disabled-text}"
  header-navigation:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.muted}"
    typography: "{typography.control}"
    rounded: "{rounded.square}"
    padding: "8px 12px"
  header-navigation-selected:
    backgroundColor: "{colors.selected-slate}"
    textColor: "{colors.teal}"
  field-search:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.search}"
    rounded: "{rounded.square}"
    padding: "6px 9px"
  field-metadata:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.square}"
    padding: "6px 8px"
  field-filter:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.square}"
    padding: "4px 6px"
  poster-card:
    backgroundColor: "{colors.shell}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.square}"
  facts-strip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.brass}"
    typography: "{typography.control}"
    padding: "5px 0px"
---

# Design System: Movie Shelf

## Overview

**Creative North Star: "Projection Booth"**

Movie Shelf uses an indigo shell and slate panels to frame the movie collection. Cover artwork supplies the visual variety. Square controls and Segoe UI fit the Windows desktop, with brass for the action that advances the movie choice and teal for navigation selection and focus.

The poster, title, and facts form a clear reading order on Discover and Details. In the Library, evenly sized wells and caption rows make the collection easy to scan. The shared header keeps search, navigation, and maintenance in reach as the user moves between views.

**Key Characteristics:**

- Local poster artwork shown whole in dark rectangular wells
- Persistent desktop navigation with a visible selected tab
- Brass movie actions and a ruled facts strip
- Paged library grid with two-line title space and fixed pager placement

## Colors

### Primary

- **Brass** highlights View movie and Play movie, and ties the facts strip to the title
- **Pale Brass** marks hover on the brass action. **Disabled Brass Slate** replaces the bright fill when playback is unavailable

### Secondary

- **Soft Teal** marks active navigation, poster hover and keyboard focus, entry focus, and selected dropdown options
- **Selected Slate** underlays the active navigation tab

### Neutral

- **Indigo Shell** backs the window and the poster grid. **Raised Slate** groups the shared header, featured pick, filters, and detail information
- **Deep Well** backs search and metadata fields, dropdown selections before opening, and letterboxed artwork. It also provides text contrast on brass buttons
- **Ivory** carries headings and primary text. **Cool Slate Text** carries status, labels, and secondary metadata
- **Slate Rule** defines field borders and the scrollbar treatment. Native separators divide the header and frame the facts strip
- **Control Slate**, **Hovered Control Slate**, and **Pressed Control Slate** distinguish the resting, hover, and press states of standard controls. **Disabled Control Text** and **Disabled Pager Text** distinguish unavailable actions

**The Accent Roles Rule.** Use brass for the primary movie action and the facts strip. Use teal for selection and focus, with a dark focus mark on brass buttons.

## Typography

The interface uses installed Windows Segoe UI faces. The text sizes in the frontmatter are Tk point sizes. Widget insets use pixels.

- **Display** (27 pt, Semibold) titles the featured pick and selected movie
- **Headline** (20 pt, Semibold) titles views and major sections. **Brand** (17 pt, Semibold) identifies the app, and **Shelf** (16 pt, Semibold) identifies rows and Library empty states
- **Search** (16 pt, regular) gives the shared search entry its larger input face
- **Title** (11 pt, Semibold) labels poster cards. **Label** (9 pt, regular) carries card metadata
- **Body** (10 pt, regular) supports labels, helper text, and status. **Control** (10 pt, Semibold) labels buttons and movie facts

## Layout

The shared header stays above all views. Discover and Library are on the left next to Movie Shelf. Search, Rescan, and Keys sit on the right. The client window opens at up to 1200 by 820 px and has an up-to-860 by 590 px minimum, adjusted to the initial screen fit on smaller displays.

- **Discover** scrolls vertically inside the window. The 246 px high feature pairs a 164 px wide poster with a wrapping information column and a bottom-aligned action. Recommendations advance every eight seconds while Discover is visible and can also be stepped manually. Each shelf pages four evenly distributed slots with a 10 px horizontal gap. Genre shelf counts use singular or plural wording as appropriate
- **Library** places the result count alongside the heading and four labeled selectors above the grid. The launcher requests six columns and two rows by default. The controller caps those settings against the available screen when the app starts. Window resizing refits the artwork and captions to those cells. The pager reserves space below the grid. With zero results, the view displays 0 movies. An empty collection also shows where to add movie folders before rescanning
- **Details** leaves Back above a two-column slate panel. The portrait well follows the panel height and width up to 480 px tall. The title, facts, and genres wrap in the remaining column. The playback action sits above the maintenance actions
- **Metadata editor** uses a native modal with two columns, labels on the left and fields on the right. The actions sit together at the bottom right

**The Caption Alignment Rule.** Reserve two title lines in Library cells and shorten overflow with an ellipsis on the second line.

## Elevation & Depth

Tonal layering distinguishes the shell, raised slate panels, and recessed poster and input wells. Native dividers and the change in surface tone define edges. The app uses flat fills without decorative shadows.

## Shapes

Navigation, controls, panels, and poster wells use square corners (0 px radius). Poster cards place a 2 px focus outline around the well and retain the original artwork proportions within the frame.

## Components

### Buttons

- Brass actions use dark text and generous padding (8 px vertical, 16 px horizontal). Hover lightens the brass. Disabled playback gains a slate fill and a file-status message
- Standard actions use ivory on slate (7 px vertical, 12 px horizontal), brighter hover and press fills, and muted disabled text
- Compact shelf and recommendation paging buttons use the panel fill (4 px vertical, 9 px horizontal). At the ends of a shelf, the corresponding button dims against the shell

### Inputs / Fields

- The search and metadata entries use recessed wells with a slate border, ivory text, and a teal focus border. Search is labeled in the header and uses slightly wider horizontal insets than the metadata editor
- Genre, Studio, Type, and Sort use labeled readonly native dropdowns. Their lists use ivory on the well with a teal highlight and dark text for the selected option

### Navigation

The header uses text buttons. The active Discover or Library button pairs teal text with a selected slate fill. The detail Back button names the originating view.

### Cards / Containers

- Poster cards show full covers against a dark well. Missing or unreadable art has a centered No poster caption. Titles sit below the well with a small gap (5 px), followed by muted metadata
- Discover cards align their 140 by 200 px artwork wells with the left edge of their wrapping captions. Library cards refit art and captions as the window resizes. Hover and keyboard focus color the poster rim teal. Enter and Space open a focused poster

### Facts Strip

Two horizontal rules enclose brass, semibold metadata on slate. The strip reads year, type, studio, and watch history in that order. Slashes separate the values, and missing type or studio leaves the remaining sequence intact. Genres sit below the strip.

## Do's and Don'ts

### Do

- Do preserve the whole cover and center it in the artwork well
- Do keep the feature artwork, title, facts, and position in sync when a pick changes
- Do pair empty states with the appropriate recovery action, such as Clear filters or Rescan library

### Don't

- Don't crop covers to fill a frame
- Don't use brass as the active navigation color
- Don't place the Library pager inside the resizing poster grid

Implementation and review evidence are in [movie_shelf_ui.py](movie_shelf_ui.py), [movie_shelf.py](movie_shelf.py), and the [native window captures](.impeccable/review/).
