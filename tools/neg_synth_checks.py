"""Checks 455 to 459 (standing order 102, D-707): the synthetic negotiation item pipeline, proven on fixtures.

- 455 the sampler is seeded and deterministic: one seed gives one card, key and brief, byte for byte, whatever the
  process's global random state; another seed gives another;
- 456 the brief never holds a key field: it is the same for any two hidden draws of one structure (persona,
  fates, stances, red lines, firm variants, trades), holds no seed, digest, POS or proposal id or label word, and
  shares no 8-word run with Shimmer's own advisor prompts; role V's labelling sheet holds no stance, target
  article or wording, red-line mark or round k+1;
- 457 the validator accepts a well-formed reply and rejects a mismatch, both by form (a bracket, a missing slot,
  a revision outside its share band, two wordings of one article overlapping) and by key (an assembled build
  whose scorer key differs from the card's declared key), and role V's labels drop an item they do not match;
- 458 provenance is written: one row per item with every declared field, its digests equal to the files'
  own, refused for a missing field, a second row of the same item, a dated snapshot id or a family the system
  under test uses;
- 459 the screens and the plan: the cue-only check flags a planted surface cue and not its absence; the
  deduplication counts the exact, 8-word-run, 5-gram Jaccard and cosine rules and keeps one of a near-duplicate
  pair; the split plan refuses a final-test purpose and overlapping ranges; the final test's guard refuses a
  synthetic file.

Each is neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no network, no real item: every
reply is invented here by Python from the brief's slots, every file goes to a temporary folder outside the
repository, and the embedder is a fixed hashing stand-in.
"""
import contextlib
import copy
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
import neg_synth_cue as cue  # noqa: E402
import neg_synth_dedup as dd  # noqa: E402
import neg_synth_label as nsl  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

CFG = ns.load_config()
GEN = ns.load_generator(CFG)
SEEDS = (424242, 424243, 424250)
LABEL_WORDS = ("fate", "fates", "persona", "stance", "stances", "no_conflict", "not_stated", "red_line",
               "red_lines", "not_advanced", "approach_targets", "configuration", "rubric", "movable", "settled",
               "kept", "removed", "declared_key", "hidden")
_CONS, _VOW = "bcdfghjklmnprstvz", "aeiou"


def _words(rng, n):
    return ["".join(rng.choice(_CONS) + rng.choice(_VOW) for _ in range(3)) for _ in range(n)]


def fixture_reply(card, salt="x"):
    """A well-formed reply written by Python from the brief's slots alone, with invented words."""
    view = ns.brief_view(card)
    rng = random.Random("fixture:%s:%s" % (salt, card["item_id"]))
    sent = lambda n: " ".join(_words(rng, n)) + "."
    reply = {"titles": {a: " ".join(_words(rng, 3)) for a in view["titles"]}, "articles": {}, "statements": {}}
    for a in view["articles"]:
        if a["agreed"]:
            reply["articles"][a["id"]] = {"agreed_text": sent(20) + "\n\n" + sent(15)}
            continue
        body = {"chapeau": sent(12), "wordings": {}}
        for x in a["slots"]:
            w = _words(rng, 20)
            r = w[:12] + _words(rng, 8)
            body["wordings"][x] = {"wording": " ".join(w) + ".", "revision": " ".join(r) + "."}
        reply["articles"][a["id"]] = body
    for x in view["statements"]:
        reply["statements"][x["slot"]] = {v: sent(12) for v in sorted(set(CFG["generation"]["variants"].values()))}
    return reply


def fake_embed(texts):
    """A fixed hashing embedder: one bucket per word, so equal word bags give a cosine of 1."""
    out = []
    for t in texts:
        v = [0.0] * 64
        for w in str(t).lower().split():
            v[int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16) % 64] += 1.0
        out.append(v)
    return out


def _strings(value):
    if isinstance(value, str):
        if len(value.split()) >= 8:
            yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _card(seed=SEEDS[0]):
    return ns.sample_card(seed, CFG, version="fixture")


class NegSynthChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        NegSynthChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))


class Determinism(NegSynthChecks):
    def test_455_seeded_determinism(self):
        def observe():
            a = ns.sample_card(SEEDS[0], CFG, version="fixture")
            random.seed(99)
            random.random()
            b = ns.sample_card(SEEDS[0], CFG, version="fixture")
            c = ns.sample_card(SEEDS[1], CFG, version="fixture")
            return {"same_card": ns._sha(a) == ns._sha(b), "same_brief": ns.brief_of(a, CFG, GEN) == ns.brief_of(b, CFG, GEN),
                    "other_seed_differs": ns._sha(a) != ns._sha(c)}

        expected = {"same_card": True, "same_brief": True, "other_seed_differs": True}
        unseeded = lambda seed, stream: random.Random()
        self.prove("one_seed_one_card_key_and_brief", observe, expected, lambda: patch.object(ns, "_rng", unseeded))

    def test_455_set_ranges_never_overlap(self):
        base = 10 ** 12

        def observe():
            sets = ns.check_split(CFG)
            seeds = [s for st in sets for s in ns.seeds_for(CFG, st["name"], base)]
            return {"ranges_disjoint": len(set(seeds)) == sum(st["drawn"] for st in sets),
                    "ids_distinct": len({ns.item_id_of(s) for s in seeds}) == len(seeds)}

        expected = {"ranges_disjoint": True, "ids_distinct": True}
        self.prove("set_ranges_never_overlap", observe, expected,
                   lambda: patch.object(ns, "seeds_for", lambda cfg, name, base: list(range(base, base + 3))))


