"""The shared leakage check of D-S100 and D-S102 item 3: one tool for every item set.

Split so no one reads both sides, as `overlap.py` is (D-S77 item 1):

  fingerprint --part <name>=<path>[;<path>...][#key,key] [--part ...] --out <file> [--embed | --count]
      run on the lead's side over every training, tuning, calibration and development file of
      every part. A path is a file or a folder (every file under it). Read: JSON and JSON lines
      (every string value at any depth), plain text (.txt, .md: each paragraph; .csv, .tsv: each
      line), and the members of .tar.gz, .tgz, .tar and .zip archives by the same rules. Any other
      archive format is refused; any other file is skipped and listed with its digest; a key file
      (`answer_key.json`, or anything under a `keys` folder) is skipped unread and listed; a path
      under the fresh set's folder (NEVER) is refused; a sealed bundle's model assets (`assets.tar`, an
      `hf_cache` folder) are skipped unread and listed. `--count` counts records and words only, so
      the embedding is forecast before it runs. With `#key,key` only the values under those
      keys, at any depth (a judge mix: `#rows,held_out`, leaving out the read-development
      `questions`). A record is a string of at least MIN_WORDS words; a string of SHORT_MIN_WORDS
      to MIN_WORDS - 1 words is a short record, held by its exact hash alone. Written: each file's
      SHA-256, the files skipped, each part's record counts, the exact hash of every record, its
      8-word runs (`overlap.py`'s rule) and, with --embed, one float32 unit vector per distinct
      record from the repository's own embedding model, embedded in chunks. No text is written.
  check --fingerprints <file> (--benchmark contradoc|scitab --input <release file> [--assignment
        <split file>] [--side holdout] | --candidates <file>) --exclude-groups <ids> --out <file> [--embed]
      run by role B in its own folder: each candidate's own benchmark text (never an adapter's
      wording) is checked by the four rules below, a group is excluded whole when any member is,
      and written are counts, the parts hit, ids (candidate ids and group keys), and the digests of
      every input (the fingerprints, the release or candidates file, the assignment and the
      exclusion file), so the draw can refuse a check that ran on anything else. Any other item set
      (PUBHEALTH, CLadder, Corr2Cause, a judge's held-out rows) is checked by writing its candidates
      as `--candidates`: a JSON list of {id, group, texts[, table]}, each text the item's own source
      text; `group` is the unit items share when they are not independent (the item itself when not).
  cosine-step --dev <ContraDoc development file> --assignment <its split file> --prompts <prompts
        file> --items <its build's items.json> --out <file> [--embed]
      run on the lead's side on development material only, before role B starts (LEAKAGE_PROTOCOL.md
      step 2): the cosine of documents within one near-duplicate group, across groups, and of a
      document against a prompt that wraps it, and the threshold the rule written below gives.

The four rules and their thresholds, written before any candidate is checked (D-S100); none is ever
relaxed after a count of any check is seen:
  1. exact: the NFKC, case-folded, whitespace-collapsed text of a candidate text (or of the
     candidate's texts joined) has the SHA-256 of a part's record or short record. Any hit excludes.
  2. runs: the candidate shares at least RUNS_MIN 8-word runs with a part's records. A run of
     digits only is not counted (table cells and figures repeat by chance). RUNS_MIN is 1.
  3. cosine: a candidate text's unit vector and a part record's have a dot product of at least
     COSINE (0.92). Both sides embed one text form (`embed_form`: NFKC, whitespace collapsed, case
     kept), since bge-m3's tokenizer is cased. The step 2 rule may only lower it (cosine_step).
  4. source: a candidate whose group key, own id or table id is listed in --exclude-groups (the
     fresh set by id, every development group, paper and table) is excluded.

A candidate text under MIN_WORDS words has no 8-word run: it is caught by rules 1, 3 and 4 only, and
the result counts such texts (`short_texts`).

Standard library, and numpy for the vectors.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import random
import sys
import tarfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import ids, overlap  # noqa: E402

MIN_WORDS = 8
SHORT_MIN_WORDS = 4
RUNS_MIN = 1
COSINE = 0.92
EMBED_CHUNK = 512
RULES = ("exact", "runs", "cosine", "source")
THRESHOLDS = {"min_words": MIN_WORDS, "short_min_words": SHORT_MIN_WORDS, "runs_min": RUNS_MIN, "run_words": overlap.SHINGLE,
              "run_hash_chars": overlap.HASH_CHARS, "cosine_ceiling": COSINE, "digit_only_runs": "not counted",
              "embed_form": "NFKC, whitespace collapsed, case kept"}
FORMAT = "shimmer-gate-leakage-fingerprints-v2"
JSON_SUFFIXES = (".json", ".jsonl")
PARAGRAPH_SUFFIXES = (".txt", ".md")
LINE_SUFFIXES = (".csv", ".tsv")
TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar")
REFUSED_ARCHIVES = (".gz", ".bz2", ".xz", ".7z", ".rar", ".zst", ".lz", ".lzma", ".z", ".tbz2", ".txz")
NEVER = ("external/s05/D-S56",)   # the fresh set's folder: excluded by id only (rule 4), never read
NEVER_COMPONENTS = {n.rsplit("/", 1)[-1].lower() for n in NEVER}   # "d-s56" alone, as in an archive member's name
ASSET_NAMES = ("assets.tar",)     # a sealed bundle's model weights: skipped by name, listed, never opened
# The step 2 rule, fixed before step 2 runs: the threshold becomes the lowest of COSINE, the 5th
# percentile within one group and the 5th percentile of a document against its own prompt, rounded
# down to .01. It is never raised.
STEP2_PERCENTILE = 5
STEP2_ACROSS_PERCENTILE = 99.9
STEP2_ACROSS_PAIRS = 2000
STEP2_SEED = 20261109


def normalise(text) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text)).casefold().split())


def embed_form(text) -> str:
    """The one text form both sides embed: NFKC, whitespace collapsed, case kept."""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split())


def exact_hash(text) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def runs(text) -> set:
    """`overlap.py`'s 8-word runs, a run of digits only left out."""
    w = overlap.words(text)
    return {hashlib.sha256(" ".join(w[i:i + overlap.SHINGLE]).encode("utf-8")).hexdigest()[:overlap.HASH_CHARS]
            for i in range(len(w) - overlap.SHINGLE + 1)
            if not all(x.isdigit() for x in w[i:i + overlap.SHINGLE])}


