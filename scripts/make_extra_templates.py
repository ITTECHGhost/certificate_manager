"""Builds the postgraduate and English-language confirmations from the college's sample files
(templets/new_temp): the sample's text is replaced by template tags, its layout is kept.

Run again after editing a sample:  py scripts\\make_extra_templates.py [templets folder]
Pictures and shapes (photo box, logo) are never touched: only the text of chosen paragraphs."""
import copy
import json
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn

AVG = "({{ average|replace('.', ',') }}) {{ average_words_permille or average_words }}"
FIRST = "({{Average_of_First_Student}}) {{Average_of_First_Student_words}}"

AR_WORDS = {
    "female": dict(photo="الملصقة صورتها أعلاه هي إحدى خريجات", granted="قد منحت", dept="قسمها",
                   req="وبناء على طلبها زودت بهذا التأييد."),
    "male": dict(photo="الملصقة صورته أعلاه هو أحد خريجي", granted="قد منح", dept="قسمه",
                 req="وبناء على طلبه زود بهذا التأييد."),
}


def postgrad_text(gender: str, evening: bool) -> str:
    w = AR_WORDS[gender]
    if evening:
        scope = f"على {w['dept']} للدراستين الصباحية والمسائية وللدورين الأول والثاني"
    else:
        scope = f"على {w['dept']} للدراسة {{{{study_type}}}} علمًا أنه لا توجد دراسة مسائية للسنة أعلاه"
    return ("نؤيد لكم ان {{student_name}} " + w["photo"] + " كليتنا للعام الدراسي "
            "{{ graduation_academic_year or graduation_year }} " + w["granted"] + " شهادة بكالوريوس العلوم في "
            "تكنولوجيا المعلومات/ {{department_id}}/ الدراسة {{study_type}}/ (الدور {{graduation_semester}}) للعام أعلاه "
            "حسب الامر الجامعي ذي العدد ({{order_number}}) في ({{order_date}}) بتقدير ({{Grade}}) وبمعدل تخرج "
            + AVG + " بتسلسل ({{Sequence_of_Graduation}}) من أصل ({{num_students}}) خريج " + scope +
            " وان معدل التخرج للطالب الأول هو " + FIRST + ". ولا يعتبر هذا التأييد وثيقة تخرج " + w["req"])


def language_text(gender: str) -> str:
    who, pron = ("Mr.", "his") if gender == "male" else ("Ms.", "her")
    return (f"This is to certify that {who} {{{{ student_name|upper }}}} has been graduated from the College of "
            "Computer Science and Information Technology, {{department_id}} Department. Note that most of the "
            "courses studied in the bachelor's degree program were conducted in English. "
            f"Upon {pron} request, this information was provided.")


def _runs(p):
    return [r for r in p.iter(qn("w:r")) if not r.xpath(".//w:drawing|.//w:pict")
            and r.getparent() is p or (r.getparent().tag == qn("w:hyperlink") and r.getparent().getparent() is p)]


def set_text(p, text: str) -> None:
    """Whole text into the first text run (keeps its format); other text runs emptied."""
    runs = [r for r in p.findall(qn("w:r")) if not r.xpath(".//w:drawing|.//w:pict")]
    for i, r in enumerate(runs):
        for t in r.findall(qn("w:t")):
            r.remove(t)
        if i == 0:
            t = r.makeelement(qn("w:t"), {})
            t.text = text
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            r.append(t)


def _text(p) -> str:
    return "".join(t.text or "" for t in p.iter(qn("w:t")))


def convert(src: Path, out: Path, rules) -> None:
    """rules: [(predicate(text) -> bool, new_text)], applied to every paragraph incl. text boxes."""
    d = docx.Document(str(src))
    done = set()
    for p in d.element.body.iter(qn("w:p")):
        txt = _text(p).strip()
        for i, (match, new) in enumerate(rules):
            if txt and match(txt):
                set_text(p, new)
                done.add(i)
                break
    missing = [i for i in range(len(rules)) if i not in done]
    if missing:
        sys.exit(f"{src.name}: rules {missing} matched nothing")
    d.save(str(out))


def sig_rules(lang: str):
    if lang == "En":   # one signer: the assistant dean (sig3)
        return [(lambda t: t.startswith("Prof.") or "Alasadi" in t, "{{sig3_title}} {{sig3_name}}"),
                (lambda t: t.lower().startswith(("dean assistant", "vice chancellor")), "{{sig3_resp}}")]
    return [(lambda t: t == "الأستاذ الدكتور", "{{sig3_title}}"),
            (lambda t: t in ("عباس حنون حسن", "رائدة سالم خضير"), "{{sig3_name}}"),
            (lambda t: t.startswith("معاون العميد"), "{{sig3_resp}}"),
            (lambda t: t in ("ثمينة محمد خلف", "اسراء فاضل عبد"), "{{sig5_name}}"),
            (lambda t: t == "مسؤول وحدة الوثائق", "{{sig5_resp}}")]


def main(folder: Path) -> None:
    src = folder / "new_temp"
    cfg_path = folder / "templates_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.is_file() else {}
    jobs = []
    for evening, sample, label in ((False, "تاييد تقديم دراسات عليا_ بدون مسائي.docx", "بدون مسائي"),
                                   (True, "تاييد تقديم دراسات عليا_مع مسائي.docx", "مع مسائي")):
        for g in ("female", "male"):
            key = f"postgrad - {'evening' if evening else 'morning'} - Ar - {g}"
            rules = [(lambda t: t.startswith("الـــــى//") or t.startswith("الـــــى"), "الـــــى// {{Title}}"),
                     (lambda t: t.startswith("نؤيد لكم ان"), postgrad_text(g, evening))] + sig_rules("Ar")
            jobs.append((sample, key, rules, dict(display_name=f"تأييد تقديم دراسات عليا ({label})", lang="Ar",
                                                  lang_ar="عربي", type_ar="تأييد دراسات عليا", gender=g.capitalize())))
    for sample, g in (("تاييد لغة انكليزية انثى.docx", "female"), ("تاييد لغة انكليزية ذكر.docx", "male")):
        rules = [(lambda t: t.startswith("This is to certify"), language_text(g))] + sig_rules("En")
        jobs.append((sample, f"language - En - {g}", rules,
                     dict(display_name="تأييد لغة إنكليزية", lang="En", lang_ar="إنكليزي", type_ar="تأييد لغة",
                          gender=g.capitalize())))
    for sample, key, rules, info in jobs:
        convert(src / sample, folder / f"{key}.docx", rules)
        entry = copy.deepcopy(cfg.get(key) or {})
        entry.update(info, file=f"{key}.docx", system="Any", system_ar="كل الأنظمة", sbs=False)
        cfg[key] = entry
        print(key)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "templets")
