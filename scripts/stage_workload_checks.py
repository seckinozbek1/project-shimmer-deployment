"""Gate check: built benchmark bundles staged as the sealer's workload (loop S5 join, item 3).

tools/stage_workload.py turns an adapter build (benchmark/adapters: context/ holding
_review_targets.json, conventions/, answer_key.json, items.json beside the bundles) or a
generator build (benchmark/generators: the same, and case_manifest.json for a multi-round
case) into the folder tools/prepare_ordinary_final_run.py --workload reads, plus the B1
item table its --items takes. Every case EXECUTES the tool and the sealer's own reader on a
synthetic fixture written to a temporary folder (no model, no pipeline run, no provider):

1. an adapter build of two bundles is staged; the sealer's workload_members accepts each
   staged folder, no member is the answer key or named like one, and each staged item table
   holds only its own document's items with the four fields bare_model.py reads, which the
   sealer's b1_fields seals;
2. a generator-style multi-round bundle is staged with its case manifest, every staged byte
   equal to its source byte (a document with CRLF line endings included: the sealer, not the
   staging, normalises line endings);
3. a bundle holding a file named like a key under context/ or conventions/ is refused whole,
   and nothing is written.

Each is proven by neutralise, fail, restore, pass (scripts/effect_proof.py).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effect_proof import prove_effect  # noqa: E402

TARGETS = '{"grounding": [], "prior": [], "resolved_at": "", "source": "operator", "targets": ["%s.md"]}\n'
RULES = "# Review rules\n\n## CONV-1 Statements agree [required] [conformance]\n\nEvery statement agrees with the others.\n"


def _modules():
    import prepare_ordinary_final_run as sealer
    import stage_workload
    return stage_workload, sealer


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def adapter_build(root):
    """Two bundles as benchmark/adapters/common/bundle.py writes them, with the build records."""
    build = root / "build"
    for doc in ("d0a1", "d0b2"):
        _write(build / doc / "context" / (doc + ".md"), "# D-%s\n\n## P-00001\n\nPassage: part 1\n\nOne line.\n" % doc)
        _write(build / doc / "context" / "_review_targets.json", TARGETS % doc)
        _write(build / doc / "conventions" / "rules.md", RULES)
        _write(build / doc / "answer_key.json", json.dumps({"document": doc + ".md", "items": [{"item_id": "x"}]}))
    rows = [{"item_id": "i%d" % k, "document_id": doc, "rule_id": "CONV-1", "benchmark": "fixture",
             "source_item_id": "s%d" % k, "source_document_id": "src-" + doc}
            for k, doc in enumerate(("d0a1", "d0a1", "d0b2"))]
    _write(build / "items.json", json.dumps({"benchmark": "fixture", "items": rows}))
    _write(build / "parts.json", json.dumps({"documents": []}))
    return build


def generator_bundle(root):
    """A multi-round bundle as benchmark/generators writes one: two rounds, a case manifest,
    the key at the top. One document carries CRLF line endings to prove a byte copy."""
    bundle = root / "case" / "mr01"
    _write(bundle / "context" / "round_two.md", b"# Round two\r\n\r\nValue: 4 units\r\n")
    _write(bundle / "context" / "round_one.md", "# Round one\n\nValue: 3 units\n")
    _write(bundle / "context" / "_review_targets.json",
           '{"grounding": ["round_one.md"], "prior": ["round_one.md"], "resolved_at": "", "source": "operator", '
           '"targets": ["round_two.md"]}\n')
    _write(bundle / "conventions" / "rules.md", RULES)
    _write(bundle / "case_manifest.json", '{"case_id": "mr01"}\n')
    _write(bundle / "answer_key.json", '{"document": "round_two.md"}\n')
    return bundle


def _source_bytes_equal(source, staged):
    pairs = {"_review_targets.json": source / "context" / "_review_targets.json"}
    for path in source.rglob("*"):
        rel = path.relative_to(source).as_posix()
        if path.is_file() and rel.split("/")[0] in ("context", "conventions") and rel != "context/_review_targets.json":
            pairs[rel] = path
    if (source / "case_manifest.json").is_file():
        pairs["case_manifest.json"] = source / "case_manifest.json"
    return all((staged / k).is_file() and (staged / k).read_bytes() == p.read_bytes() for k, p in pairs.items())


def observe_adapter():
    stage, sealer = _modules()
    with tempfile.TemporaryDirectory(prefix="shimmer_stage_") as td:
        root = Path(td)
        build = adapter_build(root)
        out = root / "staged"
        stage.stage_build(build, out)
        seen = {}
        for doc in ("d0a1", "d0b2"):
            workload = out / doc / "workload"
            try:
                members = sorted(sealer.workload_members(workload))
            except RuntimeError as exc:
                members = "refused: " + str(exc)
            table = json.loads((out / doc / "items.json").read_text(encoding="utf-8"))
            sealed = sealer.b1_fields((out / doc / "items.json").read_bytes(),
                                      (workload / "_review_targets.json").read_bytes(),
                                      [dict(name="base", args=[])])["item_ids"]
            seen[doc] = {"members": members,
                         "key_like": sorted(p.name for p in workload.rglob("*") if stage.key_like(p.name)),
                         "bytes_equal": _source_bytes_equal(build / doc, workload),
                         "item_fields": sorted({k for r in table["items"] for k in r}),
                         "sealed_item_ids": sealed}
        seen["staged_top"] = sorted(p.name for p in out.iterdir())
        return seen


ADAPTER = {"d0a1": {"members": ["_review_targets.json", "context/d0a1.md", "conventions/rules.md"], "key_like": [],
                    "bytes_equal": True, "item_fields": ["benchmark", "document_id", "item_id", "rule_id"],
                    "sealed_item_ids": ["i0", "i1"]},
           "d0b2": {"members": ["_review_targets.json", "context/d0b2.md", "conventions/rules.md"], "key_like": [],
                    "bytes_equal": True, "item_fields": ["benchmark", "document_id", "item_id", "rule_id"],
                    "sealed_item_ids": ["i2"]},
           "staged_top": ["d0a1", "d0b2"]}


def observe_generator():
    stage, sealer = _modules()
    with tempfile.TemporaryDirectory(prefix="shimmer_stage_") as td:
        root = Path(td)
        bundle = generator_bundle(root)
        out = root / "staged"
        counts = stage.stage(bundle, out)
        return {"members": sorted(sealer.workload_members(out)), "bytes_equal": _source_bytes_equal(bundle, out),
                "multi_round": counts["multi_round"], "not_copied": counts["not_copied"]}


GENERATOR = {"members": ["_review_targets.json", "case_manifest.json", "context/round_one.md", "context/round_two.md",
                         "conventions/rules.md"],
             "bytes_equal": True, "multi_round": True, "not_copied": 1}


def observe_key_refusal():
    stage, _ = _modules()
    seen = {}
    for name, where in (("answer_key.json", "context"), ("gold_labels.md", "conventions"), ("key.md", "context"),
                        ("keynote.md", "context")):
        with tempfile.TemporaryDirectory(prefix="shimmer_stage_") as td:
            root = Path(td)
            bundle = generator_bundle(root)
            _write(bundle / where / name, "x\n")
            out = root / "staged"
            try:
                stage.stage(bundle, out)
                verdict = "accepted"
            except stage.StagingError as exc:
                verdict = "refused: " + str(exc).split(":")[0]
            seen[where + "/" + name] = {"verdict": verdict, "written": out.exists()}
    return seen


KEY_REFUSAL = {"context/answer_key.json": {"verdict": "refused: A file named like a key is in the bundle's context/",
                                           "written": False},
               "conventions/gold_labels.md": {"verdict": "refused: A file named like a key is in the bundle's conventions/",
                                              "written": False},
               "context/key.md": {"verdict": "refused: A file named like a key is in the bundle's context/",
                                  "written": False},
               "context/keynote.md": {"verdict": "accepted", "written": True}}


# ---- neutralisations ---------------------------------------------------------------------

def whole_bundle_copied():
    """The naive staging: every file of the bundle copied as it stands, the key included."""
    stage, _ = _modules()

    def everything(bundle):
        bundle = Path(bundle)
        members = {p.relative_to(bundle).as_posix(): p for p in bundle.rglob("*") if p.is_file()}
        members["_review_targets.json"] = members.pop("context/_review_targets.json")
        return members
    return patch.object(stage, "bundle_files", everything)


def text_mode_copy():
    """Members copied through text mode, which rewrites line endings: the sealer's job done
    early and the source bytes lost."""
    stage, _ = _modules()

    def through_text(source, target):
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return patch.object(stage, "copy_member", through_text)


def no_key_filter():
    stage, _ = _modules()
    return patch.object(stage, "key_like", lambda name: False)


class StageWorkloadChecks(unittest.TestCase):
    evidence = []

    @classmethod
    def setUpClass(cls):
        if not (ROOT / "tools" / "stage_workload.py").is_file():
            raise unittest.SkipTest("tools/stage_workload.py is not in this tree")

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: True, observe=observe,
                              check=lambda: ("PASS" if observe() == expected else "FAIL", name),
                              neutralise=neutralise)
        StageWorkloadChecks.evidence.append(result)

    def test_an_adapter_build_stages_without_its_key_and_with_its_own_items(self):
        """Neutralised: the whole bundle is copied; the key travels and the sealer refuses."""
        self.prove("adapter_build_staged", observe_adapter, ADAPTER, whole_bundle_copied)

    def test_a_multi_round_bundle_stages_byte_for_byte_with_its_case(self):
        """Neutralised: members copied in text mode; a CRLF document's bytes change."""
        self.prove("generator_bundle_staged", observe_generator, GENERATOR, text_mode_copy)

    def test_a_file_named_like_a_key_refuses_the_staging(self):
        """Neutralised: no name filter; every key-named file is copied."""
        self.prove("key_named_file_refused", observe_key_refusal, KEY_REFUSAL, no_key_filter)


def check():
    StageWorkloadChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StageWorkloadChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    if result.skipped:
        return "SKIP", "staging checks skipped: %s" % result.skipped[0][1]
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: an adapter build and a multi-round "
                    "generator bundle staged by tools/stage_workload.py are accepted by the sealer's "
                    "workload_members, carry no key file and keep every source byte, each B1 item table holds "
                    "only its own document's items and is sealed by b1_fields, and a file named like a key "
                    "refuses the staging with nothing written" % result.testsRun)


def main():
    status, detail = check()
    for proof in StageWorkloadChecks.evidence:
        print(proof["name"], proof["status"])
        print("  before:  ", json.dumps(proof["before"], sort_keys=True)[:400])
        print("  mutated: ", json.dumps(proof["mutated"], sort_keys=True)[:400])
        print("  restored:", json.dumps(proof["restored"], sort_keys=True)[:400])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
