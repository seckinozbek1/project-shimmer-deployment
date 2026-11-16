# Interface check for v1.0

Lane `lane/interface-check`, from the lead tip `6e63d91b`, 16 November 2026. Scope: every surface a
user sees, except the document reader wiring that lanes #280 and #281 change (`scripts/*layers*.py`
and the reader wiring were not touched). Line numbers are those of this branch after the fixes.

## What was run, and on what

No pipeline run, no real review, no whole gate. Everything below ran on this laptop on fixtures,
one process at a time, after reading free memory.

| Surface | How it was run | Result |
|---|---|---|
| `scripts/server.py` | FastAPI test client, empty run folder, every non-loopback socket refused | 43 routes; `/health` and `/console` answer with no token; `/docs`, `/redoc`, `/openapi.json` are off; every other route answers 401 without the token; the console page names no outside address |
| `scripts/intake_wizard.py` | `--help`; `--mode-only` and `--import-only` with piped answers that end in a decline | starts with no network; nothing placed, `config/review_scope.json` unchanged |
| `tools/build_demo.py` | built from `scripts/fixtures/demo/` into the session scratch folder, outside the repository | 2 cases, 12 files; no ISO date, no em dash, no second-person plural form |
| `scripts/ui/` | `localization_checks.js` (17 pass), `scripts/localization_checks.py` (22 pass), `scripts/demo_checks.py` (pass), `scripts/console_cloud_checks.py` (26 of 26) | pass |
| Launchers | `bash -n shimmer.sh`; gate checks 219, 222, 223, 307 one per process | pass |
| README commands | every named file checked on disk, every pipeline flag found in its argument parser, the CLI flags of `score_corpus.py`, `generate.py`, `cloud_run_checks.py` and `bus_viewer.py` read | all exist as written; `docs/history/COMMIT_MAP.md` is on the tag `loop-v1`, as the README says |
| Vocabulary | gate checks 174 and 22 | pass |

Gate checks not run here because one process alone went above about 400 MB: **220** (424 MB when
stopped), **308** (971 MB when stopped) and **333** (407 MB when stopped). **311** (the launcher arm,
which drives the real `shimmer.sh` and wizard) was not tried for the same reason. All four touch
the files this lane changed and belong in the next Lambda gate run. Check **257** fails with
`draft role mutation: OBSERVATION_ERROR` on the unchanged lead tip too (measured with this lane's
changes set aside), so this lane did not cause it.

## Fixed (14)

1. **The Turkish console spoke in the plural polite form throughout.**
   `scripts/ui/localization_catalog.js` (about 190 forms in about 140 rows, for example
   "Kararınız bekleniyor", "günlüğe bakın", "yeniden gönderebilirsiniz"), `scripts/ui/cloud_mode.js:11, 47, 57, 68, 77`,
   `scripts/console_cloud.py:58, 61`, the demo line in `scripts/ui/console.html`, the demo README in
   `tools/build_demo.py:436`, and the quoted sentence in `docs/CLOUD_CONSOLE.md`. Fix: every row in the
   singular form ("Kararın bekleniyor", "günlüğe bak", "yeniden gönderebilirsin"), word by word from a
   reviewed list, so a genitive such as "belgenin" is never touched; the check that quotes the demo
   line (`scripts/demo_checks.py:410`) follows. The same catalogue renders the Turkish deliverables,
   so they change the same way. Proof: the four UI check sets above pass; no old form is left in
   `scripts/`, `tools/` or `config/`.
2. **No Python found sent the user to a JSON file.** `tools/resolve_python.bat:7`, `shimmer.sh:41`
   said "No compatible Python found. See tools/cloud_run/runtime.json." Fix: "No Python 3.12 was found.
   Install Python 3.12 from python.org, then run this again."
3. **A wrong `.venv` named a JSON file.** `shimmer.bat:39`, `shimmer.sh:72`. Fix: "The Python in the
   .venv folder is not the version Shimmer needs, Python 3.12. Delete the .venv folder and run this
   script again."
4. **"(Add --help for all options.)" could not be followed from the menu.** `shimmer.bat:197, 232`,
   `shimmer.sh:244, 267`. Fix: the line names the command to type (`.venv\Scripts\python.exe
   scripts\pipeline.py --help`, and `$VENV_BIN/python ...` in the shell launcher).
