# Shimmer user guide

Shimmer reads a document and a set of rules you write, and reports where the document breaks them. Python works out everything that can be worked out from the document's own figures. A language model is asked only about what is left, and anything it writes is marked as a model's.

This guide takes you from a clean install to reading your first results. The [runbook](RUNBOOK.md) covers each screen in detail, the [input format](INPUT_FORMAT.md) covers how to write rules, and the [output format](OUTPUT_FORMAT.md) covers every file a run writes.

## Install

You need Python 3.12 and a copy of this repository. From its folder, on Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Linux or macOS, use `python3.12 -m venv .venv` and `.venv/bin/python` in the same commands. The packages take several gigabytes, because PyTorch is among them.

To check an install without a model, a GPU or a provider key, run this from a fresh copy, naming a new folder outside the repository:

```powershell
py -3.12 tools/clean_install_check.py --venv ..\shimmer_check_env
```

It creates a new environment, installs the packages, runs Shimmer's computing layer on the worked case with no model, starts the console and stops it. It prints each step's result and exits with 0 only if all of them passed. It says nothing about a review with a model.

## Three ways in

- Demo: no installation, saved examples. A static page of the two worked cases' saved results, with nothing to install and nothing to type: `tools/build_demo.py` builds it into a demo folder, opened with open_demo.bat, with no server and no token. Your documents go nowhere, because the demo shows only the saved examples. No built demo ships in this repository yet; the console's footer names it.
- On your own computer with a strong graphics card. Shimmer reviews your documents with models on your machine. Your documents stay on your computer. It needs the configured model files in the model cache and a CUDA graphics card, and the packages above do not include those files. All our measured runs used a rented card with 24 GB of memory; on an 8 GB laptop card a run takes hours. To see what is missing, run `python scripts/preflight.py --check-startup --backend-profile local`, which changes nothing.
- On a rented cloud machine. A machine is rented for the run and shut down after it. Your documents go to the rented machine and are deleted with it. The console has this mode (`docs/CLOUD_CONSOLE.md`), but it is proven on fakes only and has not yet started a real machine; until it has, a rented run is started with the operator tools in `docs/CLOUD_RUN_PREPARATION.md`.

The starter window's **Cloud** choice is something else again: provider models instead of models on your machine. The text of your documents then goes to the providers, and each call is charged. It needs Anthropic and OpenAI keys in a file outside the repository, found through `SHIMMER_CONFIG_PATH`, a sibling `../api_keys/config.py`, or a path named in `.env_path`. Never put a key in the repository.

## Start the console

On Windows, run `start_shimmer.bat`. A small window opens. Choose Local (your own computer with a strong graphics card) or Cloud (provider models), click **Check and start**, and read anything it reports as missing. It opens the console in your browser. Click **Copy access token** and paste the token into the console. Keep the small window open, and use **Stop Shimmer** to stop: closing the browser leaves the server running.

On Linux or macOS, run `./shimmer.sh` and choose option 3. It shows the token once, and then starts the server.

The console has four pages: **Runs**, **Submit**, **Agents** and **Test changes**. Its language is set by **Output language** at the top of the page.

## Run a review

You need the document to review, and your rules in a Markdown file. A rule looks like this:

```
## CONV-P01 Line arithmetic [required] [conformance]

The line total must equal the quantity times the unit price.
```

The rule names the document's own labels, here `line total`, `quantity` and `unit price`, and that is how Shimmer knows which part of the document it applies to. Sections 3 to 5 of the [input format](INPUT_FORMAT.md) give the rest.

Documents are best written as Markdown. A Word `.docx` also works: it is read as it would stand with every tracked change accepted, and its heading styles become sections. A review reads figures from label lines (`Quantity: 4 box`) and from tables, not from running text.

On the **Submit** page:

