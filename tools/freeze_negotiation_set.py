#!/usr/bin/env python3
"""Freeze the negotiation held-out set (D-S102 item 8; plan sections 2.4 to 2.7; D-395, D-419).

Run by role B on the laptop's CPU with the network off, after the cases and their keys exist. Case
folders sit under `<set>/real/` (subset R) and `<set>/synthetic/` (F when the case id ends in
`-free`, else S). The tool:

1. **Fills the declarations.** Each open issue's `text_units` and `closed_units` come from
   `declarations.json`, by matching the exact round-3 headings to the units the pipeline's own
   splitter makes (`pairing_map.split_units`). For a real case it also fills the declarer's
   `position` and `fallback`.
2. **Validates.** `multi_round.validate_manifest`, every source span against its file, and the
   minimums the plan's n rests on (3 rounds, 2 parties, at least 6 issues, at least 2 open issues
   per case). A case below them refuses the freeze.
3. **Settles the movement key on the pooled rows** of every case:
   - Cohen's kappa of labellers 1 and 2 (`KEY_MOVEMENT.json`, `KEY_MOVEMENT_L2.json`) is taken over
     every row, with per-case kappas beside it.
   - Below the 0.60 floor, the one revision round's files (`KEY_MOVEMENT_REVISED.json`,
     `KEY_MOVEMENT_L2_REVISED.json`) are read and kappa is taken again; the figures before and after
     are both recorded.
   - If kappa is still below the floor, labeller 3 (`KEY_MOVEMENT_L3.json`) labels every row.
     Otherwise labeller 3 labels the rows labellers 1 and 2 disagree on.
   - The settled label is the majority of three, and a row with three different labels is dropped
     and counted.
4. **Runs the leakage pass.** Each case passage (a paragraph of at least 20 words) is compared with
   every passage of every committed corpus and of every other case, on exact normalised text, word
   5-gram Jaccard of at least 0.5, and embedding cosine of at least 0.9. Corpora are read as follows:
   - Markdown, text, HTML: by paragraph;
   - JSON: by its strings;
   - JSON Lines: line by line, by each line's strings;
   - Word (.docx): through the pipeline's own `text_extract`.

   A file of any other kind, or one that cannot be read, is counted as skipped, per corpus.
   **Same source:** a case's `SOURCE.md` URLs and its document ids are compared with every URL
   written in a corpus and every corpus file's stem.
   Each corpus is encoded once, and the time is forecast from the measured rate before encoding. A
   case with any hit refuses the freeze.
5. **Writes `FREEZE.json`.** It holds:
   - the set's SHA-256, each case's subset, and the settled key;
   - the class shares of every row and of the headline rows (F and S), and the two floors;
   - the kappas;
   - the leakage counts per corpus and threshold, and the skipped files;
   - the open issues and the encoder's identity.

   With `--no-embedding` it writes `FREEZE.dryrun.json` instead. That is a dry run, which the scorer
   refuses.

It prints counts only, never a case's text.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("score_negotiation", ROOT / "tools" / "score_negotiation.py")
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)

KAPPA_FLOOR = 0.60
JACCARD = 0.5
COSINE = 0.9
NGRAM = 5
MIN_WORDS = 20         # a passage shorter than this (a heading, a label line, a short clause) is not compared (D-395)
MINIMUMS = {"rounds": 3, "parties": 2, "issues": 6, "open_issues": 2}
READ_SUFFIXES = {".md", ".txt", ".html", ".json", ".jsonl", ".docx", ".py", ".log", ".csv", ".tsv", ".yaml", ".yml"}
# Measured in the dry run of 9 November (plan section 12): 177 passages encoded in 88.5 s on the CPU.
# Kept for an encoder that cannot count tokens; bge-m3's forecast is by token (SECONDS_PER_TOKEN).
SECONDS_PER_PASSAGE = 0.5
# Measured on the real corpus list on 9 November (plan section 12), on the CPU: passages of about 60
# tokens at 0.34 s each and of about 370 at 1.9 s each, about 0.0055 s a token either way. The GPU's rate
# is not measured, so its forecast uses this one, an upper bound.
SECONDS_PER_TOKEN = 0.0055
# bge-m3 reads at most 8,192 tokens of a passage; a longer one is cut there and counted in FREEZE.json.
MAX_TOKENS = 8192
# A batch holds at most BATCH_SIZE passages and at most TOKEN_BUDGET tokens, longest first, so a run of
# long passages never shares one batch (D-437 item 2): measured, sixteen long passages in one batch took
# the working set past 6 GB on a slice of the real list, where 32 of about 370 tokens peaked at 2.5 GB.
TOKEN_BUDGET = 8192
# The comparison: one float32 matrix product per corpus; a rate of 5e8 multiply-adds a second on this
# laptop's CPU is the planning figure, replaced by the measured time in FREEZE.json.
MULTIPLY_ADDS_PER_SECOND = 5e8
DIMENSIONS = 1024
BATCH_SIZE = 16
# Passages handed to the encoder at a time; each chunk's vectors go straight into one float32 array, so
# the pass holds 4 bytes a dimension and never a Python float (D-437 item 2).
ENCODE_CHUNK = 512
# The 5-gram step (D-437 item 3): every case passage's gram set is built once, into one index; each
# corpus passage's grams are made once as it is read against that index and then dropped. Measured on
# a slice of the real corpus list on 9 November (plan section 12); replaced by the measured time in
# FREEZE.json.
JACCARD_SECONDS_PER_PASSAGE = 0.00003
_URL = re.compile(r"https?://[^\s)>\]\"']+")


def _sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _norm(text):
    return " ".join(str(text or "").casefold().split())


def passages(text):
    """A text's paragraphs, split at blank lines, normalised; those under MIN_WORDS words dropped,
    since a heading or a label line repeats across any two records of one kind."""
    return [p for p in (_norm(x) for x in re.split(r"\n\s*\n", str(text or ""))) if len(p.split()) >= MIN_WORDS]


def _grams(text):
    words = text.split()
    return {tuple(words[i:i + NGRAM]) for i in range(max(0, len(words) - NGRAM + 1))}


def jaccard(a, b):
    ga, gb = _grams(a), _grams(b)
    return len(ga & gb) / len(ga | gb) if ga and gb else 0.0


class GramIndex:
    """Every case passage's 5-gram set, built once (D-437 item 3), as an index from a gram to the
    passages holding it. `matches` reads another body of passages against it, each of its passages'
    grams made once, and gives the indexed passages at or over JACCARD with one of them: the same
    answer as `jaccard` on every pair, read through the grams the two share."""

    def __init__(self, items):
        self.owners, self.texts, self.sizes, self.index = [], [], [], {}
        for owner, text in items:
            grams = _grams(text)
            i = len(self.texts)
            self.owners.append(owner)
            self.texts.append(text)
            self.sizes.append(len(grams))
            for g in grams:
                self.index.setdefault(g, []).append(i)

    def matches(self, theirs, skip_owner=None):
        hit = set()
        for q in theirs:
            gq = _grams(q)
            if not gq:
                continue
            shared = {}
            for g in gq:
                for i in self.index.get(g, ()):
                    shared[i] = shared.get(i, 0) + 1
            for i, n in shared.items():
                if i not in hit and self.owners[i] != skip_owner and n / (self.sizes[i] + len(gq) - n) >= JACCARD:
                    hit.add(i)
        return {(self.owners[i], self.texts[i]) for i in hit}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def read_file(f):
    """(passages, the text read) of one corpus file, or None when it is of a kind not read or cannot
    be read."""
    suffix = f.suffix.lower()
    if suffix not in READ_SUFFIXES:
        return None
    try:
        if suffix == ".docx":
            import text_extract
            raw = text_extract.extract_text(f)
            return passages(raw), raw
        raw = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError, ValueError, ImportError):
        return None
    if suffix == ".json":
        try:
            return [p for s in _strings(json.loads(raw)) for p in passages(s)], raw
        except ValueError:
            return passages(raw), raw
    if suffix == ".jsonl":
        held = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                held += [p for s in _strings(json.loads(line)) for p in passages(s)]
            except ValueError:
                held += passages(line)
        return held, raw
    return passages(raw), raw


def corpus_passages(paths, *, accept_skipped=()):
    """{corpus: {passages, urls, stems, files, read, skipped}} for each file or folder named. A path that
    does not exist or holds nothing readable refuses (D-430 item 4); so does a skipped file of a kind the
    corpus list does not accept by name (`accept-skipped: .suffix`, D-430 item 5)."""
    out = {}
    for base in paths:
        base = Path(base)
        if not base.exists():
            raise ValueError("a corpus path does not exist: %s" % base)
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        held, urls, stems, skipped = [], set(), set(), {}
        read = 0
        for f in files:
            got = read_file(f)
            if got is None:
                skipped[f.suffix.lower() or "(none)"] = skipped.get(f.suffix.lower() or "(none)", 0) + 1
                continue
            read += 1
            held += got[0]
            urls |= set(_URL.findall(got[1]))
            stems.add(f.stem)
        if read == 0:
            raise ValueError("a corpus holds nothing readable: %s" % base)
        refused = sorted(s for s in skipped if s not in set(accept_skipped))
        if refused:
            raise ValueError("a corpus holds files of a kind neither read nor accepted (%s): %s" % (", ".join(refused), base))
        out[str(base)] = {"passages": held, "urls": urls, "stems": stems, "files": len(files), "read": read,
                          "skipped": skipped}
    return out


def leakage(mine, mine_vectors, corpora, corpus_vectors, *, urls=(), stems=(), jaccard_hits=None):
    """{corpus: {exact, jaccard, cosine, same_source}} hits of one case's passages against each corpus.
    Vectors are computed once per corpus and per case by the caller (None: no embedding test). The 5-gram
    hits come from the caller's one index pass (`jaccard_hits`: {corpus: the passages of mine at or over
    JACCARD}); without them every pair is compared here."""
    out = {}
    for name, corpus in corpora.items():
        theirs = corpus["passages"]
        their_set = set(theirs)
        if jaccard_hits is not None and name in jaccard_hits:
            jac = sum(1 for p in mine if p in jaccard_hits[name])
        else:
            jac = sum(1 for p in mine if any(jaccard(p, q) >= JACCARD for q in theirs))
        counts = {"exact": sum(1 for p in mine if p in their_set),
                  "jaccard": jac,
                  "cosine": 0,
                  "same_source": len(set(urls) & corpus["urls"]) + len(set(stems) & corpus["stems"])}
        tv = (corpus_vectors or {}).get(name)
        if mine_vectors is not None and len(mine_vectors) and tv is not None and len(tv):
            import numpy as np
            # Unit vectors, so the cosine is the dot product: one matrix product per corpus (D-430 item 2).
            counts["cosine"] = int((np.max(np.asarray(mine_vectors, dtype=np.float32)
                                           @ np.asarray(tv, dtype=np.float32).T, axis=1) >= COSINE).sum())
        out[name] = counts
    return out


def kappa(a, b):
    """Cohen's kappa of two labellings of the same rows; None when chance agreement is total (one label
    used by both on every row), where kappa is undefined."""
    n = len(a)
    if n == 0:
        return None
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    labels = set(a) | set(b)
    chance = sum((a.count(c) / n) * (b.count(c) / n) for c in labels)
    return None if chance == 1 else (agree - chance) / (1 - chance)


def _rows(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = value["rows"] if isinstance(value, dict) else value
    return {(r["issue_id"], tuple(r["rounds"])): r["label"] for r in rows}


def settle_all(case_dirs):
    """(settled rows, record) over every case, the kappa floor applied to the pooled rows."""
    labels = {}
    for case_id, case_dir in case_dirs:
        l1, l2 = _rows(case_dir / "KEY_MOVEMENT.json"), _rows(case_dir / "KEY_MOVEMENT_L2.json")
        if set(l1) != set(l2):
            raise ValueError("%s: the labellers' rows differ" % case_id)
        labels[case_id] = (l1, l2)

    def pooled(pairs):
        keys = [(c, x) for c, (l1, _) in sorted(pairs.items()) for x in sorted(l1)]
        return kappa([pairs[c][0][x] for c, x in keys], [pairs[c][1][x] for c, x in keys])
    record = {"kappa_before": pooled(labels), "per_case_before": {c: kappa([l1[x] for x in sorted(l1)], [l2[x] for x in sorted(l1)])
                                                                  for c, (l1, l2) in labels.items()},
              "revised": False, "kappa_after": None, "labeller_3": None}
    k = record["kappa_before"]
    if k is None or k < KAPPA_FLOOR:
        revised = {}
        for case_id, case_dir in case_dirs:
            p1, p2 = case_dir / "KEY_MOVEMENT_REVISED.json", case_dir / "KEY_MOVEMENT_L2_REVISED.json"
            if not (p1.is_file() and p2.is_file()):
                raise ValueError("kappa %s is below the floor: the revision round is needed (%s)" % (k, case_id))
            revised[case_id] = (_rows(p1), _rows(p2))
        labels, record["revised"] = revised, True
        k = record["kappa_after"] = pooled(labels)
    every = k is None or k < KAPPA_FLOOR
    record["labeller_3"] = "every row" if every else "the rows labellers 1 and 2 disagree on"
    settled, decided, dropped = [], 0, 0
    for case_id, case_dir in case_dirs:
        l1, l2 = labels[case_id]
        need = sorted(l1) if every else [x for x in sorted(l1) if l1[x] != l2[x]]
        l3_path = case_dir / "KEY_MOVEMENT_L3.json"
        l3 = _rows(l3_path) if l3_path.is_file() else {}
        missing = [x for x in need if x not in l3]
        if missing:
            raise ValueError("%s: labeller 3 is needed on %d row(s)" % (case_id, len(missing)))
        for x in sorted(l1):
            if x in need:
                votes = [l1[x], l2[x], l3[x]]
                top = max(sorted(set(votes)), key=votes.count)
                decided += 1
                if votes.count(top) < 2:
                    dropped += 1
                    continue
                label = top
            else:
                label = l1[x]
            if label not in score.LABELS:
                raise ValueError("%s: a key label is not one of the four" % case_id)
            settled.append({"case_id": case_id, "issue_id": x[0], "rounds": list(x[1]), "label": label})
    record.update(decided_by_labeller_3=decided, dropped=dropped)
    return settled, record


def fill_declarations(manifest, documents, declarations):
    """The open issues' text_units and closed_units from the exact last-round headings declared."""
    import pairing_map
    last = max(manifest["rounds"], key=lambda r: r["sequence"])
    by_title = {}
    for doc_id in last["document_ids"]:
        for u in pairing_map.split_units(documents[doc_id], document_id=doc_id):
            by_title.setdefault(u["title"].strip(), set()).add(u["unit_id"].split("-", 1)[-1])
    for issue in manifest["issues"]:
        if not issue.get("open"):
            continue
        d = (declarations or {}).get(issue["issue_id"]) or {}
        for field, src in (("text_units", "text_headings"), ("closed_units", "closed_headings")):
            slugs = set()
            for heading in d.get(src) or []:
                if heading.strip() not in by_title:
                    raise ValueError("%s: a declared heading is not a last-round heading" % manifest["case_id"])
                slugs |= by_title[heading.strip()]
            issue[field] = sorted(slugs)
        for field in ("position", "fallback"):
            if d.get(field):
                issue[field] = d[field]
    return manifest