5. **Menu option 4 did not say it loads models.** `shimmer.bat:149`, `shimmer.sh:202` showed "Run the
   verify gate", while the README says to run the full gate only on a machine prepared for it. Fix:
   "Run the full self-test (long; loads models; for a prepared machine)". The menu prompt itself,
   which the sealed launcher map reads, is unchanged.
6. **The Sensitive choice named a law id.** `scripts/intake_wizard.py:224` ("the active LAW-IV
   privacy layer"). Fix: "Needs the privacy layer (it masks sensitive content) and the local
   redaction model."
7. **The Sensitive refusal named a law id and gave no next step.** `scripts/preflight.py:174` (shown by
   the wizard and the console): "the required LAW-IV privacy layer is inactive. It requires operator
   activation". Fix: "...the privacy layer that masks sensitive content is switched off. Choose
   Normal only for documents that are not sensitive; do not submit sensitive documents." The Turkish
   row moved with it. Proof: the wizard's `--mode-only` dry run prints the new sentence.
8. **The cloud screens showed ISO text.** `scripts/ui/cloud_mode.js:254` showed the code's expiry as
   the server's `2026-11-16T18:45:00+00:00`, and `:109` a measured forecast's date as `2026-11-07`.
   Fix: the expiry as the viewer's clock time (18:45) and the date in words (7 November 2026, 7 Kasım
   2026). Proof: a new proof in `scripts/console_cloud_checks.py`
   (`proof_dates_and_times_are_shown_in_words`, inside gate check 338) renders the ready screen and
   the confirmation step under node in both languages; its neutralisation (the ISO text shown as
   sent) fails, restored it passes.
