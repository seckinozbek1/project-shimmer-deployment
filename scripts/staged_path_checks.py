"""Gate check 275: the staged-path refusal in guard_secrets.

A seal manifest (``seals/``) must never be committed, even when force-added past
``.gitignore`` (Annex B.3 of the 2026-10-27 loop). ``guard_secrets.py --staged``
reads git's own staged-name list and refuses such a path, and likewise any path
with the segment ``audit/model_replies/`` (a run folder's saved model replies,
scripts/reply_records.py). Both segments are refused at any depth and
case-insensitively (Windows .gitignore matches case-insensitively). A staged
deletion is allowed, so a file committed by mistake can be removed. A staged
archive is read from the index (`:0:<path>`, the literal path) with the reader
its SUFFIX names (never by sniffing): a tar (.tar, .tar.gz, .tgz, .tar.xz, .txz,
.tar.bz2, .tbz2) is streamed from git and never holds the archive's bytes in
memory, through every gzip member or bz2/xz stream, and anything after the tar's
end that is not zero bytes (a second tar joined on) is refused; a .zip above
ZIP_SIZE_CAP is refused unread with the limit named; an archive or compressed
suffix the guard cannot read (.7z, .rar, .zst, .tzst, .lz4, a bare .gz, .bz2 or
.xz) is refused unread. It is refused when a member name carries a refused
segment, or when it cannot be read in full, a MemoryError included (fail
closed): the controller packs project/output into collected_evidence.tar.gz,
which has been force-committed under docs/fix/ before. A failed `git diff
--cached` refuses with one line, and every printed name stays on one line.

The path test is a pure function, proven on name lists; the archive test is a
pure function over bytes; the git-backed cases run only where git is installed
(the container image has no git, so there they are skipped with the reason,
never failed).
"""
import contextlib
import gzip
import io
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import guard_secrets as gs

REPLY = "run/audit/model_replies/r.json"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True,
                          text=True).stdout


class _Bounded:
    """A reader that fails if anyone asks it for the whole stream at once."""

    def __init__(self, raw):
        self.raw = raw

    def read(self, size=-1):
        if size is None or size < 0 or size > gs._CHUNK:
            raise AssertionError("a tar was read whole")
        return self.raw.read(size)


def _bounded_stream(real):
    @contextlib.contextmanager
    def opener(root, name):
        with real(root, name) as raw:
            yield _Bounded(raw)
    return opener