def below_minimums(manifest):
    """The minimums a case falls short of (plan section 2.7), [] when it meets them."""
    have = {"rounds": len(manifest.get("rounds") or []), "parties": len(manifest.get("actors") or []),
            "issues": len(manifest.get("issues") or []),
            "open_issues": sum(1 for i in manifest.get("issues") or [] if i.get("open"))}
    exact = ("rounds", "parties")  # three rounds and two parties exactly; issues and open issues at least
    return sorted(k for k, v in MINIMUMS.items() if (have[k] != v if k in exact else have[k] < v))


def read_case(case_dir):
    manifest = json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))
    documents = {p.stem: p.read_text(encoding="utf-8").replace("\r\n", "\n")
                 for p in sorted((case_dir / "context").iterdir()) if p.is_file()}
    declarations = (json.loads((case_dir / "declarations.json").read_text(encoding="utf-8"))
                    if (case_dir / "declarations.json").is_file() else {})
    return manifest, documents, declarations


def set_digest(root):
    listing = sorted((p.relative_to(root).as_posix(), _sha_bytes(p.read_bytes()))
                     for p in Path(root).rglob("*") if p.is_file() and not p.name.startswith("FREEZE"))
    return _sha_bytes(json.dumps(listing, separators=(",", ":")).encode("utf-8")), listing


