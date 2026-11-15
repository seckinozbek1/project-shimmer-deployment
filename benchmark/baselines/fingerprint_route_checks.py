"""Proof of fingerprint_route (#260): prepare then finish gives exactly gate_leakage.fingerprint's output
for the same vectors, on a fixture part; no model is loaded."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (str(HERE), str(HERE.parent / "adapters")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fingerprint_route as fr  # noqa: E402
import embed_records as er  # noqa: E402
from common import gate_leakage as gl  # noqa: E402

TEXTS = ["The first public record holds more than eight words in its plain sentence here.",
         "A second public record also holds well over eight words of plain English text.",
         "The first public record holds more than eight words in its plain sentence here.",
         "Too short to count."]


def fake_embed(texts):
    rows = []
    for t in texts:
        seed = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
        v = np.random.default_rng(seed).standard_normal(er.DIM).astype(np.float32)
        rows.append(v / np.linalg.norm(v))
    return np.array(rows, dtype=np.float32)


class FingerprintRouteChecks(unittest.TestCase):
    def test_prepare_then_finish_equals_the_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            part = tmp / "public.json"
            part.write_text(json.dumps([{"text": t} for t in TEXTS]), encoding="utf-8")
            parts = [("public", str(part), None)]
            info = fr.prepare(parts, tmp / "route")
            keys = json.loads((tmp / "route" / "keys.json").read_text(encoding="utf-8"))
            self.assertEqual(info["rows"], len(keys))
            texts = fr._texts(parts)
            merged = tmp / "merged"
            merged.mkdir()
            vectors = np.lib.format.open_memmap(merged / "vectors.f32", mode="w+", dtype=np.float32, shape=(len(keys), er.DIM))
            vectors[:] = fake_embed([texts[k] for k in keys])
            vectors.flush()
            del vectors
            (merged / "state.json").write_text(json.dumps({"keys_sha256": er.key_digests(keys)["newline"], "dim": er.DIM,
                                                           "n": len(keys), "done": len(keys)}), encoding="utf-8")
            fr.finish(tmp / "route", merged, tmp / "fp.json")
            routed = json.loads((tmp / "fp.json").read_text(encoding="utf-8"))
            direct = json.loads(json.dumps(gl.fingerprint(parts, embed=fake_embed)))
            self.assertEqual(routed, direct)
            with self.assertRaises(ValueError):
                (merged / "state.json").write_text(json.dumps({"keys_sha256": "x", "dim": er.DIM, "n": len(keys), "done": len(keys)}),
                                                   encoding="utf-8")
                fr.finish(tmp / "route", merged, tmp / "fp2.json")


def check():
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(FingerprintRouteChecks).run(result)
    if result.failures or result.errors:
        return ("FAIL", (result.failures + result.errors)[0][1].strip().splitlines()[-1])
    with patch.object(fr, "_texts", lambda parts: {}):
        broken = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(FingerprintRouteChecks).run(broken)
    if broken.wasSuccessful():
        return ("FAIL", "neutralising the row texts did not fail the proof")
    return ("PASS", "prepare then finish equals gate_leakage.fingerprint for the same vectors; a merge for other keys is refused")


if __name__ == "__main__":
    print(check())