class BriefHoldsNoKey(NegSynthChecks):
    def _variants(self, card):
        """The same structure under other hidden draws, and under a hand-flipped hidden part."""
        out = []
        for attempt in (1, 2, 3):
            h = ns.draw_hidden(card["seed"], card["structure"], CFG, attempt + 50)
            out.append(dict(card, hidden=h, declared_key=ns.declared_key(card["structure"], h)))
        flipped = copy.deepcopy(card)
        flipped["hidden"]["fates"] = {x: ("open" if f != "open" else "kept") for x, f in card["hidden"]["fates"].items()}
        flipped["hidden"]["stances"] = {x: ("oppose" if s != "oppose" else "support")
                                        for x, s in card["hidden"]["stances"].items()}
        flipped["hidden"]["persona"] = [p["id"] for p in card["structure"]["parties"]
                                        if p["id"] not in card["structure"]["missing_parties"]][-1]
        out.append(flipped)
        return out

    def test_456_brief_invariant_to_every_hidden_field(self):
        cards = [_card(s) for s in SEEDS]

        def observe():
            same = all(ns.brief_of(v, CFG, GEN) == ns.brief_of(c, CFG, GEN) for c in cards for v in self._variants(c))
            words = set()
            leaks = 0
            for c in cards:
                text = ns.brief_of(c, CFG, GEN)
                low = text.lower()
                words |= {w for w in LABEL_WORDS if (" %s " % w) in (" " + low.replace(",", " ").replace(".", " ")
                                                                     .replace(";", " ").replace("(", " ")
                                                                     .replace(")", " ") + " ")}
                leaks += sum(1 for s in (str(c["seed"]), c["sampler_sha256"], "POS-", "P-A") if s in text)
            return {"invariant": same, "label_words": sorted(words), "leaks": leaks}

        expected = {"invariant": True, "label_words": [], "leaks": 0}
        real_view = ns.brief_view

        def leaky_view(card):
            v = real_view(card)
            for a in v["articles"]:
                a["slots"] = ["%s (%s)" % (x, card["hidden"]["fates"][x]) for x in a["slots"]]
            return v

        self.prove("brief_same_for_any_hidden_draw_and_holds_no_key", observe, expected,
                   lambda: patch.object(ns, "brief_view", leaky_view))

    def test_456_label_sheet_holds_no_answer(self):
        builds = [ns.assemble(c, fixture_reply(c), CFG) for c in (_card(s) for s in SEEDS)]

        def tampered(b):
            t = copy.deepcopy(b)
            t["red_lines"] = []
            t["next_articles"] = {}
            for p in t["positions"]:
                p["stance"] = "accept"
                p["article"], p["proposal"] = "A0", None
            return t

        def observe():
            sheets = [ns.label_sheet(b) for b in builds]
            text = json.dumps(sheets)
            return {"same_without_answers": all(ns.label_sheet(b) == ns.label_sheet(tampered(b)) for b in builds),
                    "answer_fields": sorted({f for s in sheets for p in s["positions"] for f in p
                                             if f in ("stance", "article", "proposal")}
                                            | ({"red_lines"} if '"red_lines"' in text else set())
                                            | ({"next_articles"} if '"next_articles"' in text else set()))}

        self.prove("label_sheet_holds_no_stance_target_or_red_line_mark", observe,
                   {"same_without_answers": True, "answer_fields": []},
                   lambda: patch.object(ns, "SHEET_POSITION_FIELDS", ns.SHEET_POSITION_FIELDS + ("stance",)))

    def test_456_brief_shares_no_run_with_shimmer_prompts(self):
        prompts = json.loads((ROOT / "benchmark" / "baselines" / "neg_advisor_prompt.json").read_text(encoding="utf-8"))
        texts = list(_strings(prompts))
        shimmer_runs = set()
        for t in texts:
            shimmer_runs |= dd.gl.runs(t)
        cards = [_card(s) for s in SEEDS]
        state = {"template": GEN["template"]}

        def observe():
            gen = dict(GEN, template=state["template"])
            return {"prompt_strings": len(texts) > 0,
                    "shared_runs": sum(len(dd.gl.runs(ns.render_prompt(ns.brief_view(c), gen, CFG)) & shimmer_runs)
                                       for c in cards)}

        @contextlib.contextmanager
        def plant():
            longest = max(texts, key=lambda t: len(t.split()))
            state["template"] = GEN["template"] + "\n" + longest
            try:
                yield
            finally:
                state["template"] = GEN["template"]

        self.prove("brief_shares_no_8_word_run_with_shimmer_prompts", observe, {"prompt_strings": True, "shared_runs": 0},
                   plant)


class Validator(NegSynthChecks):
    def _cases(self):
        card = _card()
        good = fixture_reply(card)
        open_art = next(a for a in card["structure"]["articles"] if not a["agreed"])
        slot = "%s.1" % open_art["id"]
        stmt = card["structure"]["slots"][0]["slot"]
        bad = {}
        r = copy.deepcopy(good)
        r["statements"][stmt]["against"] = "[" + r["statements"][stmt]["against"] + "]"
        bad["bracket"] = r
        r = copy.deepcopy(good)
        del r["statements"][stmt]
        bad["missing_slot"] = r
        r = copy.deepcopy(good)
        r["articles"][open_art["id"]]["wordings"][slot]["revision"] = r["articles"][open_art["id"]]["wordings"][slot]["wording"]
        bad["revision_share"] = r
        r = copy.deepcopy(good)
        ch = r["articles"][open_art["id"]]["chapeau"]
        r["articles"][open_art["id"]]["wordings"][slot]["wording"] = ch.rstrip(".") + " " + \
            " ".join(r["articles"][open_art["id"]]["wordings"][slot]["wording"].split()[:8])
        bad["overlap"] = r
        return card, good, bad

    def test_457_form_mismatch_rejected(self):
        card, good, bad = self._cases()

        def observe():
            out = {"good": ns.validate(card, good, CFG)[0]}
            for name, r in bad.items():
                try:
                    out[name] = "rejected" if ns.validate(card, r, CFG)[0] else "accepted"
                except (KeyError, TypeError, ValueError):
                    out[name] = "crashed"
            return out

        expected = {"good": [], "bracket": "rejected", "missing_slot": "rejected", "revision_share": "rejected",
                    "overlap": "rejected"}
        self.prove("validator_rejects_a_reply_whose_form_or_texts_break_the_card", observe, expected,
                   lambda: patch.object(ns, "reply_problems", lambda card, reply, cfg: []))

    def test_457_key_mismatch_rejected(self):
        cards = [_card(s) for s in SEEDS]

        def observe():
            out = {}
            for c in cards:
                build = ns.assemble(c, fixture_reply(c), CFG)
                out[c["item_id"] + ":good"] = ns.key_problems(c, build)
                tampered = copy.deepcopy(c)
                pid = sorted(tampered["declared_key"]["proposals"])[0]
                f = tampered["declared_key"]["proposals"][pid]["fate"]
                tampered["declared_key"]["proposals"][pid]["fate"] = "open" if f != "open" else "kept"
                out[c["item_id"] + ":fate"] = bool(ns.key_problems(tampered, build))
                moved = copy.deepcopy(build)
                aid = pid.split("-")[1]
                if aid in moved["next_articles"]:
                    moved["next_articles"][aid] += "\n\n" + next(a["text"] for a in moved["articles"] if a["id"] == aid)
                else:
                    moved["next_articles"][aid] = next(a["text"] for a in moved["articles"] if a["id"] == aid)
                out[c["item_id"] + ":text"] = bool(ns.key_problems(c, moved))
            return out

        expected = {}
        for c in cards:
            expected.update({c["item_id"] + ":good": [], c["item_id"] + ":fate": True, c["item_id"] + ":text": True})
        real = ns.key_problems

        def blind(card, build):
            real(card, build)
            return []

        self.prove("validator_rejects_a_build_whose_scorer_key_differs_from_the_card", observe, expected,
                   lambda: patch.object(ns, "key_problems", blind))


    def test_457_labeller_mismatch_drops_the_item(self):
        cards = [_card(s) for s in SEEDS]

        def labels_of(card):
            red = {"POS-" + s[1:] for s in card["hidden"]["red_lines"]}
            return {p["id"]: {"article": p["article"], "proposal": p["proposal"], "stance": p["stance"],
                              "red_line": p["id"] in red}
                    for p in ns.positions_of(card["structure"], card["hidden"])}

        labels = {c["item_id"]: labels_of(c) for c in cards}
        flipped = copy.deepcopy(labels)
        first = sorted(flipped[cards[1]["item_id"]])[0]
        s = flipped[cards[1]["item_id"]][first]["stance"]
        flipped[cards[1]["item_id"]][first]["stance"] = "oppose" if s != "oppose" else "support"
        missing = copy.deepcopy(labels)
        del missing[cards[2]["item_id"]]

        def observe():
            same, one, gone = (ns.compare_labels(cards, x) for x in (labels, flipped, missing))
            return {"same": [same["kept"], same["dropped"], same["mapping"]["kappa"]],
                    "flipped": one["dropped_ids"], "missing": gone["dropped_ids"]}

        expected = {"same": [3, 0, 1.0], "flipped": [cards[1]["item_id"]], "missing": [cards[2]["item_id"]]}
        self.prove("labeller_mismatch_or_missing_label_drops_the_item", observe, expected,
                   lambda: patch.object(ns, "_label_tuple", lambda article, proposal, stance: str(article)))


