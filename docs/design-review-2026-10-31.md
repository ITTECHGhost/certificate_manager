# Design Review: Certificate Manager (2026-10-31)

Tested from source (`py -3 main.py --web`, port 2323) in an 800×600 window, dark theme, logged in as admin.
Every page in the sidebar was opened, plus the main views. Nothing was saved, issued or deleted.

To fix an item, refer to its **ID** (e.g. "fix G2"). Status column: `open` / `fixed (commit)` / `won't fix`.

Severity: **H** = looks broken or blocks the user · **M** = clearly unprofessional · **L** = polish.

---

## G: Global (affects every page)

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| G1 | H | **Bilingual text everywhere, at two sizes.** Every label, button, tab and title is "Arabic big + English tiny" (English ~8–9px). The English is unreadable and doubles the visual noise. | Pick one UI language (Arabic) with an optional English setting; at most keep English in page titles. | fixed (e9d307f) |
| G2 | H | **Labels truncated with "…" all over** (field labels "رقم الأمر الجامعي / …", "Certificate Number / …", "تسلسل …", "معدل ال…", "…icate Printer", "ility (EN)…", template "… D - SBS.docx]"). The bilingual labels don't fit. | Shorter single-language labels; allow 2-line labels; widen fields. | partly (e9d307f): English removed, not verified |
| G3 | M | **Double scrollbars.** The page content has its own scrollbar at the left edge *and* the outer window scrollbar between content and sidebar. | One scroll container (the content area only). | open |
| G4 | M | **Scrollbar on the wrong side.** In RTL, the content scrollbar sits at the far left, separated from the content it scrolls. | Follow the native RTL position or hide the inner one (see G3). | open |
| G5 | M | **Font stack is not bundled** (`nicegui_ui/theme.css:19`: Arial first, Cairo third). Arabic falls back to whatever the PC has, so the installed exe looks different from source. | Bundle Cairo (or IBM Plex Sans Arabic) woff2 in `assets/fonts` and load it with `@font-face`; put it first. | open |
| G6 | M | **Button color has no meaning.** Primary (green), secondary (dark green) and "back" buttons all look like primary actions; for example "العودة لبيانات الطالب" is the same weight as "Issue". | 1 filled primary per screen, outlined secondary, text/ghost for back/cancel. | open |
| G7 | M | **Red filled delete + red filled "Disable" on every row.** Lists are walls of red buttons (Personnel, Students, Departments, Courses). Destructive actions should be quiet until needed. | Icon-only ghost buttons, red only on hover, or a ⋮ menu per row. | open |
| G8 | L | **Header top-left is crowded**: avatar, status pill "متصل Online", name, logout and a separate "Refresh Data" card, all different heights. | One aligned header bar: refresh icon, then user chip (avatar + name) with a menu containing profile/logout. | open |
| G9 | L | **Sidebar items are separate bordered boxes** with bilingual text; the active item uses only a faint outline + green text. | Flat list, active = filled background + accent bar; single-language labels. | open |
| G10 | L | **Empty dark area below short pages** (Departments, Issue Certificate, Student view): the cards float with no anchoring. | Fine on its own; add page-level spacing scale and consistent top margin (currently 60–95 px, varies per page). | open |
| G11 | L | **Inconsistent page header**: some pages repeat the title twice (top bar "إدارة الطلاب" plus card title "إدارة الطلاب Students Management"), others don't. | Title once, in the top bar; cards get section titles only. | open |
| G12 | M | **Page switch is slow** (pages appear 1–3 s after click; also reported 2–3 s in the exe). | Profile page build; cache lookups; show skeleton immediately. | open |

## L: Login

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| L1 | M | Placeholders repeat both languages ("Enter Username / أدخل اسم المستخدم") on top of bilingual labels. | One-language placeholder or none. | open |
| L2 | M | Sign-in button is light blue: the only blue in an app whose accent is green. | Use the app accent. | open |
| L3 | L | Theme toggle floats under the card with no label. | Move to a corner, add tooltip. | open |
| L4 | L | Left half: generic network-dots background; logo slightly off-center; the person icon on the card adds nothing. | Plain brand background, centered logo, remove icon. | open |

