# Design Review: Certificate Manager (2026-10-31)

Tested from source (`py -3 main.py --web`, port 2323) in an 800×600 window, dark theme, logged in as admin.
Every page in the sidebar was opened, plus the main views. Nothing was saved, issued or deleted.

To fix an item, refer to its **ID** (e.g. "fix G2"). Status column: `open` / `fixed (commit)` / `won't fix`.

Severity: **H** = looks broken or blocks the user · **M** = clearly unprofessional · **L** = polish.

---

## G: Global (affects every page)

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| G1 | H | **Bilingual text everywhere, at two sizes.** Every label, button, tab and title is "Arabic big + English tiny" (English ~8–9px). The English is unreadable and doubles the visual noise. | Pick one UI language (Arabic) with an optional English setting; at most keep English in page titles. | fixed (e9d307f, 219891c) |
| G2 | H | **Labels truncated with "…" all over** (field labels "رقم الأمر الجامعي / …", "Certificate Number / …", "تسلسل …", "معدل ال…", "…icate Printer", "ility (EN)…", template "… D - SBS.docx]"). The bilingual labels don't fit. | Shorter single-language labels; allow 2-line labels; widen fields. | fixed (219891c): no clipped text on any page at 800×600 or 1366×768, both themes |
| G3 | M | **Double scrollbars.** The page content has its own scrollbar at the left edge *and* the outer window scrollbar between content and sidebar. | One scroll container (the content area only). | fixed (4d77088) |
| G4 | M | **Scrollbar on the wrong side.** In RTL, the content scrollbar sits at the far left, separated from the content it scrolls. | Follow the native RTL position or hide the inner one (see G3). | fixed (4d77088) |
| G5 | M | **Font stack is not bundled** (`nicegui_ui/theme.css:19`: Arial first, Cairo third). Arabic falls back to whatever the PC has, so the installed exe looks different from source. | Bundle Cairo (or IBM Plex Sans Arabic) woff2 in `assets/fonts` and load it with `@font-face`; put it first. | open: Cairo is not in the repo; f560bac puts local('Cairo') first, but bundling the woff2 needs a download the user must approve |
| G6 | M | **Button color has no meaning.** Primary (green), secondary (dark green) and "back" buttons all look like primary actions; for example "العودة لبيانات الطالب" is the same weight as "Issue". | 1 filled primary per screen, outlined secondary, text/ghost for back/cancel. | fixed (f560bac, then each page step) |
| G7 | M | **Red filled delete + red filled "Disable" on every row.** Lists are walls of red buttons (Personnel, Students, Departments, Courses). Destructive actions should be quiet until needed. | Icon-only ghost buttons, red only on hover, or a ⋮ menu per row. | fixed (f560bac, 5ec51ac, 6d90954, c69e59a) |
| G8 | L | **Header top-left is crowded**: avatar, status pill "متصل Online", name, logout and a separate "Refresh Data" card, all different heights. | One aligned header bar: refresh icon, then user chip (avatar + name) with a menu containing profile/logout. | fixed (4d77088) |
| G9 | L | **Sidebar items are separate bordered boxes** with bilingual text; the active item uses only a faint outline + green text. | Flat list, active = filled background + accent bar; single-language labels. | fixed (4d77088) |
| G10 | L | **Empty dark area below short pages** (Departments, Issue Certificate, Student view): the cards float with no anchoring. | Fine on its own; add page-level spacing scale and consistent top margin (currently 60–95 px, varies per page). | fixed (4d77088) |
| G11 | L | **Inconsistent page header**: some pages repeat the title twice (top bar "إدارة الطلاب" plus card title "إدارة الطلاب Students Management"), others don't. | Title once, in the top bar; cards get section titles only. | fixed (4d77088) |
| G12 | M | **Page switch is slow** (pages appear 1–3 s after click; also reported 2–3 s in the exe). | Profile page build; cache lookups; show skeleton immediately. | fixed (9f4b449): courses 596–883 → 38 ms, settings 717–793 → 135 ms; exe not measured |

## L: Login

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| L1 | M | Placeholders repeat both languages ("Enter Username / أدخل اسم المستخدم") on top of bilingual labels. | One-language placeholder or none. | fixed (9ad3403) |
| L2 | M | Sign-in button is light blue: the only blue in an app whose accent is green. | Use the app accent. | fixed (9ad3403) |
| L3 | L | Theme toggle floats under the card with no label. | Move to a corner, add tooltip. | fixed (9ad3403) |
| L4 | L | Left half: generic network-dots background; logo slightly off-center; the person icon on the card adds nothing. | Plain brand background, centered logo, remove icon. | fixed (9ad3403) |

