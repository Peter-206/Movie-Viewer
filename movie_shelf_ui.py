"""Native Movie Shelf views. The controller owns the catalog, filesystem and playback."""

import tkinter as tk
from functools import partial
from tkinter import font as tkfont, ttk

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk


# Input: Projection booth palette. Output: Window indigo. Goal: Frame local artwork. Description: Main application background.
SHELL = "#171d2b"
# Input: Projection booth palette. Output: Raised slate. Goal: Group controls and information. Description: Used by the header and feature surface.
PANEL = "#222c3e"
# Input: Projection booth palette. Output: Dark blue. Goal: Separate poster wells from surrounding panels. Description: Also fills text entry fields.
WELL = "#111823"
# Input: Projection booth palette. Output: Ivory. Goal: Keep primary text readable. Description: Used for headings and body copy.
INK = "#f3f0e8"
# Input: Projection booth palette. Output: Cool light slate. Goal: Distinguish secondary information. Description: Used for labels and facts.
MUTED = "#b9c6d7"
# Input: Projection booth palette. Output: Brass. Goal: Highlight the primary action. Description: Used for buttons and film facts.
BRASS = "#e4bb70"
# Input: Projection booth palette. Output: Teal. Goal: Indicate selection and focus. Description: Used by active navigation and keyboard focus.
TEAL = "#86c9be"
# Input: Projection booth palette. Output: Slate outline. Goal: Distinguish edges on dark surfaces. Description: Used by rules and text fields.
RULE = "#415066"


# Input: Event binding and command. Output: Tk break signal. Goal: Run a callback once. Description: Consumes the event before other navigation bindings.
# Parameter callback. Input: Bound callable. Output: Action to invoke. Goal: Connect a native control. Description: Runs without a Tk event argument.
# Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
def activate(callback, event):
    callback()
    return "break"


# Input: Saved catalog metadata. Output: A compact viewing history string. Goal: Use natural singular and plural forms. Description: A zero count identifies an unwatched movie.
# Parameter movie. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
def watch_history(movie):
    return f"Watched {movie.watch_count} time{'s' if movie.watch_count != 1 else ''}"


# Input: Movie fields. Output: One line of film facts. Goal: Keep frequently scanned details together. Description: Drops absent optional fields and preserves year and watch history.
# Parameter movie. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
def movie_facts(movie):
    return "    /    ".join(filter(None, (str(movie.year or "Year unknown"), movie.presentation,
                                          movie.studio, watch_history(movie))))


