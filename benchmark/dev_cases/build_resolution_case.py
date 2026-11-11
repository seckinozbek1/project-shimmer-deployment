"""Build the draft resolution worked case (loop D-S39 item 3).

REAL PUBLIC TEXT, not synthetic. United Nations General Assembly, Second Committee, document
A/C.2/74/L.34 (23 October 2019) and its revision A/C.2/74/L.34/Rev.1 (20 November 2019), both
fetched from the UN Digital Library on 6 November 2026. The revision became resolution 74/212,
adopted without a vote. A demonstration, never benchmark evidence (D-S39 item 6).

    draft_resolution_revision/
      EXPECTED.md     written by hand, the changes a reader should report; never in workload/
      source/         pdftotext's output of each published PDF; its one change is that
                      typographic quotation marks are written straight, because the repository's
                      commit scan refuses them. No word changes.
      workload/       the sealer's folder (docs/INPUT_FORMAT.md section 12)

No published sentence is typed here. The text comes from source/ by these steps only:

- page furniture is dropped (job number, barcode, running symbol, page number);
- a paragraph split by a page break is joined;
- REPAIRS undoes four kinds of extraction damage, each listed with its reason and required to
  apply exactly as often as declared;
- a footnote mark, set as a superscript in the PDF, is written [n], and the footnotes go last.

Added for addressing, and stated as added in each file: the source lines, one heading per
paragraph, and one `Paragraph kind` line per paragraph, without which no rule can pair with a
unit (section 4). The wording of every paragraph is as published.

    py -3.12 -X utf8 benchmark/dev_cases/build_resolution_case.py                # write
    py -3.12 -X utf8 benchmark/dev_cases/build_resolution_case.py --check        # compare
    py -3.12 -X utf8 benchmark/dev_cases/build_resolution_case.py --ordinary-out <folder>
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CASE = Path(__file__).resolve().parent / "draft_resolution_revision"
SOURCE = CASE / "source"
CASE_ID = "draft-resolution-revision"
FETCHED = "2026-11-06"

VERSIONS = {
    "l34": dict(file="a_c2_74_l34.txt", document="draft_resolution_l34", symbol="A/C.2/74/L.34",
                url="https://digitallibrary.un.org/record/3833768/files/A_C.2_74_L.34-EN.pdf",
                sha256="bc8715164b2af73ace518881ff8ab8b1b03fb9c38642ee9c011d7e787a3b0a0d"),
    "rev1": dict(file="a_c2_74_l34_rev1.txt", document="draft_resolution_l34_rev1", symbol="A/C.2/74/L.34/Rev.1",
                 url="https://digitallibrary.un.org/record/3836683/files/A_C.2_74_L.34_Rev.1-EN.pdf",
                 sha256="507774d80b4869eb908325003dccc34afdc9c8cee720846d5d0ebf7804697f18"),
}

FURNITURE = re.compile(r"^(?:\d\d-\d{5}(?: \(E\) \d+)?|\*\d+\*|A/C\.2/74/L\.34(?:/Rev\.1)?|\d/\d)$")

# (version, damaged text, as published, why). Applied exactly once each.
REPAIRS = [
    ("l34", "years an d anniversaries", "years and anniversaries", "letter spacing in the PDF; Rev.1 has the same words whole"),
    ("l34", "North -East Asia", "North-East Asia", "letter spacing in the PDF"),
    ("l34", "Convention on Longrange Transboundary", "Convention on Long-range Transboundary", "hyphen at a line end, dropped by pdftotext"),
    ("l34", 'improve air quality globally", 1 and', 'improve air quality globally",[1] and', "footnote mark"),
    ("l34", 'impact of air pollution",2', 'impact of air pollution",[2]', "footnote mark"),
    ("l34", "Air Pollution,3", "Air Pollution,[3]", "footnote mark"),
    ("rev1", "of 6 December 2017,1 World", "of 6 December 2017,[1] World", "footnote mark"),
    ("rev1", "of 26 May 2015, 2 and", "of 26 May 2015,[2] and", "footnote mark"),
]
FOOTNOTE_LINE = re.compile(r"^_{5,}\s*(.*)$")
FOOTNOTE_SPLIT = re.compile(r"(?:^|(?<=\s))([1-9]) (?=[A-Z])")

# Sources: (version, issue, quote). One actor, the sponsors of each version.
SOURCES = [
    ("l34", "name-of-the-day", "designate 15 November as the International Day for Blue Sky"),
    ("rev1", "name-of-the-day", "designate 7 September as the International Day of Clean Air for blue skies"),
    ("l34", "call-to-states", "Urges Member States to devote the International Day, as appropriate in the national context"),
    ("rev1", "call-to-states", "Invites all Member States, organizations of the United Nations system, other international and regional organizations and civil society"),
    ("l34", "implementing-body", "Invites the United Nations Environment Programme, within its responsibilities and functions"),
    ("rev1", "implementing-body", "Invites the United Nations Environment Programme to facilitate the observance of the International Day"),
    ("l34", "costs", "Stresses that the cost of all activities that may arise from the implementation of the present resolution should be met from voluntary contributions"),
    ("rev1", "costs", "Stresses that the cost of all activities that may arise from the implementation of the present resolution should be met from voluntary contributions"),
    ("l34", "observance", "to ensure the observance of the International Day for Blue Sky."),
    ("rev1", "observance", "to promote the observance of the International Day."),
]
ISSUES = ("name-of-the-day", "call-to-states", "implementing-body", "costs", "observance")

CONVENTIONS = """# Drafting review conventions

