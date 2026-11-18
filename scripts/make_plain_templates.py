"""Builds every "without grades" graduation certificate (تأييد تخرج) from ONE master:
templets/year - Temp - Ar - female.docx (the layout the documents unit approved).

Run again after editing that master:  py scripts\\make_plain_templates.py [templets folder]
Writes male/female x Arabic/English x annual/semester and updates templates_config.json.
Only the three text paragraphs change; layout, photo box and signature table are copied."""
import copy
import json
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

MASTER = "year - Temp - Ar - female.docx"

AR_BODY = {
    "female": ("الملصقة صورتها أعلاه هي إحدى خريجات", "قد منحت"),
    "male": ("الملصقة صورته أعلاه هو أحد خريجي", "قد منح"),
}
EN_PRONOUN = {"female": "She was", "male": "He was"}


def ar_rest(gender: str, system: str) -> str:
    who, granted = AR_BODY[gender]
    round_part = "(الدور {{graduation_semester}})" if system == "year" else "({{graduation_semester}})"
    return (f" {who} كليتنا للعام الدراسي {{{{ graduation_academic_year or graduation_year }}}} {round_part}، "
            f"{granted} شهادة بكالوريوس العلوم في تكنولوجيا المعلومات/ {{{{department_id}}}}/ الدراسة {{{{study_type}}}} "
            "حسب الامر الجامعي ذي العدد ({{order_number}}) في {{order_date}} بتقدير ({{Grade}}) "
            "وبمعدل تخرج ({{ average|replace('.', ',') }}) {{ average_words_permille or average_words }}.")


def en_rest(gender: str, system: str) -> str:
    round_part = "({{graduation_semester}} round)" if system == "year" else "({{graduation_semester}})"
    return (", whose photograph is attached above, is one of the graduates of our college for the academic year "
            f"{{{{ graduation_academic_year or graduation_year }}}} {round_part}. {EN_PRONOUN[gender]} awarded the degree "
            "of Bachelor of Science in Information Technology / {{department_id}} / {{study_type}} study, according to "
            "University Order No. ({{order_number}}) dated {{order_date}}, with the grade ({{Grade}}) and a graduation "
            "average of ({{average}}).")


def _set_runs(paragraph, texts):
    """Put texts into the paragraph's runs in order (extra runs emptied), keeping each run's format."""
    runs = paragraph.runs
    for i, r in enumerate(runs):
        r.text = texts[i] if i < len(texts) else ""


def _to_ltr(document):
    """English: drop right-to-left marks so the text reads left to right."""
    body = document.element.body
    for tag in ("w:bidi", "w:rtl", "w:bidiVisual"):
        for el in body.iter(qn(tag)):
            el.getparent().remove(el)


def build(master: Path, out: Path, lang: str, gender: str, system: str) -> None:
    d = docx.Document(str(master))
    paras = [p for p in d.paragraphs if p.text.strip()]
    title, to_line, body = paras[0], paras[1], paras[2]
    if lang == "Ar":
        _set_runs(title, ["", "تأييد", " تخرج"])
        _set_runs(to_line, ["الـــى/  {{Title}}"])
        _set_runs(body, ["نؤيد لكم ان ", "{{student_name}}", ar_rest(gender, system)])
    else:
        _to_ltr(d)
        _set_runs(title, ["", "Certification of Graduation"])
        _set_runs(to_line, ["To/ {{Title}}"])
        _set_runs(body, ["We certify that ", "{{student_name}}", en_rest(gender, system)])
        body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    d.save(str(out))


def main(folder: Path) -> None:
    master = folder / MASTER
    if not master.is_file():
        sys.exit(f"Master not found: {master}")
    tmp_master = folder / ".master_copy.docx"
    tmp_master.write_bytes(master.read_bytes())          # the master itself is rewritten too
    cfg_path = folder / "templates_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.is_file() else {}
    system_info = {
        "year": ("Annual", "فصلي"),
        "semester": ("Semester", "مقررات"),
    }
    made = []
    try:
        for system in ("year", "semester"):
            for lang in ("Ar", "En"):
                for gender in ("female", "male"):
                    key = f"{system} - Temp - {lang} - {gender}"
                    build(tmp_master, folder / f"{key}.docx", lang, gender, system)
                    sys_tag, sys_word = system_info[system]
                    entry = copy.deepcopy(cfg.get(key) or {})
                    entry.update({
                        "display_name": f"تأييد تخرج {'عربي' if lang == 'Ar' else 'انجليزي'} {sys_word}",
                        "file": f"{key}.docx", "lang": lang,
                        "lang_ar": "عربي" if lang == "Ar" else "إنكليزي",
                        "system": sys_tag, "sbs": False, "type_ar": "بدون درجات",
                        "gender": gender.capitalize(),
                    })
                    if system == "semester":
                        entry.setdefault("system_ar", "نظام المقررات (الساعات المعتمدة)")
                        entry.setdefault("system_name", "نظام المقررات (الساعات المعتمدة)")
                    cfg[key] = entry
                    made.append(key)
    finally:
        tmp_master.unlink(missing_ok=True)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(made))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "templets")