class MovieShelfPresentation:
    """The desktop presentation mixed into the existing MovieBrowser controller."""

    # Input: Current Tk display. Output: Coordinated native styles. Goal: Make each component legible on its own surface. Description: Configures shared fonts, state colors and keyboard focus.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _configure_shelf_styles(self):
        # Input: Active Tk interpreter. Output: ttk style manager. Goal: Style this window. Description: Updates the clam theme selected by the controller.
        style = ttk.Style(self)
        self.configure(background=SHELL)
        style.configure(".", font=("Segoe UI", 10), background=SHELL, foreground=INK)
        style.configure("TFrame", background=SHELL)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Tile.TFrame", background=PANEL)
        style.configure("TLabel", background=SHELL, foreground=INK)
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("Status.TLabel", background=SHELL, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Brand.TLabel", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 17))
        style.configure("Heading.TLabel", background=SHELL, foreground=INK, font=("Segoe UI Semibold", 20))
        style.configure("Shelf.TLabel", background=SHELL, foreground=INK, font=("Segoe UI Semibold", 16))
        style.configure("Title.TLabel", background=SHELL, foreground=INK, font=("Segoe UI Semibold", 11))
        style.configure("Meta.TLabel", background=SHELL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Movie.TLabel", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 27))
        style.configure("Facts.TLabel", background=PANEL, foreground=BRASS, font=("Segoe UI Semibold", 10))
        style.configure("TSeparator", background=RULE)
        style.configure("TScrollbar", background=RULE, troughcolor=SHELL, arrowcolor=MUTED,
                        lightcolor=RULE, darkcolor=RULE, borderwidth=0, arrowsize=12)
        style.configure("TButton", background="#314057", foreground=INK, padding=(12, 7),
                        font=("Segoe UI Semibold", 10), borderwidth=0, focuscolor=TEAL)
        style.map("TButton", background=[("disabled", PANEL), ("pressed", "#425771"), ("active", "#3e4f68")],
                  foreground=[("disabled", "#8492a6")])
        style.configure("Nav.TButton", background=PANEL, foreground=MUTED, padding=(12, 8))
        style.configure("Selected.Nav.TButton", background="#2f454d", foreground=TEAL)
        style.configure("Accent.TButton", background=BRASS, foreground=WELL, padding=(16, 8), focuscolor=WELL)
        style.map("Accent.TButton", background=[("disabled", "#384150"), ("active", "#f2cd88")],
                  foreground=[("disabled", MUTED), ("!disabled", WELL)])
        style.configure("RowNav.TButton", background=PANEL, foreground=MUTED, padding=(9, 4), borderwidth=0)
        style.map("RowNav.TButton", background=[("active", "#3e4f68"), ("disabled", SHELL)],
                  foreground=[("disabled", "#8996a8")])
        style.configure("TEntry", padding=(8, 6), fieldbackground=WELL, foreground=INK, insertcolor=INK,
                        bordercolor=RULE, lightcolor=WELL, darkcolor=WELL)
        style.configure("Search.TEntry", padding=(9, 6), fieldbackground=WELL, foreground=INK,
                        insertcolor=INK, bordercolor=RULE, lightcolor=WELL, darkcolor=WELL)
        style.configure("TCombobox", padding=(6, 4), bordercolor=RULE, lightcolor=WELL, darkcolor=WELL)
        style.map("TCombobox", fieldbackground=[("readonly", WELL)], background=[("readonly", PANEL)],
                  foreground=[("readonly", INK)], arrowcolor=[("readonly", MUTED)])
        style.map("TEntry", bordercolor=[("focus", TEAL)])
        self.option_add("*TCombobox*Listbox.background", WELL)
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", TEAL)
        self.option_add("*TCombobox*Listbox.selectForeground", WELL)

    # Input: Available screen and controller state. Output: Application shell and Library view. Goal: Provide persistent navigation. Description: Builds the common header, library controls and detail frame.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _build_modern_ui(self):
        self._configure_shelf_styles()
        self.title("Movie Shelf")
        # Input: Available desktop pixels. Output: Initial client width. Goal: Fit common desktop screens. Description: Window margin subtraction leaves space for the OS frame.
        initial_width = min(1200, max(640, self.winfo_screenwidth() - 64))
        # Input: Available desktop pixels. Output: Initial client height. Goal: Keep the bottom controls reachable. Description: Window margin subtraction reserves space for the taskbar and title bar.
        initial_height = min(820, max(480, self.winfo_screenheight() - 110))
        self.minsize(min(860, initial_width), min(590, initial_height))
        self.geometry(f"{initial_width}x{initial_height}")
        # Input: Root window. Output: Persistent top navigation. Goal: Keep all destinations reachable. Description: Stays mapped when changing views.
        header = ttk.Frame(self, padding=(20, 10), style="Panel.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Movie Shelf", style="Brand.TLabel").pack(side="left", padx=(0, 24))
        # Input: Header and Discover callback. Output: Discover tab. Goal: Navigate home. Description: Its selected appearance follows the current view.
        self.discover_tab = ttk.Button(header, text="Discover", width=9, command=self._show_home, style="Nav.TButton")
        self.discover_tab.pack(side="left", padx=(0, 3))
        # Input: Header and Library callback. Output: Library tab. Goal: Navigate to results. Description: Its selected appearance follows the current view.
        self.library_tab = ttk.Button(header, text="Library", width=8, command=self._open_library, style="Nav.TButton")
        self.library_tab.pack(side="left")
        ttk.Button(header, text="Keys", command=self._shortcut_help, style="Nav.TButton").pack(side="right")
        ttk.Button(header, text="Rescan", command=self._rescan, style="Nav.TButton").pack(side="right", padx=(5, 2))
        # Input: User input on Discover. Output: Discover search text. Goal: Allow a fresh search from home. Description: Retains the entry when changing views.
        self.home_search = tk.StringVar(self)
        # Input: User input on Library. Output: Library search text. Goal: Filter the catalog. Description: Controller matches this query against all metadata.
        self.search_var = tk.StringVar(self)
        # Input: Header and search state. Output: Shared search widget. Goal: Keep search visible on every screen. Description: Navigation swaps the active text variable.
        self.library_search_entry = ttk.Entry(header, textvariable=self.search_var, width=23, style="Search.TEntry")
        self.library_search_entry.pack(side="right", padx=(0, 6))
        # Input: Shared search entry. Output: Discover shortcut target. Goal: Support existing shortcut dispatch. Description: Both names identify the visible entry.
        self.home_search_entry = self.library_search_entry
        self.library_search_entry.bind("<Return>", self._submit_search)
        self.library_search_entry.bind("<KeyRelease>", self._live_search)
        ttk.Label(header, text="Search", style="PanelMuted.TLabel").pack(side="right", padx=(10, 7))
        ttk.Separator(self).pack(fill="x")
        # Input: Main window. Output: Library screen. Goal: Group filters, paging and poster grid. Description: Mapped by the navigation controller.
        self.browser_view = ttk.Frame(self, padding=(22, 12, 22, 12))
        # Input: Library header. Output: Section heading row. Goal: Pair title with result count. Description: Positions the metadata beside the heading.
        heading = ttk.Frame(self.browser_view)
        heading.pack(fill="x", pady=(0, 9))
        ttk.Label(heading, text="Library", style="Heading.TLabel").pack(side="left")
        # Input: Result count from controller. Output: Summary label. Goal: Explain the current filter result. Description: Updates whenever the page renders.
        self.status = ttk.Label(heading, style="Status.TLabel")
        self.status.pack(side="left", padx=15, anchor="s", pady=4)
        # Input: Library screen. Output: Filter controls row. Goal: Keep filters above their results. Description: Groups four labeled native selectors.
        filters = ttk.Frame(self.browser_view, padding=(10, 7), style="Panel.TFrame")
        filters.pack(fill="x", pady=(0, 12))
        # Input: Genre selector. Output: Genre variable. Goal: Filter by genre. Description: Controller reads the active choice.
        self.genre_var = tk.StringVar(self, "All genres")
        # Input: Studio selector. Output: Studio variable. Goal: Filter by studio. Description: Controller reads the active choice.
        self.studio_var = tk.StringVar(self, "All studios")
        # Input: Presentation selector. Output: Type variable. Goal: Filter by presentation. Description: Controller reads the active choice.
        self.presentation_var = tk.StringVar(self, "All types")
        # Input: Sort selector. Output: Sort variable. Goal: Order visible movies. Description: The existing controller implements all six choices.
        self.sort_var = tk.StringVar(self, "Title (A-Z)")
        # Input: Genre variable. Output: Genre dropdown. Goal: Update available genres. Description: Retained for catalog refresh.
        self.genre_combo = self._filter_combo(filters, "Genre", self.genre_var, 0)
        # Input: Studio variable. Output: Studio dropdown. Goal: Update available studios. Description: Retained for catalog refresh.
        self.studio_combo = self._filter_combo(filters, "Studio", self.studio_var, 2)
        # Input: Type variable. Output: Type dropdown. Goal: Update available types. Description: Retained for catalog refresh.
        self.presentation_combo = self._filter_combo(filters, "Type", self.presentation_var, 4)
        # Input: Sort variable. Output: Sort dropdown. Goal: Select the result order. Description: All orders reuse the controller's exact names.
        self.sort_combo = self._filter_combo(filters, "Sort", self.sort_var, 6, (
            "Title (A-Z)", "Title (Z-A)", "Year (newest)", "Year (oldest)", "Most watched", "Least watched"))
        self._refresh_filter_choices()
        # Input: Library screen. Output: Fixed footer. Goal: Keep page controls visible. Description: Packed before the expanding grid to reserve its space.
        footer = ttk.Frame(self.browser_view)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        # Input: Controller page. Output: Page indicator. Goal: Show the current page. Description: Retained for paging updates.
        self.page_label = ttk.Label(footer, style="Status.TLabel")
        self.page_label.pack(side="left")
        # Input: Page controller. Output: Next button. Goal: Move forward. Description: Disabled on the final page.
        self.next_btn = ttk.Button(footer, text="Next", command=self._next_page)
        self.next_btn.pack(side="right")
        # Input: Page controller. Output: Previous button. Goal: Move back. Description: Disabled on the first page.
        self.prev_btn = ttk.Button(footer, text="Previous", command=self._prev_page)
        self.prev_btn.pack(side="right", padx=7)
        # Input: Remaining Library space. Output: Grid container. Goal: Display the requested rows and columns. Description: Its allocated size controls artwork scaling.
        self.grid = ttk.Frame(self.browser_view)
        self.grid.pack(fill="both", expand=True)
        self.grid.grid_propagate(False)
        # Input: Current page capacity. Output: Reusable poster and caption slots. Goal: Keep lazy loading compatible. Description: Each tuple owns a poster, title and metadata label.
        self.slots = []
        # Input: Native caption typography. Output: Measurable font. Goal: Fit titles exactly. Description: The same font draws and measures each card caption.
        self.card_font = tkfont.Font(self, family="Segoe UI Semibold", size=11)
        # Input: Requested row count. Output: Row index. Goal: Lay out library cards. Description: Rows receive equal height.
        for row in range(self.rows):
            self.grid.rowconfigure(row, weight=1, uniform="movies")
            # Input: Requested column count. Output: Column index. Goal: Lay out library cards. Description: Columns receive equal width.
            for column in range(self.cols):
                self.grid.columnconfigure(column, weight=1, uniform="movies")
                self._build_library_slot(row, column)
        # Input: Library grid. Output: Empty state. Goal: Explain zero results. Description: Placed only while the result set is empty.
        self.empty_results = ttk.Frame(self.grid)
        # Input: Current filter state. Output: Empty heading. Goal: Describe the absence of movies. Description: Changes when the collection itself is empty.
        self.empty_heading = ttk.Label(self.empty_results, style="Shelf.TLabel")
        self.empty_heading.pack()
        # Input: Empty catalog state. Output: Recovery instruction. Goal: Explain how to add movies. Description: Shown only when the active library has no movies.
        self.empty_instruction = ttk.Label(self.empty_results, style="Status.TLabel",
                                           text="Add movie folders beside Movie Shelf, then rescan.")
        # Input: Current filter state. Output: Empty recovery action. Goal: Restore a useful screen. Description: Clears filters or rescans an empty collection.
        self.empty_action = ttk.Button(self.empty_results)
        self.empty_action.pack(pady=(12, 0))
        # Input: Grid configure events. Output: Pending resize callback. Goal: Coalesce rapid window changes. Description: The timer is canceled at shutdown.
        self.resize_job = None
        self.grid.bind("<Configure>", self._queue_grid_resize)
        # Input: Root window. Output: Detail screen. Goal: Inspect a selected movie. Description: Shares navigation with the other views.
        self.detail_view = ttk.Frame(self, padding=(24, 16))
        self._build_detail_view()

    # Input: Parent, label, variable and grid location. Output: Readonly combobox. Goal: Present a labeled filter. Description: Expands its column and routes selection to the controller.
    # Parameter self. Input: Browser instance. Output: Active window. Goal: Connect filtering. Description: Owns the catalog and filter handler.
    # Parameter parent. Input: Filter toolbar. Output: Container. Goal: Place controls. Description: Owns the label and dropdown.
    # Parameter caption. Input: Filter name. Output: Visible label. Goal: Identify the criterion. Description: Appears before the selector.
    # Parameter attribute. Input: Tk StringVar. Output: Active selection. Goal: Synchronize filter state. Description: Connects the dropdown to the controller.
    # Parameter column. Input: Grid position. Output: Label column. Goal: Align the toolbar. Description: Places the dropdown in the next column.
    # Parameter values. Input: Optional choice sequence. Output: Dropdown entries. Goal: Supply known options. Description: Catalog-backed choices are filled on refresh.
    def _filter_combo(self, parent, caption, attribute, column, values=()):
        ttk.Label(parent, text=caption, style="PanelMuted.TLabel").grid(row=0, column=column, padx=(4, 5))
        # Input: Filter variable and available choices. Output: Combobox widget. Goal: Edit one criterion. Description: A short requested width lets the outer grid distribute free space.
        selector = ttk.Combobox(parent, textvariable=attribute, values=values, width=8, state="readonly")
        selector.grid(row=0, column=column + 1, sticky="ew", padx=(0, 8))
        parent.columnconfigure(column + 1, weight=1, uniform="filter")
        selector.bind("<<ComboboxSelected>>", partial(activate, self._apply_filter))
        return selector

    # Input: Current catalog choices. Output: Valid dropdown selections. Goal: Remove obsolete filters after edits. Description: Clears only values that disappeared from the available choices.
    # Parameter self. Input: Browser instance. Output: Active window. Goal: Refresh selector state. Description: Owns the controller's dropdown widgets.
    def _refresh_filter_choices(self):
        super()._refresh_filter_choices()
        # Input: The three catalog-derived selectors. Output: One dropdown. Goal: Validate its current selection. Description: The first choice always accepts all values.
        for selector in (self.genre_combo, self.studio_combo, self.presentation_combo):
            if selector.get() not in selector["values"]:
                selector.current(0)

    # Input: Active view and shared entry. Output: Filtered Library. Goal: Submit a search. Description: Discover transfers its text and Details enters Library.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _submit_search(self, event):
        if self.home_view.winfo_ismapped():
            self._search_from_home()
        else:
            self._open_library()
            self._apply_filter()
        return "break"

    # Input: Entry key release. Output: Updated visible results. Goal: Provide live Library search. Description: Other screens wait for Return.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _live_search(self, event):
        if self.browser_view.winfo_ismapped() and event.keysym != "Return":
            self._apply_filter()

    # Input: Filter defaults. Output: Unfiltered Library results. Goal: Recover from an empty search. Description: Restores all filter values together.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _clear_filters(self):
        self.search_var.set("")
        self.genre_var.set("All genres")
        self.studio_var.set("All studios")
        self.presentation_var.set("All types")
        self._apply_filter()

    # Input: Grid coordinates. Output: Reusable card. Goal: Present artwork and identifying metadata. Description: The poster takes the space left after two caption rows.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter row. Input: Grid row index. Output: Vertical position. Goal: Align poster cells. Description: Counts rows from the top.
    # Parameter column. Input: Grid column index. Output: Horizontal position. Goal: Align related controls. Description: Counts columns from the left.
    def _build_library_slot(self, row, column):
        # Input: Parent grid. Output: Poster card. Goal: Keep one film's content together. Description: Fixed outer dimensions prevent its image from enlarging the page.
        card = ttk.Frame(self.grid, cursor="hand2")
        card.grid(row=row, column=column, sticky="nsew", padx=5, pady=4)
        card.grid_propagate(False)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        # Input: Card surface. Output: Focusable poster label. Goal: Open the selected movie by keyboard or pointer. Description: Permanent focus border preserves geometry across focus changes.
        poster = tk.Label(card, image=self.placeholder, background=WELL, width=1, height=1,
                          bd=0, takefocus=True, highlightthickness=2, highlightcolor=TEAL,
                          highlightbackground=WELL, cursor="hand2")
        poster.grid(row=0, column=0, sticky="nsew")
        # Input: Movie title. Output: Card heading. Goal: Identify the poster. Description: A fixed two-line caption keeps neighboring posters aligned.
        title = tk.Label(card, background=SHELL, foreground=INK, font=self.card_font,
                         anchor="nw", justify="left", height=2, width=1, bd=0, cursor="hand2")
        title.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        # Input: Movie year and type. Output: Card metadata. Goal: Scan the page quickly. Description: Sits directly beneath the title.
        meta = ttk.Label(card, style="Meta.TLabel", width=1, cursor="hand2")
        meta.grid(row=2, column=0, sticky="ew")
        # Input: Existing slot count. Output: Reusable position. Goal: Resolve records after paging. Description: The position stays fixed while the bound movie changes.
        position = len(self.slots)
        self.slots.append((poster, title, meta))
        card.bind("<Button-1>", partial(activate, partial(self._open_slot, position)))
        card.bind("<Button-3>", partial(activate, partial(self._edit_slot, position)))
        poster.bind("<Return>", partial(activate, partial(self._open_slot, position)))
        poster.bind("<space>", partial(activate, partial(self._open_slot, position)))
        poster.bind("<Enter>", partial(activate, partial(poster.configure, highlightbackground=TEAL)))
        poster.bind("<Leave>", partial(activate, partial(poster.configure, highlightbackground=WELL)))

    # Input: Current page and slot index. Output: Selected record. Goal: Resolve a reusable library cell. Description: Page offset plus the local index locates the corresponding filtered record.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter position. Input: Integer slot index. Output: Cell position. Goal: Identify the reusable card. Description: Starts at zero within its page.
    def _slot_movie(self, position):
        # Input: Page number, capacity and cell index. Output: Catalog offset. Goal: Find the visible movie. Description: The page offset formula multiplies page by capacity then adds the slot.
        index = self.page * self.page_size + position
        return self.filtered[index] if index < len(self.filtered) else None

    # Input: Selected slot. Output: Visible movie details. Goal: Open from a persistent cell. Description: Resolves its current movie at activation time.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter position. Input: Integer slot index. Output: Cell position. Goal: Identify the reusable card. Description: Starts at zero within its page.
    def _open_slot(self, position):
        # Input: Page and cell position. Output: Current movie. Goal: Avoid stale bindings. Description: Ignores unoccupied slots.
        movie = self._slot_movie(position)
        if movie:
            self._show_details(movie)

    # Input: Selected slot. Output: Metadata dialog. Goal: Edit from any part of the card. Description: Resolves its movie at activation time.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter position. Input: Integer slot index. Output: Cell position. Goal: Identify the reusable card. Description: Starts at zero within its page.
    def _edit_slot(self, position):
        # Input: Page and cell position. Output: Current movie. Goal: Avoid stale bindings. Description: Ignores unoccupied slots.
        movie = self._slot_movie(position)
        if movie:
            self._edit_metadata(movie)

    # Input: Grid allocation change. Output: One pending repaint. Goal: Keep artwork inside the actual window. Description: Delays expensive resizing until the layout settles.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _queue_grid_resize(self, event):
        if self.resize_job is not None:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(80, self._resize_grid)

    # Input: Measured card widths. Output: Updated wrapping and artwork. Goal: Adapt to resizing and high DPI. Description: Reuses the existing lazy page renderer.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _resize_grid(self):
        self.resize_job = None
        if self.browser_view.winfo_ismapped() and self.slots:
            self._render_page()

    # Input: Movie title and a pixel width. Output: A two-line display caption. Goal: Signal clipped titles explicitly. Description: Wraps at a word boundary and marks overflow with an ellipsis.
    # Parameter self. Input: Browser instance. Output: Active font. Goal: Measure native text. Description: Owns the font used by all library captions.
    # Parameter title. Input: Catalog title. Output: Caption source. Goal: Identify the movie. Description: Details always shows the full title.
    # Parameter width. Input: Measured usable pixels. Output: Line limit. Goal: Avoid clipped text. Description: Excludes the label's horizontal padding.
    def _card_caption(self, title, width):
        if self.card_font.measure(title) <= width:
            return title
        # Input: Full title. Output: First-line character count. Goal: Find a fitting prefix. Description: Binary search halves the remaining prefix range after each comparison.
        # Parameter text. Input: Candidate line. Output: Measured source. Goal: Choose a fitting prefix. Description: Contains the words or characters that remain.
        # Parameter suffix. Input: Optional ellipsis. Output: Reserved ending. Goal: Keep truncation visible. Description: Its measured width counts toward the line limit.
        def fitting_prefix(text, suffix):
            # Input: Empty prefix. Output: Lower bound. Goal: Track fitting prefixes. Description: Prefix length is counted in characters.
            lower = 0
            # Input: Source length. Output: Upper bound. Goal: Limit the search. Description: No prefix can exceed the whole line.
            upper = len(text)
            while lower < upper:
                # Input: Search bounds. Output: Candidate length. Goal: Halve the search space. Description: The upper midpoint formula rounds toward the longer candidate.
                middle = (lower + upper + 1) // 2
                if self.card_font.measure(text[:middle] + suffix) <= width:
                    lower = middle
                else:
                    upper = middle - 1
            return lower
        # Input: Measured title prefix. Output: First line endpoint. Goal: Wrap at a readable break. Description: Falls back to a character boundary for long unbroken titles.
        end = fitting_prefix(title, "")
        # Input: Candidate prefix. Output: Last space index. Goal: Preserve whole words. Description: The next word starts on line two.
        boundary = title.rfind(" ", 0, end + 1)
        if boundary > 0:
            end = boundary
        # Input: First-line endpoint. Output: Remaining title. Goal: Populate the second line. Description: Removes leading spaces at the line break.
        remainder = title[end:].lstrip()
        if self.card_font.measure(remainder) > width:
            remainder = remainder[:fitting_prefix(remainder, "…")].rstrip() + "…"
        return title[:end].rstrip() + "\n" + remainder

    # Input: Filtered movies and page index. Output: Visible cards and navigation state. Goal: Keep the current results legible. Description: Reuses controller paging and hides unused page slots.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _render_page(self):
        super()._render_page()
        # Input: Slot order. Output: Local index. Goal: Identify occupied cells. Description: The current page slice can end before the last slot.
        # Input: Reusable view slots. Output: Widget tuple. Goal: Update visibility. Description: The poster's parent contains both captions.
        for position, slot in enumerate(self.slots):
            # Input: Current page and cell index. Output: Visible movie. Goal: Format its caption. Description: Empty cells have no matching record.
            movie = self._slot_movie(position)
            if movie:
                slot[0].master.grid()
                if slot[0].master.winfo_width() > 8:
                    slot[1].configure(text=self._card_caption(movie.title, slot[0].master.winfo_width() - 6))
            else:
                slot[0].master.grid_remove()
        if self.filtered:
            self.empty_results.place_forget()
        else:
            self.status.configure(text="0 movies")
            self.empty_heading.configure(text="No matching movies" if self.all_items else "Your library is empty")
            if self.all_items:
                self.empty_instruction.pack_forget()
            else:
                self.empty_instruction.pack(before=self.empty_action, pady=(6, 0))
            self.empty_action.configure(text="Clear filters" if self.all_items else "Rescan library",
                                        command=self._clear_filters if self.all_items else self._rescan)
            self.empty_results.place(relx=0.5, rely=0.4, anchor="center")

    # Input: Local images and target frame dimensions. Output: Tk photo. Goal: Preserve poster proportions. Description: Tries both local files and renders a readable fallback for missing art.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter movie. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    # Parameter size. Input: Width and height in pixels. Output: Artwork bounds. Goal: Fit the intended display slot. Description: Limits the displayed poster dimensions.
    def _poster_photo(self, movie, size):
        # Input: Movie art names and display bounds. Output: Cache key. Goal: Avoid repeated decoding. Description: The same poster can have different shelf and detail sizes.
        cache_key = (movie.thumb_path, movie.cover_path, size)
        if cache_key in self.thumb_cache:
            return self.thumb_cache[cache_key]
        # Input: Requested dimensions. Output: Preferred source path order. Goal: Preserve detail resolution. Description: Large displays use the original cover before its thumbnail.
        candidates = (movie.cover_path, movie.thumb_path) if size[1] > 220 else (movie.thumb_path, movie.cover_path)
        # Input: Requested frame dimensions. Output: Dark backing image. Goal: Frame local art consistently. Description: Letterboxing keeps every pixel of the original cover visible.
        surface = Image.new("RGB", size, WELL)
        # Input: Cover and thumbnail paths. Output: One candidate path. Goal: Recover from absent or unreadable artwork. Description: A valid alternate remains available after a decoding failure.
        for source in candidates:
            if source:
                try:
                    # Input: Local file path. Output: Open PIL source. Goal: Release file handles promptly. Description: The image is decoded within a context manager.
                    with Image.open(source) as original:
                        # Input: Original pixels and frame. Output: Scaled RGB image. Goal: Preserve the full aspect ratio. Description: Pillow contain scales uniformly to fit both bounds.
                        image = ImageOps.contain(original.convert("RGB"), size, Image.Resampling.LANCZOS)
                    # Centering formula. Half the unoccupied space centers the image independently on each axis.
                    surface.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
                    break
                except (OSError, ValueError, Image.DecompressionBombError):
                    continue
        else:
            # Input: Frame bounds. Output: Drawing context. Goal: Identify unavailable covers. Description: Uses a text fallback instead of an unrelated picture.
            drawing = ImageDraw.Draw(surface)
            # Input: Installed Windows font. Output: Fallback caption font. Goal: Keep the artwork status readable. Description: Pillow's default face works on other systems.
            try:
                font = ImageFont.truetype("segoeui.ttf", 13)
            except OSError:
                font = ImageFont.load_default()
            drawing.text((size[0] // 2, size[1] // 2), "No poster", font=font, fill=MUTED, anchor="mm")
        # Input: Prepared poster pixels. Output: Tk image handle. Goal: Display the fitted artwork. Description: Widget references and the bounded cache keep images alive.
        photo = ImageTk.PhotoImage(surface, master=self)
        if len(self.thumb_cache) >= 220:
            self.thumb_cache.pop(next(iter(self.thumb_cache)))
        self.thumb_cache[cache_key] = photo
        return photo

    # Input: Catalog record and measured poster well. Output: Fitted Tk image. Goal: Honor requested pixel bounds. Description: Uses the smallest of the available cell and configured thumbnail dimensions.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter item. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    def _load_thumb(self, item):
        if not self.slots or self.slots[0][0].winfo_width() < 8:
            return self.placeholder
        # Input: First occupied card's allocated poster rectangle. Output: Image well. Goal: Find the actual display bounds. Description: Uniform grid cells use the same dimensions.
        poster = self.slots[0][0]
        # Input: Allocated rectangle minus focus stroke. Output: Usable image size. Goal: Avoid clipped artwork. Description: Independent minima also honor the requested thumbnail limits.
        size = (min(self.thumb_size[0], max(1, poster.winfo_width() - 4)),
                min(self.thumb_size[1], max(1, poster.winfo_height() - 4)))
        return self._poster_photo(item, size)

    # Input: Root window and catalog. Output: Scrollable Discover screen. Goal: Browse recommended and popular movies. Description: Uses a canvas containing native widgets and routes descendant wheels.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _build_home_ui(self):
        # Input: Root. Output: Discover screen. Goal: Group discovery controls. Description: Shares the global header with other views.
        self.home_view = ttk.Frame(self)
        # Input: Discover surface. Output: Scrolling canvas. Goal: Browse all genre shelves. Description: Uses native scrolling increments and a linked scrollbar.
        self.home_canvas = tk.Canvas(self.home_view, bg=SHELL, highlightthickness=0, yscrollincrement=24)
        # Input: Canvas scroll range. Output: Vertical scrollbar. Goal: Show position in the collection. Description: Scroll commands go directly to the canvas.
        scrollbar = ttk.Scrollbar(self.home_view, orient="vertical", command=self.home_canvas.yview)
        self.home_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.home_canvas.pack(fill="both", expand=True)
        # Input: Canvas. Output: Discover content frame. Goal: Host movie shelves. Description: Its width follows the viewport.
        self.home_content = ttk.Frame(self.home_canvas, padding=(24, 15, 24, 24))
        # Input: Content frame. Output: Canvas window ID. Goal: Resize its width. Description: Anchors the layout to the top left.
        self.home_window = self.home_canvas.create_window((0, 0), window=self.home_content, anchor="nw")
        # Input: Initial content layout. Output: Last measured dimensions. Goal: Ignore scroll-only moves. Description: A dimension change alone requires a new scroll region.
        self.home_region_size = None
        self.home_canvas.bind("<Configure>", self._size_home)
        self.home_content.bind("<Configure>", self._scroll_region)
        self.bind("<MouseWheel>", self._scroll_home, add="+")
        # Input: Controller recommendation state. Output: Selected position. Goal: Start on the first pick. Description: The inherited rotation logic updates this index.
        self.feature_index = 0
        # Input: Startup. Output: Recommendation timer handle. Goal: Cancel pending rotation on shutdown. Description: The timer is registered after the initial layout.
        self.rotation_job = None
        self._refresh_home()
        self._schedule_feature()
        self._apply_filter()

    # Input: Canvas viewport event. Output: Updated content width. Goal: Keep horizontal alignment. Description: Adopts the measured viewport width only when it changes.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _size_home(self, event):
        if int(float(self.home_canvas.itemcget(self.home_window, "width"))) != event.width:
            self.home_canvas.itemconfigure(self.home_window, width=event.width)

    # Input: Content layout event. Output: Updated scroll region. Goal: Reach the final shelf. Description: Uses the bounding rectangle of the canvas content.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _scroll_region(self, event):
        if self.home_region_size != (event.width, event.height):
            self.home_region_size = (event.width, event.height)
            self.home_canvas.configure(scrollregion=self.home_canvas.bbox("all"))

    # Input: Selected destination. Output: Visible Discover screen. Goal: Show recommendations. Description: Restores the home query and selected tab state.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _show_home(self):
        super()._show_home()
        self.discover_tab.configure(style="Selected.Nav.TButton")
        self.library_tab.configure(style="Nav.TButton")
        self.library_search_entry.configure(textvariable=self.home_search)

    # Input: Selected destination. Output: Visible Library screen. Goal: Show the filtered collection. Description: Restores the library query and selected tab state.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _open_library(self):
        super()._open_library()
        self.discover_tab.configure(style="Nav.TButton")
        self.library_tab.configure(style="Selected.Nav.TButton")
        self.library_search_entry.configure(textvariable=self.search_var)

    # Input: Submitted Discover query. Output: Filtered Library screen. Goal: Search all saved metadata. Description: Transfers the literal text before presenting the results.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _search_from_home(self, event=None):
        self.search_var.set(self.home_search.get())
        self._apply_filter()
        self._open_library()

    # Input: Discover gallery and current catalog. Output: Refreshed recommendations and shelves. Goal: Keep edits and playback reflected. Description: Rebuilds only on a catalog change.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _refresh_home(self):
        # Input: Existing sections. Output: A child widget. Goal: Replace outdated shelves. Description: Destroying a row releases the images held by its labels.
        for child in self.home_content.winfo_children():
            child.destroy()
        # Input: Existing recommendation scorer. Output: Ordered picks. Goal: Preserve recommendation rules. Description: The picks include at most five catalog records.
        self.featured = self._featured_movies()
        self.feature_index = 0
        # Input: Discover content. Output: Feature heading row. Goal: Name the recommendation and show its position. Description: The title stands separately from the selected movie.
        feature_heading = ttk.Frame(self.home_content)
        feature_heading.pack(fill="x", pady=(0, 8))
        ttk.Label(feature_heading, text="Picked for you", style="Heading.TLabel").pack(side="left")
        # Input: Current feature position. Output: Counter label. Goal: Tell viewers which pick is showing. Description: Lives beside the navigation controls.
        position = ttk.Label(feature_heading, style="Status.TLabel")
        ttk.Button(feature_heading, text="Next pick", style="RowNav.TButton",
                   command=partial(self._rotate_feature, 1),
                   state="normal" if len(self.featured) > 1 else "disabled").pack(side="right")
        ttk.Button(feature_heading, text="Previous pick", style="RowNav.TButton",
                   command=partial(self._rotate_feature, -1),
                   state="normal" if len(self.featured) > 1 else "disabled").pack(side="right", padx=5)
        position.pack(side="right", padx=8)
        # Input: Discover content. Output: Feature panel. Goal: Show one poster and its information. Description: A fixed panel height keeps rotation from moving the shelves.
        self.feature_panel = ttk.Frame(self.home_content, style="Panel.TFrame", height=246)
        self.feature_panel.pack(fill="x", pady=(0, 20))
        self.feature_panel.pack_propagate(False)
        # Input: Newly constructed panel. Output: Persistent featured controls. Goal: Update rotation without rebuilding children. Description: The tuple stores poster, position, title and genres.
        self.feature_widgets = None
        if self.featured:
            self._build_feature(position)
        else:
            ttk.Label(self.feature_panel, text="Your library is empty", style="Movie.TLabel").pack(pady=(50, 6))
            ttk.Label(self.feature_panel, text="Add movie folders beside Movie Shelf, then rescan.",
                      style="PanelMuted.TLabel").pack()
            ttk.Button(self.feature_panel, text="Rescan library", command=self._rescan).pack(pady=12)
        # Input: Active catalog. Output: Movies ranked by plays. Goal: Explain personal popularity. Description: The existing title order breaks ties.
        popular = sorted(self.all_items, key=self._popular_order)
        if popular:
            self._home_row("Popular in your library", "Ranked by watches", popular[:8], True)
        # Input: Active movies. Output: Genre-to-movies mapping. Goal: Build collection-specific shelves. Description: Preserves the title ordering supplied by the catalog.
        genre_movies = {}
        # Input: Active catalog. Output: Catalog record. Goal: Assign titles to their shelves. Description: One title may appear in several genres.
        for movie in self.all_items:
            # Input: Movie genre tags. Output: Genre name. Goal: Group by metadata. Description: Records without a genre stay in Library.
            for genre in movie.genres:
                genre_movies.setdefault(genre, []).append(movie)
        # Input: Rendered shelves. Output: Genre-to-widget mapping. Goal: Enable jump navigation. Description: The inherited jump handler reads each section's position.
        self.genre_sections = {}
        # Input: Discover content. Output: Genre navigation. Goal: Jump through long collections. Description: Groups the dropdown with its section heading.
        navigation = ttk.Frame(self.home_content)
        navigation.pack(fill="x", pady=(3, 12))
        ttk.Label(navigation, text="Explore by genre", style="Heading.TLabel").pack(side="left")
        # Input: Genre navigation. Output: Selected jump destination. Goal: Keep genre filtering independent. Description: Changes only the Discover scroll position.
        self.home_genre_var = tk.StringVar(self, "Jump to genre")
        # Input: Known genre sections. Output: Native selector. Goal: Jump to a specific genre. Description: Disabled for a collection without genres.
        selector = ttk.Combobox(navigation, textvariable=self.home_genre_var, values=sorted(genre_movies, key=str.casefold),
                                state="readonly" if genre_movies else "disabled", width=19)
        selector.pack(side="right")
        selector.bind("<<ComboboxSelected>>", self._jump_to_genre)
        if not genre_movies:
            ttk.Label(self.home_content, text="No genres added yet", style="Status.TLabel").pack(anchor="w")
        # Input: Sorted catalog genres. Output: A genre name. Goal: Present shelves alphabetically. Description: The matching records were collected above.
        for genre in sorted(genre_movies, key=str.casefold):
            # Input: Movies assigned to this genre. Output: Number of titles. Goal: Label the shelf accurately. Description: Selects the singular or plural form for this collection.
            title_count = len(genre_movies[genre])
            self.genre_sections[genre] = self._home_row(
                genre, f"{title_count} {'title' if title_count == 1 else 'titles'}", genre_movies[genre])

    # Input: Movie record. Output: Watch and title sort key. Goal: Preserve Popular ordering. Description: Negative watches put frequent plays first.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter movie. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    def _popular_order(self, movie):
        return -movie.watch_count, movie.title.casefold()

    # Input: Prepared recommendation list and position label. Output: Persistent feature widgets. Goal: Make rotating recommendations stable. Description: The artwork, title, facts and actions retain their positions.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter position. Input: Integer slot index. Output: Cell position. Goal: Identify the reusable card. Description: Starts at zero within its page.
    def _build_feature(self, position):
        # Input: Feature panel. Output: Clickable artwork label. Goal: Open the recommendation. Description: Image dimensions match the panel height.
        poster = tk.Label(self.feature_panel, background=WELL, borderwidth=0, cursor="hand2")
        poster.pack(side="left", fill="y")
        poster.bind("<Button-1>", partial(activate, self._open_feature))
        # Input: Feature panel. Output: Metadata and action column. Goal: Pair the movie with its poster. Description: Provides a generous left inset and a consistent baseline.
        info = ttk.Frame(self.feature_panel, style="Panel.TFrame", padding=(24, 15))
        info.pack(side="left", expand=True, fill="both")
        # Input: Feature actions. Output: Details button. Goal: Inspect the currently visible film. Description: Bottom placement keeps actions reachable for long titles.
        actions = ttk.Frame(info, style="Panel.TFrame")
        actions.pack(side="bottom", fill="x", pady=(5, 0))
        ttk.Button(actions, text="View movie", style="Accent.TButton", command=self._open_feature).pack(side="left")
        # Input: Recommendation record. Output: Title label. Goal: Identify the selected movie. Description: Wraps to fit its allocated information column.
        title = ttk.Label(info, style="Movie.TLabel", justify="left", wraplength=550)
        title.pack(anchor="w")
        # Input: Feature information column. Output: Ticket-style facts strip. Goal: Scan the selected movie's year and history. Description: Shared with Details.
        self.feature_facts = self._facts_strip(info)
        # Input: Movie genre tags. Output: Genre label. Goal: Show the available categories. Description: Shares the feature surface.
        genres = ttk.Label(info, style="PanelMuted.TLabel", justify="left", wraplength=550)
        genres.pack(anchor="w", pady=(4, 0))
        self.feature_widgets = (poster, position, title, genres)
        info.bind("<Configure>", self._wrap_feature)
        self._draw_feature()

    # Input: Feature container width. Output: Updated wrapping. Goal: Keep long titles inside the panel. Description: Subtracts the horizontal information insets from available width.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _wrap_feature(self, event):
        if self.feature_widgets:
            self.feature_widgets[2].configure(wraplength=max(120, event.width - 50))
            self.feature_widgets[3].configure(wraplength=max(120, event.width - 50))
            self.feature_facts.configure(wraplength=max(120, event.width - 50))

    # Input: Current feature index. Output: Movie details. Goal: Open the displayed recommendation. Description: Looks up the current record after rotation.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _open_feature(self):
        if self.featured:
            self._show_details(self.featured[self.feature_index])

    # Input: Current pick and persistent controls. Output: Updated feature contents. Goal: Avoid layout churn during rotation. Description: Only text and the photo handle change.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _draw_feature(self):
        if self.feature_widgets and self.featured:
            # Input: Active index. Output: Current recommendation. Goal: Synchronize artwork, labels and controls. Description: Uses the controller's existing ranking.
            movie = self.featured[self.feature_index]
            # Input: Persistent feature tuple. Output: Poster widget. Goal: Update the shown artwork. Description: Keeps a Python reference to its photo.
            poster = self.feature_widgets[0]
            # Input: Recommended movie and panel size. Output: Retained poster photo. Goal: Display local artwork. Description: The image retains the movie's aspect ratio.
            poster.image = self._poster_photo(movie, (164, 246))
            poster.configure(image=poster.image)
            self.feature_widgets[1].configure(text=f"{self.feature_index + 1} of {len(self.featured)}")
            self.feature_widgets[2].configure(text=movie.title)
            self.feature_widgets[3].configure(text="  /  ".join(movie.genres))
            self.feature_facts.configure(text=movie_facts(movie))

    # Input: Root timer. Output: Scheduled feature rotation. Goal: Rotate picks every eight seconds. Description: The first pick stays visible for a full interval.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _schedule_feature(self):
        self.rotation_job = self.after(8000, self._advance_feature)

    # Input: Recommendation timer. Output: Next visible pick. Goal: Keep discovery moving. Description: The controller advances only while Discover is visible.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _advance_feature(self):
        self._rotate_feature(1)
        self._schedule_feature()

    # Input: Section details and sorted films. Output: Scrollable shelf section. Goal: Browse four movies at a time. Description: Each row retains its own page and controls.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter heading. Input: Shelf name. Output: Visible section title. Goal: Identify a collection. Description: Names the group of movies.
    # Parameter description. Input: Shelf metadata. Output: Supporting text. Goal: Explain the collection. Description: Summarizes the contents beside its heading.
    # Parameter movies. Input: Ordered catalog records. Output: Shelf collection. Goal: Paginate a movie group. Description: Preserves the supplied ordering.
    # Parameter show_watch_count. Input: Boolean flag. Output: Caption option. Goal: Explain the Popular ranking. Description: Includes local watch counts when enabled.
    def _home_row(self, heading, description, movies, show_watch_count=False):
        # Input: Discover content. Output: Section wrapper. Goal: Keep row heading and cards together. Description: Returned for genre jump navigation.
        section = ttk.Frame(self.home_content)
        section.pack(fill="x", pady=(0, 21))
        # Input: Section wrapper. Output: Heading row. Goal: Align title, description and paging. Description: All controls apply to this shelf.
        header = ttk.Frame(section)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=heading, style="Shelf.TLabel").pack(side="left")
        ttk.Label(header, text=description, style="Status.TLabel").pack(side="left", padx=12)
        # Input: Shelf section. Output: Four-column grid. Goal: Keep each card width consistent. Description: Unoccupied columns stay empty on the last page.
        cards = ttk.Frame(section)
        cards.pack(fill="x")
        # Input: Four visible positions. Output: Column index. Goal: Use even spacing. Description: A uniform grid keeps partial pages aligned to full pages.
        for column in range(4):
            cards.columnconfigure(column, weight=1, uniform="shelf")
        # Input: Shelf creation. Output: Current page number. Goal: Keep independent paging state. Description: Captured by this row's navigation actions.
        page = 0

        # Input: Local page and movie list. Output: Updated shelf cards. Goal: Render the selected page. Description: Releases the preceding page's native labels and image references.
        def draw():
            # Input: Existing page widgets. Output: A card. Goal: Replace the displayed movies. Description: Each page has at most four children.
            for child in cards.winfo_children():
                child.destroy()
            # Input: Page index and four-card capacity. Output: First record index. Goal: Locate the page slice. Description: The page offset formula multiplies page by capacity.
            start = page * 4
            # Input: Four-record slice. Output: Column index. Goal: Position the current card. Description: Enumerates from the first column on every page.
            # Input: Four-record slice. Output: Movie record. Goal: Build its poster card. Description: The original shelf ordering is preserved.
            for column, movie in enumerate(movies[start:start + 4]):
                self._home_card(cards, movie, show_watch_count=show_watch_count).grid(
                    row=0, column=column, sticky="new", padx=(0, 10))
            previous.configure(state="normal" if page else "disabled")
            following.configure(state="normal" if start + 4 < len(movies) else "disabled")

        # Input: Signed direction. Output: Changed shelf page. Goal: Navigate independently. Description: The bounded buttons enable only valid transitions.
        # Parameter direction. Input: Signed page step. Output: Movement direction. Goal: Navigate one page. Description: A positive value moves forward.
        def change(direction):
            nonlocal page
            page += direction
            draw()

        # Input: Local page callback. Output: Next button. Goal: Reveal later movies. Description: Enabled only if another page exists.
        following = ttk.Button(header, text="Next", style="RowNav.TButton", command=partial(change, 1))
        following.pack(side="right")
        # Input: Local page callback. Output: Previous button. Goal: Reveal earlier movies. Description: Enabled only after the first page.
        previous = ttk.Button(header, text="Previous", style="RowNav.TButton", command=partial(change, -1))
        previous.pack(side="right", padx=5)
        draw()
        return section

    # Input: Parent and shelf movie. Output: Clickable poster card. Goal: Browse movies by their actual artwork. Description: Captions identify the title and optional play count.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter parent. Input: Tk container. Output: Parent widget. Goal: Place this component. Description: Owns the component and its children.
    # Parameter movie. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    # Parameter show_watch_count. Input: Boolean flag. Output: Caption option. Goal: Explain the Popular ranking. Description: Includes local watch counts when enabled.
    def _home_card(self, parent, movie, show_watch_count=False):
        # Input: Shelf grid. Output: Card column. Goal: Group artwork and captions. Description: Uses the surrounding shell as its surface.
        card = ttk.Frame(parent, cursor="hand2")
        # Input: Movie paths and shelf height. Output: Artwork photo. Goal: Give each cover the same display area. Description: The full cover is preserved within the portrait well.
        photo = self._poster_photo(movie, (140, 200))
        # Input: Shelf artwork. Output: Focusable poster label. Goal: Open a movie from the keyboard. Description: A stable border changes color for hover and focus.
        poster = tk.Label(card, image=photo, bg=WELL, bd=0, takefocus=True, cursor="hand2",
                          highlightthickness=2, highlightcolor=TEAL, highlightbackground=WELL)
        # Input: Prepared movie artwork. Output: Retained image handle. Goal: Preserve the visible cover. Description: Tk image names depend on a live Python object.
        poster.image = photo
        poster.pack(anchor="w")
        ttk.Label(card, text=movie.title, style="Title.TLabel", wraplength=185,
                  justify="left", cursor="hand2").pack(anchor="w", pady=(5, 0))
        # Input: Year and watch count preference. Output: Card metadata text. Goal: Explain popularity at a glance. Description: Only known year and requested count are displayed.
        metadata = "   /   ".join(filter(None, (str(movie.year or ""),
                                  f"{movie.watch_count} {'watch' if movie.watch_count == 1 else 'watches'}"
                                  if show_watch_count else "")))
        if metadata:
            ttk.Label(card, text=metadata, style="Meta.TLabel", cursor="hand2").pack(anchor="w")
        # Input: Card and its captions. Output: Interactive widget. Goal: Open the right movie from any visible area. Description: Right click preserves quick metadata editing.
        for widget in (card, *card.winfo_children()):
            widget.bind("<Button-1>", partial(activate, partial(self._show_details, movie)))
            widget.bind("<Button-3>", partial(activate, partial(self._edit_metadata, movie)))
        poster.bind("<Return>", partial(activate, partial(self._show_details, movie)))
        poster.bind("<space>", partial(activate, partial(self._show_details, movie)))
        poster.bind("<Enter>", partial(activate, partial(poster.configure, highlightbackground=TEAL)))
        poster.bind("<Leave>", partial(activate, partial(poster.configure, highlightbackground=WELL)))
        return card

    # Input: Feature or detail column. Output: Ruled facts label. Goal: Give movie metadata a recognizable place. Description: Two fine rules bracket compact brass text on the parent panel.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter parent. Input: Tk container. Output: Parent widget. Goal: Place this component. Description: Owns the component and its children.
    def _facts_strip(self, parent):
        ttk.Separator(parent).pack(fill="x", pady=(8, 0))
        # Input: Parent surface. Output: Facts label. Goal: Keep metadata legible. Description: The available width determines line wrapping.
        facts = ttk.Label(parent, style="Facts.TLabel", justify="left", wraplength=480)
        facts.pack(anchor="w", pady=5)
        ttk.Separator(parent).pack(fill="x")
        return facts

    # Input: Detail frame. Output: Movie details layout. Goal: Inspect and act on a local film. Description: Pairs full artwork with title, facts and actions.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _build_detail_view(self):
        # Input: Detail screen. Output: Contextual Back button. Goal: Restore the originating screen. Description: Its caption changes between Library and Discover.
        self.detail_back = ttk.Button(self.detail_view, text="Back", command=self._show_browser)
        self.detail_back.pack(anchor="w", pady=(0, 14))
        # Input: Detail frame. Output: Information surface. Goal: Display movie art and information together. Description: The surrounding shell retains margins.
        body = ttk.Frame(self.detail_view, style="Panel.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.grid_propagate(False)
        # Input: Detail layout events. Output: Pending idle redraw. Goal: Fit artwork to the current window. Description: Coalesces geometry notifications until layout settles.
        self.detail_resize_job = None
        body.bind("<Configure>", self._queue_detail_resize)
        # Input: Selected movie art. Output: Detail poster. Goal: Show the best available local image. Description: Takes a limited portion of the width.
        self.detail_poster = tk.Label(body, bg=WELL, bd=0)
        self.detail_poster.grid(row=0, column=0, sticky="nw", padx=(0, 22))
        # Input: Detail surface. Output: Text and actions column. Goal: Keep information beside the artwork. Description: The column follows the available width.
        info = ttk.Frame(body, style="Panel.TFrame")
        info.grid(row=0, column=1, sticky="new")
        # Input: Current movie title. Output: Detail heading. Goal: Identify the title. Description: Adapts wrapping to the available column.
        self.detail_title = ttk.Label(info, style="Movie.TLabel", justify="left", wraplength=440)
        self.detail_title.pack(anchor="w", pady=(6, 5))
        # Input: Current movie facts. Output: Metadata label. Goal: Show year, presentation, studio and history. Description: Uses the same ruled treatment as the feature.
        self.detail_facts = self._facts_strip(info)
        # Input: Current movie genres. Output: Genre label. Goal: Identify its categories. Description: Missing genres receive a readable empty state.
        self.detail_genres = ttk.Label(info, style="PanelMuted.TLabel", wraplength=440, justify="left")
        self.detail_genres.pack(anchor="w", pady=(12, 18))
        # Input: Selected movie. Output: Play button. Goal: Launch the system player. Description: Disabled when the title has no playable file.
        self.detail_play = ttk.Button(info, text="Play movie", style="Accent.TButton")
        self.detail_play.pack(anchor="w")
        # Input: Disabled playback or normal state. Output: File status message. Goal: Explain why playback is unavailable. Description: Occupies no space unless the video is missing.
        self.video_status = ttk.Label(info, style="PanelMuted.TLabel")
        self.video_status.pack(anchor="w")
        # Input: Information column. Output: Secondary actions. Goal: Keep maintenance reachable. Description: Sits beneath the primary playback action.
        actions = ttk.Frame(info, style="Panel.TFrame")
        actions.pack(anchor="w", pady=(12, 0))
        # Input: Movie details. Output: Metadata button. Goal: Edit the selected title. Description: Uses the existing atomic save dialog.
        self.detail_edit = ttk.Button(actions, text="Edit metadata")
        self.detail_edit.pack(side="left", padx=(0, 7))
        # Input: Movie details. Output: Folder button. Goal: Open its local folder. Description: Uses the existing Windows folder action.
        self.detail_folder = ttk.Button(actions, text="Open folder")
        self.detail_folder.pack(side="left")
        info.bind("<Configure>", self._wrap_details)

    # Input: Detail column width. Output: Wrapped text. Goal: Fit long movie titles and facts. Description: Leaves room for the rules and outer insets.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter event. Input: Tk event. Output: Input notification. Goal: Handle the native binding. Description: Includes the source widget, dimensions or key state.
    def _wrap_details(self, event):
        # Input: Related text labels. Output: Detail label. Goal: Keep all text inside the column. Description: Adjusts the line width to the same available space.
        for widget in (self.detail_title, self.detail_facts, self.detail_genres):
            widget.configure(wraplength=max(100, event.width - 6))

    # Input: Detail body geometry. Output: Scheduled poster update. Goal: Keep the entire cover visible. Description: Recalculates after the native layout settles.
    # Parameter self. Input: Browser instance. Output: Current window. Goal: Manage resizing. Description: Owns the image and idle timer.
    # Parameter event. Input: Native configure event. Output: Resize notification. Goal: Track the visible frame. Description: Fired when the allocated body dimensions change.
    def _queue_detail_resize(self, event):
        if self.detail_resize_job is None:
            self.detail_resize_job = self.after_idle(self._size_detail_poster)

    # Input: Current detail record and body allocation. Output: Full fitted cover. Goal: Keep artwork visible during live resize. Description: Limits poster dimensions to the padded height and one third of the available width.
    # Parameter self. Input: Browser instance. Output: Visible detail image. Goal: Fit the selected art. Description: Holds the current movie and its poster label.
    def _size_detail_poster(self):
        self.detail_resize_job = None
        if not self.detail_view.winfo_manager():
            return
        # Input: Poster parent. Output: Detail body. Goal: Measure the actual layout. Description: This native frame already excludes the header and Back control.
        body = self.detail_poster.master
        # Input: Allocated body height and width. Output: Usable portrait height in pixels. Goal: Keep adequate information space. Description: The aspect ratio formula converts a one-third-width poster at a 2:3 ratio to half the available width.
        height = max(1, min(480, body.winfo_height() - 40, (body.winfo_width() - 40) // 2))
        if height <= 1:
            return
        # Input: Current movie and fitted frame. Output: Detail photo. Goal: Show the complete cover. Description: Two-thirds of the fitted height gives a conventional portrait frame.
        self.detail_image = self._poster_photo(self.detail_record, (max(1, height * 2 // 3), height))
        self.detail_poster.configure(image=self.detail_image)
        # Input: Prepared detail photo. Output: Retained widget image. Goal: Preserve artwork while showing details. Description: Tk requires a live Python reference.
        self.detail_poster.image = self.detail_image

    # Input: Selected catalog movie. Output: Visible details. Goal: Inspect, play or maintain the title. Description: Tracks the originating screen only on first entry.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter item. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    def _show_details(self, item):
        if not self.detail_view.winfo_manager():
            # Input: Current screen. Output: Return destination. Goal: Preserve navigation across saves and plays. Description: A detail refresh keeps the original destination.
            self.return_view = "home" if self.home_view.winfo_manager() else "library"
        # Input: Selected record ID. Output: Detail selection. Goal: Find the fresh record after catalog changes. Description: Retains identity independently of the path or title.
        self.detail_movie_id = item.id
        # Input: Selected catalog record. Output: Current detail movie. Goal: Refit its image during resizing. Description: Replaced whenever the selected record refreshes.
        self.detail_record = item
        self.home_view.pack_forget()
        self.browser_view.pack_forget()
        self.detail_view.pack(fill="both", expand=True)
        self.library_search_entry.configure(textvariable=self.search_var)
        self.detail_back.configure(text="Back to Discover" if self.return_view == "home" else "Back to Library")
        self.detail_title.configure(text=item.title)
        self.detail_facts.configure(text=movie_facts(item))
        self.detail_genres.configure(text="  /  ".join(item.genres) or "No genres added yet")
        # Input: Resolved local video. Output: Playback availability. Goal: Enable safe playback. Description: The existing resolver stays within the selected movie folder.
        can_play = bool(self._resolve_video_path(item))
        self.detail_play.configure(command=partial(self._play, item), state="normal" if can_play else "disabled")
        self.video_status.configure(text="" if can_play else "No playable video in this folder.")
        self.detail_edit.configure(command=partial(self._edit_metadata, item))
        self.detail_folder.configure(command=partial(self._open_folder, item))
        if self.detail_resize_job is None:
            self.detail_resize_job = self.after_idle(self._size_detail_poster)

    # Input: Stored detail origin. Output: Restored screen. Goal: Return to the viewer's place. Description: Original search, page and scroll state are preserved by the views.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _show_browser(self):
        if getattr(self, "return_view", "library") == "home":
            self._show_home()
        else:
            self._open_library()

    # Input: Latest catalog records. Output: Updated open details. Goal: Keep visible information current. Description: Routes back if a rescan removed the selected folder.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _refresh_open_detail(self):
        if self.detail_view.winfo_manager():
            # Input: Refreshed catalog. Output: Current record. Goal: Locate the original selection. Description: IDs survive metadata edits and portable path repair.
            for movie in self.all_items:
                if movie.id == self.detail_movie_id:
                    self._show_details(movie)
                    return
            self._show_browser()

    # Input: Selected movie. Output: System player launch and updated details. Goal: Reflect the watch immediately. Description: Reuses the controller's path repair and count transaction.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    # Parameter item. Input: Catalog record. Output: Selected movie. Goal: Identify the title. Description: Supplies its ID, paths and saved metadata.
    def _play(self, item):
        super()._play(item)
        self._refresh_open_detail()

    # Input: Active library root. Output: Updated catalog and details. Goal: Reflect changes from disk. Description: Reuses the existing rescan then synchronizes the open record.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _rescan(self):
        super()._rescan()
        self._refresh_open_detail()

    # Input: Pending native timer handles. Output: Closed window and database. Goal: Prevent callbacks after shutdown. Description: Controller separately cancels its thumbnail loader.
    # Parameter self. Input: MovieBrowser instance. Output: Active window. Goal: Update the current view. Description: Owns the catalog controller and Tk widgets.
    def _close(self):
        # Input: Rotation and resize jobs. Output: Pending timer handle. Goal: Cancel incomplete view work. Description: A completed timer has no active ID.
        for pending in (self.rotation_job, self.resize_job, self.detail_resize_job):
            if pending is not None:
                self.after_cancel(pending)
        super()._close()
