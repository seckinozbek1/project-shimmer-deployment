# Shimmer operator guide

This guide is for the operator: the one person who installs Shimmer, starts it, runs reviews and reads the
results. It is organised by task. Every command, button and screen name below is taken from the code or from
the project's pages ([README.md](../README.md), [INSTALL.md](INSTALL.md)); where something is built but not yet proven, the guide says so.

Related documents: the short [guide](GUIDE_EN.md) ([Turkish](GUIDE_TR.md)), the [operator runbook](RUNBOOK.md)
(each screen in detail), the [input format](INPUT_FORMAT.md) (how to write rules), the
[output format](OUTPUT_FORMAT.md) (every file a run writes), the [runtime reference](RUNTIME_REFERENCE.md) (every
server route and setting) and the [cloud mode](CLOUD_CONSOLE.md).

## 1. Install

You need Python 3.12 (3.12.x) and a copy of the repository. From the repository folder, on Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
# only on a machine with an NVIDIA GPU, when torch reports no CUDA:
.venv\Scripts\python.exe -m pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

On Linux or macOS use `python3.12 -m venv .venv` and `.venv/bin/python` in the same commands.

To check an install without a model, a GPU or a provider key (it makes a new environment in the folder you name,
outside the repository, and exits 0 only if every step passed):

```powershell
py -3.12 tools/clean_install_check.py --venv ..\shimmer_check_env
```

To see what a local review would still need (it changes nothing):

```powershell
python scripts/preflight.py --check-startup --backend-profile local
```

What the packages do not include:

- **Model files.** The local backend needs the configured Qwen and Phi model files in the model cache and a CUDA
  graphics card. The desktop starter downloads nothing. The bge-m3 embedding model is fetched on first use when it is
  not cached.
- **Provider keys.** Only the Cloud backend needs them. They live outside the repository: Shimmer looks through
  `$SHIMMER_CONFIG_PATH`, then a sibling `../api_keys/config.py`, then the path named in a repository-root
  `.env_path` file. Never put a key in the repository.

The menu launchers (`shimmer.bat` on Windows, `./shimmer.sh` on Linux, macOS and Git Bash) do the install steps
above on every start; `SHIMMER_SKIP_INSTALL=1` skips them when the environment is already installed.

## 2. Put your material in place

A fresh copy has no `input/` folder. Create it:

- `input/context/`: the documents to review and their supporting material.
- `input/conventions/`: your rules (`review_conventions.md` and `review_mandate.md`). A rule is a Markdown heading
  with your own id, its severity and its subject in brackets, and the rule's text below it:

  ```
  ## CONV-P01 Line arithmetic [required] [conformance]

  The line total must equal the quantity times the unit price.
  ```

- `input/context/_review_targets.json` (optional): an explicit list of the documents under review and the earlier
  versions to compare with. It wins over the date cutoff in `config/review_scope.json`.

You can also skip this step and upload the files from the console (section 4). The menu launcher's import option
([5]) can place files and set the cutoff for you. Sections 3 to 5 of the [input format](INPUT_FORMAT.md) give the
rest of the rule format.

## 3. Start Shimmer

### On Windows (desktop starter)

Run `start_shimmer.bat` from the repository folder. A small window opens, titled **Project Shimmer**.

1. Choose **Local: installed models, no provider API charges** or **Cloud: configured providers, usage charges
   apply**. Local means models inside Shimmer's own run and nothing sent to the internet. Cloud means the text of your
   documents goes to the providers, and each call is charged. To change it later, stop and start again: the server
   does not take a different backend per submission.
2. Click **Check and start** and read anything it reports as missing. It starts the server on this computer only
   ("Only this computer can connect.") and opens the console in your browser.
3. Click **Copy access token** and paste the token into the console's access field. **Open console** opens the page
   again; **View startup log** shows the start-up output.
4. Keep the small window open. **Stop Shimmer** stops the server. Closing the browser leaves the server running.

### On Linux or macOS (menu launcher)

Run `./shimmer.sh` and choose option 3 (server). Press Enter for Local or C for Cloud. It shows the token once and
starts the server. Its banner names the two addresses that open without a token, `/health` and `/console`.

### The token

The server keeps only the SHA-256 hash of one access token (`SHIMMER_TOKEN_HASH`); there are no user accounts. The
browser holds the token for the session and sends it with every request. Never put the token in a web address, a
log, a screenshot or a shared document. `python scripts/server.py` with no hash set refuses to start and prints a
one-line command that makes a token and its hash.

## 4. Run a review from the console

The console's pages are **Runs**, **Submit**, **Agents**, **Test changes** and **On a rented cloud machine**.
**Output language** (English or Türkçe) is at the top, beside the **Reviewer** and **Developer** view switch.

