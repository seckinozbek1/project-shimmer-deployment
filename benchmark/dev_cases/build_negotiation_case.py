"""Build the negotiation multi-round development case from the anonymised corpus files.

Loop S5 item 0.9 (DS5-10). The case is three rounds of one party's offer, read only from
the anonymised files tracked under benchmark/corpora/negotiation_r2_to_r3/ and
benchmark/corpora/negotiation_r3_to_r4/ (H6: no other copy of this material is read).
It writes, under benchmark/dev_cases/negotiation_three_rounds/, a folder in the test
archive layout of docs/INPUT_FORMAT.md section 12:

    _review_targets.json   the last round as target, the round before it as prior
    case_manifest.json     the live case manifest (fixture false)
    context/               the three offers, byte copies of the corpus files (LF)
    conventions/           the corpus's own mandate, copied

What the manifest declares, and nothing else:

- three rounds, r2, r3 and r4 (sequence 2, 3 and 4, the corpus folders' own round
  names), one document each;
- two actors: `company`, whose offers the documents are, and `union`, whose vote on each
  offer the documents report;
- one issue per term the corpus's fixed label schema names, and one issue for the vote;
- one source per round in which a term is stated, quoting its whole label line exactly,
  on the unit that holds it (pairing_map.split_units, the pipeline's own splitter), and
  one source per round quoting the sentence that reports the vote. Every source is
  `accepted`: each quotes its document exactly (section 12 says never to mark a flaw by
  a state).

A term a round does not state gets no source in that round (the year-by-year increases
and the incentive minimum in r2, the pension multiplier in r2, the one-time contribution
in r4). No figure is interpreted: a quote is the line as written.

    py -3.12 -X utf8 benchmark/dev_cases/build_negotiation_case.py           # write
    py -3.12 -X utf8 benchmark/dev_cases/build_negotiation_case.py --check   # compare

The case is exposed and for development only: the material, its earlier keys and this
manifest are all in the repository.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPORA = ROOT / "benchmark" / "corpora"
CASE = Path(__file__).resolve().parent / "negotiation_three_rounds"
CASE_ID = "negotiation-offers-three-rounds"

# (round id, sequence, corpus folder, file name). The 19 October offer is in both corpus
# folders, byte-identical; it is read from the r3_to_r4 folder, where it is the prior.
ROUNDS = (
    ("r2", 2, "negotiation_r2_to_r3", "company_a_union_b_offer_2024_09_23.md"),
    ("r3", 3, "negotiation_r3_to_r4", "company_a_union_b_offer_2024_10_19.md"),
    ("r4", 4, "negotiation_r3_to_r4", "company_a_union_b_offer_2024_10_31.md"),
)
CONVENTIONS = ("negotiation_r3_to_r4", "mandate_conventions.md")

# The corpus's fixed label schema (its documents say so), one issue per label.
TERMS = (
    ("General wage increase total", "wage-increase-total"),
    ("Year one increase", "year-one-increase"),
    ("Year two increase", "year-two-increase"),
    ("Year three increase", "year-three-increase"),
    ("Year four increase", "year-four-increase"),
    ("Ratification bonus", "ratification-bonus"),
    ("Company match rate", "match-rate"),
    ("Company match ceiling", "match-ceiling"),
    ("Special company retirement contribution", "special-retirement-contribution"),
    ("One-time 401(k) contribution", "one-time-contribution"),
    ("Pension multiplier", "pension-multiplier"),
    ("GPP minimum annual payout", "incentive-minimum"),
    ("Contract length", "contract-length"),
)
VOTE_ISSUE = "offer-vote"
# The sentence each round's document uses to report the vote on that offer, as written.
VOTES = {
    "r2": "offer was not put to a vote; the union declined to schedule one",
    "r3": "64 percent of\nthe members voted to reject it",
    "r4": "ratified by the members on 4 November 2024 with 59 percent in favour",
}


def _scripts():
    path = str(ROOT / "scripts")
    if path not in sys.path:
        sys.path.insert(0, path)


def read_text(path):
    """A corpus file as the pipeline reads it: UTF-8, every CRLF and lone CR made LF."""
    return Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def unit_spans(text):
    """[(unit id, start, end)] for the units pairing_map.split_units makes of `text`, each
    located in the text in order (a unit's text is a contiguous run of the document)."""
    _scripts()
    import pairing_map
    out, cursor = [], 0
    for unit in pairing_map.split_units(text):
        body = unit["text"].strip()
        start = text.find(body, cursor)
        if start < 0:
            raise ValueError("unit %s is not a contiguous run of its document" % unit["unit_id"])
        out.append((unit["unit_id"], start, start + len(body)))
        cursor = start + len(body)
    return out


def unit_of(spans, start, end):
    held = [u for u, a, b in spans if a <= start and end <= b]
    if len(held) != 1:
        raise ValueError("a quote at %d is held by %d units" % (start, len(held)))
    return held[0]


def documents():
    """{round id: (document id, file name, text)}."""
    return {rid: (name.rsplit(".", 1)[0], name, read_text(CORPORA / folder / "context" / name))
            for rid, _seq, folder, name in ROUNDS}


def sources(docs):
    out = []
    for rid, _seq, _folder, _name in ROUNDS:
        doc_id, _file, text = docs[rid]
        spans = unit_spans(text)
        for label, issue in TERMS:
            hits = [m for m in re.finditer(r"^%s: [^\n]+$" % re.escape(label), text, re.M)]
            if not hits:
                continue
            if len(hits) != 1:
                raise ValueError("%s states %r on %d lines" % (doc_id, label, len(hits)))
            m = hits[0]
            out.append(dict(source_id="%s-%s" % (rid, issue), round_id=rid, actor_id="company",
                            issue_id=issue, document_id=doc_id,
                            unit_id=unit_of(spans, m.start(), m.end()),
                            char_start=m.start(), char_end=m.end(), quote=m.group(0), state="accepted"))
        quote = VOTES[rid]
        start = text.find(quote)
        if start < 0 or text.find(quote, start + 1) >= 0:
            raise ValueError("%s does not state the vote sentence exactly once" % doc_id)
        out.append(dict(source_id="%s-%s" % (rid, VOTE_ISSUE), round_id=rid, actor_id="union",
                        issue_id=VOTE_ISSUE, document_id=doc_id,
                        unit_id=unit_of(spans, start, start + len(quote)),
                        char_start=start, char_end=start + len(quote), quote=quote, state="accepted"))
    return out


def build():
    """{relative path: bytes} of the case folder."""
    docs = documents()
    manifest = dict(
        schema_version=1, case_id=CASE_ID, fixture=False,
        rounds=[dict(round_id=rid, sequence=seq, document_ids=[docs[rid][0]]) for rid, seq, _f, _n in ROUNDS],
        actors=[dict(actor_id="company"), dict(actor_id="union")],
        issues=[dict(issue_id=issue) for _label, issue in TERMS] + [dict(issue_id=VOTE_ISSUE)],
        sources=sources(docs))
    names = [docs[rid][1] for rid, _s, _f, _n in ROUNDS]
    targets = dict(targets=[names[-1]], grounding=names[:-1], prior=[names[-2]], source="operator",
                   resolved_at="")
    files = {"case_manifest.json": (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("ascii"),
             "_review_targets.json": (json.dumps(targets, indent=2) + "\n").encode("ascii"),
             "conventions/" + CONVENTIONS[1]:
                 read_text(CORPORA / CONVENTIONS[0] / "conventions" / CONVENTIONS[1]).encode("utf-8")}
    for rid, _s, _f, _n in ROUNDS:
        files["context/" + docs[rid][1]] = docs[rid][2].encode("utf-8")
    return files


def on_disk(folder=CASE):
    """The case folder's files, text LF-normalised (a Windows checkout writes CRLF)."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
            for p in sorted(folder.rglob("*")) if p.is_file()}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    files = build()
    if "--check" in argv:
        same = on_disk() == files
        print("case folder %s the build" % ("matches" if same else "DIFFERS FROM"))
        return 0 if same else 1
    for name, data in files.items():
        target = CASE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print("%d files written under %s" % (len(files), CASE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