class Provenance(NegSynthChecks):
    def test_458_provenance_written(self):
        card = dict(_card(), set="dev_1")
        reply = fixture_reply(card)
        reply_bytes = json.dumps(reply).encode("utf-8")

        def attempt(fn):
            try:
                fn()
                return "written"
            except ValueError:
                return "refused"

        def observe():
            with tempfile.TemporaryDirectory(prefix="neg_synth_prov_") as tmp:
                set_dir = ns.prepare_set(Path(tmp) / "dev_1", "dev_1", CFG)
                prompt = ns.brief_of(card, CFG, GEN)
                problems, build = ns.validate(card, reply, CFG)
                row = ns.provenance_row(card, "dev_1", prompt, reply_bytes, build, family="olmo",
                                        model_id="olmo-fixture", decoding={"temperature": 1.0}, regeneration=0,
                                        cfg=CFG, generated_at="2026-11-16T20:30:00+0300")
                ns.write_item(set_dir, card, build, CFG)
                ns.write_provenance(set_dir, row)
                rows = [json.loads(x) for x in (set_dir / ns.PROVENANCE_FILE).read_text(encoding="utf-8").splitlines()]
                back = rows[0] if rows else {}
                built = json.loads((set_dir / "build" / card["item_id"] / "build.json").read_text(encoding="utf-8"))
                kw = dict(family="olmo", model_id="olmo-fixture", decoding={}, regeneration=0, cfg=CFG)
                return {
                    "rows": len(rows), "problems": problems,
                    "fields": sorted(f for f in ns.PROVENANCE_REQUIRED if back.get(f) not in (None, "")),
                    "digests": [back.get("brief_sha256") == hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                                back.get("reply_sha256") == hashlib.sha256(reply_bytes).hexdigest(),
                                back.get("card_sha256") == ns._sha(card), back.get("build_sha256") == ns._sha(built),
                                back.get("seed") == card["seed"], back.get("synthetic") is True],
                    "second_row": attempt(lambda: ns.write_provenance(set_dir, row)),
                    "missing_field": attempt(lambda: ns.write_provenance(set_dir, dict(row, item_id="other", seed=None))),
                    "dated_id": attempt(lambda: ns.provenance_row(card, "dev_1", prompt, reply_bytes, build,
                                                                  **dict(kw, model_id="olmo-fixture-20261101"))),
                    "family": attempt(lambda: ns.provenance_row(card, "dev_1", prompt, reply_bytes, build,
                                                                **dict(kw, family="qwen"))),
                    "synthetic_flag": built.get("synthetic")}

        expected = {"rows": 1, "problems": [], "fields": sorted(ns.PROVENANCE_REQUIRED), "digests": [True] * 6,
                    "second_row": "refused", "missing_field": "refused", "dated_id": "refused",
                    "family": "refused", "synthetic_flag": True}
        real_row = ns.provenance_row

        def no_seed(*a, **k):
            row = real_row(*a, **k)
            row.pop("seed")
            return row

        @contextlib.contextmanager
        def neutralise():
            with patch.object(ns, "provenance_row", no_seed), patch.object(ns, "PROVENANCE_REQUIRED",
                                                                          tuple(f for f in ns.PROVENANCE_REQUIRED
                                                                                if f != "seed")):
                yield

        self.prove("provenance_row_per_item_with_its_digests", observe, expected, neutralise)


