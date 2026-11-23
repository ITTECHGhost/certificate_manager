"""Make temporary student ID cards from the Google-Form sheet + Drive photos zip.

Data lives OUTSIDE the repo (real student data): F:\\CR_PY\\student_ids_data
  *.xlsx  form responses   *.zip  Drive photos   front.*  back.*  card images
Usage:
  py -3 tools\\student_ids\\make_ids.py --issue 23/11/2026 --expiry 30/09/2027
Output in <data>\\output: cards\\NNN - name.png, cards_print.pdf (A4, 8 per page,
fronts then mirrored backs for duplex), matches.csv (row -> photo, editable:
fix a wrong photo in the 'photo' column and run again).
"""
import argparse
import csv
import glob
import io
import os
import sys
import zipfile
from datetime import datetime, timedelta

import arabic_reshaper
import openpyxl
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, ImageOps

DATA = r"F:\CR_PY\student_ids_data"
FONT_AR = r"C:\Windows\Fonts\tahomabd.ttf"
FONT_EN = r"C:\Windows\Fonts\arialbd.ttf"

# Layout for the 1063x650 front image: value boxes (left, top, right, bottom)
BOXES = [(272, 218, 828, 268), (272, 280, 828, 328), (272, 340, 828, 388),
         (272, 400, 828, 450), (272, 464, 828, 514), (272, 526, 828, 576)]
PHOTO = (36, 212, 250, 468)           # inside the purple frame
DEPT_BOX = (40, 596, 380, 646)        # left of "قسم", white text
TYPE_BOX = (480, 596, 880, 646)       # left of "نوع الدراسة", white text
TEXT = (40, 20, 60)


def ar(s):
    return get_display(arabic_reshaper.reshape(s))


def fit_font(path, text, max_w, size):
    while size > 12:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 1
    return ImageFont.truetype(path, size)


def draw_in(d, box, text, arabic, fill=TEXT, size=30, align="right"):
    if not text:
        return
    txt = ar(text) if arabic else text
    f = fit_font(FONT_AR if arabic else FONT_EN, txt, box[2] - box[0] - 24, size)
    w = f.getlength(txt)
    x = box[2] - 12 - w if align == "right" else (box[0] + box[2] - w) / 2
    d.text((x, (box[1] + box[3]) / 2), txt, font=f, fill=fill, anchor="lm")


def fmt_date(v):
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y")
    return str(v or "").strip()


def cover(img, w, h):
    img = ImageOps.exif_transpose(img).convert("RGB")
    # keep the top part (faces) when cropping tall photos
    return ImageOps.fit(img, (w, h), Image.LANCZOS, centering=(0.5, 0.3))