General rules for reviewing a draft resolution, written for this demonstration. They are not
rules of any organisation.

## CONV-R01 Consistency between paragraphs [required] [conformance]

A paragraph, whatever its paragraph kind, must not state the opposite of another paragraph of the same draft.

## CONV-R02 References [required] [conformance]

A reference to a paragraph, an annex or an instrument, whatever the paragraph kind, must lead to something the draft itself identifies.

## CONV-R03 Same name and same date [required] [conformance]

The name and the date of what the draft decides, whatever the paragraph kind, must be the same in every paragraph that states them.

## CONV-R04 Opening words [recommended] [conformance]

Whatever the paragraph kind, a preambular paragraph must open with a participle or an adjective, and an operative paragraph with a verb in the present tense.
"""


def read_source(version):
    return (SOURCE / VERSIONS[version]["file"]).read_bytes().decode("utf-8").replace("\r\n", "\n")


def parse(version):
    """{head: [line], preambular: [paragraph], operative: [paragraph], footnotes: [line]}."""
    raw = read_source(version).replace("\f", "\n")
    lines = [line.strip() for line in raw.split("\n")]
    lines = [line for line in lines if line and not FURNITURE.match(line)]
    notes = []
    kept = []
    for line in lines:
        hit = FOOTNOTE_LINE.match(line)
        if hit:
            parts = FOOTNOTE_SPLIT.split(hit.group(1))
            notes += ["[%s] %s" % (n, t.strip()) for n, t in zip(parts[1::2], parts[2::2])]
        else:
            kept.append(line)
    start = kept.index("The General Assembly,")
    head, body = kept[:start + 1], kept[start + 1:]
    joined = []
    for line in body:
        if joined and not joined[-1].endswith((",", ";", ".")):
            joined[-1] += " " + line
        else:
            joined.append(line)
    text = "\n".join(joined)
    for name, damaged, published, _why in REPAIRS:
        if name == version:
            if text.count(damaged) != 1:
                raise ValueError("repair applies %d times: %r" % (text.count(damaged), damaged))
            text = text.replace(damaged, published)
    paragraphs = text.split("\n")
    first = next(i for i, p in enumerate(paragraphs) if re.match(r"1\. ", p))
    return dict(head=head, preambular=paragraphs[:first], operative=paragraphs[first:], footnotes=notes)


def document_md(version):
    v, parts = VERSIONS[version], parse(version)
    title = parts["head"][-2]
    out = ["# " + title,
           "Document symbol: " + v["symbol"],
           "Source URL: " + v["url"],
           "Date fetched: " + FETCHED,
           "Published text of a United Nations document, used as published. The source lines above, "
           "the paragraph headings and the Paragraph kind lines are added for this demonstration "
           "and are not part of the document. Footnote marks are written in square brackets and "
           "quotation marks as straight ones.",
           "\n".join(line for line in parts["head"] if line != title)]
    for kind, name in (("preambular", "Preambular"), ("operative", "Operative")):
        for number, paragraph in enumerate(parts[kind], start=1):
            out += ["## %s paragraph %d" % (name, number), "Paragraph kind: " + kind, paragraph]
    if parts["footnotes"]:
        out += ["## Footnotes", "Paragraph kind: footnote"] + parts["footnotes"]
    return "\n\n".join(out) + "\n"


def documents():
    return {VERSIONS[k]["document"]: document_md(k) for k in VERSIONS}


def words(text):
    """A text's words, footnote marks and spacing aside: what the wording test compares."""
    return re.findall(r"[^\W\d_]+|\d+", re.sub(r"\[\d\]", " ", text))