On **Submit**:

1. Under **Task**, choose **Review: upload documents**.
2. Click **Choose files** and add the document, your rules and any reference material.
3. Give each file a role: **Document to review**, **Reference material or review rules**, or **Earlier version for
   comparison**. An earlier version is evidence for the comparison, never a new target.
4. Under **Privacy**, choose **Normal: I declare these documents non-sensitive**. A Sensitive submission is refused
   while the privacy layer (LAW-IV) ships switched off. Do not send sensitive documents through a Normal run.
5. Click **Review the plan**, read the plan, and click **Confirm and start**.

The run appears under **Runs**. One run works at a time, and a local run can take a long time. "Queued" means
accepted into the queue, nothing more.

**Multi-round review.** Open **Advanced intake and review options**, tick **Multi-round positioning (unverified
with models)** and paste the case manifest into **Case manifest JSON (multi-round only)**. Section 12 of the
[input format](INPUT_FORMAT.md) gives every field.

**From the command line instead.** One review, with both declarations the shipped privacy layer requires:

```powershell
py -3.12 scripts/pipeline.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override --backend-profile local
```

Without `--sensitivity-layer-inactive-override` the run exits with code 6. Without `--no-redaction-override` it
exits with code 4 when no operator redaction rule compiles, which is the case for every shipped corpus.

## 5. Follow a run

Open the run from **Runs**. It shows its steps, its documents, any decision it is waiting for, agent activity, the
log (**Load log**) and the archive downloads.

| What you see | What it means |
|---|---|
| Waiting to start | Queued. No model has run. |
| In progress | The run is working. Findings already written can be read. |
| Paused: needs your decision | Read the question and its reason, then answer. Your answer is recorded; the run decides what it means when it next reads it. |
| Process finished | The process ended normally. This does not mean every agent succeeded or every problem was found. |
| Stopped on purpose | A governance stop with its reason. Fix the stated cause; it is not a crash. |
| Stopped by a system fault, timeout or cancelled | The run is incomplete; files already written stay and are partial. |
| Unknown, not recorded, unavailable | The evidence is missing. Do not read it as success or as zero work. |

Cancel stops a queued or running job and deletes nothing. There is no shutdown address on the server: stop it from
the starter window.

## 6. Read the results

Each run has a folder `output/runs/<UTC time>__<run id>/` with `deliverables/_run_summary.md` as its index and one
folder per document. Start with these, in this order:

| File | What it is |
|---|---|
| `reviewed_document.md` | Your document, whole and in order, with each finding shown under the part it concerns, and at the top what was asked, the counts and what was not checked |
| `document_summary.md` | A summary of the findings |
| `review_findings.md` | Each proposed amendment, with its reasons |
| `tracked_changes.docx` | The amendments as a Word file with tracked changes |
| `review_data.json` | The master record the others are drawn from |
| `agent_record.md` | Each agent's raw reply, a technical record |

The console's **Archive** downloads these as zip files: the whole run, or one document. A run that did not finish
gives a partial archive. A file being there does not prove that every stage ran.

### Read a finding

An amendment reads like this (from the shipped three-round example):

