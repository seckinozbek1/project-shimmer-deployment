"""Gate checks 495 to 499: the reader gaps D-668 names that were still open (15 November audit).

495 Unicode heading ids (gap 11): a heading in any script gets a stable id of its own through the
    one tokeniser, an ASCII heading's id is byte for byte the legacy one, and every id that moves
    is listed by the migration; two versions of a document written in another script are told
    apart by heading, where every heading used to be `unit`.
496 One tokeniser: `pairing_map.words` is the split every label, heading and passage word goes
    through; a combining mark joins its letter and composed and decomposed text read alike.
497 PDF layout (READER-LAYERS-A): a two-column PDF built here is read column by column, its
    running header and footer set apart, its table written as `|` rows, its headings as `#`
    lines; a table that does not line up and text at an angle are recorded lost; with no
    settings declared the structure is recorded lost.
498 Sentences in other scripts: ends decided by form (wide stops, danda, Arabic, Greek and
    Armenian marks, capitals of any script), and ASCII text ends exactly where it always did.
499 READING-A: a stretch Python cannot split is refused on the record, in the passage pairs row.

Every proof runs the real code on a fixture built here and is proven by neutralise, fail, restore,
pass (scripts/effect_proof.py). The PDF proofs read through a stand-in for pypdf's reader whose
pages hand the text visitor exactly what the built file draws, so they need no library; one more
proof reads the built file with the real pypdf and is SKIPPED, saying so, when pypdf is not
installed. Fixtures carry no domain vocabulary.
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import pairing_map  # noqa: E402
import passage_pairs  # noqa: E402
import pdf_layers  # noqa: E402
import pdf_layout  # noqa: E402
import sentence_split  # noqa: E402
from effect_proof import ProofFailure, prove_effect  # noqa: E402


def _verdict(ok, detail=""):
    return ("PASS", detail) if ok else ("FAIL", detail)


def _run(proofs, detail):
    for name, observe, check, neutralise in proofs:
        try:
            prove_effect(name=name, validate=lambda: True, observe=observe, check=check, neutralise=neutralise)
        except ProofFailure as e:
            return "FAIL", "%s: %s" % (name, e.category)
    return "PASS", "%d proof(s): %s" % (len(proofs), detail)


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stderr(io.StringIO()):
        yield


# ---------- 495: Unicode heading ids --------------------------------------------------------------

CYRILLIC = "Обзор"                    # a heading in Cyrillic
CYRILLIC_B = "Итог"                         # another
CJK = "概要"                                            # two ideographs
CJK_B = "結論"
DEVANAGARI = "मुख्य भाग"  # vowel signs and a virama
ARABIC = "مقدمة"
LATIN_MARKED = "Résumé général"
LATIN_DECOMPOSED = unicodedata.normalize("NFD", LATIN_MARKED)


def _doc(headings, body="A line of text under it."):
    return "# Title\n\nLead text above the first heading.\n\n" + "".join(
        "## %s\n%s\n\n" % (h, body) for h in headings)


def _observe_ids():
    ids = [u["unit_id"] for u in pairing_map.split_units(_doc([CYRILLIC, CJK, DEVANAGARI, ARABIC, LATIN_MARKED]))]
    again = [u["unit_id"] for u in pairing_map.split_units(_doc([CYRILLIC, CJK, DEVANAGARI, ARABIC, LATIN_DECOMPOSED]))]
    return {"ids": ids, "again": again,
            "migration": pairing_map.unit_id_migration(_doc([CYRILLIC, CJK])),
            "migrate": [pairing_map.migrate_unit_id("u01-unit", pairing_map.unit_id_migration(_doc([CYRILLIC]))),
                        pairing_map.migrate_unit_id("u01-unit", pairing_map.unit_id_migration(_doc([CYRILLIC]))
                                                    + pairing_map.unit_id_migration(_doc([CJK])))]}


def _check_ids():
    o = _observe_ids()
    sections = o["ids"][1:]
    slugs = [i.split("-", 1)[1] for i in sections]
    ok = (len(sections) == 5 and len(set(slugs)) == 5 and "unit" not in slugs
          and all(re.fullmatch(r"u0\d-[a-z0-9-]+", i) for i in sections)
          and slugs[4] == "resume-general" and o["ids"] == o["again"]
          and o["migration"] == [{"index": 1, "from": "u01-unit", "to": sections[0]},
                                 {"index": 2, "from": "u02-unit", "to": sections[1]}]
          and o["migrate"] == [sections[0], None])
    return _verdict(ok, "headings in five scripts get distinct ASCII ids, the same composed or decomposed")


def _observe_ascii():
    """Every unit id of every shipped corpus document is the legacy id, and nothing moves."""
    out = {}
    for path in sorted((ROOT / "benchmark" / "corpora").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        out[path.name] = {"ids": [u["unit_id"] for u in pairing_map.split_units(text)],
                          "moved": pairing_map.unit_id_migration(text)}
    return out


def _check_ascii():
    import json
    pinned = json.loads((ROOT / "benchmark" / "fixtures" / "unit_identity_before_preamble.json").read_text(encoding="utf-8"))
    o = _observe_ascii()
    by_name = {Path(k).name: v for k, v in pinned["documents"].items()}
    ok = bool(o) and all(not v["moved"] for v in o.values())
    for name, record in by_name.items():
        ok = ok and name in o and all(i in o[name]["ids"] for i in record["section_unit_ids"])
    return _verdict(ok, "every corpus document keeps its pinned unit ids; the migration moves none")


def _observe_versions():
    import version_changes
    config = version_changes.load_config()
    before = {"id": "v1", "text": _doc([CYRILLIC, CJK])}
    after = {"id": "v2", "text": _doc([CYRILLIC, CJK_B])}
    out = version_changes.document_changes(before, after, config)
    return {"added": out["units_added"], "removed": out["units_removed"]}


def _check_versions():
    o = _observe_versions()
    cjk_b = pairing_map._slug(CJK_B)
    cjk = pairing_map._slug(CJK)
    ok = (len(o["added"]) == 1 and o["added"][0].endswith(cjk_b)
          and len(o["removed"]) == 1 and o["removed"][0].endswith(cjk))
    return _verdict(ok, "two versions in another script are told apart by heading")


def check_495():
    proofs = [
        ("ids in any script", _observe_ids, _check_ids,
         lambda: patch.object(pairing_map, "_slug", pairing_map.legacy_slug)),
        ("ascii ids unchanged", _observe_ascii, _check_ascii,
         lambda: patch.object(pairing_map, "legacy_slug", lambda text, limit=40: "x" + str(text)[:3].lower())),
        ("versions told apart", _observe_versions, _check_versions,
         lambda: patch.object(pairing_map, "_slug", pairing_map.legacy_slug)),
    ]
    return _run(proofs, "Unicode heading ids through the one tokeniser, ASCII ids unchanged, the migration listed")


# ---------- 496: one tokeniser --------------------------------------------------------------------

def _observe_tokeniser():
    import reference_tables
    import relation_checks
    hindi = "वाक्य"                   # one word with a vowel sign and a virama
    return {"hindi": list(pairing_map._norm_label(hindi + " " + hindi)),
            "composed": list(pairing_map._norm_label(LATIN_MARKED)),
            "decomposed": list(pairing_map._norm_label(LATIN_DECOMPOSED)),
            "passage_words": passage_pairs._words("Class-A " + hindi),
            "reference": sorted(reference_tables._words("sensor " + hindi)),
            "relation": sorted(relation_checks._words("sensor " + hindi)),
            "slug": pairing_map._slug(DEVANAGARI)}


def _check_tokeniser():
    o = _observe_tokeniser()
    hindi = "वाक्य"
    ok = (o["hindi"] == [hindi, hindi] and o["composed"] == o["decomposed"] == ["résumé", "général"]
          and o["passage_words"] == ["class", "a", hindi]
          and o["reference"] == o["relation"] == sorted(["sensor", hindi])
          and o["slug"].count("xn--") == 2)
    return _verdict(ok, "marks join their letter, composed and decomposed read alike, every reader delegates")


def check_496():
    proofs = [
        ("one tokeniser", _observe_tokeniser, _check_tokeniser,
         lambda: patch.object(pairing_map, "_word_part", lambda ch: ch.isalnum())),
        ("one tokeniser normal form", _observe_tokeniser, _check_tokeniser,
         lambda: patch.object(pairing_map.unicodedata, "normalize", lambda form, text: text)),
    ]
    return _run(proofs, "pairing_map.words is the one split: marks, normal form C and every delegating reader")


# ---------- 497: PDF layout -----------------------------------------------------------------------

W, H = 612.0, 792.0
LEFT_LINES = ["aaaa bbbb cccc dddd eeee ffff gggg hhhh iiiii",
              "jjjj kkkk llll mmmm nnnn oooo pppp qqqq rrrrr",
              "ssss tttt uuuu vvvv wwww xxxx yyyy zzzz aaaaa",
              "left end."]
RIGHT_LINES = ["Bbbb cccc dddd eeee ffff gggg hhhh iiii jjjjj",
               "kkkk llll mmmm nnnn oooo pppp qqqq rrrr sssss",
               "tttt uuuu vvvv wwww xxxx yyyy zzzz aaaa bbbbb",
               "right end."]
TITLE = "A title line that runs across both of the columns of the page here"


def _page_one():
    """(x, y, size, text, rotated) drawn on page 1: header, title, two columns, footer."""
    out = [(72, 770, 9, "Shared running header", False), (72, 720, 18, TITLE, False),
           (72, 690, 14, "Left part", False), (320, 690, 14, "Right part", False)]
    for i, (a, b) in enumerate(zip(LEFT_LINES, RIGHT_LINES)):
        out += [(72, 670 - 14 * i, 10, a, False), (320, 670 - 14 * i, 10, b, False)]
    out.append((300, 30, 9, "Page 1", False))
    return out


TABLE = [["Name", "Count", "Mass"], ["alpha", "4", "2.5"], ["beta", "7", "1.0"]]
UNEVEN = [["one", "two", "three"], ["four", "six"], ["seven", "eight", "nine"]]


def _page_two():
    out = [(72, 770, 9, "Shared running header", False), (72, 700, 14, "Table part", False)]
    for i, row in enumerate(TABLE):
        out += [(x, 670 - 14 * i, 10, cell, False) for x, cell in zip((72, 200, 330), row)]
    out.append((72, 600, 10, "Between the two tables a line of plain text stands alone here.", False))
    for i, row in enumerate(UNEVEN):
        xs = (72, 200, 330) if len(row) == 3 else (72, 330)
        out += [(x, 570 - 14 * i, 10, cell, False) for x, cell in zip(xs, row)]
    out.append((560, 400, 10, "sideways", True))
    out.append((300, 30, 9, "Page 2", False))
    return out


PAGES = [_page_one(), _page_two()]


class _VPage(dict):
    """A stand-in for a pypdf page: its text visitor is handed what the built file draws."""

    def __init__(self, drawn):
        super().__init__({"/MediaBox": [0, 0, W, H]})
        self.drawn = drawn

    def extract_text(self, visitor_text=None, visitor_operand_before=None):
        identity = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        for x, y, size, text, rotated in self.drawn:
            tm = [0.0, 1.0, -1.0, 0.0, x, y] if rotated else [1.0, 0.0, 0.0, 1.0, x, y]
            if visitor_operand_before is not None:
                visitor_operand_before(b"Tj", [], identity, tm)
            if visitor_text is not None:
                # as pypdf does: the piece is flushed with a stale matrix
                visitor_text(text, identity, identity, {}, size)
        return "\n".join(d[3] for d in self.drawn)


class _Reader:
    def __init__(self, pages):
        self.pages = pages


def _pdf_string(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def build_pdf(pages) -> bytes:
    """A PDF file drawing each (x, y, size, text, rotated) where it says. Written by hand so the
    fixture needs no PDF library."""
    objects = {1: "<< /Type /Catalog /Pages 2 0 R >>", 3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids, n = [], 4
    for drawn in pages:
        page_no, content_no, n = n, n + 1, n + 2
        parts = []
        for x, y, size, text, rotated in drawn:
            matrix = "0 1 -1 0 %s %s Tm" % (x, y) if rotated else "1 0 0 1 %s %s Tm" % (x, y)
            parts.append("BT /F1 %s Tf %s %s Tj ET" % (size, matrix, _pdf_string(text)))
        stream = "\n".join(parts)
        objects[content_no] = "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        objects[page_no] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R >> >>"
                            " /Contents %d 0 R >>" % (W, H, content_no))
        kids.append("%d 0 R" % page_no)
    objects[2] = "<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(kids), len(kids))
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += ("%d 0 obj\n%s\nendobj\n" % (number, objects[number])).encode("latin-1")
    xref = len(out)
    size = max(objects) + 1
    out += ("xref\n0 %d\n0000000000 65535 f \n" % size).encode("latin-1")
    for number in range(1, size):
        out += ("%010d 00000 n \n" % offsets[number]).encode("latin-1")
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)).encode("latin-1")
    return bytes(out)


def _layer(record, name):
    return next((l for l in record["layers"] if l["name"] == name), None)


def _observe_pdf():
    reading = pdf_layers.read_reader(_Reader([_VPage(p) for p in PAGES]))
    return {"pages": [t for _, t in reading.pages], "record": reading.record,
            "running": [[i["page"], i["kind"], i["note"]] for i in reading.items if i["layer"] == "running"]}


def _expected_page_one():
    return "\n\n".join(["# " + TITLE, "## Left part", " ".join(LEFT_LINES), "## Right part", " ".join(RIGHT_LINES)])


def _check_order():
    o = _observe_pdf()
    return _verdict(o["pages"][0] == _expected_page_one(), "two columns read one after the other")


def _check_running():
    o = _observe_pdf()
    lay = _layer(o["record"], pdf_layers.RUNNING)
    ok = (lay is not None and lay["count"] == 4 and [1, "top", "Shared running header"] in o["running"]
          and [2, "bottom", "Page 2"] in o["running"] and "Page 1" not in o["pages"][0]
          and "Shared running header" not in "".join(o["pages"]))
    return _verdict(ok, "running header and footer set apart, kept as items")


def _check_tables():
    o = _observe_pdf()
    page = o["pages"][1]
    uneven = _layer(o["record"], pdf_layers.UNEVEN)
    ok = ("| Name | Count | Mass |\n|---|---|---|\n| alpha | 4 | 2.5 |\n| beta | 7 | 1.0 |" in page
          and "one two three\nfour six\nseven eight nine" in page
          and uneven is not None and not uneven["read"] and uneven["count"] == 1
          and pdf_layers.UNEVEN in o["record"]["lost"])
    return _verdict(ok, "a table as | rows; a table not lining up kept as lines and recorded lost")


def _check_headings():
    o = _observe_pdf()
    units = pairing_map.split_units("\n".join(o["pages"]))
    ids = [u["unit_id"] for u in units]
    # the title is a level-1 heading with nothing under it, so it makes no preamble unit
    ok = (ids == ["u01-left-part", "u02-right-part", "u03-table-part"]
          and o["pages"][0].startswith("# " + TITLE + "\n\n## Left part") and _layer(o["record"], "headings")["count"] == 4)
    return _verdict(ok, "headings by size become # lines, so the PDF splits into units")


def _check_rotated():
    o = _observe_pdf()
    lay = _layer(o["record"], pdf_layers.ROTATED)
    ok = (lay is not None and not lay["read"] and lay["count"] == 1 and o["pages"][1].endswith("sideways")
          and pdf_layers.STRUCTURE not in o["record"]["lost"])
    return _verdict(ok, "text at an angle kept at the page's end and recorded lost")


def _observe_no_settings():
    import text_extract
    with patch.object(text_extract, "_reader_settings", lambda: {}):
        reading = pdf_layers.read_reader(_Reader([_VPage(p) for p in PAGES]))
    return {"record": reading.record, "first": reading.pages[0][1].splitlines()[:2]}


def _check_no_settings():
    o = _observe_no_settings()
    lay = _layer(o["record"], pdf_layers.STRUCTURE)
    ok = (lay is not None and not lay["read"] and lay["note"] == pdf_layers.NOTE_NO_SETTINGS
          and o["first"] == ["Shared running header", TITLE])
    return _verdict(ok, "no settings declared: the structure recorded lost, the plain text kept")


def _plain_reader(reader):
    pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    return pdf_layers.Reading(pages=pages, record={"format": "pdf", "layers": [], "lost": []})


def _real_pdf():
    import text_extract
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "two_columns.pdf"
        path.write_bytes(build_pdf(PAGES))
        with _quiet():
            text = text_extract.extract_text(path)
            record = text_extract.layer_record(path)
    return {"text": text, "lost": record["lost"]}


def _check_real_pdf():
    o = _real_pdf()
    ok = (o["text"].startswith(_expected_page_one()) and "| Name | Count | Mass |" in o["text"]
          and pdf_layers.STRUCTURE not in o["lost"] and pdf_layers.UNEVEN in o["lost"])
    return _verdict(ok, "a real two-column PDF read through pypdf and text_extract")


def check_497():
    proofs = [
        ("pdf columns", _observe_pdf, _check_order, lambda: patch.object(pdf_layout, "_gutter", lambda lines, s: None)),
        ("pdf running lines", _observe_pdf, _check_running,
         lambda: patch.object(pdf_layout, "running_lines", lambda pages, page_lines, s: set())),
        ("pdf tables", _observe_pdf, _check_tables,
         lambda: patch.object(pdf_layout, "blocks_of", lambda lines, s: [("lines", [l]) for l in lines])),
        ("pdf headings", _observe_pdf, _check_headings,
         lambda: patch.object(pdf_layout, "_is_heading", lambda line, body, s: False)),
        ("pdf text at an angle", _observe_pdf, _check_rotated,
         lambda: patch.object(pdf_layers, "_layout", lambda pages, positioned: (pdf_layers.structure_layers(), pages, []))),
        ("pdf no settings", _observe_no_settings, _check_no_settings,
         lambda: patch.object(pdf_layout, "settings", lambda declared: dict.fromkeys(pdf_layout.SETTINGS_KEYS, 1.0))),
    ]
    skipped = ""
    try:
        import pypdf  # noqa: F401
        proofs.append(("real two-column pdf", _real_pdf, _check_real_pdf,
                       lambda: patch.object(pdf_layers, "read_reader", _plain_reader)))
    except ImportError:
        skipped = "; the real-file proof is SKIPPED: pypdf is not installed here"
    return _run(proofs, "a two-column PDF's columns, running lines, tables, headings and what is lost" + skipped)


# ---------- 498: sentences in other scripts -------------------------------------------------------

SCRIPTS = {
    # a wide stop with no space after it
    "cjk": "今日は晴れでした。明日は雨が降るでしょう。",
    # danda, space, a letter of a script with no case
    "devanagari": "यह एक लंबा वाक्य है। "
                  "यह दूसरा वाक्य है।",
    # Arabic question mark
    "arabic": "هل هذا هو السؤال الأول؟ "
              "هذه هي الجملة الثانية.",
    # Greek question mark, then a Greek capital
    "greek": "Ποιο είναι το πρώτο ερώτημα; "
             "Αυτή είναι η δεύτερη πρόταση.",
    # Armenian full stop
    "armenian": "Այս առաջին նախադասությունն է։ "
                "Սա երկրորդ նախադասությունն է։",
    # Cyrillic: a capital after the stop ends; a lowercase letter does not
    "cyrillic": "Это первое предложение здесь. "
                "Второе идёт следом т. е. потом тоже.",
}


def _observe_sentences():
    return {name: [p["text"] for p in passage_pairs.passages(text)] for name, text in SCRIPTS.items()}


def _check_sentences():
    o = _observe_sentences()
    ok = all(len(o[name]) == 2 for name in SCRIPTS) and all(
        "".join(o[name]).replace(" ", "") == SCRIPTS[name].replace(" ", "") for name in SCRIPTS)
    return _verdict(ok, "two sentences each in six scripts, nothing dropped")


_OLD_CLOSING = re.escape("\"')]" + chr(0x201D) + chr(0x2019))
_OLD_OPENING = re.escape("\"'([" + chr(0x201C) + chr(0x2018))
_OLD_END = re.compile(r"(?<=[.!?])[" + _OLD_CLOSING + r"]*\s+(?=[" + _OLD_OPENING + r"]?[^\W\d_a-z]|\d)")


def _observe_ascii_ends():
    """The ends found on every ASCII line of the shipped corpora, beside the old pattern's."""
    lines = []
    for path in sorted((ROOT / "benchmark" / "corpora").rglob("*.md")):
        lines += [l for l in path.read_text(encoding="utf-8").splitlines() if l.isascii() and l.strip()]
    lines += ["See e.g. the note. Then 3 more. \"Quoted.\" (Bracketed.) end.", "A.B. Smith said so! Yes? no."]
    return {"lines": len(lines), "differ": sum(1 for l in lines if sentence_split.ends(l) != [m.end() for m in _OLD_END.finditer(l)]),
            "found": sum(len(sentence_split.ends(l)) for l in lines)}