class Screens(NegSynthChecks):
    @staticmethod
    def _rows(cued):
        rng = random.Random("cue-fixture")
        fates = ("kept", "changed", "removed", "open")
        rows = []
        for i in range(60):
            for j in range(4):
                f = fates[(i + j) % 4]
                words = _words(rng, 14)
                if cued and f == "removed":
                    words[3] = "zqmark"
                rows.append({"item": "it-%02d" % i, "text": " ".join(words), "siblings": 2, "fate": f,
                             "conflict": ("conflict", "no_conflict", "not_stated")[(i * 7 + j) % 3],
                             "m10": ns.m10_class(CFG, f)})
        return rows

    def test_459_cue_check_flags_a_planted_cue(self):
        small = copy.deepcopy(CFG)
        small["screens"]["cue"].update(epochs=8, bootstrap=200, permutations=3, targets=["fate"],
                                       baseline="permutation")
        cued, clean = self._rows(True), self._rows(False)

        def observe():
            a = cue.screen(cued, small)["targets"]["fate"]
            b = cue.screen(clean, small)["targets"]["fate"]
            # Recorded beside the proof: the method's majority-class rule flags the cue-free fixture too.
            return {"cued": a["flag"], "clean": b["flag"], "both_flags_written": all(
                isinstance(x.get(f), bool) for x in (a, b) for f in ("flag_majority", "flag_permutation"))}

        self.prove("cue_check_flags_a_surface_cue_and_not_its_absence", observe,
                   {"cued": True, "clean": False, "both_flags_written": True},
                   lambda: patch.object(cue, "features", lambda row: {"bias": 1.0}))

    def test_459_cue_baseline_is_declared(self):
        """D-714: the shipped config rejects a batch by the permutation null; an undeclared baseline is refused;
        the majority-class flag is still written beside it, as information."""
        bad = copy.deepcopy(CFG)
        bad["screens"]["cue"]["baseline"] = "none"
        small = copy.deepcopy(CFG)
        small["screens"]["cue"].update(epochs=4, bootstrap=50, permutations=2, targets=["fate"])
        rows = Screens._rows(False)

        def observe():
            try:
                cue.screen([], bad)
                undeclared = "ran"
            except ValueError:
                undeclared = "refused"
            except Exception:
                undeclared = "ran past the declaration"
            got = cue.screen(rows, small)["targets"]["fate"]
            return {"undeclared": undeclared, "shipped": CFG["screens"]["cue"]["baseline"],
                    "flag_follows_shipped": got["flag"] == got["flag_" + CFG["screens"]["cue"]["baseline"]],
                    "majority_written": isinstance(got.get("flag_majority"), bool)}

        expected = {"undeclared": "refused", "shipped": "permutation", "flag_follows_shipped": True,
                    "majority_written": True}
        self.prove("cue_baseline_declared_permutation_by_d714", observe, expected,
                   lambda: patch.object(cue, "BASELINES", ("majority", "permutation", "none")))

    def test_459_dedup_rules_and_within_set(self):
        rng = random.Random("dedup-fixture")
        ref_long = " ".join(_words(rng, 30))
        ref_run = " ".join(_words(rng, 16))
        paraphrase_base = _words(rng, 25)
        ref_para = " ".join(paraphrase_base)
        refs = {"pilot": [ref_long, ref_run], "development": [ref_para]}
        fresh = lambda n: " ".join(_words(rng, n))
        jac_words = ref_long.split()
        cands = [
            {"id": "c-exact", "group": "c-exact", "texts": [ref_long.upper(), fresh(12)]},
            {"id": "c-runs", "group": "c-runs", "texts": [fresh(5) + " " + " ".join(ref_run.split()[2:10]) + " " + fresh(5)]},
            {"id": "c-jaccard", "group": "c-jaccard", "texts": [" ".join(jac_words[:24]) + " " + fresh(3)]},
            {"id": "c-cosine", "group": "c-cosine", "texts": [" ".join(reversed(paraphrase_base))]},
            {"id": "c-clean", "group": "c-clean", "texts": [fresh(30), fresh(12)]}]
        twin = fresh(40)
        pair = [{"id": "s-a", "group": "s-a", "texts": [twin]}, {"id": "s-b", "group": "s-b", "texts": [twin + " "]},
                {"id": "s-c", "group": "s-c", "texts": [fresh(40)]}]

        def observe():
            fp = dd.fingerprint(refs, CFG, fake_embed)
            got = dd.check(fp, cands, CFG, fake_embed)
            w = dd.within(pair, CFG, fake_embed)
            return {"exact": "c-exact" in got["ids"]["exact"], "runs": "c-runs" in got["ids"]["runs"],
                    "jaccard": "c-jaccard" in got["ids"]["jaccard"], "cosine": "c-cosine" in got["ids"]["cosine"],
                    "clean_kept": "c-clean" not in got["dropped_ids"], "within": w["dropped_ids"],
                    "no_text_in_fingerprint": not any(t in json.dumps(fp) for t in (ref_long, ref_run, ref_para))}

        expected = {"exact": True, "runs": True, "jaccard": True, "cosine": True, "clean_kept": True,
                    "within": ["s-b"], "no_text_in_fingerprint": True}
        strict = copy.deepcopy(CFG)

        @contextlib.contextmanager
        def neutralise():
            strict["screens"]["dedup"].update(jaccard=1.01, cosine=1.01, within_set_cosine=1.01)
            with patch.object(dd.gl, "runs", lambda text: set()), \
                    patch.object(dd.ns, "load_config", lambda path=None: strict), \
                    patch.object(dd, "thresholds", lambda cfg=None: dict(strict["screens"]["dedup"])), \
                    patch.object(dd.gl, "exact_hash", lambda text: hashlib.sha256(str(text).encode()).hexdigest()):
                yield

        self.prove("dedup_counts_four_rules_and_keeps_one_of_a_pair", observe, expected, neutralise)

    def test_459_dedup_vectors_from_the_rented_route(self):
        """EMBED-ROUTE-A for the dedup: `export` writes exactly the texts the commands embed; the merged vectors
        (here written by Python from a fixed 1,024-wide stand-in, as embed_records.py merge leaves them) give the
        same fingerprint vectors and the same check and within results as the embedder itself; a text the
        records do not hold is refused."""
        import numpy as np
        fns = dd._freeze_tools()
        er = fns._embed_records()
        rng = random.Random("dedup-route-fixture")
        para = _words(rng, 25)
        refs = {"development": [" ".join(para), " ".join(_words(rng, 30))]}
        cands = [{"id": "r-cos", "group": "r-cos", "texts": [" ".join(reversed(para))]},
                 {"id": "r-clean", "group": "r-clean", "texts": [" ".join(_words(rng, 30))]},
                 {"id": "r-twin", "group": "r-twin", "texts": [" ".join(reversed(para)) + " "]}]

        def wide(texts):
            return [v + [0.0] * (er.DIM - len(v)) for v in fake_embed(texts)]

        def merged(texts, folder):
            got = fns.export_records(texts, folder / "export")
            keys = [k for _r, k, _t in er.read_records(folder / "export" / "records.jsonl")]
            rows = [t for _r, _k, t in er.read_records(folder / "export" / "records.jsonl")]
            (folder / "merged").mkdir()
            with open(folder / "merged" / "vectors.f32", "wb") as fh:
                np.save(fh, er.unit_rows(np.asarray(wide(rows), dtype=np.float32)))
            (folder / "merged" / "state.json").write_text(json.dumps(
                {"schema": fns.ROUTE_STATE_SCHEMA, "keys_sha256": er.key_digests(keys)["newline"], "dim": er.DIM,
                 "n": len(keys), "done": len(keys)}), encoding="utf-8")
            return got, dd.route_embedder(folder / "merged", folder / "export" / "records.jsonl")

        def observe():
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                (tmp / "ref").mkdir()
                (tmp / "cand").mkdir()
                _got, ref_embed = merged(dd.embed_inputs(parts=refs, cfg=CFG), tmp / "ref")
                _got, cand_embed = merged(dd.embed_inputs(candidates=cands, cfg=CFG), tmp / "cand")
                direct = dd.fingerprint(refs, CFG, wide)
                routed = dd.fingerprint(refs, CFG, ref_embed)
                same_vectors = bool(np.allclose(np.asarray(direct["vectors"]["rows"]),
                                                np.asarray(routed["vectors"]["rows"]), atol=1e-6))
                got = dd.check(routed, cands, CFG, cand_embed)
                w = dd.within(cands, CFG, cand_embed)
                try:
                    cand_embed(["a text the records never held at all"])
                    unknown = "accepted"
                except ValueError:
                    unknown = "refused"
                side = dd.fingerprint(refs, CFG, ref_embed, sidecar=tmp / "fp" / ("reference" + dd.SIDECAR_SUFFIX))
                side_got = dd.check(side, cands, CFG, cand_embed, base=tmp / "fp")
                (tmp / "fp" / ("reference" + dd.SIDECAR_SUFFIX)).write_bytes(b"changed")
                try:
                    dd.check(side, cands, CFG, cand_embed, base=tmp / "fp")
                    changed = "accepted"
                except ValueError:
                    changed = "refused"
                return {"same_vectors": same_vectors, "route_recorded": "route" in routed["vectors"],
                        "cosine": got["ids"]["cosine"], "within": w["dropped_ids"], "unknown_text": unknown,
                        "sidecar_cosine": side_got["ids"]["cosine"], "sidecar_inline_rows": "rows" in side["vectors"],
                        "sidecar_changed": changed}

        expected = {"same_vectors": True, "route_recorded": True, "cosine": ["r-cos", "r-twin"], "within": ["r-twin"],
                    "unknown_text": "refused", "sidecar_cosine": ["r-cos", "r-twin"], "sidecar_inline_rows": False,
                    "sidecar_changed": "refused"}

        def zeros(_vectors, _records):
            def embed(texts):
                return [[0.0] * er.DIM for _ in texts]
            return embed

        self.prove("dedup_takes_the_rented_route_vectors_as_the_embedder", observe, expected,
                   lambda: patch.object(dd, "route_embedder", zeros))

    def test_459_split_plan_and_final_guard(self):
        def refused(fn):
            try:
                fn()
                return False
            except ValueError:
                return True

        def observe():
            final = copy.deepcopy(CFG)
            final["split"]["sets"][0]["purpose"] = "final"
            overlap = copy.deepcopy(CFG)
            overlap["split"]["sets"][1]["offset"] = overlap["split"]["sets"][0]["offset"] + 1
            one_pilot = copy.deepcopy(CFG)
            one_pilot["split"]["sets"] = [s for s in one_pilot["split"]["sets"] if s["name"] != "pilot_2"]
            with tempfile.TemporaryDirectory(prefix="neg_synth_final_") as tmp:
                final_dir = Path(tmp) / "final"
                (final_dir / "build" / "syn-x").mkdir(parents=True)
                (final_dir / "build" / "syn-x" / "build.json").write_text(json.dumps({"synthetic": True}), encoding="utf-8")
                real_dir = Path(tmp) / "real"
                (real_dir / "build" / "r-1").mkdir(parents=True)
                (real_dir / "build" / "r-1" / "build.json").write_text(json.dumps({"synthetic": False}), encoding="utf-8")
                return {"declared_plan": not refused(lambda: ns.check_split(CFG)),
                        "final_purpose": refused(lambda: ns.check_split(final)),
                        "overlap": refused(lambda: ns.check_split(overlap)),
                        "one_pilot": refused(lambda: ns.check_split(one_pilot)),
                        "final_with_synthetic": refused(lambda: ns.refuse_synthetic_in_final(final_dir)),
                        "final_real_only": not refused(lambda: ns.refuse_synthetic_in_final(real_dir))}

        expected = {k: True for k in ("declared_plan", "final_purpose", "overlap", "one_pilot", "final_with_synthetic",
                                      "final_real_only")}
        self.prove("split_plan_refuses_final_and_overlap_and_final_guard_refuses_synthetic", observe, expected,
                   lambda: patch.multiple(ns, check_split=lambda cfg: cfg["split"]["sets"],
                                          synthetic_count=lambda d: (0, False)))