def _json_values(raw: bytes):
    text = raw.decode("utf-8-sig")
    try:
        yield json.loads(text)
    except ValueError:
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)


def _posix(label) -> str:
    return str(label).replace("\\", "/")


def _is_asset(name) -> bool:
    parts = PurePosixPath(_posix(name)).parts
    return parts[-1].lower() in ASSET_NAMES or any(p.lower() == "hf_cache" for p in parts[:-1])


def _is_key(name) -> bool:
    parts = PurePosixPath(_posix(name)).parts
    return parts[-1].lower() == "answer_key.json" or any(p.lower() == "keys" for p in parts[:-1])


def _kind(name):
    n = name.lower()
    if n.endswith(JSON_SUFFIXES):
        return "json"
    if n.endswith(PARAGRAPH_SUFFIXES):
        return "paragraphs"
    if n.endswith(LINE_SUFFIXES):
        return "lines"
    if n.endswith(TAR_SUFFIXES):
        return "tar"
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(REFUSED_ARCHIVES):
        return "refused"
    return None


# D-442 (corrected): the one file under NEVER any gate tool may read, ids only, by its digest, and only
# as `exclude-ids --fresh-ids`: the fresh set's ids file, which choice-build built (D-315).
FRESH_IDS_FILE = "external/s05/D-S56/contradoc_fresh100_ids.json"
FRESH_IDS_SHA256 = "ec2498fde66cb667c960c5ae3ae518739503e1b09df1df2e3d8c5dec608a075b"