def _check_ascii_ends():
    o = _observe_ascii_ends()
    return _verdict(o["lines"] > 100 and o["found"] > 10 and o["differ"] == 0,
                    "ASCII ends unchanged on %d corpus lines" % o["lines"])


def check_498():
    proofs = [
        ("sentences in other scripts", _observe_sentences, _check_sentences,
         lambda: patch.object(sentence_split, "ends", lambda line: [m.end() for m in _OLD_END.finditer(line)])),
        ("wide words counted", _observe_sentences, _check_sentences,
         lambda: patch.object(sentence_split, "size", lambda text: len(pairing_map.words(text, join_hyphens=False)))),
        ("ascii ends unchanged", _observe_ascii_ends, _check_ascii_ends,
         lambda: patch.object(sentence_split, "_starts", lambda ch: ch.isalpha() or ch.isdigit())),
    ]
    return _run(proofs, "sentence ends decided by form in six scripts; ASCII ends as they always were")


# ---------- 499: text Python cannot split is refused on the record -----------------------------------

THAI_WORD = "ภาษาไทย"          # Thai writes no sentence stop
GEORGIAN = "ეს არის წინადადება. "


def _units_unsplit():
    long_thai = " ".join([THAI_WORD] * 200)                    # no terminator at all
    long_georgian = GEORGIAN * 70                              # stops before lowercase letters only
    text = "# Title\n\n## First\n" + long_thai + "\n\n## Second\n" + long_georgian + "\n\nA short sentence stands here.\n"
    return pairing_map.split_units(text)