class RecordKinds(NegSynthChecks):
    """D-711: complete-record and missing-notes items in every set; a missing party's answer is not_stated."""

    def test_466_both_kinds_and_missing_party_not_stated(self):
        seeds = list(range(424300, 424312))

        def observe():
            cards = [ns.sample_card(x, CFG, version="fixture") for x in seeds]
            kinds = sorted({c["structure"]["record_kind"] for c in cards})
            missing_ok, recorded = True, True
            for c in cards:
                miss = c["structure"]["missing_parties"]
                if c["structure"]["record_kind"] == "missing_notes":
                    missing_ok &= len(miss) == 1 and miss[0] != c["hidden"]["persona"]
                    missing_ok &= not any(sl["party"] in miss for sl in c["structure"]["slots"])
                    missing_ok &= all(cells.get(miss[0]) == "not_stated"
                                      for cells in c["declared_key"]["alignment"].values())
                    missing_ok &= miss[0] not in c["declared_key"]["approach_targets"]
                build = ns.assemble(c, fixture_reply(c), CFG)
                item, key = ns.sna.build_item(build)
                recorded &= item["record_kind"] == c["structure"]["record_kind"] == key["record_kind"]
                recorded &= not ns.key_problems(c, build)
            return {"kinds": kinds, "missing_party_not_stated": missing_ok, "recorded": recorded}

        expected = {"kinds": ["complete", "missing_notes"], "missing_party_not_stated": True, "recorded": True}
        self.prove("both_record_kinds_and_the_missing_party_is_not_stated", observe, expected,
                   lambda: patch.object(ns, "record_kind_of", lambda seed, cfg: "complete"))

    def test_466_set_check_needs_both_kinds(self):
        def observe():
            with tempfile.TemporaryDirectory(prefix="neg_synth_kinds_") as tmp:
                out = {}
                for name, kinds in (("both", ["complete", "complete", "missing_notes", "missing_notes"]),
                                    ("one", ["complete"] * 4), ("unrecorded", ["complete", "complete",
                                                                              "missing_notes", None])):
                    d = Path(tmp) / name
                    for n, kind in enumerate(kinds):
                        f = d / "build" / ("syn-%d" % n) / "build.json"
                        f.parent.mkdir(parents=True)
                        f.write_text(json.dumps({"synthetic": True, "record_kind": kind}), encoding="utf-8")
                    out[name] = ns.set_kind_problems(d, CFG)
                return out

        expected = {"both": [], "one": ["record_kind:missing_notes"],
                    "unrecorded": ["record_kind_missing", "record_kind:missing_notes"]}
        self.prove("set_check_refuses_a_set_without_both_kinds", observe, expected,
                   lambda: patch.object(ns, "set_kind_problems", lambda d, cfg: []))

    def test_466_select_keeps_the_first_target_in_seed_order(self):
        seeds = list(range(424500, 424510))
        cards = [ns.sample_card(x, CFG, version="fixture") for x in reversed(seeds)]
        by_seed = {c["seed"]: c["item_id"] for c in cards}

        def observe():
            with tempfile.TemporaryDirectory(prefix="neg_synth_select_") as tmp:
                for c in cards:
                    f = Path(tmp) / "build" / c["item_id"] / "build.json"
                    f.parent.mkdir(parents=True)
                    f.write_text("{}", encoding="utf-8")
                out = ns.select(cards, tmp, 4, dropped=[by_seed[seeds[1]]])
                return {"kept": out["kept"], "short": out["short"], "kinds": sorted(out["record_kinds"])}

        expected = {"kept": [by_seed[x] for x in (seeds[0], seeds[2], seeds[3], seeds[4])], "short": 0,
                    "kinds": ["complete", "missing_notes"]}
        self.prove("select_keeps_the_first_target_items_in_seed_order_past_the_dropped", observe, expected,
                   lambda: patch.object(ns, "select", lambda cards, set_dir, target, dropped=(): {
                       "kept": [c["item_id"] for c in cards][:target], "short": 0, "record_kinds": {}}))

    def test_466_reply_read_by_its_form_only(self):
        card = _card()
        body = json.dumps(fixture_reply(card))
        forms = {"plain": body, "fenced": "```json\n" + body + "\n```", "prose": "Here it is:\n" + body + "\nDone.",
                 "none": "I cannot write this."}

        def observe():
            out = {}
            for name, text in forms.items():
                obj, why = ns.read_reply(text.encode("utf-8"))
                out[name] = "read" if obj == json.loads(body) else (why or "other")
            return out

        expected = {"plain": "read", "fenced": "read", "prose": "read", "none": ns.af.NO_OBJECT}
        self.prove("generator_reply_read_by_form_only_never_dropped_for_its_fence", observe, expected,
                   lambda: patch.object(ns, "read_reply", lambda raw: (
                       (json.loads(raw.decode("utf-8")), None) if raw.decode("utf-8").lstrip().startswith("{")
                       else (None, "json"))))

    def test_466_scorer_refuses_a_synthetic_build_without_its_kind(self):
        card = _card()
        build = ns.assemble(card, fixture_reply(card), CFG)

        def observe():
            out = {}
            for name, kind in (("recorded", build["record_kind"]), ("absent", None), ("unknown", "partial")):
                b = copy.deepcopy(build)
                if kind is None:
                    b.pop("record_kind")
                else:
                    b["record_kind"] = kind
                try:
                    ns.sna.build_item(b)
                    out[name] = "built"
                except ValueError:
                    out[name] = "refused"
            return out

        self.prove("scorer_refuses_a_synthetic_build_without_a_declared_kind", observe,
                   {"recorded": "built", "absent": "refused", "unknown": "refused"},
                   lambda: patch.object(ns.sna, "check_build", lambda b: None))