def match_photos(rows, zf):
    """Drive zip times are upload times in another zone (whole-hour offset),
    a few seconds to minutes before the form timestamp. Pick the offset that
    matches most rows, then the closest earlier unused photo for each row."""
    infos = [i for i in zf.infolist() if not i.is_dir()]
    times = [(datetime(*i.date_time), i.filename) for i in infos]
    import difflib
    tr = str.maketrans("أإآةىؤئ", "اااهيوي")

    def norm(s):
        return "".join(c for c in str(s or "").lower().translate(tr) if c.isalpha())

    def sim(names, uploader):
        u = norm(uploader)
        if len(u) < 3:
            return 0.0
        # compare uploader name with the same-length start of each student name
        return max(difflib.SequenceMatcher(None, u, norm(x)[:len(u) + 2]).ratio() for x in names)

    best = None
    for h in range(-14, 15):
        pairs = []
        for idx, r in enumerate(rows):
            t = r[0] - timedelta(hours=h)
            for zt, n in times:
                sec = (t - zt).total_seconds()
                if -5 <= sec <= 900:
                    uploader = os.path.splitext(n.split("/")[-1])[0].rsplit(" - ", 1)[-1]
                    s = sim((r[1], r[2]), uploader)
                    pairs.append((sec - (600 * s if s > 0.6 else 0), idx, n))
        used, res = set(), {}
        for _, idx, n in sorted(pairs):  # best pairs first (time + name)
            if idx not in res and n not in used:
                res[idx] = n
                used.add(n)
        if best is None or len(res) > len(best):
            best = res
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--issue", default="", help="issue date text, e.g. 23/11/2026")
    ap.add_argument("--expiry", default="", help="expiry date text")
    a = ap.parse_args()

    xlsx = glob.glob(os.path.join(a.data, "*.xlsx"))[0]
    zpath = glob.glob(os.path.join(a.data, "*.zip"))[0]
    front = Image.open(glob.glob(os.path.join(a.data, "front.*"))[0]).convert("RGB")
    back = Image.open(glob.glob(os.path.join(a.data, "back.*"))[0]).convert("RGB")
    out = os.path.join(a.data, "output")
    os.makedirs(os.path.join(out, "cards"), exist_ok=True)

    ws = openpyxl.load_workbook(xlsx).active
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] and r[1]]
    zf = zipfile.ZipFile(zpath)

    mcsv = os.path.join(out, "matches.csv")
    if os.path.exists(mcsv):  # user-edited matches win
        with open(mcsv, encoding="utf-8-sig") as f:
            saved = {int(r["row"]): r["photo"] for r in csv.DictReader(f)}
        matches = {i: saved.get(i + 2, "") for i in range(len(rows))}
    else:
        matches = match_photos(rows, zf)
        with open(mcsv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["row", "name", "photo"])
            for i, r in enumerate(rows):
                w.writerow([i + 2, (r[1] or "").strip(), matches.get(i, "")])

    cards, problems = [], []
    for i, r in enumerate(rows):
        name_ar, name_en = (r[1] or "").strip(), (r[2] or "").strip()
        card = front.copy()
        d = ImageDraw.Draw(card)
        vals = [(name_ar, True), (name_en, False), (fmt_date(r[3]), False),
                ((r[6] or "").strip(), True), (a.issue, False), (a.expiry, False)]
        for box, (v, is_ar) in zip(BOXES, vals):
            draw_in(d, box, v, is_ar)
        draw_in(d, DEPT_BOX, (r[4] or "").strip(), True, fill="white", size=28, align="center")
        draw_in(d, TYPE_BOX, (r[5] or "").strip(), True, fill="white", size=28, align="center")
        pname = matches.get(i, "")
        try:
            if not pname:
                raise ValueError("no photo matched")
            ph = cover(Image.open(io.BytesIO(zf.read(pname))),
                       PHOTO[2] - PHOTO[0], PHOTO[3] - PHOTO[1])
            card.paste(ph, PHOTO[:2])
        except Exception as e:  # HEIC, missing, broken
            problems.append(f"row {i + 2} {name_ar}: photo - {e}")
        safe = "".join(c for c in name_en if c.isalnum() or c == " ").strip() or f"row{i + 2}"
        card.save(os.path.join(out, "cards", f"{i + 2:03d} - {safe}.png"))
        cards.append(card)

    make_pdf(cards, back, os.path.join(out, "cards_print.pdf"))
    print(f"{len(cards)} cards -> {out}")
    for p in problems:
        print("  !", p)


def make_pdf(cards, back, path, dpi=300):
    mm = dpi / 25.4
    pw, ph = int(210 * mm), int(297 * mm)
    cw, ch = int(85.6 * mm), int(54 * mm)
    gx, gy = int(6 * mm), int(6 * mm)
    x0 = (pw - 2 * cw - gx) // 2
    y0 = (ph - 4 * ch - 3 * gy) // 2
    bk = back.resize((cw, ch), Image.LANCZOS)
    pages = []
    for s in range(0, len(cards), 8):
        fp = Image.new("RGB", (pw, ph), "white")
        bp = Image.new("RGB", (pw, ph), "white")
        for k, c in enumerate(cards[s:s + 8]):
            col, row = k % 2, k // 2
            y = y0 + row * (ch + gy)
            fp.paste(c.resize((cw, ch), Image.LANCZOS), (x0 + col * (cw + gx), y))
            bp.paste(bk, (x0 + (1 - col) * (cw + gx), y))  # mirrored for duplex
        pages += [fp, bp]
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=dpi)


if __name__ == "__main__":
    sys.exit(main())