def guard(path, fresh_ids=False):
    """Every path a gate tool is given, and every archive member it opens, is refused under NEVER
    (audit gap 10). With `fresh_ids`, the fresh set's ids file alone is admitted, and only while its
    bytes have the pinned digest; nothing else under NEVER, ever."""
    member = "!" in str(path)
    text = _posix(path) if member else _posix(Path(str(path)).resolve())
    components = {c.lower() for c in _posix(path).replace("!", "/").split("/")} | {c.lower() for c in text.replace("!", "/").split("/")}
    if not any(n in text or n in _posix(path) for n in NEVER) and not components & NEVER_COMPONENTS:
        return path
    if fresh_ids and not member and text.endswith(FRESH_IDS_FILE) and Path(str(path)).is_file() \
            and hashlib.sha256(Path(str(path)).read_bytes()).hexdigest() == FRESH_IDS_SHA256:
        return path
    raise ValueError("a path reaches the fresh set's folder, read only for its pinned ids file: " + str(path))


PATH_ARGS = ("fingerprints", "input", "candidates", "assignment", "exclude_groups", "out", "dev", "prompts", "items",
             "cosine_step", "leakage", "counts", "fresh_ids", "scitab_development", "contradoc_assignment",
             "demonstration_tables", "contradoc_ids", "scitab_ids", "out_dir", "class_setting")


def guard_args(args):
    """The guard on every path argument of a gate tool's command line, parts included."""
    for name in PATH_ARGS:
        value = getattr(args, name, None)
        for v in (value if isinstance(value, list) else [value]):
            if v:
                guard(v, fresh_ids=(name == "fresh_ids"))
    for part in getattr(args, "part", None) or []:
        for q in part.partition("=")[2].partition("#")[0].split(";"):
            if q:
                guard(q)


def _entries(label, raw, skipped):
    """(label, kind, bytes) of a file's readable content, archives opened member by member."""
    guard(label)
    if _is_key(label):
        skipped.append({"file": label, "sha256": None, "reason": "key file, not read"})
        return
    if _is_asset(label):
        skipped.append({"file": label, "sha256": None, "reason": "model assets, not read"})
        return
    kind = _kind(label)
    if kind == "refused":
        raise ValueError("an archive in a format the check cannot read: " + label)
    if kind == "tar":
        try:
            tar = tarfile.open(fileobj=io.BytesIO(raw), mode="r:*")
        except tarfile.TarError:
            raise ValueError("an archive that cannot be read: " + label) from None
        with tar:
            for member in sorted(tar.getmembers(), key=lambda m: m.name):
                if member.isfile():
                    yield from _entries("%s!%s" % (label, member.name), tar.extractfile(member).read(), skipped)
    elif kind == "zip":
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise ValueError("an archive that cannot be read: " + label) from None
        with z:
            for name in sorted(z.namelist()):
                if not name.endswith("/"):
                    yield from _entries("%s!%s" % (label, name), z.read(name), skipped)
    elif kind is None:
        skipped.append({"file": label, "sha256": hashlib.sha256(raw).hexdigest(), "reason": "not a format the check reads"})
    else:
        yield label, kind, raw


def _files(path, skipped):
    path = Path(guard(path))
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file():
                yield from _files(p, skipped)
        return
    if _is_key(path) or _is_asset(path):
        skipped.append({"file": str(path), "sha256": None, "reason": "key file, not read" if _is_key(path) else "model assets, not read"})
        return
    yield from _entries(str(path), path.read_bytes(), skipped)


