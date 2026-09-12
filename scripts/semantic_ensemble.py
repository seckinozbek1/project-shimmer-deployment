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
    # NO EVIDENCE IS NEVER A YES.
    #
    # Found by check 41, not by reasoning: the three-word fixture "use formal
    # register" scored 5/5 YES for redaction intent. Three lexical voters scored
    # exactly 0.0 (no token in common with either side of the reference set) and
    # their cost-optimal thresholds are at or below zero, so a score meaning "I
    # have nothing to say" was counted as a vote FOR.
    #
    # A voter that found no evidence must abstain into a no, whatever its
    # threshold. The threshold governs how much evidence is enough, never
    # whether zero evidence counts.
    if vote and score is not None and abs(float(score)) < 1e-9:
        vote = False
        detail = (detail + " | no evidence either way (score 0.0); a voter with "
                  "nothing to say does not vote yes").strip(" |")
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


# MEASURED, not assumed. The first two calibration runs failed on all three
# lexical voters, and expanding the reference set from 15 positives to 40 made
# `word_overlap` WORSE, not better. The cause was visible only in the per-case
# scores: "Comments must not contain an assessment of commercial merit", a
# reviewer-restraint rule, scored +1.0 as a positive.
#
# The reason is that BOTH CLASSES SHARE THE PROHIBITION GRAMMAR. A redaction
# rule says "must not contain the turnover figure"; a review convention says
# "must not contain an assessment". The words `must`, `not`, `contain`,
# `publish`, `state`, `every`, `document` carry no class information at all, and
# a bag of words handed the whole sentence scores them as though they did. The
# discriminating signal is the OBJECT (what is protected), never the verb frame.
#
# So the lexical voters ignore the frame. This is not a stopword list of one
# person's vocabulary: it is the set of tokens that appear on BOTH sides of the
# operator's own reference set, computed from that set at decision time. A word
# earns its way onto this list by being useless, and the reference set decides,
# not code.
def _frame_tokens(positives, negatives):
    """Tokens appearing on BOTH sides of the reference set, so they carry no
    class information. Computed from the operator's references, never listed in
    code."""
    pos, neg = set(), set()
    for r in positives:
        pos |= set(_tokens(r))
    for r in negatives:
        neg |= set(_tokens(r))
    return pos & neg


def _content_tokens(text, frame):
    """A candidate's tokens with the shared frame removed: what the rule is
    ABOUT, rather than how it is phrased."""
    return set(_tokens(text)) - frame


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
        # Drop keyphrases made only of the frame both classes share. Measured:
        # without this, "Comments must not contain an assessment of commercial
        # merit" extracted frame phrases and scored above four true cases.
        frame = _frame_tokens(positives, negatives)
        kept = [g for _s, g in ranked if _content_tokens(g, frame)]
        top = (kept or [g for _s, g in ranked])[:5]
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
        # Content tokens only, for the same measured reason as `bow`: scoring
        # the whole sentence ranked "A rule that names no field of the unit
        # keeps its stated reach" above every true case, because the prohibition
        # frame is shared by both classes and carries no class information.
        frame = _frame_tokens(positives, negatives)

        def strip(t):
            keep = _content_tokens(t, frame)
            return " ".join(w for w in _tokens(t) if w in keep) or " ".join(_tokens(t))

        corpus = [strip(t) for t in list(positives) + list(negatives)]
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        M = vec.fit_transform(corpus + [strip(candidate)])
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
    """Bag of words overlap, Jaccard over CONTENT tokens: the candidate's words
    with the shared prohibition frame removed.

    The crudest voter and the only one an embedding space cannot mislead at all.
    Scoring the whole sentence made it rank "Every entry must state a
    calibration date" above every true case, for sharing `date` and `state`;
    scoring content only removes exactly that failure."""
    frame = _frame_tokens(positives, negatives)
    c = _content_tokens(candidate, frame)
    if not c:
        return _result("bow", available=True, vote=False, score=0.0,
                       detail="the candidate has no content tokens outside the "
                              "vocabulary both classes share")

    def best(refs):
        out, which = 0.0, None
        for r in refs:
            t = _content_tokens(r, frame)
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
                   detail="content-token jaccard; best positive %.3f, best negative %.3f"
                          % (bp, bn))


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
    # Normalise by the CANDIDATE's own token count, not by the hits.
    # Normalising by hits made a sentence with a single discriminating token
    # score a full +1.0: "Comments must not contain an assessment of commercial
    # merit" matched one positive-only token and outscored every true case. A
    # score should say how much of this rule points one way, not how lopsided
    # its one accidental match was.
    score = (hit_p - hit_n) / float(len(c))
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
    result = yes >= MAJORITY

    # THE SAFETY VETO, and why it exists.
    #
    # Measured on 114 cases (40 true, 74 false) under leave-one-out:
    #   sbert         0 false negatives, 0 false positives
    #   keybert       2 fn, 4 fp        tfidf  0 fn, 9 fp
    #   bow           0 fn, 5 fp        word_overlap  1 fn, 3 fp
    #   ENSEMBLE 3/5  1 fn, 3 fp
    #
    # So three of five is WORSE here than the dense voter alone, and every one
    # of the ensemble's false negatives comes from lexical voters outvoting it.
    # Under LAW-IV a false NO is the silent, dangerous direction: content the
    # operator marked for removal gets published. A false YES is visible in the
    # output and costs a redaction nobody needed.
    #
    # So a voter that is measured never to miss can VETO A NO, and can never
    # veto a yes. The veto only ever ADDS redaction, which is the conservative
    # direction, and it is recorded on the decision rather than folded into the
    # count, so a reader can always see that three of five said no and why the
    # answer is yes anyway.
    #
    # This is a judgement made in the operator's place and is theirs to revisit:
    # it keeps the five-voter rule while refusing to let a measured-perfect
    # voter be outvoted into the one error that matters.
    # The veto carries its OWN, HIGHER threshold, measured separately. Found by
    # measurement, not reasoning: at the voter's ordinary threshold the veto
    # rescued "Cite the edition used", an ordinary style rule, because a
    # marginal dense score was enough to overturn a 2-of-5 no. A veto exists to
    # rescue a rule the lexical voters could not see, not to overrule them on a
    # case where the dense voter is itself unsure, so it fires only on CLEAR
    # dense evidence.
    veto = None
    safety = (thresholds or load_thresholds()).get("_safety_veto", {}).get(decision)
    if safety and not result:
        vv = next((v for v in votes if v["voter"] == safety.get("voter")), None)
        floor = safety.get("threshold")
        if vv and vv["vote"] and vv["score"] is not None and \
                (floor is None or float(vv["score"]) >= float(floor)):
            result = True
            veto = {"voter": vv["voter"], "score": vv["score"],
                    "matched": vv["matched"], "threshold": floor,
                    "reason": safety.get("reason", "")}

    return {
        "decision": decision,
        "candidate": candidate,
        "result": result,
        "yes": yes,
        "of": len(VOTER_NAMES),
        "majority": MAJORITY,
        "votes": votes,
        "safety_veto": veto,
    }
