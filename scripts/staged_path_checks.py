"""Gate check 275: the staged-path refusal in guard_secrets.

A seal manifest (``seals/``) must never be committed, even when force-added past
``.gitignore`` (Annex B.3 of the 2026-10-27 loop). ``guard_secrets.py --staged``
reads git's own staged-name list and refuses such a path, and likewise any path
with the segment ``audit/model_replies/`` at any depth (a run folder's saved
model replies, scripts/reply_records.py). The path test is a
pure function, proven on name lists; the git-backed cases run only where git is
installed (the container image has no git, so there they are skipped with the
reason, never failed).
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import guard_secrets as gs


def _git(root, *args):
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True)


class StagedPathChecks(unittest.TestCase):
    def test_name_list_refuses_seals_only(self):
        names = ["seals/manifest_01.json", "docs/readme.md", "benchmark/seals_note.md",
                 "tools/seals/x.json", "seals\\windows_form.json"]
        self.assertEqual(gs.refused_staged_paths(names),
                         ["seals/manifest_01.json", "seals\\windows_form.json"])
        self.assertEqual(gs.refused_staged_paths(["scripts/pipeline.py"]), [])

    def test_git_staged_and_force_added_seals_are_refused(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed here (for example inside the container image)")
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_paths_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            (root / "docs").mkdir()
            (root / "docs" / "note.md").write_text("ordinary\n", encoding="utf-8")
            _git(root, "add", "docs/note.md")
            self.assertEqual(gs.main_staged(root), 0, "an ordinary staged path must pass")
            (root / "seals").mkdir()
            (root / "seals" / "plain.json").write_text("{}\n", encoding="utf-8")
            _git(root, "add", "seals/plain.json")
            self.assertEqual(gs.refused_staged_paths(gs.staged_names(root)), ["seals/plain.json"])
            self.assertEqual(gs.main_staged(root), 1, "a staged seals/ path must be refused")
            _git(root, "rm", "-q", "--cached", "seals/plain.json")
            (root / ".gitignore").write_text("seals/\n", encoding="utf-8")
            (root / "seals" / "forced.json").write_text("{}\n", encoding="utf-8")
            _git(root, "add", "-f", "seals/forced.json")
            self.assertEqual(gs.refused_staged_paths(gs.staged_names(root)), ["seals/forced.json"])
            self.assertEqual(gs.main_staged(root), 1, "a force-added seals/ path must be refused")

    def test_name_list_refuses_model_replies_at_any_depth(self):
        names = ["audit/model_replies/r.json", "run/x/audit/model_replies/r.json",
                 "output\\runs\\a\\audit\\model_replies\\0001_c.json",
                 "run/x/audit/model_replies_note.md", "run/x/audit/contract_violations/a.txt",
                 "docs/audit/model_replies.md", "run/x/myaudit/model_replies/r.json"]
        self.assertEqual(gs.refused_staged_paths(names),
                         ["audit/model_replies/r.json", "run/x/audit/model_replies/r.json",
                          "output\\runs\\a\\audit\\model_replies\\0001_c.json"])

    def test_git_staged_and_force_added_model_replies_are_refused(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed here (for example inside the container image)")
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_replies_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            folder = root / "run" / "x" / "audit" / "model_replies"
            folder.mkdir(parents=True)
            (folder / "r.json").write_text("{}\n", encoding="utf-8")
            _git(root, "add", "run/x/audit/model_replies/r.json")
            self.assertEqual(gs.refused_staged_paths(gs.staged_names(root)),
                             ["run/x/audit/model_replies/r.json"])
            self.assertEqual(gs.main_staged(root), 1, "a staged model_replies path must be refused")
            _git(root, "rm", "-q", "--cached", "run/x/audit/model_replies/r.json")
            self.assertEqual(gs.main_staged(root), 0, "an empty index must pass")
            (root / ".gitignore").write_text("**/audit/model_replies/\n", encoding="utf-8")
            _git(root, "add", "-f", "run/x/audit/model_replies/r.json")
            self.assertEqual(gs.refused_staged_paths(gs.staged_names(root)),
                             ["run/x/audit/model_replies/r.json"])
            self.assertEqual(gs.main_staged(root), 1, "a force-added model_replies path must be refused")


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StagedPathChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        return ("FAIL", f"{len(result.failures)} failures, {len(result.errors)} errors")
    ran = result.testsRun - len(result.skipped)
    if result.skipped:
        return ("SKIP", f"{ran} name-list case(s) passed; git-backed case skipped: {result.skipped[0][1]}")
    return ("PASS", f"{ran} cases: name lists and a real git index refuse staged and force-added seals/ "
                    f"and audit/model_replies/ paths; ordinary paths pass")


if __name__ == "__main__":
    unittest.main()