1. Under **Task**, choose **Review: upload documents**.
2. Click **Choose files** and add the document, your rules and any reference material.
3. Give each file a role: **Document to review**, **Reference material or review rules**, or **Earlier version for comparison**.
4. Under **Privacy**, choose **Normal: I declare these documents non-sensitive**. The Sensitive setting is refused, because the privacy layer ships switched off. Do not send sensitive documents through a Normal run.
5. Choose the **Output language**, click **Review the plan**, read the plan, and click **Confirm and start**.

The run appears under **Runs**. One run works at a time, and a local run can take a long time. A finished run does not mean every problem was found: look at what was refused or left unchecked as well as at what was found.

The results are in `output/runs/`, in a folder for each run, with `_run_summary.md` as the index and a folder for each document. Start with these:

| File | What it is |
|---|---|
| `reviewed_document.md` | Your document, whole, with each finding placed where it applies |
| `document_summary.md` | A summary of the findings |
| `review_findings.md` | Each proposed amendment, with its reasons |
| `tracked_changes.docx` | The amendments as a Word file with tracked changes |
| `review_data.json` | The master record the others are drawn from |

## Run several rounds of a negotiation

A multi-round run reads successive versions of a text in order. You describe the case in a case manifest: the rounds and which documents belong to each, the parties, the issues, and the exact passages that state each party's position. Section 12 of the [input format](INPUT_FORMAT.md) gives every field.

On the **Submit** page, choose **Review** and **Normal** as above, and open **Advanced intake and review options**. Tick **Multi-round positioning (unverified with models)**, and paste the manifest into **Case manifest JSON (multi-round only)**.

Such a run writes no amendments. It writes two files:

- `version_changes.md`, in the folder of each later version: what changed from the version before, sentence by sentence and table cell by table cell, and any numbered reference that leads nowhere. Python writes all of it.
- `case_positions.md`, in the last round's folder: the parties' stated positions on each issue. Whether a position moved toward the other party's stays `unknown` unless a model has been asked, and every line says whether Python or a model wrote it.

A complete example is in `benchmark/dev_cases/host_agreement_three_rounds/`: an invented agreement over three rounds, with the texts as Word files with tracked changes and the delegations' notes as Markdown. It is a demonstration, not evidence of how well Shimmer performs.

## Read a finding

This amendment comes from that example, where a table in Annex II no longer adds up:

> Unit u16-annex-ii-annual-contribution-of-the-host (Annex II. Annual contribution of the host state) under rule CONV-005 (operator's id CONV-H05): the values under 'annual contribution' (1200000.0 + 400000.0 + 200000.0 + 300000.0 EUR) add up to 2100000.0 EUR, but the stated total annual contribution is 2200000.0 EUR. Computed in code from the figures in this unit, not judged by a model. Rule CONV-005 (operator's id CONV-H05); cited passage REF-0219.

Read it in this order:

- **The unit** is the part of the document it concerns, usually a section.
- **The rule** appears twice. `CONV-005` is Shimmer's number for it, and `CONV-H05` is your own.
- **The figures** are Python's, with their units, and they come first. If a model's sentence follows, it is quoted and named as a model's. Only the quotation is the model's.
- **A REF number**, such as `REF-0219`, points to the passage the finding rests on. Click it in the console to read the passage.

A finding is a proposal for you to check, never a decision. Look too at what the run refused to compute and at the rules it left unchecked, which `reviewed_document.md` states in words.

## What is computed and what is a model's

| | Computed by Python | Written by a model |
|---|---|---|
| What it covers | Sums, products, ranges, missing fields, changes from an earlier version | Whatever Python could not settle, such as what words mean or whether two passages conflict |
| Same answer each time | Yes | No: treat it as a lead to check by hand |
| Becomes an amendment | Yes | Never |
| How you can tell | It carries Python's figures and citations | It carries this mark: "Written by a model. Not promoted to an amendment. Not checked by Python." |

Under Local, nothing in Shimmer reaches the web. Each run saves every model call's reply in its `audit/model_replies/` folder, so you can see what a model was asked and what it said.