def _shares(rows):
    labels = [r["label"] for r in rows]
    return {c: (labels.count(c) / len(labels) if labels else None) for c in score.LABELS}


def forecast_seconds(case_passages, corpus_passages_count, other_case_passages):
    """(encoding, comparison, 5-gram) seconds: every passage encoded once, then each case against every
    corpus and every other case by the cosine, and every corpus and case passage read once against the
    cases' gram index (D-437 item 3)."""
    total = corpus_passages_count + sum(case_passages)
    encoding = total * SECONDS_PER_PASSAGE
    pairs = sum(n * (corpus_passages_count + other_case_passages - n) for n in case_passages)
    return encoding, pairs * DIMENSIONS / MULTIPLY_ADDS_PER_SECOND, total * JACCARD_SECONDS_PER_PASSAGE


def token_batches(lengths, *, budget=None, most=None):
    """Index lists, longest passage first, each batch at most `most` passages and `budget` tokens (a passage
    over the budget alone); every index once."""
    budget, most = budget or TOKEN_BUDGET, most or BATCH_SIZE
    order = sorted(range(len(lengths)), key=lambda i: (-lengths[i], i))
    batches, current, tokens = [], [], 0
    for i in order:
        n = min(lengths[i], MAX_TOKENS)
        if current and (len(current) >= most or tokens + n > budget):
            batches.append(current)
            current, tokens = [], 0
        current.append(i)
        tokens += n
    if current:
        batches.append(current)
    return batches