def _under(value, keys):
    """The values held under any of `keys`, at any depth."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in keys:
                yield v
            else:
                yield from _under(v, keys)
    elif isinstance(value, list):
        for v in value:
            yield from _under(v, keys)


def _texts(kind, raw, label, keys):
    if kind == "json":
        try:
            values = list(_json_values(raw))
        except ValueError:
            raise ValueError("not JSON or JSON lines: " + label)
        if keys:
            values = [v for value in values for v in _under(value, set(keys))]
        for value in values:
            yield from overlap._strings(value)
        return
    if keys:
        return
    text = raw.decode("utf-8-sig", errors="replace")
    if kind == "lines":
        yield from text.splitlines()
    else:
        yield from (p for p in text.replace("\r\n", "\n").split("\n\n"))


def records(path, keys=None, skipped=None):
    """(file, its SHA-256, text, short) for every string of at least SHORT_MIN_WORDS words in the files
    `path` names (only under `keys` when given); `short` when it has fewer than MIN_WORDS words."""
    skipped = [] if skipped is None else skipped
    for label, kind, raw in _files(path, skipped):
        sha = hashlib.sha256(raw).hexdigest()
        for text in _texts(kind, raw, label, keys):
            n = len(overlap.words(text))
            if n >= SHORT_MIN_WORDS:
                yield label, sha, text, n < MIN_WORDS


def _unit_rows(matrix):
    import numpy as np
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return (matrix / norms).astype(np.float32)


def _embed_all(embed, texts):
    """float32 unit rows of `texts`, embedded EMBED_CHUNK at a time."""
    import numpy as np
    chunks, dim = [], None
    for i in range(0, len(texts), EMBED_CHUNK):
        rows = _unit_rows(embed(texts[i:i + EMBED_CHUNK]))
        if rows.shape[0] != len(texts[i:i + EMBED_CHUNK]) or (dim is not None and rows.shape[1] != dim):
            raise ValueError("the embedder returned vectors of the wrong number or size")
        dim = rows.shape[1]
        chunks.append(rows)
    return np.concatenate(chunks) if chunks else np.zeros((0, 0), dtype=np.float32)


S05 = "external/s05"
S05_UNPARTED = ("D-S56", "GATE")   # the fresh set's folder (excluded by id) and the gate's own outputs


def uncovered(paths) -> list:
    """The entries of every external/s05 folder the parts reach that no part path covers (equal to it or
    under it), D-S56 and GATE aside: a fingerprint over an external/s05 with such an entry is refused,
    so a new run folder can never be left out of the leakage check (gap: SAVINGS_PROOF)."""
    given = [_posix(Path(q).resolve()).rstrip("/") for q in paths]
    roots = {g[:g.index("/" + S05 + "/") + len(S05) + 1] for g in given if ("/" + S05 + "/") in g}
    missing = []
    for r in sorted(roots):
        for child in sorted(Path(r).iterdir()):
            if child.name in S05_UNPARTED:
                continue
            c = _posix(child.resolve())
            if not any(c == g or c.startswith(g + "/") for g in given):
                missing.append(S05 + "/" + child.name)
    return missing


def fingerprint(parts, embed=None) -> dict:
    """`parts` is a list of (name, path) or (name, path, keys). `embed(list of texts)` returns one
    vector a text."""
    if not parts:
        raise ValueError("no part named")
    parts = [tuple(p) + (None,) * (3 - len(p)) for p in parts]
    names = [n for n, _p, _k in parts]
    if len(set(names)) != len(names) or not all(names):
        raise ValueError("every part needs its own non-empty name")
    left_out = uncovered([q for _n, path, _k in parts for q in str(path).split(";") if q])
    if left_out:
        raise ValueError("external/s05 entries no part covers: " + ", ".join(left_out))
    files, counts, short, exact, run_parts, texts, skipped = {}, {}, {}, {}, {}, {}, {}
    for name, path, keys in parts:
        paths = [q for q in str(path).split(";") if q]
        for q in paths:
            if not Path(q).exists():
                raise ValueError("part %s: no such path %s" % (name, q))
        seen = files.setdefault(name, {})
        skipped[name] = []
        counts[name], short[name] = 0, 0
        for label, sha, text, is_short in (r for q in paths for r in records(q, keys, skipped[name])):
            seen[label] = sha
            h = exact_hash(text)
            exact.setdefault(h, set()).add(name)
            if is_short:
                short[name] += 1
                continue
            counts[name] += 1
            for r in runs(text):
                run_parts.setdefault(r, set()).add(name)
            texts.setdefault(h, embed_form(text))
        if not seen and not skipped[name]:
            raise ValueError("part %s holds no file" % name)
        if keys and not counts[name]:
            raise ValueError("part %s holds no record under %s" % (name, ", ".join(keys)))
    out = {"format": FORMAT, "thresholds": THRESHOLDS, "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "parts": sorted(names), "files": {n: [{"file": f, "sha256": s} for f, s in sorted(v.items())] for n, v in files.items()},
           "skipped": skipped, "records": counts, "short_records": short,
           "exact": {h: sorted(p) for h, p in sorted(exact.items())},
           "runs": {h: sorted(p) for h, p in sorted(run_parts.items())}, "vectors": None}
    if embed is not None:
        keys = sorted(texts)
        matrix = _embed_all(embed, [texts[k] for k in keys])
        out["vectors"] = {"dim": int(matrix.shape[1]) if len(keys) else 0, "parts": [sorted(exact[k]) for k in keys],
                          "data": base64.b64encode(matrix.tobytes()).decode("ascii")}
    return out


def count(parts) -> dict:
    """Records, short records, distinct records and words per part, nothing stored: the forecast's input."""
    out = {}
    for name, path, keys in [tuple(p) + (None,) * (3 - len(p)) for p in parts]:
        skipped, n, short, words, distinct = [], 0, 0, 0, set()
        for q in [q for q in str(path).split(";") if q]:
            for _label, _sha, text, is_short in records(q, keys, skipped):
                if is_short:
                    short += 1
                    continue
                n += 1
                words += len(overlap.words(text))
                distinct.add(exact_hash(text)[:16])
        out[name] = {"records": n, "short_records": short, "distinct_records": len(distinct), "words": words, "skipped": len(skipped)}
    return out