## D: Dashboard

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| D1 | M | Stat card order is random (Departments 2, Students 1598): the most important number isn't first. | Order: Students, Issued certificates, Courses, Personnel. Issued count is missing entirely. | fixed (4940186) |
| D2 | L | Stat icons are 4 different colors (green/blue/purple/yellow) with no meaning. | One accent color, or meaning-based color. | fixed (f560bac, 9ad3403) |
| D3 | L | Quick Actions duplicate sidebar items and use "<" arrows that point the wrong way for "go forward" in RTL. | Keep but make them large tiles; fix arrow direction. | fixed (9ad3403) |
| D4 | L | The "Recent students" table is cut off at the bottom of the viewport with no visible rows on 800×600. | Put the table higher or make the stats compact. | fixed (9ad3403) |

## S: Students

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| S1 | M | Search placeholder is cut: "ابحث بالاسم (…nt by name)". | Shorter placeholder. | fixed (219891c, 5ec51ac) |
| S2 | M | Test data shown: "test2…test5", "تست تست", average "0", grad year "N/A". These look like bugs to a viewer. (Data, not design, but it hurts every screenshot.) | Clean test students from the dataset used for demos. | won't fix: this is data in the shared database, not design; the app must not write to MySQL here |
| S3 | L | Averages have inconsistent decimals (90, 56.895, 61.019). | Always 2 decimals. | fixed (5ec51ac) |
| S4 | M | Student view: the **Add Student** button does nothing while a student is open (the view replaces the list in place, with no clear "back" button except a small arrow). | Make the view a page with a clear back button, or a side panel over the list. | fixed (5ec51ac) |
| S5 | L | Student view "Personal details": label/value pairs run together ("الجنس: ذكر / Gender Male"), no columns; a lot of empty space. | Two-column definition list. | fixed (5ec51ac) |

## O: Graduation Orders

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| O1 | L | Each order card has 5 pill chips, all the same weight; the order number and date get lost. | Number + date prominent, chips as plain secondary text. | fixed (6d90954) |
| O2 | L | Date shown with stretched letter spacing ("تاريخ الأمر: 11-11-2025"). | Normal spacing; one date format app-wide. | fixed (6d90954) |

## P: Departments / Courses / Personnel

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| P1 | M | Departments: the search box has no placeholder or icon; it looks like an empty bar. | Placeholder + search icon. | fixed (c69e59a) |
| P2 | M | Departments: college name truncated in the chip "كلية علوم الحاسوب وتكنولوجيا المـ…". | Wrap or show on hover. | fixed (c69e59a) |
| P3 | M | Courses: each course card shows **editable dropdowns** inline (department/stage/units), with labels truncated ("…ment / القسم", "الوحـ…", "المر…"). Looks like a form, not a list, and invites accidental edits. | Read-only row; edit in a dialog. | fixed (6d90954) |
| P4 | L | Pagination buttons "السابق Previous / التالي Next" are tiny and the record text "Records 1 - 2 of 2 \| السجلات 1 - 2 من 2" is duplicated. | Standard paginator, one language. | fixed (6d90954) |
| P5 | L | Personnel: "بدون توقيع" chip appears on every row, adding noise. | Show only when a signature exists. | fixed (6d90954) |

## C: Issue Certificate

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| C1 | M | Search input text is vertically off (text sits at the bottom) and the field is very tall. | Normal input height, centered text. | fixed (79f9731) |
| C2 | M | Options view: many truncated labels (G2) plus template name "…D - SBS.docx]" showing a raw file name with a stray bracket. | Show template display_name from templates_config.json. | fixed (79f9731) |
| C3 | M | Toggle states are ambiguous: the "on" toggle (green track, dark knob) looks like "off", and the "Postponed years" toggle (white knob) looks like "on" but is off. | Standard switch styling: clear on/off colors. | fixed (f560bac) |
| C4 | L | The Rank dropdown shows overlapping text "الأمر ال… / r Count". | Fix width/label. | fixed (79f9731) |
| C5 | L | Transcript: course rows are bordered boxes inside a bordered card inside a bordered card (3 nested borders). | Flat table rows. | fixed (79f9731) |
| C6 | L | Grade chips "الدرجة: 90" use monospace + letter-spacing, unlike the rest of the app. | One font. | fixed (f560bac) |
| C7 | M | The bottom action row has 3 buttons of similar weight; the main action "Issue + PDF preview" is not the most prominent. | One primary button. | fixed (79f9731) |
| C8 | M | (From earlier) printer dialog label "…ect Printer" truncated, long file name truncated (`certificate_screen.py` ~1338–1349). | See G2. | fixed (79f9731) |

## R: Issued Certificates log

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| R1 | H | **Table is too wide**: columns are squeezed: "السنة Year" splits into 3 lines, "الدراسة" is cut, "الجه To" is cut at the left edge, and the template column text "Ar, Semester, SBS, cr" is clipped. | Fewer columns (merge Dept/Study), horizontal scroll, or detail on row click. | fixed (c9243f1, redone in 486a916: five columns) |
| R2 | M | Filter dropdowns show truncated values ("كل السنـ…", "كل الدرا…"). | Wider filters or 2 rows. | fixed (486a916) |
| R3 | L | Certificate numbers in blue chips, the rest plain. Fine, but numbers like "1000/29" vs "942/26" show the year mixed. | Data check. | won't fix: the numbers are stored that way; a data check, not a design change |

