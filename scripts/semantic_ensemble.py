"""The five-voter semantic ensemble (WORDS-A).

Where a decision rests on WHAT WORDS MEAN, it is decided here, by five
independent voters against operator-visible reference text, never by a literal
keyword table in code and never by one method alone.

WHY, measured rather than asserted. A keyword table is one person's vocabulary
frozen into code, and it has now failed three times in this repository in the
same shape: silently, in one direction, on the sentences nobody thought to write
down.

  - `severity`: 6 of 44 shipped rules matched NO pattern at all and fell to a
    trailing default, silently, always toward advisory.
  - `action`: a rule about reviewer restraint classified as `redact`.
  - redaction intent: the PASSIVE prohibition compiled and the ACTIVE one did
    not, so "the reviewer must not publish the client's address" was silently
    ignored, which under LAW-IV is the worse direction.

A single similarity method has the same weakness with a number attached. Five
methods disagreeing is information; one method agreeing with itself is not.

REGEX KEEPS EVERYTHING STRUCTURAL. Declared syntax, bracket declarations, ids,
delimiters, formats, run-id shapes: that is READING, not interpreting, and none
of it belongs here.

THE FIVE VOTERS, and what each contributes that the others do not:

  sbert        dense sentence embedding, cosine against each reference. Reads
               meaning; blind to exact wording.
  keybert      keyphrase extraction against the same model, then matching on the
               extracted phrases rather than the whole sentence. Reads what the
               sentence is ABOUT; resists a long sentence diluting its own point.
  tfidf        term weighting over the reference set. Reads distinctive
               vocabulary; blind to meaning but immune to a model's bad day.
  bow          bag of words overlap. Crude, lexical, and the one voter that
               cannot be fooled by an embedding space at all.
  word_overlap word by word agreement on the discriminating tokens. The most
               literal of the five, kept deliberately: when a rule quotes an
               operator's own phrasing this is the voter that sees it.

FIVE CONSTRAINTS, all load bearing and all enforced here rather than by
convention:

  1. EVERY DECISION RECORDS ALL FIVE VOTES, with score and matched reference,
     not only the outcome. A vote nobody can read is a keyword table with extra
     steps.
  2. REFERENCE TEXT LIVES IN CONFIG (config/semantic_references.json), beside
     the band tables and the domain vocabulary.
  3. EACH THRESHOLD IS JUSTIFIED BY MEASUREMENT, with the margin between the
     closest true case and the closest false one recorded beside it.
  4. NO VOTER IS DROPPED SILENTLY. Fewer than five and the decision REFUSES and
     names the missing ones. Three of three is a different rule from three of
     five and the difference must not be invisible in the output.
  5. ONE INTERFACE FOR ALL FIVE, so a voter can be replaced or measured alone.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pairing_map

ROOT = Path(__file__).resolve().parent.parent
REFERENCES_PATH = ROOT / "config" / "semantic_references.json"

# Three of five or above. Not a tunable: it is the operator's rule.
MAJORITY = 3
VOTER_NAMES = ("sbert", "keybert", "tfidf", "bow", "word_overlap")

# Thresholds. Every one is justified by measurement in
# docs/fix/ENSEMBLE_THRESHOLDS.md, with the margin between the closest true case
# and the closest false one stated. These are NOT round numbers and must not be
# rounded: each sits at the midpoint of a measured gap.
THRESHOLDS = {}
THRESHOLDS_PATH = ROOT / "config" / "semantic_thresholds.json"


class EnsembleRefusal(Exception):
    """Fewer than five voters could run, so no decision was made.

    Deliberately an exception rather than a False: a caller that treats a
    refusal as a no has silently changed a five-voter rule into a three-voter
    one, which is constraint 4. The message names what is missing."""


def load_references(path=None):
    p = Path(path or REFERENCES_PATH)
    if not p.is_file():
        raise EnsembleRefusal(
            "the semantic reference set is missing (%s). Every decision that "
            "rests on what words mean is decided against operator-visible "
            "references, so without them there is nothing to decide against and "
            "the ensemble refuses rather than falling back to a keyword table."
            % p)
    return json.loads(p.read_text(encoding="utf-8"))


def load_thresholds(path=None):
    p = Path(path or THRESHOLDS_PATH)
    if not p.is_file():
        raise EnsembleRefusal(
            "the measured thresholds are missing (%s). A threshold that is not "
            "measured is a round number, and a round number is not a "
            "justification." % p)
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# One interface for all five voters (constraint 5).
#
# A voter is a callable: (candidate, positives, negatives, threshold) ->
#   {"voter", "available", "vote", "score", "matched", "detail"}
# `available` False means this voter could not run; it never votes in that case
# and the ensemble refuses rather than proceeding with four.
# --------------------------------------------------------------------------

def _result(name, *, available, vote=None, score=None, matched=None, detail=""):
    return {"voter": name, "available": bool(available), "vote": vote,
            "score": None if score is None else round(float(score), 4),
            "matched": matched, "detail": detail}


def _tokens(text):
    """The project's ONE tokeniser. Not a second normaliser: CLAUDE.md's
    two-tokenisers rule applies here as everywhere else."""
    out = []
    for word in re.split(r"[\W_]+", str(text or "").lower()):
        if word:
            out.extend(pairing_map._norm_label(word))
    return out


# ---- voter 1: SBERT ------------------------------------------------------

_MODEL_CACHE = {}


def _sbert_model():
    """The model this project ALREADY SHIPS (BAAI/bge-m3, embedding_store's own),
    loaded through embedding_store's own resolve path so there is one loader and
    one cache. No second model is added for the ensemble."""
    if "m" in _MODEL_CACHE:
        return _MODEL_CACHE["m"]
    try:
        import embedding_store as es
        st = es._try_import_st()
        if st is None:
            _MODEL_CACHE["m"] = None
            return None
        _name, model = es._resolve_model(st, es.DEFAULT_MODEL_NAME)
        _MODEL_CACHE["m"] = model
        return model
    except Exception:
        _MODEL_CACHE["m"] = None
        return None


def _encode(model, texts):
    return model.encode(list(texts), normalize_embeddings=True)


def vote_sbert(candidate, positives, negatives, threshold):
    """Dense sentence similarity: the best positive beats the best negative by
    the threshold margin. Comparing against negatives too, rather than a bare
    positive score, is what stops a sentence that is merely IN THE DOMAIN from
    scoring as a match."""
    model = _sbert_model()
    if model is None:
        return _result("sbert", available=False,
                       detail="the embedding model could not be loaded")
    try:
        vecs = _encode(model, [candidate] + list(positives) + list(negatives))
    except Exception as exc:
        return _result("sbert", available=False,
                       detail="encode failed: %s" % type(exc).__name__)
    c, rest = vecs[0], vecs[1:]
    npos = len(positives)
    pos = [float(c @ rest[i]) for i in range(npos)]
    neg = [float(c @ rest[npos + i]) for i in range(len(negatives))]
    best_pos = max(pos) if pos else 0.0
    best_neg = max(neg) if neg else 0.0
    idx = pos.index(best_pos) if pos else -1
    return _result("sbert", available=True,
                   vote=(best_pos - best_neg) >= threshold,
                   score=best_pos - best_neg,
                   matched=(positives[idx] if idx >= 0 else None),
                   detail="best positive %.3f, best negative %.3f" % (best_pos, best_neg))


# ---- voter 2: KeyBERT ----------------------------------------------------

def vote_keybert(candidate, positives, negatives, threshold):
    """Keyphrase similarity: extract the phrases the candidate is ABOUT, then
    score those against the references rather than the whole sentence.

    KeyBERT's algorithm over the model this project already ships: candidate
    n-grams are embedded and ranked by cosine against the document embedding,
    the top phrases are kept, and those are matched against the references. The
    keybert package is a thin wrapper over exactly this plus scikit-learn's
    vectoriser, both already present, so the algorithm is implemented here
    rather than adding a dependency.

    What it contributes that sbert does not: a long rule whose point is one
    clause is diluted as a whole sentence and is not diluted as a keyphrase."""
    model = _sbert_model()
    if model is None:
        return _result("keybert", available=False,
                       detail="the embedding model could not be loaded")
    try:
        from sklearn.feature_extraction.text import CountVectorizer
    except Exception:
        return _result("keybert", available=False,
                       detail="scikit-learn's vectoriser is unavailable")
    try:
        vec = CountVectorizer(ngram_range=(1, 2), stop_words="english")
        grams = vec.fit([candidate]).get_feature_names_out()
        if len(grams) == 0:
            return _result("keybert", available=True, vote=False, score=0.0,
                           detail="the candidate yielded no keyphrases")
        embs = _encode(model, [candidate] + list(grams))
        doc, gram_vecs = embs[0], embs[1:]
        ranked = sorted(((float(doc @ gram_vecs[i]), grams[i])
                         for i in range(len(grams))), reverse=True)
        top = [g for _s, g in ranked[:5]]
        phrase = " ".join(top)
        pv = _encode(model, [phrase] + list(positives) + list(negatives))
        c, rest = pv[0], pv[1:]
        npos = len(positives)
        pos = [float(c @ rest[i]) for i in range(npos)]
        neg = [float(c @ rest[npos + i]) for i in range(len(negatives))]
        best_pos = max(pos) if pos else 0.0
        best_neg = max(neg) if neg else 0.0
        idx = pos.index(best_pos) if pos else -1
        return _result("keybert", available=True,
                       vote=(best_pos - best_neg) >= threshold,
                       score=best_pos - best_neg,
                       matched=(positives[idx] if idx >= 0 else None),
                       detail="keyphrases %r; best positive %.3f, best negative %.3f"
                              % (top, best_pos, best_neg))
    except Exception as exc:
        return _result("keybert", available=False,
                       detail="keyphrase extraction failed: %s" % type(exc).__name__)


# ---- voter 3: TF-IDF -----------------------------------------------------

def vote_tfidf(candidate, positives, negatives, threshold):
    """Term weighting over the reference set: distinctive vocabulary, not
    meaning. Blind to paraphrase and immune to an embedding model's bad day,
    which is precisely why it is in the ensemble."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except Exception:
        return _result("tfidf", available=False,
                       detail="scikit-learn is unavailable")
    try:
        corpus = list(positives) + list(negatives)
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        M = vec.fit_transform(corpus + [candidate])
        cand = M[-1]
        sims = (M[:-1] @ cand.T).toarray().ravel()
        npos = len(positives)
        pos = sims[:npos]
        neg = sims[npos:]
        best_pos = float(pos.max()) if len(pos) else 0.0
        best_neg = float(neg.max()) if len(neg) else 0.0
        idx = int(pos.argmax()) if len(pos) else -1
        return _result("tfidf", available=True,
                       vote=(best_pos - best_neg) >= threshold,
                       score=best_pos - best_neg,
                       matched=(positives[idx] if idx >= 0 else None),
                       detail="best positive %.3f, best negative %.3f" % (best_pos, best_neg))
    except Exception as exc:
        return _result("tfidf", available=False,
                       detail="tfidf failed: %s" % type(exc).__name__)


# ---- voter 4: bag of words ----------------------------------------------

def vote_bow(candidate, positives, negatives, threshold):
    """Bag of words overlap, Jaccard over the project's own tokens. The crudest
    voter and the only one an embedding space cannot mislead at all."""
    c = set(_tokens(candidate))
    if not c:
        return _result("bow", available=True, vote=False, score=0.0,
                       detail="the candidate has no tokens")

    def best(refs):
        out, which = 0.0, None
        for r in refs:
            t = set(_tokens(r))
            if not t:
                continue
            j = len(c & t) / float(len(c | t))
            if j > out:
                out, which = j, r
        return out, which

    bp, matched = best(positives)
    bn, _ = best(negatives)
    return _result("bow", available=True, vote=(bp - bn) >= threshold,
                   score=bp - bn, matched=matched,
                   detail="best positive %.3f, best negative %.3f" % (bp, bn))


# ---- voter 5: word by word agreement -------------------------------------

def vote_word_overlap(candidate, positives, negatives, threshold):
    """Word by word agreement on the DISCRIMINATING tokens: those that appear on
    one side of the reference set and not the other.

    The most literal of the five, kept deliberately. When a rule quotes the
    operator's own phrasing this is the voter that sees it, and it is the one
    that degrades most gracefully when the references are few."""
    pos_tok, neg_tok = set(), set()
    for r in positives:
        pos_tok |= set(_tokens(r))
    for r in negatives:
        neg_tok |= set(_tokens(r))
    only_pos = pos_tok - neg_tok
    only_neg = neg_tok - pos_tok
    c = set(_tokens(candidate))
    if not c:
        return _result("word_overlap", available=True, vote=False, score=0.0,
                       detail="the candidate has no tokens")
    hit_p = len(c & only_pos)
    hit_n = len(c & only_neg)
    denom = float(hit_p + hit_n) or 1.0
    score = (hit_p - hit_n) / denom
    matched = None
    if hit_p:
        best = 0
        for r in positives:
            n = len(c & (set(_tokens(r)) & only_pos))
            if n > best:
                best, matched = n, r
    return _result("word_overlap", available=True, vote=score >= threshold,
                   score=score, matched=matched,
                   detail="%d discriminating positive token(s), %d negative"
                          % (hit_p, hit_n))


VOTERS = {
    "sbert": vote_sbert,
    "keybert": vote_keybert,
    "tfidf": vote_tfidf,
    "bow": vote_bow,
    "word_overlap": vote_word_overlap,
}


def decide(candidate, decision, *, references=None, thresholds=None):
    """The ensemble decision. Returns a record carrying ALL FIVE VOTES.

    Raises EnsembleRefusal when fewer than five voters can run (constraint 4):
    a caller that silently proceeded with four would have changed the rule
    without the output showing it."""
    refs = (references or load_references())
    block = refs.get(decision)
    if not block:
        raise EnsembleRefusal(
            "no reference set for decision %r in %s; the ensemble decides against "
            "operator-visible references and refuses without them"
            % (decision, REFERENCES_PATH))
    thr = (thresholds or load_thresholds()).get(decision)
    if not thr:
        raise EnsembleRefusal(
            "no measured thresholds for decision %r; a threshold that is not "
            "measured is a round number" % decision)
    positives = list(block.get("positive") or [])
    negatives = list(block.get("negative") or [])

    votes = []
    for name in VOTER_NAMES:
        t = thr.get(name)
        if t is None:
            votes.append(_result(name, available=False,
                                 detail="no measured threshold for this voter"))
            continue
        votes.append(VOTERS[name](candidate, positives, negatives, float(t)))

    missing = [v["voter"] for v in votes if not v["available"]]
    if missing:
        raise EnsembleRefusal(
            "only %d of %d voters could run (%s missing: %s). The decision is "
            "three of FIVE; proceeding on fewer would silently apply a different "
            "rule, so it refuses instead."
            % (len(VOTER_NAMES) - len(missing), len(VOTER_NAMES),
               ", ".join(missing),
               "; ".join("%s: %s" % (v["voter"], v["detail"])
                         for v in votes if not v["available"])))

    yes = sum(1 for v in votes if v["vote"])
    return {
        "decision": decision,
        "candidate": candidate,
        "result": yes >= MAJORITY,
        "yes": yes,
        "of": len(VOTER_NAMES),
        "majority": MAJORITY,
        "votes": votes,
    }