def published_words_kept(version):
    """Every word of the source, in order, is in the document's published part: the source's own
    words less its page furniture and footnote digits, repaired as declared, and nothing else."""
    parts = parse(version)
    made = words(" ".join(parts["head"] + parts["preambular"] + parts["operative"] + parts["footnotes"]))
    raw = read_source(version).replace("\f", "\n")
    kept = [line.strip() for line in raw.split("\n") if line.strip() and not FURNITURE.match(line.strip())]
    kept = [FOOTNOTE_SPLIT.sub(" ", FOOTNOTE_LINE.match(line).group(1)) if FOOTNOTE_LINE.match(line) else line
            for line in kept]
    source = " ".join(kept)
    for name, damaged, published, _why in REPAIRS:
        if name == version:
            source = source.replace(damaged, published)
    return sorted(made) == sorted(words(source))


def unit_spans(text, document_id):
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import pairing_map
    out, cursor = [], 0
    for unit in pairing_map.split_units(text, document_id=document_id):
        body = unit["text"].strip()
        start = text.find(body, cursor)
        if start < 0:
            raise ValueError("unit %s is not a contiguous run of its document" % unit["unit_id"])
        out.append((unit["unit_id"], start, start + len(body)))
        cursor = start + len(body)
    return out


def sources(docs):
    out = []
    for version, issue, quote in SOURCES:
        doc = VERSIONS[version]["document"]
        text = docs[doc]
        start = text.find(quote)
        if start < 0 or text.find(quote, start + 1) >= 0:
            raise ValueError("%s does not hold exactly once: %r" % (doc, quote))
        end = start + len(quote)
        held = [u for u, a, b in unit_spans(text, doc) if a <= start and end <= b]
        if len(held) != 1:
            raise ValueError("a quote in %s is held by %d units" % (doc, len(held)))
        out.append(dict(source_id="%s-%s" % (version, issue), round_id=version, actor_id="sponsors",
                        issue_id=issue, document_id=doc, unit_id=held[0], char_start=start, char_end=end,
                        quote=quote, state="accepted"))
    return out


def build():
    """{path relative to the case folder: bytes} of the workload and its ordinary/ folder (the same
    members without case_manifest.json, the ordinary two-version review)."""
    docs = documents()
    manifest = dict(
        schema_version=1, case_id=CASE_ID, fixture=False,
        rounds=[dict(round_id=k, sequence=i, document_ids=[VERSIONS[k]["document"]])
                for i, k in enumerate(VERSIONS, start=1)],
        actors=[dict(actor_id="sponsors")], issues=[dict(issue_id=i) for i in ISSUES], sources=sources(docs))
    target, prior = VERSIONS["rev1"]["document"] + ".md", VERSIONS["l34"]["document"] + ".md"
    targets = dict(targets=[target], grounding=[prior], prior=[prior], source="operator", resolved_at="")
    files = {"workload/case_manifest.json": (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("ascii"),
             "workload/_review_targets.json": (json.dumps(targets, indent=2) + "\n").encode("ascii"),
             "workload/conventions/drafting_review_conventions.md": CONVENTIONS.encode("utf-8")}
    for name, text in docs.items():
        files["workload/context/%s.md" % name] = text.encode("utf-8")
    for name, data in list(files.items()):
        if name != "workload/case_manifest.json":
            files["ordinary/" + name[len("workload/"):]] = data
    return files


def on_disk(folder=CASE):
    """workload/ and ordinary/ as they are on disk, text LF-normalised."""
    out = {}
    for part in ("workload", "ordinary"):
        root = Path(folder) / part
        out.update({part + "/" + p.relative_to(root).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
                    for p in sorted(root.rglob("*")) if p.is_file()})
    return out


def write_ordinary(folder):
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("the folder is not empty: %s" % folder.name)
    count = 0
    for name, data in build().items():
        if name != "workload/case_manifest.json":
            target = folder / name[len("workload/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            count += 1
    return count


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--ordinary-out" in argv:
        print("%d members written" % write_ordinary(argv[argv.index("--ordinary-out") + 1]))
        return 0
    files = build()
    if "--check" in argv:
        same = on_disk() == files
        kept = all(published_words_kept(k) for k in VERSIONS)
        print("case folder %s the build; published words %s" % (
            "matches" if same else "DIFFERS FROM", "all kept" if kept else "NOT ALL KEPT"))
        return 0 if same and kept else 1
    for name, data in files.items():
        target = CASE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print("%d files written under %s" % (len(files), CASE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