def _truthful(builds, wrong=None):
    """A fake generate answering each statement from its build (the proof's oracle, never the runner's input).
    `wrong` names a quote whose stance it gets wrong. Replies wrap the object in a fence and prose."""
    truth = {}
    for b in builds:
        red = set(b["red_lines"])
        for p in b["positions"]:
            truth[p["quote"]] = {"article": p["article"], "wording": "whole" if p["proposal"] is None else p["proposal"],
                                 "stance": p["stance"], "firm_limit": "yes" if p["id"] in red else "no"}

    def generate(prompts):
        out = []
        for prompt in prompts:
            quote = next(q for q in truth if ("\n" + q + "\n") in prompt)
            ans = dict(truth[quote])
            if quote == wrong:
                ans["stance"] = "support" if ans["stance"] != "support" else "oppose"
            out.append("Here is my reading.\n```json\n" + json.dumps(ans) + "\n```")
        return out
    return generate


def _fake_info(table):
    return lambda repo: table.get(repo, {"exists": False})


OPEN = {"exists": True, "gated": False, "terms": "apache-2.0", "revision": "abc123"}


class LabellerRunner(NegSynthChecks):
    """Role V's runner on fixtures: label sheets only, a fake generate, a fake live resolver; nothing downloaded."""

    def setUp(self):
        self.cards = [_card(x) for x in SEEDS]
        self.builds = [ns.assemble(c, fixture_reply(c), CFG) for c in self.cards]
        self.sheets = {"schema": ns.SHEET_SCHEMA, "sheets": [ns.label_sheet(b) for b in self.builds]}
        self.info = _fake_info({CFG["labeller"]["candidates"][0]: OPEN})

    def test_467_runner_labels_match_cards(self):
        wrong = self.builds[1]["positions"][0]["quote"]

        def observe():
            out = {}
            for name, gen in (("truthful", _truthful(self.builds)), ("one_wrong", _truthful(self.builds, wrong))):
                labels, record = nsl.run(self.sheets, CFG, generate=gen, info=self.info)
                cmp = ns.compare_labels(self.cards, labels["labels"])
                out[name] = {"dropped": cmp["dropped_ids"], "perfect": cmp["mapping"]["kappa"] == 1.0,
                             "model": record["model_id"], "unread": sum(v for k, v in record["by_reason"].items()
                                                                        if k != "read")}
            return out

        m = CFG["labeller"]["candidates"][0]
        expected = {"truthful": {"dropped": [], "perfect": True, "model": m, "unread": 0},
                    "one_wrong": {"dropped": [self.cards[1]["item_id"]], "perfect": False, "model": m, "unread": 0}}
        self.prove("labeller_runner_labels_from_sheets_and_a_wrong_answer_drops_its_item", observe, expected,
                   lambda: patch.object(nsl, "_wordings", lambda article: 0))

    def test_467_sheet_with_an_answer_refused(self):
        leaky = copy.deepcopy(self.sheets)
        leaky["sheets"][0]["positions"][0]["stance"] = "oppose"
        marked = copy.deepcopy(self.sheets)
        marked["sheets"][0]["red_lines"] = ["POS-1"]
        prompts = []

        def spy(ps):
            prompts.extend(ps)
            return _truthful(self.builds)(ps)

        def observe():
            out = {}
            for name, value in (("leaky", leaky), ("marked", marked), ("clean", self.sheets)):
                try:
                    nsl.run(value, CFG, generate=spy, info=self.info)
                    out[name] = "ran"
                except ValueError:
                    out[name] = "refused"
            first = list(prompts)
            prompts.clear()
            moved = []
            for bld in self.builds:
                t2 = copy.deepcopy(bld)
                t2["red_lines"], t2["next_articles"] = [], {}
                for pos in t2["positions"]:
                    pos["stance"], pos["article"], pos["proposal"] = "accept", "A0", None
                moved.append(ns.label_sheet(t2))
            nsl.run({"schema": ns.SHEET_SCHEMA, "sheets": moved}, CFG, generate=spy, info=self.info)
            out["prompts_same_without_answers"] = first == prompts
            prompts.clear()
            return out

        self.prove("labeller_refuses_a_sheet_carrying_an_answer_and_its_prompt_holds_none", observe,
                   {"leaky": "refused", "marked": "refused", "clean": "ran", "prompts_same_without_answers": True},
                   lambda: patch.object(nsl, "check_sheets", lambda value: value["sheets"]))

    def test_467_model_declared_and_resolved_live(self):
        cands = CFG["labeller"]["candidates"]

        def attempt(fn):
            try:
                return fn()
            except ValueError:
                return "refused"

        def observe():
            return {
                "first_open": attempt(lambda: nsl.resolve(CFG, _fake_info({cands[0]: OPEN}))["model_id"]),
                "first_gated": attempt(lambda: nsl.resolve(CFG, _fake_info(
                    {cands[0]: dict(OPEN, gated=True), cands[1]: OPEN}))["model_id"]),
                "other_terms": attempt(lambda: nsl.resolve(CFG, _fake_info({c: dict(OPEN, terms="other") for c in cands}))),
                "none": attempt(lambda: nsl.resolve(CFG, _fake_info({}))),
                "qwen": attempt(lambda: nsl.check_model("Qwen/Qwen2.5-7B-Instruct", CFG)),
                "claude": attempt(lambda: nsl.check_model("claude-olmo", CFG)),
                "dated": attempt(lambda: nsl.check_model("allenai/olmo-instruct-20261101", CFG)),
                "other_family": attempt(lambda: nsl.check_model("google/gemma-2-9b-it", CFG))}

        expected = {"first_open": cands[0], "first_gated": cands[1], "other_terms": "refused", "none": "refused",
                    "qwen": "refused", "claude": "refused", "dated": "refused", "other_family": "refused"}
        self.prove("labeller_model_declared_in_config_resolved_live_and_family_refused", observe, expected,
                   lambda: patch.object(nsl, "check_model", lambda model_id, cfg: model_id))

    def test_467_unreadable_answer_leaves_the_position_unlabelled(self):
        good = _truthful(self.builds)
        target = self.builds[2]["positions"][0]["quote"]

        def garbled(prompts):
            out = good(prompts)
            return ["I am not sure." if ("\n" + target + "\n") in pr else r for pr, r in zip(prompts, out)]

        def observe():
            labels, record = nsl.run(self.sheets, CFG, generate=garbled, info=self.info)
            cmp = ns.compare_labels(self.cards, labels["labels"])
            return {"no_object": record["by_reason"].get(nsl.af.NO_OBJECT, 0), "dropped": cmp["dropped_ids"]}

        real = nsl.read_answer

        def lenient(reply, sheet, position, t):
            lab, why = real(reply, sheet, position, t)
            return (lab, why) if lab else ({"article": sheet["articles"][0]["id"], "proposal": None,
                                            "stance": "support", "red_line": False}, None)

        self.prove("labeller_unreadable_answer_counted_by_reason_and_its_item_dropped", observe,
                   {"no_object": 1, "dropped": [self.cards[2]["item_id"]]},
                   lambda: patch.object(nsl, "read_answer", lenient))


