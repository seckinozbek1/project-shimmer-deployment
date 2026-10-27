# Gate baselines

Every gate result in the loop is compared with the baseline of its own environment, never with zero (IV.7). A baseline is recorded the first time the gate runs in an environment.

## Environment 1: the main checkout (S0, 2026-10-27)

- **Tree.** `main` at `f31eff4`, plus the loop's uncommitted `.gitignore` line and its new untracked files under `tools/loop/` and `docs/loop/` (none of them read by a gate check).
- **Interpreter.** `py -3.12` (anaconda Python 3.12) with `KMP_DUPLICATE_LIB_OK=TRUE` (decision D-006). It has no `fastapi`, `uvicorn` or `pypdf`. Nothing was installed.
- **Command.** `py -3.12 -X utf8 scripts/verify_session1.py`. Run time 270 seconds. The raw log stays private (it carries temporary-folder paths).
- **Network.** Not blocked; `--offline` not used, as in every earlier laptop baseline. Check 16 cannot reach a paid provider: it builds its extractor with an empty key, and the extractor calls the provider only when a key is set (`scripts/claim_classifier.py`, `extract`). Other gate paths that build a model wrapper pass placeholder keys to patched clients.

### Main gate: 275 entries (00 to 274)

**PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28.** This equals the last recorded laptop gate (`docs/fix/ordinary_final_v13_gates/main_gate_after_274.log`: PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28), with the same check numbers.

| Check | Result | Reason printed by the gate | Cause |
|---|---|---|---|
| 01 | SKIP | local directory coverage unavailable for `snapshots/` (exists only after a snapshot is saved) | Tree state |
| 38 | WARN | fpdf2/pypdf not installed; cannot exercise full store build | Interpreter (no `pypdf`) |
| 145 | SKIP | `tests/fixtures/planted_figure_hashes.json` is an optional local fixture not present | Tree state |
| 261 | SKIP | 17 fixture-only cases passed; 1 unavailable check; no generation | Tree state (an unavailable case) |
| 91, 96, 101, 108, 110, 126, 129, 140, 196, 203, 210, 213, 214, 247, 250, 251, 259 | ERROR | `ModuleNotFoundError: No module named 'fastapi'` | Interpreter (no `fastapi`) |
| 117 | FAIL | `import scripts.server` from the repo root failed | Interpreter (no `fastapi`) |
| 118 | FAIL | `scripts/server.py` imports `uvicorn` at module level and it is not installed | Interpreter (no `uvicorn`) |
| 121 | FAIL | 1 module under `scripts/` does not import: server (no `fastapi`) | Interpreter (no `fastapi`) |
| 257 | FAIL | startup submission proof failed: ModuleNotFoundError | Interpreter (missing module) |
| 255 | FAIL | desktop startup fixture failed (StartupFailure) | Not established at S0; the desktop server needs the server stack, so most likely the missing `fastapi` |
| 146 | FAIL | the compared prompt carries no convention registry section | Not established at S0 |
| 193 | FAIL | BAD PROOF: removing snapshot resolution caused no network attempt | Not established at S0 (depends on the local model cache) |
| 246 | FAIL | pipeline completion is not marked at its final return boundary | Not established at S0 |
| 248 | FAIL | the real consumer proof failed: BASELINE_FAILED | Not established at S0 |
| 112 | FAIL | `scripts/agent_wrapper.py:1783` interpolates a content-bearing expression (the event name contains the word `prompt`) | **Code, not environment.** The check reads source text. Recorded for S1 Part 4, which changes `agent_wrapper.py` (P16). |
| 252 | FAIL | the product image build does not execute the shipping gate | **Code, not environment.** The check requires the exact Dockerfile line `RUN python scripts/ship_gate.py`; `Dockerfile:153` reads `RUN /opt/shimmer-runtime/bin/python scripts/ship_gate.py`. Recorded for the stage that changes the Dockerfile (S10 or S11) and in `docs/fix/OPEN_ITEMS.md`. |

The earlier comparison record (`main_gate_comparison_274.json`) put all 28 reds down to the interpreter. Checks 112 and 252 fail on the source text itself, so that attribution is corrected here (P1). The causes marked "not established" are recorded as they are; they are not re-diagnosed in S0.

### Side gates (same interpreter, run one at a time after the main gate)

| Side gate | Exit | Seconds | Result |
|---|---|---|---|
| `scripts/execution_topology_no_generation_gate.py` | 0 | 6 | unit tests: 23 OK, then 18 OK with 1 skipped; its subset of main-gate checks PASS; "Full gate: NOT RUN (contains prohibited model/GPU checks)" by design |
| `scripts/report_recommendations_no_generation_gate.py` | 0 | 6 | 40 tests OK; `ORDINARY_SAFE_GATE {'PASS': 49, 'FAIL': 0, 'SKIP': 1}` |
| `scripts/final_integration_no_generation_gate.py` | 0 | 13 | passed, 0 failures, 0 errors; model loads 0; network not allowed |
| `scripts/localization_no_generation_gate.py` | 0 | 8 | 23 OK, then 18 OK with 1 skipped |
| `tools/cloud_run_checks.py` | 0 | 10 | passed, 83 tests, 0 failures, 0 errors, 0 skipped; network blocked |
| `tools/ordinary_final_controller_gate.py --output-dir <private folder>` | 0 | 29 | passed, 0 failures, 0 errors (it requires `--output-dir`; a first call without it exited 2 with the usage message) |

Every later side-gate run is compared with these figures.