def encode_chunked(encode, texts, *, progress=None, label="", chunk=None):
    """One float32 array of `texts`' vectors, encoded ENCODE_CHUNK passages at a time (D-437 item 2),
    with a measured progress line after each chunk (PROGRESS-A): done of total, elapsed, rate, remaining."""
    import numpy as np
    chunk = chunk or ENCODE_CHUNK
    texts = list(texts)
    out, started = None, time.perf_counter()
    for start in range(0, len(texts), chunk):
        part = np.asarray(encode(texts[start:start + chunk]), dtype=np.float32)
        if out is None:
            out = np.empty((len(texts), part.shape[1]), dtype=np.float32)
        out[start:start + len(part)] = part
        done, elapsed = start + len(part), time.perf_counter() - started
        if progress and len(texts) > chunk:
            rate = done / elapsed if elapsed else 0.0
            progress("encoding %s: %d of %d passages, %.0f s, %.2f a second, %.0f s left at that rate"
                     % (label, done, len(texts), elapsed, rate, (len(texts) - done) / rate if rate else float("nan")))
    return out if out is not None else np.empty((0, DIMENSIONS), dtype=np.float32)


def freeze(root, corpus_paths, *, encode=None, model=None, progress=print, accept_skipped=()):
    import multi_round as mr
    root = Path(root)
    cases = [(d, "R") for d in sorted((root / "real").glob("*")) if d.is_dir()] + \
            [(d, "F" if d.name.endswith("-free") else "S") for d in sorted((root / "synthetic").glob("*")) if d.is_dir()]
    if not cases:
        raise ValueError("no case folders under real/ or synthetic/")
    corpora = corpus_passages(corpus_paths, accept_skipped=accept_skipped)
    subsets, report, open_issues, case_dirs, case_passages, case_sources = {}, {}, [], [], {}, {}
    for case_dir, subset in cases:
        manifest, documents, declarations = read_case(case_dir)
        manifest = fill_declarations(manifest, documents, declarations)
        mr.validate_manifest(manifest)
        short = below_minimums(manifest)
        if short:
            raise ValueError("%s: below the plan's minimums: %s" % (manifest["case_id"], ", ".join(short)))
        for s in manifest["sources"]:
            if documents[s["document_id"]][s["char_start"]:s["char_end"]] != s["quote"]:
                raise ValueError("%s: a source span does not match its file" % manifest["case_id"])
        (case_dir / "case_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                                     encoding="utf-8", newline="\n")
        case_id = manifest["case_id"]
        subsets[case_id] = subset
        case_dirs.append((case_id, case_dir))
        case_passages[case_id] = [p for t in documents.values() for p in passages(t)]
        source_md = (case_dir / "SOURCE.md").read_text(encoding="utf-8") if (case_dir / "SOURCE.md").is_file() else ""
        case_sources[case_id] = (set(_URL.findall(source_md)), set(documents))
        open_issues += [[case_id, i["issue_id"]] for i in manifest["issues"] if i.get("open")]
    key, kappas = settle_all(case_dirs)
    corpus_count = sum(len(c["passages"]) for c in corpora.values())
    sizes = [len(p) for p in case_passages.values()]
    enc_s, cmp_s, jac_s = forecast_seconds(sizes, corpus_count, sum(sizes))
    counter = getattr(encode, "count_tokens", None)
    tokens = None
    if counter is not None:
        # The forecast by token, from the encoder's own tokenizer (D-437 item 2).
        tokens = sum(min(n, MAX_TOKENS) for c in corpora.values() for n in counter(c["passages"])) + \
            sum(min(n, MAX_TOKENS) for ps in case_passages.values() for n in counter(ps))
        enc_s = tokens * SECONDS_PER_TOKEN
    forecast = round(((enc_s + cmp_s) if encode else 0.0) / 60 + jac_s / 60, 1)
    progress("leakage pass: %d passages, forecast %.1f minutes (%.1f encoding at %.2f s a passage, %.1f comparing, "
             "%.1f on the 5-gram index at %.4f s a passage)" % (corpus_count + sum(sizes), forecast,
                                                               (enc_s if encode else 0.0) / 60, SECONDS_PER_PASSAGE,
                                                               (cmp_s if encode else 0.0) / 60, jac_s / 60,
                                                               JACCARD_SECONDS_PER_PASSAGE))
    jac_started = time.perf_counter()
    index = GramIndex([(c, p) for c, ps in case_passages.items() for p in ps])
    jaccard_hits = {}
    for name, c in corpora.items():
        jaccard_hits[name] = index.matches(c["passages"])
    for other, ps in case_passages.items():
        jaccard_hits["case:" + other] = index.matches(ps, skip_owner=other)
    jaccard_seconds = round(time.perf_counter() - jac_started, 1)
    started = time.perf_counter()
    corpus_vectors = ({name: encode_chunked(encode, c["passages"], progress=progress, label=name)
                       for name, c in corpora.items() if c["passages"]} if encode else {})
    case_vectors = {c: encode_chunked(encode, p) for c, p in case_passages.items()} if encode else {}
    for case_id, _ in case_dirs:
        others = {"case:" + c: {"passages": p, "urls": case_sources[c][0], "stems": case_sources[c][1]}
                  for c, p in case_passages.items() if c != case_id}
        other_vectors = {"case:" + c: v for c, v in case_vectors.items() if c != case_id}
        urls, stems = case_sources[case_id]
        mine_hits = {name: {t for o, t in hits if o == case_id} for name, hits in jaccard_hits.items()
                     if name != "case:" + case_id}
        leaks = leakage(case_passages[case_id], case_vectors.get(case_id) if encode else None,
                        dict(corpora, **others), dict(corpus_vectors, **other_vectors), urls=urls, stems=stems,
                        jaccard_hits=mine_hits)
        hit = {name: c for name, c in leaks.items() if any(c.values())}
        report[case_id] = {"subset": subsets[case_id], "rows": sum(1 for r in key if r["case_id"] == case_id),
                           "kappa_before": kappas["per_case_before"].get(case_id), "leakage_hits": hit}
    seconds = round(time.perf_counter() - started, 1)
    leaked = sorted(c for c, r in report.items() if r["leakage_hits"])
    if leaked:
        raise ValueError("leakage: %d case(s) over a threshold: %s" % (len(leaked), ", ".join(leaked)))
    headline = [r for r in key if subsets[r["case_id"]] in score.HEADLINE_SUBSETS]
    digest, listing = set_digest(root)
    value = {"schema": "negotiation-freeze-v1", "set_sha256": digest, "files": listing, "subsets": subsets,
             "movement_key": key, "class_shares": _shares(key), "headline_class_shares": _shares(headline),
             "floors": score.floors([(r["label"], r["label"]) for r in headline]), "cases": report, "kappa": kappas,
             "open_issues": open_issues, "corpora": sorted(str(p) for p in corpus_paths),
             "corpus_files": {n: {"files": c["files"], "read": c["read"], "skipped": c["skipped"],
                                  "passages": len(c["passages"])} for n, c in corpora.items()},
             "thresholds": {"jaccard": JACCARD, "ngram": NGRAM, "cosine": COSINE, "min_words": MIN_WORDS,
                            "kappa_floor": KAPPA_FLOOR, "minimums": MINIMUMS},
             "leakage_seconds": seconds, "jaccard_seconds": jaccard_seconds, "leakage_forecast_minutes": forecast,
             "tokens_encoded": tokens,
             "embedding": ({"model": model, "batch_size": BATCH_SIZE, "token_budget": TOKEN_BUDGET,
                            "max_tokens": MAX_TOKENS, "precision": "float32",
                            "cut_at_max_tokens": getattr(encode, "cut", None),
                            "device": (model or {}).get("device", "cpu")} if encode is not None else None),
             "dry_run": encode is None}
    name = "FREEZE.json" if encode is not None else "FREEZE.dryrun.json"
    (root / name).write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8", newline="\n")
    return value


def bge_m3_identity():
    """{path, sha256}: the cached bge-m3 snapshot the pass reads, and one digest over its weight and
    config files (sorted by name), so FREEZE.json names the exact model."""
    from huggingface_hub import snapshot_download
    path = Path(snapshot_download("BAAI/bge-m3", local_files_only=True))
    digest = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in (".safetensors", ".bin", ".json")):
        digest.update(f.relative_to(path).as_posix().encode("utf-8"))
        with open(f, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest()}