def _key_reply(item, key):
    """An advice reply that repeats the key (the proof's perfect arm)."""
    value = {"proposals": [{"id": pid, "conflict": k["conflict"], "stance": "accept", "reasons": ["PAR-1"]}
                           for pid, k in sorted(key["proposals"].items())],
             "trades": [], "approach": list(key["approach_targets"]),
             "alignment": [{"article": a, "aligned": sorted(p for p, v in cells.items() if v == "aligned"),
                            "opposed": sorted(p for p, v in cells.items() if v == "opposed")}
                           for a, cells in sorted(key["alignment"].items())],
             "state": [{"article": a, "state": v["state"]} for a, v in sorted(key["articles"].items())]}
    return ns.na.parse_advice(json.dumps(value), item)


class SyntheticRow(NegSynthChecks):
    """D-706 item 3, D-707: real items alone are the headline; synthetic items are reported apart, never pooled."""

    def setUp(self):
        self.items, self.keys = {}, {}
        for n, seed in enumerate(range(424400, 424412)):
            card = ns.sample_card(seed, CFG, version="fixture")
            b = ns.assemble(card, fixture_reply(card), CFG)
            if n < 6:
                b = dict(b, item_id="real-%02d" % n, synthetic=False)
            item, key = ns.sna.build_item(b)
            self.items[item["item_id"]], self.keys[item["item_id"]] = item, key
        ids = sorted(self.items)
        self.arms = {"system": ({"rows": [{"form": "advice", "group": "system_advice", "item_id": i,
                                           "reply": _key_reply(self.items[i], self.keys[i]), "audit": {}}
                                          for i in ids]}, "system_advice"),
                     "B1": ({"rows": [{"form": "advice", "group": "b1", "item_id": i, "reply": None} for i in ids]},
                            "b1")}

    def test_468_real_headline_synthetic_apart(self):
        def observe():
            r = ns.sna.report(self.items, self.keys, self.arms, resamples=200, python_step=False)
            syn = r.get("synthetic", {})
            return {"headline_items": r["headline_items"], "real_items": r.get("real_items"),
                    "real_m1_items": r["figures"]["system"]["M1"].get("items"),
                    "synthetic_items": syn.get("items"), "synthetic_m1_items":
                        (syn.get("figures") or {}).get("system", {}).get("M1", {}).get("items"),
                    "synthetic_row_labelled": syn.get("row") == ns.sna.SYNTHETIC_ROW,
                    "synthetic_claims_indicators": all(c.get("status") == "indicator" and c.get("shown") is False
                                                       for c in (syn.get("claims") or {}).values()),
                    "synthetic_bar_not_the_bar": (syn.get("bar") or {}).get("is_the_bar") is False,
                    "record_kind_cells": sorted(r["cells"]["system"].get("record_kind", {})),
                    "per_item_rows": len(r["_per_item"]["system"])}

        expected = {"headline_items": 6, "real_items": 6, "real_m1_items": 6, "synthetic_items": 6,
                    "synthetic_m1_items": 6, "synthetic_row_labelled": True, "synthetic_claims_indicators": True,
                    "synthetic_bar_not_the_bar": True, "record_kind_cells": None, "per_item_rows": 12}
        expected["record_kind_cells"] = sorted({self.keys[i]["record_kind"] for i in self.keys
                                                if not self.keys[i]["synthetic"]})
        real_report = ns.sna.report
        pooled = lambda items, keys, arms, **kw: ns.sna._report_on(items, keys, arms, **{
            k: v for k, v in kw.items() if k != "python_step"}, python_step=kw.get("python_step", True))
        self.prove("scorer_reads_real_items_as_the_headline_and_synthetic_items_apart", observe, expected,
                   lambda: patch.object(ns.sna, "report", pooled))
        self.assertIs(ns.sna.report, real_report)

    def test_468_power_counts_real_items_only(self):
        seen = {}

        def fake_power(sizes, shares, **kw):
            seen["sizes"] = len(sizes)
            return {"0.2": 0.9}

        def observe():
            with patch.object(ns.sna, "read_keys", lambda d: self.keys), \
                    patch.object(ns.sna, "_read", lambda path: {"set_sha256": "0" * 64}), \
                    patch.object(ns.sna, "simulate_power", fake_power):
                rec = ns.sna.power_record("unused", k=1, sims=1, resamples=1)
            return {"headline_items": rec["headline_items"], "simulated": seen.get("sizes")}

        self.prove("power_record_counts_real_items_only", observe, {"headline_items": 6, "simulated": 6},
                   lambda: patch.object(ns.sna, "is_headline", lambda key: key["part"] in ns.sna.HEADLINE))