## D: Dashboard

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| D1 | M | Stat card order is random (Departments 2, Students 1598): the most important number isn't first. | Order: Students, Issued certificates, Courses, Personnel. Issued count is missing entirely. | fixed (4940186) |
| D2 | L | Stat icons are 4 different colors (green/blue/purple/yellow) with no meaning. | One accent color, or meaning-based color. | open |
| D3 | L | Quick Actions duplicate sidebar items and use "<" arrows that point the wrong way for "go forward" in RTL. | Keep but make them large tiles; fix arrow direction. | open |
| D4 | L | The "Recent students" table is cut off at the bottom of the viewport with no visible rows on 800×600. | Put the table higher or make the stats compact. | open |

## S: Students

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| S1 | M | Search placeholder is cut: "ابحث بالاسم (…nt by name)". | Shorter placeholder. | partly (e9d307f): English removed, not verified |
| S2 | M | Test data shown: "test2…test5", "تست تست", average "0", grad year "N/A". These look like bugs to a viewer. (Data, not design, but it hurts every screenshot.) | Clean test students from the dataset used for demos. | open |
| S3 | L | Averages have inconsistent decimals (90, 56.895, 61.019). | Always 2 decimals. | open |
| S4 | M | Student view: the **Add Student** button does nothing while a student is open (the view replaces the list in place, with no clear "back" button except a small arrow). | Make the view a page with a clear back button, or a side panel over the list. | open |
| S5 | L | Student view "Personal details": label/value pairs run together ("الجنس: ذكر / Gender Male"), no columns; a lot of empty space. | Two-column definition list. | open |

## O: Graduation Orders

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| O1 | L | Each order card has 5 pill chips, all the same weight; the order number and date get lost. | Number + date prominent, chips as plain secondary text. | open |
| O2 | L | Date shown with stretched letter spacing ("تاريخ الأمر: 11-11-2025"). | Normal spacing; one date format app-wide. | open |

## P: Departments / Courses / Personnel

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| P1 | M | Departments: the search box has no placeholder or icon; it looks like an empty bar. | Placeholder + search icon. | open |
| P2 | M | Departments: college name truncated in the chip "كلية علوم الحاسوب وتكنولوجيا المـ…". | Wrap or show on hover. | open |
| P3 | M | Courses: each course card shows **editable dropdowns** inline (department/stage/units), with labels truncated ("…ment / القسم", "الوحـ…", "المر…"). Looks like a form, not a list, and invites accidental edits. | Read-only row; edit in a dialog. | open |
| P4 | L | Pagination buttons "السابق Previous / التالي Next" are tiny and the record text "Records 1 - 2 of 2 \| السجلات 1 - 2 من 2" is duplicated. | Standard paginator, one language. | open |
| P5 | L | Personnel: "بدون توقيع" chip appears on every row, adding noise. | Show only when a signature exists. | open |

## C: Issue Certificate

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| C1 | M | Search input text is vertically off (text sits at the bottom) and the field is very tall. | Normal input height, centered text. | open |
| C2 | M | Options view: many truncated labels (G2) plus template name "…D - SBS.docx]" showing a raw file name with a stray bracket. | Show template display_name from templates_config.json. | partly (e9d307f): English removed, not verified |
| C3 | M | Toggle states are ambiguous: the "on" toggle (green track, dark knob) looks like "off", and the "Postponed years" toggle (white knob) looks like "on" but is off. | Standard switch styling: clear on/off colors. | open |
| C4 | L | The Rank dropdown shows overlapping text "الأمر ال… / r Count". | Fix width/label. | open |
| C5 | L | Transcript: course rows are bordered boxes inside a bordered card inside a bordered card (3 nested borders). | Flat table rows. | open |
| C6 | L | Grade chips "الدرجة: 90" use monospace + letter-spacing, unlike the rest of the app. | One font. | open |
| C7 | M | The bottom action row has 3 buttons of similar weight; the main action "Issue + PDF preview" is not the most prominent. | One primary button. | open |
| C8 | M | (From earlier) printer dialog label "…ect Printer" truncated, long file name truncated (`certificate_screen.py` ~1338–1349). | See G2. | partly (e9d307f): English removed, not verified |

