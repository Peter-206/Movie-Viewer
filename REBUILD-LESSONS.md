# Rebuild lessons

## UI-REBUILD-001

Date. November 19, 2026

Tags. Impeccable, product context, concept-seed, initialization

Mistake. Attempted a direction seed before writing PRODUCT.md, although the context command had already reported that product initialization was required

Cause. The product confirmation arrived while setup and source discovery were running, and the seed call moved ahead of persistence

Solution. Wrote the confirmed product record first, then reran the seed command

Verification. The command completed successfully and returned seed:afedfcb133703f03

Prevention. Treat the presence of the confirmed PRODUCT.md as a hard precondition before running a new-world direction seed

## UI-REBUILD-002

Date. November 19, 2026

Tags. Tkinter, ttk.Label, native options, constructor cleanup

Mistake. The first UI implementation supplied a height option to ttk.Label, which prevented window construction on Tk 8.6

Cause. Classic Tk Label and themed ttk.Label do not accept the same options. A failed constructor also left a default Tk interpreter alive, causing image errors in subsequent test cases

Solution. Used tk.Label for the library caption that needs a fixed line height

Verification. The integrated regression suite passed all 10 tests after the correction

Prevention. Use the widget class that supports the needed layout property and verify the first real window before treating syntax checks as UI validation

## UI-REBUILD-003

Date. November 19, 2026

Tags. Design review, poster alignment, empty state

Mistake. Wide Discover shelves centered narrow posters within expanding wells while captions stayed left aligned. Empty Library also showed an unhelpful result range without folder instructions

Cause. Poster wells expanded independently of the artwork and the inherited result summary assumed a nonempty collection

Solution. Bounded poster wells to portrait dimensions and aligned them with captions. Added empty Library instructions, removed the empty result range and corrected singular genre counts

Verification. A fresh reviewer inspected all nine final recaptures and scored both requested fixes resolved with a ship verdict

Prevention. Inspect relationships between artwork and captions at wide sizes, and review empty-state copy independently from populated summaries

## UI-REBUILD-004

Date. November 19, 2026

Tags. PowerShell 5.1, UTF-8, sidecar encoding

Mistake. The documenter attempted the unsupported utf8NoBOM encoding option under Windows PowerShell 5.1

Cause. The encoding option belongs to a newer PowerShell version

Solution. Used System.IO.File.WriteAllText with System.Text.UTF8Encoding constructed with false to write the sidecar without a byte order mark

Verification. The sidecar parsed from UTF-8 bytes without a byte order mark. Token references and document metadata validated successfully

Prevention. Check the shell version before selecting encoding options, and verify JSON at the byte level

## UI-REBUILD-005

Date. November 19, 2026

Tags. Discover, scrolling, flicker, canvas Configure, Windows compositing

Correction. The user reported severe tearing while scrolling Discover after the static visual review passed

Cause. Moving the embedded native content frame emitted Configure notifications. Each wheel step rewrote the canvas scroll region despite unchanged dimensions, causing unnecessary layout invalidation. Static captures did not exercise this behavior

Solution. Update the scroll region only when content dimensions change, and set the embedded content width only when the viewport width changes. Preserve native scrolling and existing widgets

Rejected experiment. Windows WS_EX_COMPOSITED on the Discover container stalled initial Tk painting in two isolated probes. It was removed before packaging. A descendant poster class uses CS_PARENTDC, making blanket buffering unsuitable for this tree

Verification. All 10 regression tests pass. The native scroll test exercises repeated wheel movement without any canvas configuration calls and retains recommendation widget identities. An independent 120-event probe completed without scroll-region writes. Perceived tearing on the user's display still requires confirmation

Prevention. Check repeated scrolling and native callback counts, in addition to static screenshots. Do not promise display-level tear elimination from layout tests alone