def _observe_refused():
    units = _units_unsplit()
    config = passage_pairs.load_config()
    prepared = passage_pairs.prepare(units, config, embed_with=lambda items: None)
    _, calls = passage_pairs.review(prepared, {"id": "CONV-X"}, None, lambda prompt: None, config)
    return {"passages": [p["text"] for p in prepared["items"]],
            "row": [[r["unit_id"], r["reason"], r["characters"]] for r in calls.get("not_split", [])],
            "row_keys": sorted({k for r in calls.get("not_split", []) for k in r})}


def _check_refused():
    o = _observe_refused()
    units = _units_unsplit()
    ok = (o["passages"] == ["A short sentence stands here."]
          and [r[:2] for r in o["row"]] == [[units[0]["unit_id"], sentence_split.NO_END],
                                           [units[1]["unit_id"], sentence_split.NOT_DECIDED]]
          and all(r[2] > sentence_split.LONGEST for r in o["row"])
          and o["row_keys"] == ["characters", "end", "reason", "start", "unit_id"])
    return _verdict(ok, "two stretches refused with their reason, offsets and counts only, in the row")


def check_499():
    proofs = [
        ("not split is refused", _observe_refused, _check_refused,
         lambda: patch.object(sentence_split, "refusal", lambda piece: None)),
        ("refusal reaches the row", _observe_refused, _check_refused,
         lambda: patch.object(passage_pairs, "document_passages",
                              lambda units, not_split=None: [dict(p, index=i, unit_id=u["unit_id"]) for i, (u, p) in enumerate(
                                  (u, p) for u in units for p in passage_pairs.passages_read(u.get("text"))[0])])),
    ]
    return _run(proofs, "text Python cannot split refused on the passage pairs row (READING-A)")


def check():
    return [check_495(), check_496(), check_497(), check_498(), check_499()]


if __name__ == "__main__":
    for number, (status, detail) in zip(range(495, 500), check()):
        print(number, status, detail)
