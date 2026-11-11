# The leakage protocol (D-S100, D-S102 item 3)

One protocol and one tool for every item set the loop reads: the gate set first, then every other
set (PUBHEALTH, the causal probe, a judge's held-out rows). Written 9 November 2026 by `choice-build`,
before any candidate is checked. Tool: `benchmark/adapters/common/gate_leakage.py`; proofs in
`scripts/gate_set_checks.py`. The thresholds are module constants, carried in every output, and a
fingerprint or result made under other thresholds is refused.

## What counts as leakage

A candidate item leaks when any of the four rules below holds against any record of any part. What is
read in a part's files (`gate_leakage.py`'s reading rules):

- JSON and JSON lines: every string value at any depth, whatever field holds it, so a prompt, a training
  row, a reply and a document are all read; with `#key,key`, only the values under those keys.
- Plain text: `.txt` and `.md` by paragraph, `.csv` and `.tsv` by line.
- Archives: the members of `.tar.gz`, `.tgz`, `.tar` and `.zip`, by the same rules. Any other archive
  format (`.gz` alone, `.bz2`, `.xz`, `.7z`, `.rar`, `.zst` and the like) **refuses the fingerprint**, as
  does an archive that cannot be opened.
- Skipped and listed in the fingerprint file (`skipped`, with each file's SHA-256 where it was read):
  any other file (weights, images), and, never opened, key files (`answer_key.json`, anything under a
  `keys` folder) and a sealed bundle's model assets (`assets.tar`, anything under `hf_cache`).
- Refused: a fingerprint over `external/s05/` while any entry there other than `D-S56` and `GATE`
  belongs to no part (`gate_leakage.uncovered`).
- Refused: any path under `external/s05/D-S56/`, on every command of both tools (`gate_leakage.guard`
  on every path argument, every part path and every archive member's name), with the one exception (D-442): the fresh set's ids file, `external/s05/D-S56/contradoc_fresh100_ids.json`, read for its ids only, admitted by its pinned digest (`ec2498fd...`) and only by `gate_set.py exclude-ids --fresh-ids`; nothing else under `external/s05/D-S56/` is read by any gate tool.
  The fresh set is excluded by id only (rule 4).

A **record** is a string of at least 8 words; a **short record**, of 4 to 7 words, is held by its exact
hash alone. A candidate's own text is the benchmark's text only (ContraDoc: the document's `text`;
SciTab: the claim, and the table's caption, header and cells as one text), never an adapter's wording.

1. **Exact.** The SHA-256 of a candidate text, or of its texts joined, after NFKC, case folding and
   collapsing whitespace, equals a record's or a short record's. Any hit excludes.
2. **8-word runs.** The candidate shares at least **1** 8-word run with a part's records: words as
   `\w+` lower-cased, each run's SHA-256 cut to 16 hex characters (`overlap.py`, D-S77, and the
   judge's builder use the same runs). A run of digits only is not counted: table cells and figures
   repeat by chance. The producer's round 3 (D-385) found row containment alone missed shared spans of
   40 to 213 characters, which an 8-word run catches.
3. **Embedding cosine.** A candidate text's unit vector and a record's, from the repository's own
   embedding model (BAAI/bge-m3 through `embedding_store`'s loader, normalised, float32), have a dot
   product of at least **.92**. Both sides embed one text form: NFKC with whitespace collapsed and case
   kept, since bge-m3's tokenizer is cased. The figure is checked on development material before role B
   starts (step 2), and step 2's rule can only lower it.
4. **Source or group.** The candidate's group key (ContraDoc's near-duplicate group, SciTab's paper),
   its own id or its table id is listed in the exclusion file (`gate_set.py exclude-ids`: every
   development document and group, every development paper and table, the fresh set's ids), plus
   SciTab's in-context example tables, which role B adds. The check refuses to run without the file.

**A group goes whole.** When any member of a ContraDoc group or a SciTab paper leaks, the whole group or
paper is excluded, so no near-duplicate is split between the gate and anything read.

**Short candidate texts.** A candidate text of fewer than 8 words has no 8-word run, so it is caught by
rules 1, 3 and 4 only; rule 1 matches it against short records too. The result counts such texts
(`short_texts`) and the figure is reported beside the counts. A short text that appears inside a longer
record without being one of its strings is caught by cosine alone: a stated limit.

**Nothing is relaxed after a count.** No threshold, rule, floor or part list here or in GATE_SET.md is
changed once any count of any check has been seen. Only Seckin may change one after that, in writing;
the loop never does.

## The steps

1. **The record count, then the forecast, on the lead's side** (`gate_leakage.py fingerprint --part ...
   --count --out counts.json`): records, short records, distinct records and words per part, nothing
   stored. The embedding time is forecast from the distinct records at the measured bge-m3 rate
   (causal-probe, 9 November: about 30 texts a second on the laptop's GPU for 650-character texts, the
   model loaded in 27 s), and run only with the GPU idle (D-399), its progress measured (PROGRESS-A).
2. **The cosine figure checked, on development material only, before role B starts**
   (`gate_leakage.py cosine-step --dev external/contradoc/dev/ContraDoc.development.json --assignment
   external/contradoc/dev/contradoc_split_development.json --prompts external/s05/G1/g1_prompts.json
   --items external/s05/G1/build/contradoc/items.json --embed --out cosine_step.json`). Three
   distributions: two documents of one near-duplicate group, documents of different groups (2,000 seeded
   pairs), and a document against a prompt that wraps it (G1's prompts, since a record is often a prompt,
   not a document). **The rule, fixed now:** the threshold becomes the lowest of .92, the within-group 5th
   percentile and the document-against-prompt 5th percentile, rounded down to .01; it is never raised.
   If the across-group 99.9th percentile is not below it, the record says the cosine rule does not
   separate them, and the audit reads that. No candidate is read for this. Its record, with its digest,
   is an input to the role B request. The check reads its threshold from this record (`threshold_by_rule`),
   never above the ceiling `COSINE` (.92), and records the record's digest; the draw refuses a check run
   on another record.
3. **Fingerprints, on the lead's side** (`gate_leakage.py fingerprint --part name=path;path... --embed
   --out fingerprints.json.gz`), over every part named in GATE_SET.md section 9, with step 2's threshold
   in force. The file holds hashes, runs, float32 unit vectors (embedded 512 at a time), each source
   file's SHA-256 and the skipped list, and no text; it goes to `_xfer` for role B.
4. **The check, by role B in its own folder** (`gate_leakage.py check --fingerprints ... --benchmark
   contradoc|scitab --input <its pool file> [--assignment <its split file>] --side holdout
   --exclude-groups exclude_ids.json --cosine-step cosine_step.json --embed --out result.json`). The
   check takes its cosine threshold from step 2's record, refused above .92. The result holds counts, the parts
   hit, the files skipped by part, the short texts, a histogram of each candidate's best cosine in
   tenths, the excluded candidate ids with their rules, the kept and excluded group keys, and the
   digests it ran on (fingerprints, input, assignment, exclusion file, step 2's record): no text, no label. A check on
   fingerprints that carry vectors is refused without the embedder.
5. **The draw** (`gate_set.py`) on the kept groups only (GATE_SET.md section 3). It refuses a result
   without the cosine rule, without an exclusion file, made on another input, fingerprinted without
   every required part, or run on other fingerprints, another exclusion file, another step 2 record or
   another assignment than the digests it is given.
6. **The counts recorded** in the set's own file (GATE_SET.md section 9 for the gate): candidates and
   groups checked, excluded by each rule and by each part, the files skipped, kept. A vekil leakage
   audit reads them, and the drawn ids, before the first read.

## Every set, and open item 92

Every benchmark and probe item set runs this protocol before its first read, with the same tool and
thresholds (D-S102 item 3): the gate set (ContraDoc, SciTab, through `--benchmark`), and PUBHEALTH,
CLadder and Corr2Cause through `--candidates`, a JSON list of `{id, group, texts}` its own builder
writes from the source items (each text the item's own source text). Their role B sessions run the
check in their own folders, as the gate's does, and return counts and ids.

| Set | Candidate texts | `group` (the bootstrap's and the exclusion's unit, D-S99 item 3) | Metric |
|---|---|---|---|
| ContraDoc gate | the document | the near-duplicate group; one document a group, so the bootstrap is over documents | binary judgment accuracy |
| SciTab gate | the claim; the table's caption, header and cells | the paper (exclusion); the bootstrap is over tables (a cluster bootstrap, D-S102 item 14) | macro-F1, declared setting |
| PUBHEALTH | the claim; its explanation and main text | the source article, where items share one; else the item | 4-class macro-F1 where an arm gives it (D-376) |
| CLadder | the question and its background | the story or graph the questions share | accuracy |
| Corr2Cause | the premise and the hypothesis | the premise's variable set | F1 of the valid class |

The probe's and PUBHEALTH's owners (`causal-probe`, `other-domains`) state their group in their set's
own file before the check, as this table proposes.

**Open item 92** (the judge's training mixes never checked against the benchmarks' items) is closed by
naming the mixes as their own parts in every set's fingerprints and reading their counts in each
result's `candidates_by_part`:
- `judge_mix_2e=external/s05/T2E/replay_prompts.json#rows,held_out` (sha256 `08b20660...`,
  permissive_mix, 11,367 rows and 592 held out; the judge in use);
- `judge_mix_1=external/s05/T/T_TRAIN/replay_prompts.json#rows,held_out` (sha256 `eec83759...`,
  dev_mix and permissive_mix; superseded, still checked).

`#rows,held_out` reads the recipes' training and held-out rows only; the files' `questions` are
read-development prompts and are fingerprinted under the `judge` part instead. A set whose items
share a record with a mix is reported with the count by part before any judge figure on it, and its
hit items leave the set with their groups. train-judge's own filter covered ContraDoc and SciTab
development text and the 47 moved documents only; this covers every set's items.

## What it does not catch

A paraphrase below .92 that shares no 8-word run; a translation; a document that reached a part only
through a model's training data (the base models' own pretraining is not a part and cannot be checked).
These are stated beside every figure read on a set this protocol cleared.