def write(data, out):
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, sort_keys=True)


def read(path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != FORMAT or data.get("thresholds") != THRESHOLDS:
        raise ValueError("the fingerprints were made with another format or other thresholds")
    return data


# ---- candidates: each benchmark's own text, never an adapter's wording -------------------

def candidates_contradoc(records_, assignment=None, side=None) -> list:
    from contradoc import adapter as cd
    assigned = cd.read_assignment(assignment) if assignment else None
    out = []
    for r in records_:
        sid = ids.key_string(r[cd.DOCUMENT_ID_FIELD])
        if assigned is not None:
            if sid not in assigned:
                raise ValueError("the assignment file does not list document " + sid)
            group, own_side = assigned[sid]
        else:
            group, own_side = sid, None
        if side is not None and own_side != side:
            continue
        out.append({"id": sid, "group": ids.key_string(group), "texts": [r[cd.TEXT_FIELD]]})
    return out


def candidates_scitab(records_, side=None) -> list:
    """One candidate a claim: the claim, and its table's caption with its header and cells as
    one text. The group is the paper (a table never splits from its paper)."""
    from scitab import adapter as st
    out = []
    for r in records_:
        paper = ids.key_string(r[st.PAPER_ID_FIELD])
        if side is not None and ids.split_side(paper) != side:
            continue
        table = " ".join([str(r[st.CAPTION_FIELD])] + [str(c) for c in r[st.HEADER_FIELD]]
                         + [str(c) for row in r[st.ROWS_FIELD] for c in row])
        out.append({"id": ids.key_string(r[st.ID_FIELD]), "group": paper,
                    "table": ids.key_string(r[st.TABLE_ID_FIELD]), "texts": [r[st.CLAIM_FIELD], table]})
    return out


# ---- the check ------------------------------------------------------------------------------

def _matrix(data):
    import numpy as np
    vec = data["vectors"]
    return np.frombuffer(base64.b64decode(vec["data"]), dtype=np.float32).reshape(-1, vec["dim"])


def _cosine_hits(data, texts, embed):
    """{text index: (best dot product, parts of the best record)} over the fingerprint vectors."""
    vec = data["vectors"]
    if not vec or not vec["dim"]:
        return {}
    matrix = _matrix(data)
    mine = _embed_all(embed, [embed_form(t) for t in texts])
    if mine.shape != (len(texts), vec["dim"]):
        raise ValueError("the embedder's vectors are not the fingerprints' size")
    best = {}
    for i in range(0, len(mine), 256):
        dots = mine[i:i + 256] @ matrix.T
        top = dots.argmax(axis=1)
        for j, k in enumerate(top):
            best[i + j] = (float(dots[j, k]), vec["parts"][int(k)])
    return best


def check(data, candidates, embed=None, exclude_groups=(), provenance=None, cosine=COSINE) -> dict:
    """`provenance` holds the digests of what the check ran on (main fills it); the draw reads it.
    `cosine` is step 2's threshold, read from its record (main), never above COSINE."""
    if not (isinstance(cosine, (int, float)) and 0 < cosine <= COSINE):
        raise ValueError("the cosine threshold is step 2's, at most %s; %r is refused" % (COSINE, cosine))
    if data.get("vectors") and embed is None:
        raise ValueError("the fingerprints carry vectors: the cosine rule needs the embedder, so the check is refused without it")
    exclude_groups = {ids.key_string(g) for g in exclude_groups}
    flat = [(c["id"], t) for c in candidates for t in c["texts"]]
    cos = _cosine_hits(data, [t for _c, t in flat], embed) if data.get("vectors") else {}
    best_by_candidate = {}
    for i, (cid, _t) in enumerate(flat):
        if i in cos and cos[i][0] > best_by_candidate.get(cid, (-2.0, []))[0]:
            best_by_candidate[cid] = cos[i]
    reasons, parts_hit = {}, {}
    for c in candidates:
        why = set()
        texts = list(c["texts"]) + [" ".join(c["texts"])]
        hit_exact = {p for t in texts for p in data["exact"].get(exact_hash(t), ())}
        if hit_exact:
            why.add("exact")
        shared = set().union(*(runs(t) for t in c["texts"])) & data["runs"].keys()
        if len(shared) >= RUNS_MIN:
            why.add("runs")
        hit_runs = {p for r in shared for p in data["runs"][r]}
        dot, cos_parts = best_by_candidate.get(c["id"], (None, []))
        if dot is not None and dot >= cosine:
            why.add("cosine")
        if {c["group"], c["id"], c.get("table")} & exclude_groups:
            why.add("source")
        if why:
            reasons[c["id"]] = sorted(why)
            for p in hit_exact | hit_runs | (set(cos_parts) if "cosine" in why else set()):
                parts_hit[p] = parts_hit.get(p, 0) + 1
    groups = {}
    for c in candidates:
        groups.setdefault(c["group"], []).append(c["id"])
    excluded_groups = sorted(g for g, members in groups.items() if any(m in reasons for m in members))
    bins = [0] * 11   # the best dot product per candidate, in tenths, for the record (no text)
    for dot, _p in best_by_candidate.values():
        bins[max(0, min(10, int(dot * 10)))] += 1
    return {"format": FORMAT, "thresholds": THRESHOLDS, "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "provenance": dict(provenance or {}), "cosine_threshold": cosine, "fingerprint_parts": data.get("parts"),
            "fingerprint_files": data["files"], "fingerprint_records": data["records"],
            "fingerprint_skipped": {n: len(v) for n, v in (data.get("skipped") or {}).items()},
            "cosine_rule": "applied" if data.get("vectors") else "no vectors in the fingerprints: not applied",
            "candidates": len(candidates), "groups": len(groups),
            "short_texts": sum(1 for _c, t in flat if len(overlap.words(t)) < MIN_WORDS),
            "excluded_candidates": len(reasons), "excluded_groups": len(excluded_groups),
            "kept_groups": len(groups) - len(excluded_groups),
            "candidates_by_rule": {r: sum(1 for w in reasons.values() if r in w) for r in RULES},
            "candidates_by_part": dict(sorted(parts_hit.items())),
            "best_cosine_tenths": bins if data.get("vectors") else None,
            "excluded_ids": {cid: w for cid, w in sorted(reasons.items())},
            "excluded_group_keys": excluded_groups,
            "kept_group_keys": sorted(set(groups) - set(excluded_groups))}


def read_candidates(path) -> list:
    """Another set's candidates, written by its own builder: [{id, group, texts[, table]}]."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    ok = isinstance(value, list) and all(
        isinstance(c, dict) and set(c) <= {"id", "group", "texts", "table"} and {"id", "group", "texts"} <= set(c)
        and isinstance(c["texts"], list) and c["texts"] and all(isinstance(t, str) for t in c["texts"]) for c in value)
    if not ok:
        raise ValueError("--candidates is a JSON list of {id, group, texts[, table]}, texts a non-empty list of strings")
    out = [dict(c, id=ids.key_string(c["id"]), group=ids.key_string(c["group"])) for c in value]
    if len({c["id"] for c in out}) != len(out):
        raise ValueError("a candidate id appears twice")
    return out


# ---- step 2: the cosine figure checked on development material only -------------------------

def _percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    k = (len(values) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def cosine_step(documents, groups, prompts, embed) -> dict:
    """`documents` {id: text}, `groups` {id: group key}, `prompts` [(document id, prompt text)]. The
    threshold by the rule fixed above: the lowest of COSINE and the two 5th percentiles, rounded down
    to .01, never raised. Figures only, no text."""
    import math
    ids_ = sorted(documents)
    rows = _embed_all(embed, [embed_form(documents[d]) for d in ids_])
    at = {d: i for i, d in enumerate(ids_)}
    members = {}
    for d in ids_:
        members.setdefault(groups[d], []).append(d)
    within = [float(rows[at[a]] @ rows[at[b]]) for m in members.values() for i, a in enumerate(m) for b in m[i + 1:]]
    rng = random.Random(STEP2_SEED)
    across = []
    if len(members) > 1:
        for _ in range(STEP2_ACROSS_PAIRS):
            a, b = rng.sample(ids_, 2)
            if groups[a] != groups[b]:
                across.append(float(rows[at[a]] @ rows[at[b]]))
    kept = [(d, p) for d, p in prompts if d in at]
    prompt_rows = _embed_all(embed, [embed_form(p) for _d, p in kept]) if kept else None
    doc_prompt = [float(rows[at[d]] @ prompt_rows[i]) for i, (d, _p) in enumerate(kept)]
    p_within, p_prompt = _percentile(within, STEP2_PERCENTILE), _percentile(doc_prompt, STEP2_PERCENTILE)
    low = min([COSINE] + [v for v in (p_within, p_prompt) if v is not None])
    threshold = math.floor(low * 100 + 1e-9) / 100
    p_across = _percentile(across, STEP2_ACROSS_PERCENTILE)
    return {"within_group_pairs": len(within), "across_group_pairs": len(across), "document_prompt_pairs": len(doc_prompt),
            "within_p5": p_within, "document_prompt_p5": p_prompt, "across_p99_9": p_across,
            "threshold_given": COSINE, "threshold_by_rule": threshold, "lowered": threshold < COSINE,
            "separates": p_across is None or p_across < threshold,
            "rule": "the lowest of %.2f, the within-group and the document-against-prompt 5th percentiles, rounded down to .01; never raised" % COSINE}


def shipped_embedder():
    """The repository's own embedding model (BAAI/bge-m3, embedding_store's loader); float32 rows."""
    scripts = HERE.parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import embedding_store as es
    st = es._try_import_st()
    if st is None:
        raise RuntimeError("sentence-transformers is not importable: the cosine rule cannot run")
    _name, model = es._resolve_model(st, es.DEFAULT_MODEL_NAME)

    def embed(texts):
        return model.encode(list(texts), normalize_embeddings=True, batch_size=16, convert_to_numpy=True).astype("float32")
    return embed


def _ids_file(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("group_keys") or value.get("ids") or []
    if not isinstance(value, list):
        raise ValueError("--exclude-groups is a list of ids, or an object with `group_keys` or `ids`")
    return value


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fingerprint")
    f.add_argument("--part", action="append", required=True, help="name=path, or name=path#key,key")
    f.add_argument("--out", required=True)
    f.add_argument("--embed", action="store_true")
    f.add_argument("--count", action="store_true", help="count records only, store nothing (the forecast)")
    c = sub.add_parser("check")
    c.add_argument("--fingerprints", required=True)
    c.add_argument("--benchmark", choices=("contradoc", "scitab"))
    c.add_argument("--input")
    c.add_argument("--candidates", help="any other item set: a JSON list of {id, group, texts[, table]}")
    c.add_argument("--assignment")
    c.add_argument("--side", choices=(ids.DEVELOPMENT, ids.HOLDOUT))
    c.add_argument("--exclude-groups", required=True)
    c.add_argument("--cosine-step", required=True, help="step 2's record: the cosine threshold is read from it")
    c.add_argument("--embed", action="store_true")
    c.add_argument("--out", required=True)
    s = sub.add_parser("cosine-step")
    s.add_argument("--dev", required=True)
    s.add_argument("--assignment", required=True)
    s.add_argument("--prompts", required=True)
    s.add_argument("--items", required=True)
    s.add_argument("--embed", action="store_true")
    s.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        guard_args(args)
        if args.command == "fingerprint":
            parts = []
            for p in args.part:
                name, sep, path = p.partition("=")
                if not sep:
                    raise ValueError("--part is name=path: " + p)
                path, _hash, keys = path.partition("#")
                parts.append((name, path, [k for k in keys.split(",") if k] or None))
            if args.count:
                value = count(parts)
                Path(args.out).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
                print(json.dumps(value, indent=2))
                return 0
            data = fingerprint(parts, shipped_embedder() if args.embed else None)
            write(data, args.out)
            print(json.dumps({"records": data["records"], "short_records": data["short_records"], "runs": len(data["runs"]),
                              "exact": len(data["exact"]), "skipped": {n: len(v) for n, v in data["skipped"].items()},
                              "vectors": bool(data["vectors"])}, indent=2))
            return 0
        if args.command == "cosine-step":
            from contradoc import adapter as cd
            records_ = cd.read_source(args.dev)
            documents = {ids.key_string(r[cd.DOCUMENT_ID_FIELD]): r[cd.TEXT_FIELD] for r in records_}
            assigned = cd.read_assignment(args.assignment)
            groups = {d: ids.key_string(assigned[d][0]) for d in documents if d in assigned}
            documents = {d: t for d, t in documents.items() if d in groups}
            source = {r["document_id"]: ids.key_string(r["source_document_id"])
                      for r in json.loads(Path(args.items).read_text(encoding="utf-8"))["items"]}
            prompts = [(source.get(p.get("document_id")), p["user"])
                       for p in json.loads(Path(args.prompts).read_text(encoding="utf-8"))["prompts"] if p.get("user")]
            result = cosine_step(documents, groups, prompts, shipped_embedder() if args.embed else None)
            result["inputs"] = {Path(p).name: _sha(p) for p in (args.dev, args.assignment, args.prompts, args.items)}
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print(json.dumps(result, indent=2))
            return 0
        data = read(args.fingerprints)
        step = json.loads(Path(args.cosine_step).read_text(encoding="utf-8"))
        threshold = step.get("threshold_by_rule")
        if not isinstance(threshold, (int, float)):
            raise ValueError("step 2's record gives no threshold: %r" % (threshold,))
        if bool(args.candidates) == bool(args.benchmark) or bool(args.benchmark) != bool(args.input):
            raise ValueError("give --benchmark with --input, or --candidates, not both")
        if args.candidates:
            cands = read_candidates(args.candidates)
        elif args.benchmark == "contradoc":
            from contradoc import adapter as cd
            cands = candidates_contradoc(cd.read_source(args.input), args.assignment, args.side)
        else:
            from scitab import adapter as st
            cands = candidates_scitab(st.read_source(args.input), args.side)
        provenance = {"fingerprints_sha256": _sha(args.fingerprints), "input_sha256": _sha(args.input or args.candidates),
                      "assignment_sha256": _sha(args.assignment), "exclude_ids_sha256": _sha(args.exclude_groups),
                      "cosine_step_sha256": _sha(args.cosine_step),
                      "side": args.side, "benchmark": args.benchmark}
        result = check(data, cands, shipped_embedder() if args.embed else None, _ids_file(args.exclude_groups), provenance,
                       cosine=threshold)
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("candidates", "groups", "excluded_candidates", "excluded_groups",
                                                 "kept_groups", "candidates_by_rule", "cosine_rule", "short_texts")}, indent=2))
        return 0
    except (ValueError, RuntimeError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