class CardFolder(NegSynthChecks):
    """Check 510 (D-716): with only --set given, coverage, assemble, select and label-compare read the set's
    declared card folder under the role root, and what they print holds no card text, card file name or seed."""

    SET, DECOY = "pilot_1", "pilot_2"

    def _role(self, tmp):
        root = Path(tmp) / "role_s"
        cards = {}
        for name, seeds in ((self.SET, (515001, 515002, 515003, 515004)), (self.DECOY, (515101, 515102))):
            folder = root.joinpath(*CFG["card_folder"]["relative"], name)
            folder.mkdir(parents=True)
            cards[name] = []
            for seed in seeds:
                c = ns.sample_card(seed, CFG, version="fixture")
                c["set"] = name
                (folder / (c["item_id"] + ".card.json")).write_text(json.dumps(c), encoding="utf-8")
                cards[name].append(c)
        return root, cards

    @staticmethod
    def _run(argv):
        import io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = ns.main(argv)
        except SystemExit as e:
            code, buf = "refused", io.StringIO(str(e))
        return code, buf.getvalue()

    @staticmethod
    def _secrets(cards):
        """Strings a card holds that no printed line may carry: its id and file name, seed, names and subject."""
        out = set()
        for c in cards:
            out |= {c["item_id"], c["item_id"] + ".card.json", str(c["seed"]), c["structure"]["subject"]}
            out |= {p["name"] for p in c["structure"]["parties"] if p.get("name")}
        return out

    def _observe(self):
        with tempfile.TemporaryDirectory(prefix="neg_synth_cards_") as tmp:
            root, cards = self._role(tmp)
            mine = cards[self.SET]
            printed = []
            with patch.dict("os.environ", {CFG["card_folder"]["root_env"]: str(root)}):
                code, text = self._run(["coverage", "--set", self.SET])
                printed.append(text)
                cov_ok = code == 2 or code == 0
                cov_same = cov_ok and json.loads(text.splitlines()[0]) == json.loads(
                    json.dumps(ns.coverage(mine, CFG), sort_keys=True))
                set_dir = Path(tmp) / "sets" / self.SET
                accepted = 0
                for c in mine:
                    prompt = Path(tmp) / (c["item_id"] + ".prompt.md")
                    prompt.write_text(ns.brief_of(c, CFG), encoding="utf-8")
                    reply = Path(tmp) / "reply.json"
                    reply.write_text(json.dumps(fixture_reply(c)), encoding="utf-8")
                    code, text = self._run(["assemble", "--set", self.SET, "--item", c["item_id"], "--prompt",
                                            str(prompt), "--reply", str(reply), "--set-dir", str(set_dir),
                                            "--generator-family", "olmo", "--model-id", "olmo-fixture"])
                    printed.append(text)
                    accepted += code == 0
                code, text = self._run(["select", "--set", self.SET, "--set-dir", str(set_dir),
                                        "--out", str(Path(tmp) / "kept.json")])
                printed.append(text)
                built = json.loads(text.splitlines()[0])["built"] if code != "refused" else None
                labels = {c["item_id"]: {} for c in mine}
                (Path(tmp) / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
                code, text = self._run(["label-compare", "--set", self.SET, "--set-dir", str(set_dir), "--labels",
                                        str(Path(tmp) / "labels.json"), "--out", str(Path(tmp) / "lc.json")])
                printed.append(text)
                compared = json.loads(text.splitlines()[0])["items"] if code != "refused" else None
            default = ns.card_folder(CFG, self.SET, environ={}) == ns.ROOT.parent.joinpath(
                *CFG["card_folder"]["relative"], self.SET)
            secrets = self._secrets(cards[self.SET] + cards[self.DECOY])
            leaks = sorted({s for s in secrets for t in printed if s in t})
            return {"coverage_of_the_set": cov_same, "assembled": accepted, "selected_built": built,
                    "compared": compared, "default_root_is_checkout_parent": default, "leaks": len(leaks)}

    EXPECTED = {"coverage_of_the_set": True, "assembled": 4, "selected_built": 4, "compared": 4,
                "default_root_is_checkout_parent": True, "leaks": 0}

    def test_510_set_alone_reads_the_declared_card_folder(self):
        real = ns.card_folder
        decoy = lambda cfg, set_name, environ=None: real(cfg, self.DECOY, environ)
        self.prove("set_alone_reads_its_declared_card_folder", self._observe, self.EXPECTED,
                   lambda: patch.object(ns, "card_folder", decoy))

    def test_510_printed_lines_hold_no_card_text_or_name(self):
        real = ns.coverage

        def leaky(cards, cfg):
            out = real(cards, cfg)
            out["items"] = sorted(c["item_id"] + ".card.json" for c in cards)
            return out

        self.prove("printed_lines_hold_no_card_text_or_name", self._observe, self.EXPECTED,
                   lambda: patch.object(ns, "coverage", leaky))


GROUPS = {"455": (Determinism,), "456": (BriefHoldsNoKey,), "457": (Validator,), "458": (Provenance,),
          "459": (Screens,), "466": (RecordKinds,),
          "467": (LabellerRunner,), "468": (SyntheticRow,), "510": (CardFolder,)}


def check(group=None):
    NegSynthChecks.evidence = []
    result = unittest.TestResult()
    suite = unittest.TestSuite()
    for g, classes in GROUPS.items():
        if group is None or g == group:
            for c in classes:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c))
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, on invented cards and replies" % len(
        NegSynthChecks.evidence)


def main():
    group = sys.argv[1] if len(sys.argv) > 1 else None
    status, detail = check(group)
    for proof in NegSynthChecks.evidence:
        print(proof.get("name"), proof.get("status"))
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