# D-399: the laptop GPU may be used only while idle: at most 1,024 MiB in use and 10 percent busy.
GPU_IDLE_MIB = 1024
GPU_IDLE_PERCENT = 10


def gpu_reading():
    """{memory_used_mib, utilization_percent, read_at} of the first GPU, from nvidia-smi, or None."""
    import subprocess
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True,
                             timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        used, busy = [float(x) for x in out.strip().splitlines()[0].split(",")]
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None
    return {"memory_used_mib": used, "utilization_percent": busy, "read_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def gpu_idle(reading):
    """True when a reading shows the GPU idle under D-399's rule."""
    return (isinstance(reading, dict) and reading.get("memory_used_mib") is not None
            and reading["memory_used_mib"] <= GPU_IDLE_MIB and reading.get("utilization_percent") is not None
            and reading["utilization_percent"] <= GPU_IDLE_PERCENT)


# The GPU is read before the first chunk as well as after every chunk (the lead under D-456).
WATCH_BEFORE_FIRST_CHUNK = True
# Seconds the pass waits, after its chunk has finished on the GPU, before reading the card's utilisation:
# this process is then not computing, so what the card reports is the other processes' use (D-399, D-456).
UTIL_SETTLE_SECONDS = 1.0


def other_gpu_reading(own_mib=None, own_overhead_mib=None):
    """{other_processes_mib, method, utilization_percent, read_at, ...}: what processes other than this one
    hold of the GPU, or None when it cannot be read (D-456).

    Memory: per process from nvidia-smi's compute-process list (`per_process`), only when every row is a
    number and this process's own pid is listed; then this process's listed use less torch's reserved
    memory `own_mib` is its overhead (`own_overhead_mib` in the reading). Otherwise, as under Windows'
    display driver, which prints [N/A] for every process (measured on this laptop, 9 November), the
    whole card's use less this process's own (`whole_less_own`: `own_mib` plus the overhead
    `own_overhead_mib` the encoder measured at its first chunk).

    Utilisation: the card's, read by the caller's timing while this process is not computing (after its
    chunk has finished and UTIL_SETTLE_SECONDS have passed), so it is the use beyond this process's own."""
    import os
    import subprocess
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    whole = gpu_reading()
    try:
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, check=True, timeout=30, creationflags=flags).stdout
        rows = [[x.strip() for x in line.split(",")[:2]] for line in apps.strip().splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        rows = None
    base = {"utilization_percent": (whole or {}).get("utilization_percent"),
            "utilization_method": "card_while_this_process_idle", "read_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    listing = None
    try:
        if rows is not None and all(len(r) == 2 and r[1].replace(".", "", 1).isdigit() for r in rows):
            listing = {int(pid): float(used) for pid, used in rows}
    except ValueError:
        listing = None
    if listing is not None and os.getpid() in listing:
        mine = listing[os.getpid()]
        return dict(base, method="per_process", own_listed_mib=mine,
                    own_overhead_mib=(max(0.0, mine - own_mib) if own_mib is not None else None),
                    other_processes_mib=sum(v for pid, v in listing.items() if pid != os.getpid()))
    if whole is None or own_mib is None or own_overhead_mib is None:
        return None
    return dict(base, method="whole_less_own", card_used_mib=whole["memory_used_mib"], own_mib=own_mib,
                own_overhead_mib=own_overhead_mib,
                listing=("without this process" if listing is not None else "unreadable"),
                other_processes_mib=max(0.0, whole["memory_used_mib"] - own_mib - own_overhead_mib))


def _own_gpu_mib():
    """This process's reserved GPU memory in MiB, from torch, or None."""
    try:
        import torch
        return torch.cuda.memory_reserved() / 2 ** 20 if torch.cuda.is_available() else None
    except Exception:
        return None


def _gpu_settle():
    """Wait for this process's GPU work to finish, then UTIL_SETTLE_SECONDS, before a utilisation reading."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        pass
    time.sleep(UTIL_SETTLE_SECONDS)


def gpu_free_of_others(reading):
    """True when the other processes hold at most GPU_IDLE_MIB and the card is at most GPU_IDLE_PERCENT
    busy beyond this process's own use (D-399, D-456). An unreadable reading is not free."""
    return (isinstance(reading, dict) and reading.get("other_processes_mib") is not None
            and reading["other_processes_mib"] <= GPU_IDLE_MIB and reading.get("utilization_percent") is not None
            and reading["utilization_percent"] <= GPU_IDLE_PERCENT)


def bge_m3_encoder(device="cpu"):
    """(encode, release, device record): the repository's own bge-m3 (embedding_store's loader), float32,
    in batches of BATCH_SIZE, unit vectors. On the CPU by default. On the GPU only when a reading taken
    first shows it idle (D-399); the model is released at once after the pass (`release`). On the GPU,
    nvidia-smi is read again after every chunk (D-456, item 3): when another process holds more than
    GPU_IDLE_MIB, the pass stops on the GPU after that chunk, moves the model to the CPU, frees the GPU
    and goes on there; every reading and the move are recorded (`gpu_readings`, `moved_to_cpu`)."""
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    record = {"device": device}
    if device == "cuda":
        reading = gpu_reading()
        record["gpu_before"] = reading
        if not gpu_idle(reading):
            raise RuntimeError("the GPU is not idle (D-399: at most %d MiB and %d percent): %s"
                               % (GPU_IDLE_MIB, GPU_IDLE_PERCENT, reading))
        os.environ.pop("SHIMMER_BACKEND_PROFILE", None)
    elif device == "cpu":
        # embedding_store puts bge-m3 on the CPU under the local profile (its own rule).
        os.environ["SHIMMER_BACKEND_PROFILE"] = "local"
    else:
        raise ValueError("the device is cpu or cuda")
    import semantic_ensemble
    semantic_ensemble._MODEL_CACHE.pop("m", None)
    model = semantic_ensemble._sbert_model()
    if model is None:
        raise RuntimeError("bge-m3 could not be loaded from the local cache")
    on = str(getattr(model, "device", "cpu"))
    if not on.startswith(device):
        raise RuntimeError("bge-m3 loaded on %s, not the %s" % (on, device))

    model.max_seq_length = MAX_TOKENS

    def count_tokens(texts):
        return [len(ids) for ids in model.tokenizer(list(texts), add_special_tokens=True, truncation=False)["input_ids"]]

    state = {"device": device}
    record["gpu_readings"], record["moved_to_cpu"] = [], None

    def watch(after_passages):
        if state["device"] != "cuda":
            return
        _gpu_settle()
        own = _own_gpu_mib()
        reading = other_gpu_reading(own, state.get("overhead"))
        if (reading or {}).get("method") == "per_process" and "overhead" not in state:
            # The listing gives this process's own use, so its overhead is measured, not inferred.
            state["overhead"] = reading.get("own_overhead_mib")
            record["own_overhead_mib"], record["overhead_method"] = state["overhead"], "per_process"
        elif reading is None and "overhead" not in state:
            # No usable listing: at the first chunk the other processes are taken to hold what the
            # reading before the load showed, and the rest of the card's use that torch has not reserved
            # is this process's own overhead. Its limit (plan section 2.6): another process that started
            # between that reading and the first chunk is counted as this process's overhead.
            now = gpu_reading()
            before = (record.get("gpu_before") or {}).get("memory_used_mib")
            state["overhead"] = (max(0.0, now["memory_used_mib"] - own - before)
                                 if now and own is not None and before is not None else None)
            record["own_overhead_mib"], record["overhead_method"] = state["overhead"], "first_chunk_window"
            reading = other_gpu_reading(own, state["overhead"])
        record["gpu_readings"].append(dict(reading or {"unreadable": True}, after_passage=after_passages))
        if gpu_free_of_others(reading):
            return
        import torch
        model.to("cpu")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        state["device"] = "cpu"
        record["moved_to_cpu"] = {"after_passage": after_passages, "reading": reading,
                                  "after": gpu_reading()}

    def encode(texts):
        import numpy as np
        texts = list(texts)
        if encode.done == 0 and WATCH_BEFORE_FIRST_CHUNK:
            # Read before the first chunk too: the pre-load check showed the GPU idle before the model
            # was loaded, and another process could take it while it loads.
            watch(0)
        encode.done += len(texts)
        lengths = count_tokens(texts)
        encode.cut = (encode.cut or 0) + sum(n > MAX_TOKENS for n in lengths)
        out = np.empty((len(texts), DIMENSIONS), dtype=np.float32)
        for batch in token_batches(lengths):
            out[batch] = np.asarray(model.encode([texts[i] for i in batch], batch_size=len(batch),
                                                 normalize_embeddings=True, convert_to_numpy=True), dtype=np.float32)
        # Read after each chunk: the next chunk runs on the GPU only while it still reads free.
        watch(encode.done)
        return out
    encode.cut = 0
    encode.done = 0
    encode.count_tokens = count_tokens

    def release():
        semantic_ensemble._MODEL_CACHE.pop("m", None)
        if device == "cuda":
            import torch
            if state["device"] == "cuda":
                model.to("cpu")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            record["device_at_end"] = state["device"]
            record["gpu_after"] = gpu_reading()
    return encode, release, record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--set", type=Path, required=True)
    parser.add_argument("--corpora", type=Path, required=True, help="a committed file listing one corpus path a line")
    parser.add_argument("--no-embedding", action="store_true",
                        help="a dry run: no cosine test, FREEZE.dryrun.json written, which the scorer refuses")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                        help="where bge-m3 runs: the CPU, or the GPU only when it reads idle (D-399)")
    args = parser.parse_args(argv)
    lines = [line.strip() for line in args.corpora.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    accept = [l.split(":", 1)[1].strip() for l in lines if l.startswith("accept-skipped:")]
    paths = [Path(l) for l in lines if not l.startswith("accept-skipped:")]
    if args.no_embedding:
        value = freeze(args.set, paths, accept_skipped=accept)
    else:
        encode, release, device = bge_m3_encoder(args.device)
        try:
            value = freeze(args.set, paths, encode=encode, model=dict(bge_m3_identity(), **device), accept_skipped=accept)
        finally:
            release()
        if device.get("gpu_after") is not None:
            # The reading after release, written into the freeze record as well.
            path = Path(args.set) / "FREEZE.json"
            stored = json.loads(path.read_text(encoding="utf-8"))
            stored["embedding"]["model"]["gpu_after"] = device["gpu_after"]
            path.write_text(json.dumps(stored, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"set_sha256": value["set_sha256"], "cases": len(value["subsets"]), "dry_run": value["dry_run"],
                      "rows": len(value["movement_key"]), "headline_class_shares": value["headline_class_shares"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