## T: Settings

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| T1 | M | The tabs row has more tabs than fit; scroll arrows appear and the last tab is just an icon. Hidden tabs are easy to miss. | Vertical tab list on the side of the settings page. | fixed (36d9693) |
| T2 | M | Institution: "College Name (EN)" value is clipped at the start: "…ge of Computer Science and Information Technology". | Wider field / textarea. | fixed (c69e59a) |
| T3 | M | Logo upload: the green upload bar shows "0.0B / 0.00%" and a large empty black box under it. Looks broken. | Hide the progress text until uploading; drop the empty box. | fixed (c69e59a) |
| T4 | L | Appearance: "Enable RTL" toggle appears in an Arabic-only app; turning it off would break every page. | Remove or move to an advanced section. | fixed (36d9693) |
| T5 | L | Printers: field labels truncated ("…icate Printer", "Lists Printer &…"). | See G2. | fixed (219891c, c69e59a) |
| T6 | L | Roles: cards are dense; four badges per card ("افتراضي Built-in", access, counts). | Simplify card. | fixed (c69e59a) |

## U: Profile

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| U1 | L | Tooltip "الملف الشخصي والحساب" overlaps the "Back to Dashboard" button. | Tooltip below/side. | fixed (4d77088) |
| U2 | L | Labels truncated ("…ility (EN)"). | See G2. | fixed (219891c, 3de2e64) |

## W: Word templates (from the earlier template audit)

| ID | Sev | Problem | Status |
|----|-----|---------|--------|
| W1 | H | `semester - Temp - En.docx` prints raw field names: "national_id:", "Sequence_of_Graduation:", "Average_of_First_Student:". | open: Word templates were out of scope for this pass (certificates must print exactly as before) |
| W2 | M | The `- D - SBS` templates have no National ID line. | open: Word templates were out of scope for this pass (certificates must print exactly as before) |
| W3 | M | English templates have RTL paragraph direction. | open: Word templates were out of scope for this pass (certificates must print exactly as before) |
| W4 | M | Semester footer "ناجح بالدور" cell order differs between Ar and En; may land on the wrong side (needs render). | open: Word templates were out of scope for this pass (certificates must print exactly as before) |
| W5 | L | Stray `…_test_files` folder and `~$` lock files in `templets/` (move to `old/`). | open: Word templates were out of scope for this pass (certificates must print exactly as before) |

## Not tested

- The exe build (only source). G5 and G12 matter most there.
- Saving, issuing, printing and deleting. These write records, so the check only looked and navigated. Reprint and "PDF" were opened on a local copy of one issued file.
- The Word templates (W1–W5): out of scope.
- Keyboard: Enter submits the login; Tab order in the other forms and dialogs was not checked.

---

## UX check (2026-11-04, after the redesign)

Checked in the running app (`main.py --web`) on every page and every settings tab, at 800×600 and 1366×768, in light and dark. On each page a script looked for clipped text, sideways scrolling of the content area, and text contrast below 4.5:1. After 3de2e64 none were found. Before 3de2e64, dark mode had one problem: the logo cards and other uses of `--bg-main` kept their light colour (1.04:1).

| Area | Score | Why |
|---|---|---|
| Learnability | 84 | Arabic only. A flat sidebar with one label each, one title per page in the top bar, and a three-step issue wizard whose steps are named. |
| Task speed | 82 | Issuing takes four clicks from the dashboard: sidebar, a recent student, next, issue. Lists show newest first. Reprint and PDF are one click from a log row. |
| Visual quality | 80 | Common colour tokens and button types are used throughout. No walls of red buttons, and borders are no longer nested. The system font stands in for Cairo (G5), so Arabic looks different on each PC. |
| Readability | 82 | Labels fit at 800×600, text contrast is at least 4.5:1 in both themes, and averages use two decimals. Some secondary captions are small. |
| Consistency | 84 | One page header, one primary button per screen, the same table, paginator and empty state on every list, and one date format. The profile and settings forms still use older card styles. |
| Feedback and safety | 80 | Every delete asks first, and delete buttons stay quiet. The wizard shows on the review step when a number is already taken and disables Issue. Reprint is disabled, with a note, when the file is missing. Saves still report through toasts only. |
| Performance | 82 | A page change shows a skeleton at once. Slow parts (the issued count, hidden tabs, the routines tab) load afterwards. The slowest page fell from about 0.9 s to 0.14 s. The exe was not measured. |
| Data presentation | 80 | Orders, courses and personnel are read-only tables. The issued log has five columns and details on click. Students use a two-column list. The S2 and R3 test data still shows. |
| **Overall** | **82** | |

Still open: G5 (font), W1–W5 (templates, out of scope). Won't fix: S2, R3 (data).
