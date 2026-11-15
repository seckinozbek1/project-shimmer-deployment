"""Proofs of the instruction-optimisation tooling (#255), on the shipped config only; no model, key or item."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (str(ROOT / "scripts"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import instruction_opt as io  # noqa: E402


def rewrite(target, prefix="Read both carefully. "):
    return prefix + io.shipped(target)


class InstructionOptChecks(unittest.TestCase):
    def test_a_rewrite_of_the_instruction_part_is_admitted_and_renders(self):
        import cell_selection
        import passage_pairs
        c1 = io.candidate_config("T1", rewrite("T1"))
        self.assertTrue(passage_pairs.render(c1, "A says one thing.", "B says another.").startswith("Read both carefully."))
        c2 = io.candidate_config("T2", rewrite("T2"))
        self.assertIn("CLAIM\nX holds.", cell_selection.question(c2, "| a |", "X holds."))
        self.assertTrue(io.candidate_id(rewrite("T1")).startswith("cand_"))

    def test_the_screen_refuses_structural_changes(self):
        for target in ("T1", "T2"):
            base = io.shipped(target)
            block = io.answer_block(base)
            bad = {"answer block changed": base.replace(block, block.replace("Unclear", "Maybe")),
                   "placeholder dropped": base.replace(io.PLACEHOLDER.findall(base)[0].join("{}"), "", 1),
                   "placeholder twice": base.replace(block, "{%s} " % io.PLACEHOLDER.findall(base)[0] + block),
                   "too long": "x" * int(len(base) * io.MAX_LENGTH_FACTOR) + base,
                   "unchanged": base, "empty": " "}
            for name, text in bad.items():
                self.assertFalse(io.screen(target, text)[0], "%s %s" % (target, name))
                with self.assertRaises(ValueError):
                    io.candidate_config(target, text)

    def test_the_proposer_sees_counts_and_texts_only(self):
        prompt = io.proposer_prompt("T1", {"gold": {"FLAG": 12, "CLEAR": 18}, "decided": {"FLAG": 9}, "undecided": 4},
                                    best=[(rewrite("T1"), 0.71)])
        self.assertIn(io.answer_block(io.shipped("T1")), prompt)
        for bad in ({"gold": {"FLAG": "a passage"}}, {"items": [1]}, {"undecided": "four"}):
            with self.assertRaises(ValueError):
                io.proposer_prompt("T1", bad)
        reply = "<<<\n%s\n>>>\nnoise <<<\n%s\n>>> <<<\n%s\n>>>" % (rewrite("T1"), rewrite("T1", "Be strict. "), rewrite("T1"))
        self.assertEqual(io.read_proposals(reply), [rewrite("T1"), rewrite("T1", "Be strict. ")])


    def test_the_proposer_file_runs_on_the_base_and_refuses_other_forms(self):
        """The proposer form loads the base producer checkpoint (no adapter), on the sdpa path alone;
        an unknown form and a file mixing the proposer form with other prompts are refused."""
        import json
        import tempfile
        import bare_model
        import decoding_policy
        import replay_prompts

        class Tok:
            def apply_chat_template(self, messages, add_generation_prompt, tokenize):
                return "<user>" + messages[0]["content"] + "<assistant>"

        class Backend:
            def prepare(self):
                return {"model_id": "fixture", "digest": "d", "checkpoint": "base"}

            def count(self, text):
                return len(text.split())

            def max_context(self):
                return 10 ** 6

            def generate(self, text, attention, max_new_tokens, constraint=False, agent=None):
                return {"text": "<<<\nA rewrite.\n>>>", "output_tokens": 5, "attention": attention, "prefill": {"chunks": 0}}
        asked = []
        reader = dict(decoding=decoding_policy.policy("local_producer"), model_id="fixture", model_mode="base", max_new_tokens=64)

        def resolve(checkpoint=None, **kwargs):
            asked.append(checkpoint)
            return reader
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proposer.json"
            io.proposer_file([("T1_round1", io.proposer_prompt("T1", {"undecided": 3}))], path, tokenizer=Tok())
            with patch.object(bare_model, "resolve_reader", resolve):
                result = replay_prompts.run(path, Path(tmp) / "out", paths=["sdpa"], backend=Backend())
                self.assertEqual(asked, [bare_model.BASE], "the proposer loads the base, no adapter")
                with self.assertRaisesRegex(ValueError, "sdpa path alone"):
                    replay_prompts.run(path, Path(tmp) / "out2", paths=["sdpa", "sdpa_constrained"], backend=Backend())
            self.assertEqual(result["prompts"], 1)
            value = json.loads(path.read_text(encoding="utf-8"))
            for change, message in (({"form": "other"}, "unknown form"), (None, "proposer prompts only")):
                bad = json.loads(json.dumps(value))
                if change:
                    bad["prompts"][0].update(change)
                else:
                    extra = dict(bad["prompts"][0], prompt_id="p0002")
                    extra.pop("form")
                    bad["prompts"].append(extra)
                    bad["prompt_count"] = 2
                (Path(tmp) / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    replay_prompts.load_prompts(Path(tmp) / "bad.json")


def _replay():
    import replay_prompts
    return replay_prompts


NEUTRALIZATIONS = [("test_the_screen_refuses_structural_changes", "screen", lambda target, candidate, root=io.ROOT: (True, "")),
                   ("test_the_proposer_file_runs_on_the_base_and_refuses_other_forms", ("replay_prompts", "reader_checkpoint"),
                    lambda proposer: "tuned")]


def _single(name):
    result = unittest.TestResult()
    InstructionOptChecks(name).run(result)
    return result.wasSuccessful()


def check():
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(InstructionOptChecks).run(result)
    if result.failures or result.errors:
        return ("FAIL", (result.failures + result.errors)[0][1].strip().splitlines()[-1])
    for name, attr, mutant in NEUTRALIZATIONS:
        owner, attr = (_replay(), attr[1]) if isinstance(attr, tuple) else (io, attr)
        before = _single(name)
        with patch.object(owner, attr, mutant):
            failed = not _single(name)
        if not (before and failed and _single(name)):
            return ("FAIL", "the neutralise, fail, restore, pass proof of %s did not hold" % attr)
    return ("PASS", "%d cases and %d neutralisation: a candidate may change only the instruction before the shipped "
            "answer block; placeholders once each; the proposer sees counts only" % (result.testsRun, len(NEUTRALIZATIONS)))


if __name__ == "__main__":
    print(check())