def _commit(root, message):
    _git(root, "-c", "user.name=gate", "-c", "user.email=gate@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)


def _tar_gz(members, mode="w:gz"):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _need_git(case):
    if shutil.which("git") is None:
        case.skipTest("git is not installed here (for example inside the container image)")


class StagedPathChecks(unittest.TestCase):
    def test_name_list_refuses_seals_at_any_depth(self):
        names = ["seals/manifest_01.json", "docs/readme.md", "benchmark/seals_note.md",
                 "tools/seals/x.json", "seals\\windows_form.json", "a/b/seals/deep.json",
                 "unseals/x.json", "docs/seals.md"]
        self.assertEqual(gs.refused_staged_paths(names),
                         ["seals/manifest_01.json", "tools/seals/x.json",
                          "seals\\windows_form.json", "a/b/seals/deep.json"])
        self.assertEqual(gs.refused_staged_paths(["scripts/pipeline.py"]), [])

    def test_name_list_case_variants_are_refused(self):
        names = ["Seals/x.json", "SEALS/y.json", "run/Audit/Model_Replies/r.json",
                 "tools/SeAlS/z.json", "Benchmark/Seals_Note.md"]
        self.assertEqual(gs.refused_staged_paths(names),
                         ["Seals/x.json", "SEALS/y.json", "run/Audit/Model_Replies/r.json",
                          "tools/SeAlS/z.json"])

    def test_name_list_refuses_model_replies_at_any_depth(self):
        names = ["audit/model_replies/r.json", "run/x/audit/model_replies/r.json",
                 "output\\runs\\a\\audit\\model_replies\\0001_c.json",
                 "run/x/audit/model_replies_note.md", "run/x/audit/contract_violations/a.txt",
                 "docs/audit/model_replies.md", "run/x/myaudit/model_replies/r.json"]
        self.assertEqual(gs.refused_staged_paths(names),
                         ["audit/model_replies/r.json", "run/x/audit/model_replies/r.json",
                          "output\\runs\\a\\audit\\model_replies\\0001_c.json"])

    def test_archive_bytes_are_read_in_memory(self):
        self.assertTrue(gs.is_archive_name("docs/fix/collected_evidence.tar.gz"))
        self.assertTrue(gs.is_archive_name("x/Y.ZIP"))
        self.assertTrue(gs.is_archive_name("a.tgz") and gs.is_archive_name("a.tar"))
        for name in ("a.tar.xz", "a.txz", "a.tar.bz2", "a.TBZ2"):
            self.assertTrue(gs.is_archive_name(name), name)
        self.assertFalse(gs.is_archive_name("docs/fix/notes.gz.md"))
        self.assertIsNotNone(gs.archive_refusal("e.tar.gz",
                                                _tar_gz({"run/audit/model_replies/r.json": b"{}"})))
        self.assertIsNotNone(gs.archive_refusal("e.tgz",
                                                _tar_gz({"./project/output/Seals/m.json": b"{}"})))
        self.assertIsNotNone(gs.archive_refusal("b.zip", _zip({"seals/m.json": b"{}"})))
        self.assertIsNone(gs.archive_refusal("e.tar.gz",
                                             _tar_gz({"run/audit/pairing_map.json": b"{}",
                                                      "benchmark/seals_note.md": b"x"})))
        self.assertIsNone(gs.archive_refusal("b.zip", _zip({"docs/readme.md": b"x"})))
        self.assertEqual(gs.archive_refusal("x.tar.gz", b"this is not an archive"), "unreadable archive")
        self.assertEqual(gs.archive_refusal("x.zip", b"this is not an archive"), "unreadable archive")
        self.assertEqual(gs.archive_refusal("x.tar.gz", _tar_gz({"a.txt": b"x"})[:40]),
                         "unreadable archive")

    def test_xz_and_bz2_tars_are_inspected(self):
        refused = {"ok.txt": b"x", "run/audit/model_replies/r.json": b"{}"}
        for name, mode in (("e.tar.xz", "w:xz"), ("e.txz", "w:xz"),
                           ("e.tar.bz2", "w:bz2"), ("e.tbz2", "w:bz2"), ("e.tar", "w")):
            reason = gs.archive_refusal(name, _tar_gz(refused, mode))
            self.assertIsNotNone(reason, name)
            self.assertIn("run/audit/model_replies/r.json", reason, name)
            self.assertIsNone(gs.archive_refusal(name, _tar_gz({"ok.txt": b"x"}, mode)), name)

    def test_reader_is_chosen_by_suffix_never_by_sniffing(self):
        # A plain tar whose LAST member is a small zip: the zip's end record sits
        # in the tar's tail, so sniffing calls the whole tar a clean zip.
        tail_zip = _zip({"docs/readme.md": b"x"})
        data = _tar_gz({"seals/m.json": b"{}", "z.zip": tail_zip}, "w")
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(data)), "the trap must be real")
        reason = gs.archive_refusal("bundle.tar", data)
        self.assertIsNotNone(reason)
        self.assertIn("seals/m.json", reason)
        # The wrong reader for the suffix is not tried: it is refused unread.
        self.assertEqual(gs.archive_refusal("named.zip", _tar_gz({"ok.txt": b"x"})),
                         "unreadable archive")
        self.assertEqual(gs.archive_refusal("named.tar.gz", _zip({"ok.txt": b"x"})),
                         "unreadable archive")

    def test_joined_tars_and_gzip_members_are_read_in_full_or_refused(self):
        first = _tar_gz({"ok.txt": b"x"}, "w")
        second = _tar_gz({REPLY: b"{}"}, "w")
        # Two tars joined: the reader stops at the first end marker, and the
        # second tar after it is not zero bytes, so the whole is refused.
        self.assertEqual(gs.archive_refusal("joined.tar", first + second), "unreadable archive")
        self.assertIsNone(gs.archive_refusal("joined.tar", first))
        # A non-zero block where the end marker belongs is refused too.
        self.assertEqual(gs.archive_refusal("bad.tar", first[:1024] + b"\x01" * 512 + bytes(1024)),
                         "unreadable archive")
        # Two gzip members joined, the refused member only in the second: read.
        whole = _tar_gz({"ok.txt": b"x", REPLY: b"{}"}, "w")
        two = gzip.compress(whole[:1024]) + gzip.compress(whole[1024:])
        self.assertNotIn(REPLY.encode(), whole[:1024], "the refused member must be in member two")
        reason = gs.archive_refusal("two.tar.gz", two)
        self.assertIsNotNone(reason)
        self.assertIn(REPLY, reason)

    def test_unreadable_suffixes_are_refused_unread(self):
        for name in ("a.7z", "a.rar", "a.zst", "a.tzst", "a.lz4", "a.gz", "a.BZ2", "a.xz",
                     "a.tar.zst"):
            self.assertTrue(gs.is_archive_name(name), name)
            self.assertEqual(gs.archive_refusal(name, gzip.compress(_tar_gz({"ok.txt": b"x"}))),
                             "unreadable archive", name)
        self.assertIsNone(gs.archive_refusal("notes.md", b"x"))
        self.assertIsNone(gs.archive_refusal("e.tar.gz", _tar_gz({"ok.txt": b"x"})))

    def test_size_cap_and_memory_error_are_one_line_refusals(self):
        self.assertIn("512 MiB", gs.too_large())
        self.assertIn("repack as .tar.gz", gs.too_large())
        data = _zip({"docs/readme.md": b"x" * 64})
        with mock.patch.object(gs, "ZIP_SIZE_CAP", 16):
            reason = gs.archive_refusal("big.zip", data)
        self.assertEqual(reason, "archive too large to inspect (over 16 bytes); repack as .tar.gz")
        self.assertNotIn("\n", reason)
        with mock.patch.object(gs, "tar_refusal", side_effect=MemoryError):
            self.assertEqual(gs.archive_refusal("e.tar.gz", _tar_gz({"a": b"x"})),
                             "unreadable archive")
        with mock.patch.object(gs, "zip_refusal", side_effect=MemoryError):
            self.assertEqual(gs.archive_refusal("b.zip", data), "unreadable archive")

    def test_git_staged_and_force_added_seals_are_refused(self):
        _need_git(self)
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

    def test_git_staged_and_force_added_model_replies_are_refused(self):
        _need_git(self)
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

    def test_git_staged_archives_are_read_from_the_index(self):
        _need_git(self)
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_archives_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            fix = root / "docs" / "fix"
            fix.mkdir(parents=True)
            clean = fix / "collected_evidence.tar.gz"
            clean.write_bytes(_tar_gz({"project/output/runs/a/audit/pairing_map.json": b"{}"}))
            _git(root, "add", "docs/fix/collected_evidence.tar.gz")
            self.assertEqual(gs.staged_refusals(root), [])
            self.assertEqual(gs.main_staged(root), 0, "an archive of ordinary members must pass")
            # The STAGED blob is read, not the working tree: a clean working copy
            # does not excuse a refused member in the index.
            clean.write_bytes(_tar_gz({"run/audit/model_replies/r.json": b"{}"}))
            _git(root, "add", "docs/fix/collected_evidence.tar.gz")
            clean.write_bytes(_tar_gz({"ordinary.txt": b"x"}))
            refusals = gs.staged_refusals(root)
            self.assertEqual([name for name, _ in refusals], ["docs/fix/collected_evidence.tar.gz"])
            self.assertIn("run/audit/model_replies/r.json", refusals[0][1])
            self.assertEqual(gs.main_staged(root), 1, "a tar.gz holding model replies must be refused")
            _git(root, "rm", "-q", "-f", "--cached", "docs/fix/collected_evidence.tar.gz")
            (fix / "bundle.zip").write_bytes(_zip({"seals/m.json": b"{}"}))
            _git(root, "add", "docs/fix/bundle.zip")
            self.assertEqual(gs.main_staged(root), 1, "a zip holding seals/ must be refused")
            _git(root, "rm", "-q", "--cached", "docs/fix/bundle.zip")
            (fix / "broken.tar.gz").write_bytes(b"not an archive at all")
            _git(root, "add", "docs/fix/broken.tar.gz")
            self.assertEqual(gs.staged_refusals(root),
                             [("docs/fix/broken.tar.gz", "unreadable archive")])

    def test_git_staged_tars_stream_and_zips_respect_the_size_cap(self):
        _need_git(self)
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_stream_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            fix = root / "docs" / "fix"
            fix.mkdir(parents=True)
            # A tar is never read whole: git's pipe is wrapped in a reader that
            # fails on any whole or oversized read, and the refused member is
            # still named (so it was streamed).
            whole = mock.patch.object(gs, "_staged_stream", _bounded_stream(gs._staged_stream))
            tail_zip = _zip({"docs/readme.md": b"x"})
            (fix / "plain.tar").write_bytes(_tar_gz({"seals/m.json": b"{}", "z.zip": tail_zip}, "w"))
            (fix / "e.tar.xz").write_bytes(_tar_gz({"run/audit/model_replies/r.json": b"{}"}, "w:xz"))
            (fix / "ok.tar.bz2").write_bytes(_tar_gz({"ok.txt": b"x" * 4096}, "w:bz2"))
            for name in ("plain.tar", "e.tar.xz", "ok.tar.bz2"):
                _git(root, "add", "docs/fix/" + name)
            with whole:
                refusals = dict(gs.staged_refusals(root))
            self.assertEqual(sorted(refusals), ["docs/fix/e.tar.xz", "docs/fix/plain.tar"])
            self.assertIn("seals/m.json", refusals["docs/fix/plain.tar"])
            self.assertIn("run/audit/model_replies/r.json", refusals["docs/fix/e.tar.xz"])
            for name in ("plain.tar", "e.tar.xz", "ok.tar.bz2"):
                _git(root, "rm", "-q", "--cached", "docs/fix/" + name)
            # A zip above the cap is refused unread, with one line.
            (fix / "bundle.zip").write_bytes(_zip({"docs/readme.md": b"x" * 64}))
            _git(root, "add", "docs/fix/bundle.zip")
            self.assertEqual(gs.staged_refusals(root), [])
            with mock.patch.object(gs, "ZIP_SIZE_CAP", 16), \
                    mock.patch.object(gs, "_staged_stream",
                                      side_effect=AssertionError("a large zip was read")):
                self.assertEqual(gs.staged_refusals(root),
                                 [("docs/fix/bundle.zip",
                                   "archive too large to inspect (over 16 bytes); "
                                   "repack as .tar.gz")])
            _git(root, "rm", "-q", "--cached", "docs/fix/bundle.zip")
            # A MemoryError from the tar reader becomes "unreadable archive".
            _git(root, "add", "docs/fix/ok.tar.bz2")
            with mock.patch.object(gs, "tar_refusal", side_effect=MemoryError):
                self.assertEqual(gs.staged_refusals(root),
                                 [("docs/fix/ok.tar.bz2", "unreadable archive")])
            self.assertEqual(gs.staged_refusals(root), [])

    def test_git_staged_compressed_tars_odd_names_and_unreadable_suffixes(self):
        _need_git(self)
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_kinds_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            _git(root, "config", "core.protectNTFS", "false")
            refused = {"ok.txt": b"x", REPLY: b"{}"}
            names = {"e.tgz": "w:gz", "e.txz": "w:xz", "e.tbz2": "w:bz2"}
            for name, mode in names.items():
                (root / name).write_bytes(_tar_gz(refused, mode))
                _git(root, "add", name)
            (root / "joined.tar").write_bytes(_tar_gz({"ok.txt": b"x"}, "w")
                                              + _tar_gz({REPLY: b"{}"}, "w"))
            (root / "a.7z").write_bytes(b"7z\xbc\xaf\x27\x1c not read")
            (root / "a.gz").write_bytes(gzip.compress(_tar_gz({"ok.txt": b"x"})))
            # A non-ASCII name comes back from git as itself (decoded as UTF-8).
            (root / "été.tar").write_bytes(_tar_gz({REPLY: b"{}"}, "w"))
            for name in ("joined.tar", "a.7z", "a.gz", "été.tar"):
                _git(root, "add", name)
            expected = ["a.7z", "a.gz", "e.tbz2", "e.tgz", "e.txz", "joined.tar", "été.tar"]
            # A name holding ":" cannot be written to disk on Windows, so its blob
            # goes into the index directly. As ":<name>" git would read "1:ok.tar"
            # as stage 1 of "ok.tar"; ":0:<name>" reads the literal path. Git for
            # Windows refuses ":" in any index path, so there the revision itself
            # is proven by test_git_is_asked_for_the_literal_stage_0_path.
            (root / "clean.bin").write_bytes(_tar_gz({"ok.txt": b"x"}, "w"))
            (root / "bad.bin").write_bytes(_tar_gz({REPLY: b"{}"}, "w"))
            try:
                for disk, staged in (("clean.bin", "1:ok.tar"), ("bad.bin", "1:bad.tar")):
                    blob = _git(root, "hash-object", "-w", disk).strip()
                    _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{staged}")
                expected.insert(0, "1:bad.tar")
            except subprocess.CalledProcessError:
                pass  # this git refuses ":" in an index path; "1:ok.tar" is clean anyway
            refusals = dict(gs.staged_refusals(root))
            self.assertEqual(sorted(refusals), sorted(expected))
            unreadable = ("a.7z", "a.gz", "joined.tar")
            for name in expected:
                if name in unreadable:
                    self.assertEqual(refusals[name], "unreadable archive", name)
                else:
                    self.assertIn(REPLY, refusals[name], name)

    def test_git_is_asked_for_the_literal_stage_0_path(self):
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, stdout="10\n", stderr="")

        def popen(args, **kwargs):
            calls.append((args, kwargs))
            raise OSError("no pipe in this test")

        with mock.patch.object(gs.subprocess, "run", run), \
                mock.patch.object(gs.subprocess, "Popen", popen):
            self.assertEqual(gs.staged_archive_refusal(Path("."), "1:x.zip"), "unreadable archive")
        self.assertEqual([args for args, _ in calls],
                         [["git", "cat-file", "-s", ":0:1:x.zip"], ["git", "show", ":0:1:x.zip"]])
        for _, kwargs in calls:
            self.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)
        self.assertEqual(calls[0][1].get("timeout"), gs.GIT_TIMEOUT)
        self.assertEqual(calls[0][1].get("encoding"), "utf-8")

    def test_failed_git_listing_and_odd_names_print_one_line(self):
        failed = subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal")
        out = io.StringIO()
        with mock.patch.object(gs.subprocess, "run", return_value=failed), \
                contextlib.redirect_stdout(out):
            self.assertEqual(gs.main_staged(Path(".")), 1)
        self.assertEqual(out.getvalue(),
                         "guard_secrets --staged: could not list staged paths; refusing\n")
        out = io.StringIO()
        with mock.patch.object(gs, "staged_names", return_value=["seals/a\nb.json"]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(gs.main_staged(Path(".")), 1)
        self.assertEqual(out.getvalue().splitlines()[0],
                         "BLOCKED seals/a\\nb.json: this path must never be committed")

    def test_git_staged_deletion_of_a_refused_path_is_allowed(self):
        _need_git(self)
        with tempfile.TemporaryDirectory(prefix="shimmer_staged_deletion_") as td:
            root = Path(td)
            _git(root, "init", "-q")
            (root / "seals").mkdir()
            (root / "seals" / "x.json").write_text("{}\n", encoding="utf-8")
            _git(root, "add", "seals/x.json")
            _commit(root, "a seal committed by mistake")
            _git(root, "rm", "-q", "--cached", "seals/x.json")
            self.assertEqual(gs.staged_names(root), [])
            self.assertEqual(gs.main_staged(root), 0, "removing a committed seals/ file must be allowed")


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StagedPathChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        return ("FAIL", f"{len(result.failures)} failures, {len(result.errors)} errors")
    ran = result.testsRun - len(result.skipped)
    if result.skipped:
        return ("SKIP", f"{ran} name-list and archive case(s) passed; git-backed cases skipped: "
                        f"{result.skipped[0][1]}")
    return ("PASS", f"{ran} cases: name lists and a real git index refuse staged and force-added "
                    f"seals/ and audit/model_replies/ paths at any depth and in any case, and "
                    f"staged archives holding them, unreadable, unreadable by suffix or too "
                    f"large; tars streamed through every gzip member and refused when bytes "
                    f"follow their end; readers chosen by suffix; literal :0: index paths; a "
                    f"failed git listing refuses; deletions and ordinary paths pass")


if __name__ == "__main__":
    unittest.main()
