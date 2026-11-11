"""Gate check: the user guides and the clean-install check (D-S32 item 5).

A guide goes stale silently, so every checkable statement in docs/GUIDE_EN.md and docs/GUIDE_TR.md
is held to the repository: each path and file name exists or is a declared deliverable, each
command's script exists, each label in bold is one the console or the starter window shows in that
guide's language, the model's mark is the code's own sentence, and the quoted finding is what the
worked case's run writes, figure for figure. This holds what the guides name, not whether they
explain it well: nothing here reads the second-language guide for style.

tools/clean_install_check.py is held on its verdict logic with injected steps, and its no-model
step runs for real. The install itself is never run here: it needs the network, several gigabytes
and a machine to spare.

Each is neutralise, fail, restore, pass (scripts/effect_proof.py).
"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from effect_proof import prove_effect  # noqa: E402
import finding_record  # noqa: E402
from run_context import DELIVERABLE_FILENAMES, RUN_SUMMARY_NAME  # noqa: E402



def _tool():
    """tools/clean_install_check.py, by its path: a module-level import of a file outside
    scripts/ is what check 118 refuses. Loaded once, so a neutralisation patches the one observed."""
    if "module" not in _TOOL:
        spec = importlib.util.spec_from_file_location("shimmer_clean_install_check",
                                                      ROOT / "tools" / "clean_install_check.py")
        _TOOL["module"] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_TOOL["module"])
    return _TOOL["module"]


_TOOL = {}
GUIDES = {"en": ROOT / "docs" / "GUIDE_EN.md", "tr": ROOT / "docs" / "GUIDE_TR.md"}
CONSOLE = ROOT / "scripts" / "ui" / "console.html"
CATALOG = ROOT / "scripts" / "ui" / "localization_catalog.js"
STARTER = ROOT / "scripts" / "desktop_launcher.py"
# Bold text in the guides that is not a label of a screen: the two backends' names and the
# second-language guide's words for what it explains.
NOT_LABELS = {"en": {"Local", "Cloud", "The unit", "The rule", "The figures", "A REF number"},
              "tr": {"Local", "Cloud", "Birim", "Kural", "Sayılar", "REF numarası"}}
# Named in the guides, read or written at run time, so not in the repository.
RUN_TIME_PATHS = {"output/runs/", "../api_keys/config.py", ".env_path", "audit/model_replies/", ".venv",
                  ".venv/bin/python", "SHIMMER_CONFIG_PATH"}
FILE_SHAPED = re.compile(r"[\w./-]+\.(?:md|py|bat|sh|json|docx)\b|[\w.-]+/(?:[\w.-]+/)*")


def _text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _catalog():
    return dict(re.findall(r'^\s*"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)",?\s*$', _text(CATALOG), re.M))


def _starter_labels():
    return set(re.findall(r'text="([^"]{3,60})"', _text(STARTER)))


def _shown(language):
    """The strings a user of this guide sees."""
    console = _text(CONSOLE)
    english = {k for k in _catalog() if k in console} | {
        m for m in re.findall(r">([^<>]{3,80})<", console)}
    shown = set(_catalog().values()) if language == "tr" else english
    return shown | _starter_labels()


def unknown_labels(language):
    text = _text(GUIDES[language])
    shown = _shown(language)
    return sorted(b for b in set(re.findall(r"\*\*([^*]+)\*\*", text)) - NOT_LABELS[language]
                  if b not in shown and not any(b in s for s in shown))


def _known_names():
    return set(DELIVERABLE_FILENAMES.values()) | {RUN_SUMMARY_NAME}


def _marks():
    return {"en": finding_record.MODEL_FINDING_MARK, "tr": _catalog()[finding_record.MODEL_FINDING_MARK]}


def unknown_paths(language):
    """Everything in backticks shaped like a file or folder that is neither there nor expected."""
    names = _known_names()
    out = []
    for token in re.findall(r"`([^`\n]+)`", _text(GUIDES[language])):
        for word in token.split():
            hit = FILE_SHAPED.fullmatch(word.strip("."))
            if not hit or word in RUN_TIME_PATHS or word in names or word.startswith(".."):
                continue
            if not (ROOT / word).exists():
                out.append(word)
    return sorted(set(out))


def links_broken(language):
    return sorted(link for link in re.findall(r"\]\(([^)#]+)\)", _text(GUIDES[language]))
                  if not (GUIDES[language].parent / link).exists())


def _finding_sentence():
    """The finding each guide quotes, from a real run of the computing layer on the worked case."""
    sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
    import python_only
    with tempfile.TemporaryDirectory(prefix="shimmer_guide_") as td:
        out = Path(td) / "run"
        python_only.run(str(_tool().stage_case(Path(td) / "bundle")), str(out))
        return "\n".join(_text(p) for p in out.rglob("review_findings.md"))


def quote_in_run(language, written):
    """The whole quoted sentence, word for word, stands in what the run wrote."""
    quote = re.search(r"^> (Unit .+)$", _text(GUIDES[language]), re.M)
    return bool(quote) and quote.group(1) in written


def observe_guides():
    written = _finding_sentence()
    marks = _marks()
    return {language: {"labels": unknown_labels(language), "paths": unknown_paths(language),
                       "links": links_broken(language), "mark": marks[language] in _text(GUIDES[language]),
                       "quote": quote_in_run(language, written),
                       "em_dash": chr(0x2014) in _text(GUIDES[language])} for language in GUIDES}


_CLEAN = {"labels": [], "paths": [], "links": [], "mark": True, "quote": True, "em_dash": False}
GUIDES_OK = {"en": _CLEAN, "tr": _CLEAN}


def observe_verdict():
    def fails():
        raise _tool().Failed("stand-in")
    passed = [("a", lambda: "ok"), ("b", lambda: "ok")]
    stopped = _tool().perform([("a", fails), ("b", lambda: "ok")])
    return {"all_passed": _tool().verdict(_tool().perform(passed), clean=True)[0],
            "a_step_failed": _tool().verdict(stopped, clean=True)[0],
            "later_step_not_run": stopped[1]["status"],
            "no_install_is_not_clean": "not a clean install" in _tool().verdict(_tool().perform(passed), clean=False)[1]}


VERDICT = {"all_passed": 0, "a_step_failed": 1, "later_step_not_run": "NOT_RUN", "no_install_is_not_clean": True}


def observe_folder_refused():
    with tempfile.TemporaryDirectory(prefix="shimmer_venv_") as td:
        (Path(td) / "already_here").write_text("x", encoding="utf-8")
        try:
            _tool().step_venv(sys.executable, td, runner=lambda *a, **k: (0, "", ""))
        except _tool().Failed as exc:
            return str(exc).split(":")[0]
        except Exception as exc:
            return type(exc).__name__
    return "not refused"


def observe_no_model_step():
    with tempfile.TemporaryDirectory(prefix="shimmer_no_model_") as td:
        return {"real_run": _tool().step_no_model(sys.executable, td).startswith("completed with no model call"),
                "a_model_call_fails": _tool().judge_no_model_run(
                    {"state": "completed", "model_calls": 1}, [{"relation": "sum_mismatch", "value_a": 2100000.0,
                                                                "value_b": 2200000.0}]) is not None,
                "no_finding_fails": _tool().judge_no_model_run({"state": "completed", "model_calls": 0}, []) is not None}


NO_MODEL = {"real_run": True, "a_model_call_fails": True, "no_finding_fails": True}


def observe_console_judged():
    good = {"health": 200, "console": 200, "runs_no_token": 401, "runs_with_token": 200}
    return {"good": _tool().judge_console(good), "open_to_anyone": _tool().judge_console(dict(good, runs_no_token=200)) is not None}


CONSOLE_JUDGED = {"good": None, "open_to_anyone": True}


class ProductPackageChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        ProductPackageChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_labels(self):
        self.prove("guide_labels_are_on_screen", observe_guides, GUIDES_OK,
                   lambda: patch.object(sys.modules[__name__], "_shown", lambda language: set()))

    def test_paths(self):
        self.prove("guide_paths_exist", observe_guides, GUIDES_OK,
                   lambda: patch.object(sys.modules[__name__], "_known_names", set))

    def test_the_quote(self):
        self.prove("guide_quote_is_what_a_run_writes", observe_guides, GUIDES_OK,
                   lambda: patch.object(sys.modules[__name__], "_finding_sentence", lambda: ""))

    def test_the_mark(self):
        self.prove("guide_mark_is_the_codes", observe_guides, GUIDES_OK,
                   lambda: patch.object(sys.modules[__name__], "_marks", lambda: {"en": "Another.", "tr": "Başka."}))

    def test_verdict(self):
        self.prove("a_failed_step_fails_the_check", observe_verdict, VERDICT,
                   lambda: patch.object(_tool(), "verdict", lambda rows, clean: (0, "passed")))

    def test_folder(self):
        self.prove("a_used_folder_is_refused", observe_folder_refused, "the environment folder is not empty",
                   lambda: patch.object(_tool().Path, "iterdir", lambda self: iter(())))

    def test_no_model_step(self):
        self.prove("the_no_model_step_is_judged", observe_no_model_step, NO_MODEL,
                   lambda: patch.object(_tool(), "judge_no_model_run", lambda status, findings: None))

    def test_console(self):
        self.prove("the_console_must_need_a_token", observe_console_judged, CONSOLE_JUDGED,
                   lambda: patch.object(_tool(), "judge_console", lambda statuses: None))


def check():
    ProductPackageChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(ProductPackageChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: what both guides name is in the repository and "
                    "on screen, the finding they quote is what a run writes, and the clean-install check fails on a "
                    "failed step, a used folder, a model call or an open console" % len(ProductPackageChecks.evidence))


def main():
    status, detail = check()
    for proof in ProductPackageChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
