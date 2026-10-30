# FinDVer: the B1 revision and B3's reading of long filings

Development only. Loop stage S5, lane `lane/s05-findver`, carrying out the operator's decision D-S13 item 7 (30 October 2026), which overrules D-078 and keeps FinDVer in the evaluation. FinDVer's held-out (`test`) labels have been public since 14 July 2026 (MIT licence); every report that gives a FinDVer figure states it.

## 1. The revision rule (written 2026-10-30 13:52 +0300, before any B1 reply was read)

Written before this lane opened any B1 reply, any FinDVer score, metric, label, gold value or answer key. It governs every change below to the B1 arm on FinDVer (preregistration section 5.4, "Development check").

**What may change.**

1. The structure of FinDVer's B1 prompt for long inputs: the order of the user turn's blocks (the ITEM and LABELS blocks may stand before the DOCUMENT, after it, or both), a closing reminder after the document that restates the required last line, and a bound on the length of the working the system turn asks for. The question line and the three label lines are kept word for word.
2. The chunking of a filing into the B1 prompt: the filing after section 5.3's cut (the same text every arm receives) split into consecutive windows of whole parts, each prompt with its output allowance under the model's context, one reply per window and item, the windows' labels combined by a rule fixed in writing before any window reply exists. The combination rule reads only the window labels, never gold, never which items are right.
3. The parser's tolerance for well-defined formats: a format is admitted only when it is stated as a structural rule (what the reply's text must look like), applies identically to every FinDVer reply, never changes the label of a reply the frozen parser already parses, reads the label only from the reply's own label field or label line by the frozen normalisation and label names, and never reads `evidence`, `reason`, the item id's correctness or anything outside the reply.

Only FinDVer's entry changes. The system turn and the user template for ContraDoc, CUAD, SciTab, ContractNLI and B's synthetic tests, and their parsing, stay byte for byte as frozen in version 2.

**What may not change.** The label set and the label names; the decision rule (FinDVer: refuted is FLAG, entailed is CLEAR, undecided and every unparseable reply are ABSTAIN, section 5.2); the cut rule and the same-text-for-every-arm rule (section 5.3); the main reading agent, its checkpoints, decoding policy, attention and prefill, and its 2,048-token output allowance (section 12 items 8, 12, 13); anything chosen by looking at which items a reply gets right or wrong. No gold label, `labels.json`, `metrics.json`, `SUMMARY.json`, answer key or score is read for this revision, by this lane or for it.

**How a change is accepted.** By parse rate on development items only, never by accuracy:

- A parser change is measured now, offline, by re-parsing the saved S5 FinDVer B1 replies (L3e and L4b, development, exposed) under the frozen parser and under the changed one: for each reply, whether it parses and by which rule. Only the reply text's format is read. The saved set is a handful of replies on one filing, so the figure is reported as counts with its n, never as a rate that decides anything alone.
- A prompt-structure or chunking change cannot be measured on saved replies. It is accepted only by a development B1 run on both checkpoints whose pooled FinDVer development parse rate (`bare_model.py pool`) reaches the 95 percent floor of section 5.4. Until that run, the change is proposed and unmeasured, and FinDVer's B1 stays under section 5.4's rule for a benchmark below the floor.
- Order fixed now: the parser change first (measurable now); then the prompt structure (item 1), measured by a development run; chunking (item 2) only if that run stays below the floor.
- Each accepted change counts as one of the three revisions section 5.4 allows before the freeze, is logged in `docs/benchmarks/DEVIATIONS.md` with its development parse counts, and, as section 12 item 12 requires after any section 5.4 revision, both checkpoints are re-run on the items it touches and the checkpoint rule is applied again. The change enters the frozen design only through preregistration version 3 (D-S13 item 10).

**Recorded.** Which saved replies were read is listed in section 4, with what was read from each.