## R: Issued Certificates log

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| R1 | H | **Table is too wide**: columns are squeezed: "السنة Year" splits into 3 lines, "الدراسة" is cut, "الجه To" is cut at the left edge, and the template column text "Ar, Semester, SBS, cr" is clipped. | Fewer columns (merge Dept/Study), horizontal scroll, or detail on row click. | fixed (c9243f1) |
| R2 | M | Filter dropdowns show truncated values ("كل السنـ…", "كل الدرا…"). | Wider filters or 2 rows. | open |
| R3 | L | Certificate numbers in blue chips, the rest plain. Fine, but numbers like "1000/29" vs "942/26" show the year mixed. | Data check. | open |

## T: Settings

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| T1 | M | The tabs row has more tabs than fit; scroll arrows appear and the last tab is just an icon. Hidden tabs are easy to miss. | Vertical tab list on the side of the settings page. | fixed (36d9693) |
| T2 | M | Institution: "College Name (EN)" value is clipped at the start: "…ge of Computer Science and Information Technology". | Wider field / textarea. | open |
| T3 | M | Logo upload: the green upload bar shows "0.0B / 0.00%" and a large empty black box under it. Looks broken. | Hide the progress text until uploading; drop the empty box. | open |
| T4 | L | Appearance: "Enable RTL" toggle appears in an Arabic-only app; turning it off would break every page. | Remove or move to an advanced section. | fixed (36d9693) |
| T5 | L | Printers: field labels truncated ("…icate Printer", "Lists Printer &…"). | See G2. | partly (e9d307f): English removed, not verified |
| T6 | L | Roles: cards are dense; four badges per card ("افتراضي Built-in", access, counts). | Simplify card. | open |

## U: Profile

| ID | Sev | Problem | Fix | Status |
|----|-----|---------|-----|--------|
| U1 | L | Tooltip "الملف الشخصي والحساب" overlaps the "Back to Dashboard" button. | Tooltip below/side. | open |
| U2 | L | Labels truncated ("…ility (EN)"). | See G2. | partly (e9d307f): English removed, not verified |

## W: Word templates (from the earlier template audit)

| ID | Sev | Problem | Status |
|----|-----|---------|--------|
| W1 | H | `semester - Temp - En.docx` prints raw field names: "national_id:", "Sequence_of_Graduation:", "Average_of_First_Student:". | open |
| W2 | M | The `- D - SBS` templates have no National ID line. | open |
| W3 | M | English templates have RTL paragraph direction. | open |
| W4 | M | Semester footer "ناجح بالدور" cell order differs between Ar and En; may land on the wrong side (needs render). | open |
| W5 | L | Stray `…_test_files` folder and `~$` lock files in `templets/` (move to `old/`). | open |

## Not tested

- Light theme (only dark was checked).
- The exe build (only source); G5/G12 matter most there.
- Add/edit dialogs that save data, Issue/Print flow (would write records).
- Windows wider than 800×600.

---

## UX check (2026-11-02, Haiku run)

Status of the run: steps 1 (partial), 3, 4 (partial), 5 (partial), 9 (partial) are committed on `claude/certificate-design-fixes-dce558`. Steps 2, 6, 7, 8, 10 are not started. Browser checks were **not run**: they need a signed-in session, and the sign-in was not given. Each answer below is therefore based on the code, not on a screenshot.

- **Can a new admin issue a certificate in 4 clicks or fewer from the dashboard, without reading English?** Not verified. The labels are Arabic only now, but the flow was not clicked through.
- **Is there any "…" truncation left at 800×600?** Not verified. Labels lost their English halves, which should remove most truncation, but no screenshot was taken.
- **Does every screen have exactly one primary button?** Not checked. Step 2 (button variants) is not done.
- **Do Tab order and Enter-to-submit work in login, search and dialogs?** Not checked.
- **Is text contrast at least 4.5:1 in both themes?** Not checked. The accent palette still includes blue tokens (`--accent-primary` is `#607eb8`), which the brief asks to replace with green.

Open items that block a clean UX check: Cairo font not bundled (needs download approval), G7 red delete buttons on other lists, G8 and G9 header and sidebar styling, and the browser pass in light and dark themes.