> Unit u16-annex-ii-annual-contribution-of-the-host (Annex II. Annual contribution of the host state) under rule
> CONV-005 (operator's id CONV-H05): the values under 'annual contribution' (1200000.0 + 400000.0 + 200000.0 +
> 300000.0 EUR) add up to 2100000.0 EUR, but the stated total annual contribution is 2200000.0 EUR. Computed in code
> from the figures in this unit, not judged by a model. Rule CONV-005 (operator's id CONV-H05); cited passage
> REF-0219.

- **The unit** is the part of the document, usually a section.
- **The rule** appears with Shimmer's number (`CONV-005`) and your own id (`CONV-H05`).
- **The figures** are Python's, with their units, and come first. A model's sentence, if any, comes last, quoted and
  named as the model's.
- **A REF number** points to the passage the finding rests on. Click it in the console to read the passage from this
  run's reference index. Clicking a rule shows the rule's current text, which may differ from the text the run used.

### Who wrote it

| | Computed by Python | Written by a model |
|---|---|---|
| Covers | Sums, products, ranges, missing fields, changes from an earlier version | What Python could not settle, such as what words mean |
| Becomes an amendment | Yes | Never |
| How to tell | It carries Python's figures and citations | It carries the mark "Written by a model. Not promoted to an amendment. Not checked by Python." |

Read a model's finding as a lead to check by hand. Read, too, what the run refused to compute and the rules it left
unchecked: `reviewed_document.md` states them in words. An empty findings list never certifies a clean review.

## 7. The console views

The **Reviewer** view uses plain headings; the **Developer** view shows the record names and more technical
detail. Neither is a quality score. On a run you will find, among others:

- **Findings** (each with who wrote it) and **Which rules were checked against which passages** (the pairing map).
- **Written by a model**: every model finding that was not promoted, with its mark.
- **Findings without a proposed correction**, **Calls that produced nothing usable**, **Rules no agent handles**,
  **Checkers that did not run**, **Documents not reviewed, no date**.
- **Agent activity**: the profile the run recorded, the calls made and not made, failures and capped replies.
- **Model replies**: metadata of every saved model call (agent, model, time, sizes, outcome), never the text.
- **Agent switches**: whether INST_FINDER was on or off for the run, and why FACT_CHECKER is withheld.
- **Run report**: the cloud report rows of a rented run, with cost estimates (not an invoice).
- **Multi-round positioning**: the case output of a multi-round run.

The other pages: **Agents** shows the current description of every agent (not a past run's), **Test changes**
lists the requested changes to tests, read-only.

### The review desk

One plain page for a single review, at `/console?view=desk`; its short guide is [DESK_GUIDE.md](DESK_GUIDE.md).
The review desk was built for v1.0-alpha (the current state of the code, not a release that reached its targets) and was fixed after the alpha freeze, on 22 November 2026. English only in the alpha. The desktop starter opens it in keyless local mode, so it connects with no
token; while that mode is on, every protected route of the server (not only the desk) answers any program or
user on this computer with no token, and other computers are refused (DESK_GUIDE section 1). When that mode is
off, paste the access token into the **Token** field and click **Connect**. Then **In place** lists the
files in the three input folders (names and sizes, never content) and the compiled rules; **Start a review** takes
files, a role for each (**Review target**, **Earlier version**, **Reference (background)**, **Rules file (the server decides)**), an optional
framing question and the privacy choice, shows the plan, and starts only after **I have read this plan** and **Start
the review**; **Waiting for a decision** offers **Approve** and **Deny** with an optional rationale; **Runs** and
**Run** show the measured progress (documents done, elapsed, rate, remaining at that rate, or "not measurable" with
the reason), **Read reviewed document**, the findings with who wrote each, **Cancel this run**, **Show the end of
the log** and the zip downloads.

## 8. Run on a rented cloud machine

The page **On a rented cloud machine** runs a review on a machine started for the run and shut down after it. Your
documents are copied to the rented machine for this review and deleted with it when it is shut down. This mode is
proven on fakes only: no console launch has started a real machine yet.

**Once, by hand, before the first use:**

1. Set `SHIMMER_CONFIG_PATH` to your own provider key file outside the repository. The page only asks whether a key
   file can be found; it never asks for the key, reads it or shows it.
2. Write `output/cloud/console_settings.json` with `reuse_assets`, `wheelhouse`, `storage_forecast_usd` and
   `asset_copy` (or `null`), as [the cloud mode](CLOUD_CONSOLE.md#operator-setup-once-by-hand) shows.
3. Open a budget line in the ledger. The page never opens or changes one, and refuses with "No budget is open"
   without it.

**Each review:**

1. The page lists **Provider key file found**, **Settings ready**, **Budget open** with what is left, and **Machines
   running** (there is no maximum; the total budget is the limit).
2. Add **Documents to review**, **Reference documents (optional)** and **Review conventions**, then click **Prepare
   (spends nothing)**. The plan is staged and sealed; the page counts the preparation steps done.
3. Read the plan: **Forecast time**, **Forecast cost**, **Most it can cost (the cap)**, the **Machine** and its price
   per hour, whether the model upload is included, and whether the forecast is **Measured** or an **Estimate**.
4. Click **Get a confirmation code**. The page shows "This starts a rented machine that costs up to X USD. It is shut
   down after the review." **Type the amount to confirm**: the cap as shown, to the cent. Then click **Start the
   rented machine**.

The launch is refused unless the amount equals the cap shown, and the one-time code is this plan's, unused and under
15 minutes old. The page holds the code for you; you type only the amount. A code is spent on its first use, whatever
the outcome, and lives only in the server process.

**After the run** the page shows the actual minutes and cost (from the ledger, beside the upper bound; the provider's
invoice may differ), the minutes per part, and whether the machine was shut down. Only when the shutdown is confirmed
does it say "The rented machine and its copy of your documents are gone." Otherwise it says the shutdown is not
confirmed: check the provider's console at once. **Your results** lists each document's files, each with
**Download**, and **Download all files of this document**.

## 9. What a sealed run shows

A sealed run is a test whose answers must not leak. The console and the desk show it as counts and timings only.
The console says: "Sealed test: counts and timings only. Withheld: document, file and target names, finding text,
unit ids, rule ids, the reasons given for findings, and per-flaw results." A pending question of a sealed run shows
its timings, not its text. The server refuses the findings, pairs, amendments, references, log, downloads and the
other detail routes of a sealed run (403), so nothing more can be read through the browser either. The cloud page
never prepares or launches a sealed run.

## 10. What is not supported yet

- Sensitive review: refused while the privacy layer ships switched off.
- Local Draft: it runs on the local model but is not proven end to end.
- The console's cloud mode: proven on fakes only.
- Completeness: no run certifies that every problem was found.
- Automatic resume: a stopped run is not continued; a rerun is a new run.

## 11. Quickstart

This section and the next were moved from the README on 19 November 2026 (D-816).

1. Create `input/context/` and `input/conventions/` (a fresh clone has no
   `input/` folder). Put the documents and their supporting material in
   `input/context/`, and the operator's rules in `input/conventions/`
   (`review_conventions.md` and `review_mandate.md`). `docs/INPUT_FORMAT.md`
   describes both. The menu launcher's import option ([5]) can place files and
   set the cutoff for you.
2. Start the console with `start_shimmer.bat`, choose Local or Cloud, paste the
   token and submit a review from the console. The
   [operator runbook](RUNBOOK.md) walks through each screen.
3. Or run one review from the command line:

```powershell
py -3.12 scripts/pipeline.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override --backend-profile local
```

Without `--sensitivity-layer-inactive-override` every run exits with code 6,
because the privacy layer ships switched off. `--no-redaction-override` declares
the run redact-nothing: it switches redaction off for that run. Without it, a run
exits with code 4 when the local Qwen redaction model is not reachable, or when no
operator redaction rule compiles (the case for every corpus shipped in this
repository). Each override is written to the governance ledger.

The corpus-level agent INST_FINDER is optional and under development. By the
operator's decision (D-570) it is off by default once the operator has ratified
the amendment drafted in `docs/INST_FINDER_SWITCH_DELTA_DRAFT.md`;
`SHIMMER_INST_FINDER=on` then runs it for a run. Until that amendment is
ratified, a run with no value runs INST_FINDER as before, and a run with
`SHIMMER_INST_FINDER=off` refuses to start (exit code 9, shown by the server and
the console as the governance status `refused_inst_finder_unratified`, not as a
failure). Each run records the setting, and whether it was the default, in
`audit/agent_switches.json` and its run summary.

Under the local backend profile nothing in Shimmer reaches the web: the search
router refuses every web lookup, and the run summary and the console say so. Web
access opens only under the cloud profile, and only for agents whose registry entry
allows it. This is a rule about what the product sends, not about where it runs: a
local-profile run on a rented machine refuses the web exactly as one on the laptop
(gate checks 502 and 503).

4. Read the results in `output/runs/<UTC time>__<run id>/deliverables/`: one folder per
   document, plus `_run_summary.md`. `docs/OUTPUT_FORMAT.md` describes the run
   folder.

## 12. Configuration

- `input/conventions/`: the operator's rules. A rule heading can carry brackets
  that declare its severity, its scope (`[scope: ...]`) and the fields it requires
  (`[requires: ...]`).
- `config/review_scope.json`: the date cutoff that decides which documents are
  under review, and agents withheld for a review scope. It is a tracked file:
  setting the cutoff from the import wizard or the chat window rewrites it in
  place, so the change shows in `git status` and holds for every later run until
  it is set again.
- `input/context/_review_targets.json`: an explicit list of the documents under
  review, and earlier versions to compare with. It wins over the date cutoff.
- `config/agent_registry.json`: which provider model each agent uses under the
  cloud backend. Model names are read from the provider, never typed into code.
  The local backend's models come from its local profile, which
  `config/local_models.json` can override.
- The backend. With no backend named, a command-line run, the server and the preflight use
  Local (models inside Shimmer's own run and nothing sent to the internet, whether the run is on
  this machine or on a rented one; `SHIMMER_BACKEND_PROFILE` unset means `local`, and only the
  exact value `cloud` chooses Cloud, so an empty or unknown value is Local and keeps the web
  closed). The desktop starter and the import wizard make you choose, the menu launchers take
  Local when you press Enter (C chooses Cloud), and `tools/run_local_demo.py` adds Local.
  Every figure on the results page used Local.
- `config/decoding_policy.json`: the frozen decoding settings for local models.
- `config/domain_vocabulary.json`: domain words that must never appear in code.
- Server settings are `SHIMMER_*` environment variables, listed in the
  [runtime reference](RUNTIME_REFERENCE.md#server-environment).
  `SHIMMER_TOKEN_HASH` is required.