9. **The wizard used the project's own word "grounding".** `scripts/intake_wizard.py:160, 392, 417,
   427, 541` ("context/grounding", "reference/grounding", "Grounding documents", "grounding corpus").
   Fix: "reference material", "Reference documents".
10. **Three wizard stops gave no next step.** `scripts/intake_wizard.py:441, 446, 460` ("Not a folder",
    "No files found in that folder.", "No supported files to import."). Fix: each says what to do,
    and the last two name the file types Shimmer reads (.pdf, .docx, .md, .txt).
11. **The file list showed internal folder names.** `scripts/intake_wizard.py:103, 105` ("pipeline
    sorts into context or operational by the cutoff", "grounding case metadata"). Fix: "reviewed or
    used as reference, by its date and the cutoff", "description of an imported reference
    collection".
12. **The cutoff was shown as an ISO date.** `scripts/intake_wizard.py:160, 172, 507, 540`. Fix: shown
    in words ("Current date cutoff: 1 June 2025"); the typed answer stays YYYY-MM-DD and the stored
    value is unchanged. Proof: dry run with the answer `2026-03-05` prints "Proposed cutoff: 5 March
    2026".
13. **Answers piped from Windows PowerShell were never read right.** PowerShell 5.1 puts a byte-order
    mark before piped input, so the wizard's first answer, the folder, was "Not a folder: ﻿scripts\..."
    for a folder that exists. Fix: `_ask` (`scripts/intake_wizard.py:62`) drops the mark. Proof: the
    same piped dry run went from "Not a folder" to "Found 9 file(s)".
14. **The wizard's parallel prompt** is a sealed launcher prompt (see listed item 3); a comment at
    `scripts/intake_wizard.py:480` now says so, so the next person changes both together.

## Listed, not fixed (17)

1. **Server error messages are developer text, shown word for word in the console, with no next
   step.** `scripts/server.py:967` and 14 more "run_id not found"; `:1928` "task=draft requires a
   'question' field"; `:1930`; `:1937` "too many files: N > SHIMMER_MAX_UPLOAD_FILES (...)"; `:1957`,
   `:1964` name environment variables; `:1994` "could not accept upload: {e}"; `:2644` "agent harness
   not built on this server; run scripts/build_agent_harness.py"; `:2938` "top_k must be between 1
   and 50". Fix: plain sentences that say what to do ("This run is not on this server. Open Runs and
   choose it from the list."), with the catalogue rows and patterns and `scripts/localization_checks.py`
   moved together. Larger: API clients and the catalogue match these strings.
2. **The Turkish guide speaks in the plural polite form.** `docs/GUIDE_TR.md` from line 3 ("sizin
   yazdığınız kurallar", "çalıştırın", "Belgeleriniz"). It is a reader document and quotes console
   labels; convert it in one pass with the operator's choice of form for documents.
3. **The parallel-documents prompt says "uses more API quota" under Local too.**
   `scripts/intake_wizard.py:483`. It is also a sealed launcher prompt
   (`tools/prepare_ordinary_final_run.py:743`), and the sealer is a bound file: change both, then re-seal.
4. **The wizard numbers Cloud [1] and Local [2].** `scripts/intake_wizard.py:203-204`, while both
   launchers offer Local first and take it on Enter. The costly choice is the first number. Reorder
   with the checks that feed "2" for Local (219, 220, 223) and the sealed privacy answers.
5. **"The pipeline will run with default rules only" may not be true.** `scripts/intake_wizard.py:494`.
   No default rule set is shipped; what a run with no conventions does is the INFRA-042 empty-convention
   carve-out. Verify and say it plainly.
6. **An em dash reaches the Agents page.** `config/agent_registry.json:168` (EDITOR_DG's duty
   "Decide the existential editorial question", which sets off "whether the content is needed at
   all" between two em dashes), copied in `config/agent_harness.json:1161`, `genesis.md:135`
   and the catalogue key at `scripts/ui/localization_catalog.js:1904`. The registry is governed
   structure: the text changes only with the operator's approval.
7. **Internal ids in Turkish rows.** 74 catalogue rows carry snake_case keys, `SHIMMER_*` names,
   `LAW-IV`, `INFRA-040`, `INFRA-041` or `GET /runs/{run_id}/...` routes. Most are developer-view
   text by design, but pipeline log patterns such as "[sensitivity-gate] UYARI: tam LAW-IV hassasiyet
   katmanı ... (INFRA-041)" can reach the reviewer view. Needs a reviewer and developer split audit.
8. **The desktop starter is English only.** `scripts/desktop_launcher.py:287-488`; the Turkish guide
   says so. A Turkish window needs the catalogue wired into tkinter.
9. **The cloud screens show raw machine and phase names.** `scripts/ui/cloud_mode.js:215`
   (`gpu_1x_a10`), `:221` (the phase id, for example `ordinary_workload`), plan ids as link text
   (`:144`) and file sizes as "N B". Show plain names and sizes in KB or MB.
10. **The server's start text invites public exposure.** `scripts/server.py:3481` prints "Expose it
    publicly with: cloudflared tunnel --url ..." for a server with one shared token and no accounts.
    Decide whether v1.0 suggests this at all.
11. **The server's own token help says "give to the collaborator".** `scripts/server.py:3459`, while
    the README says Shimmer serves one operator. Reword with item 10.
12. **There is no page at `/`.** Both launchers explain it (`shimmer.bat:287`). A redirect to
    `/console` is a route change: the runtime reference table and checks 167 and 116 move with it.
13. **The pipeline's three questions in the menu path show flag names.** "--sensitivity-layer-inactive-override:
    declare THIS run NON-SENSITIVE ... (yes/no)" and "--no-redaction-override: ..." in the pipeline.
    They are sealed launcher prompts (`tools/prepare_ordinary_final_run.py:750-753`): change with a re-seal.
14. **The demo shows document ids as file stems.** `scripts/ui/demo.html:239, 248` print `doc.document_id`
    (for example `note_north_round_1`). Show a plain name, keeping the id in brackets as `part()` does
    for units.
15. **The README's no-generation commands use `python`, the rest `py -3.12`.** `README.md:571-575`. On
    a Windows machine with only the `py` launcher, `python` can be missing. State both forms once.
16. **The Sensitive choice is offered although it always stops in v1.** `scripts/intake_wizard.py:223-227`.
    The refusal now says why (fixed item 7); the menu line could say "switched off in this version".
17. **Gate checks 220, 308, 311 and 333 were not run on these changes** (memory, see above): run them
    on the Lambda gate.
