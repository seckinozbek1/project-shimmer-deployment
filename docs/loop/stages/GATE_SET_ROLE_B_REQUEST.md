# Request to role B: draw the D-S92 gate set from the sealed pools, with no leakage (D-S100, D-S120)

Drafted 9 November 2026 by `choice-build` for the lead (D-374), in the form of the D-S63 request, and
revised after the vekil leakage audit (D-425) and D-S120 (option A: a claim set of about 230 ContraDoc
documents and 250 SciTab claims, replacing D-S118's largest set, D-453). The lead
copies it to `docs/loop/private/` and fills the bracketed lines before role B starts; the vekil
leakage audit reads it, `GATE_SET.md` and `LEAKAGE_PROTOCOL.md` first. The lead never opens sealed
material; every step below is role B's, in role B's own folder, under the existing role separation.
Print no label and no text, anywhere.

## Inputs the lead puts in `_xfer\lead_to_B\gate_D-S100\`

- `fingerprints.json.gz` (`gate_leakage.py fingerprint`): hashes, 8-word runs and bge-m3 float32 unit
  vectors of every part of GATE_SET.md section 9, each source file's SHA-256 and the files skipped. No
  text. The judge's two mixes are parts of their own (`judge_mix_2e`, `judge_mix_1`), so the result's
  counts by part answer open item 92. [Its SHA-256.]
- `exclude_ids.json` (`gate_set.py exclude-ids`, sha256 `a0bfa6d880ce7117f6fec44dea12c0e0c052151ed1335e7edcff90dccefabad0`): every ContraDoc development
  document id and group key (184 and the 47 moved), the fresh set's 100 ids, and every SciTab
  development paper (15) and table (29). Ids only. The fresh ids come from the one exception (D-442): the fresh set's ids file, `external/s05/D-S56/contradoc_fresh100_ids.json`, read for its ids only, admitted by its pinned digest (`ec2498fd...`) and only by `gate_set.py exclude-ids --fresh-ids`; nothing else under `external/s05/D-S56/` is read by any gate tool;
  its path and digest are in the list's `fresh_ids_provenance`. Nothing under D-S56 is given to role B.
- `cosine_step.json` (LEAKAGE_PROTOCOL.md step 2): the cosine figures on development material and the
  threshold in force. [Its SHA-256.]
- The code: the loop commit 0fa199fc (lane/gate-set merged, D-459), which holds
  `benchmark/adapters/common/gate_leakage.py`, `benchmark/adapters/common/overlap.py`,
  `benchmark/baselines/gate_set.py`, `benchmark/baselines/b1_prompt.json` and
  `benchmark/dryrun/token_counter.py`. Role B runs them from a checkout at that commit and records the
  commit and each file's SHA-256.
- **Preregistration v3's SciTab sealed share is kept** (D-440): 30 tables, the preregistration's size
  (version 2, section 2), held back by `gate_set.py draw-scitab` itself from the whole holdout pool by
  the salt `20261109-v3-sealed:`, whole papers, before the quick subset. Its paper ids are in the draw's
  output with the held papers the leakage check flagged: the ids only are listed; nothing of those
  papers is built or sent, and they stay sealed. A demonstration table does not count toward the 30: role B gives its
  in-context example table ids with `--demonstration-tables`. Only Seckin may release the share.

## What to do

1. **Confirm the pools** from role B's own manifests: ContraDoc's sealed side (660 documents, 479 groups
   after D-S63), SciTab's holdout pool (1,129 claims, 184 tables). Record each source file's SHA-256
   and, for SciTab, how many not-enough-info claims the pool holds (a count, through
   `tools/score_corpus.py` or the adapter's own reading, no claim shown). If the pool holds none while
   the released file does, say so and stop: the pool was filtered and D-380's draw cannot run as written.
2. **Check every candidate** of each pool:
   `python -X utf8 benchmark/adapters/common/gate_leakage.py check --fingerprints fingerprints.json.gz
   --benchmark contradoc --input <pool file> --assignment <B's frozen split file> --side holdout
   --exclude-groups exclude_ids.json --cosine-step cosine_step.json --embed --out contradoc_leakage.json`,
   and the same with
   `--benchmark scitab` and no assignment, its exclusion file extended by the SciTab paper's in-context
   example table ids (written as a second file, its digest recorded). The embedder is the repository's
   bge-m3, loaded offline from B's cache. The output is counts, ids and digests only.
3. **Draw** on what was kept, each command given the three digests above (`--fingerprints-sha256`,
   `--exclude-ids-sha256`, `--cosine-step-sha256`; for SciTab the exclusion digest of the extended
   file; for SciTab also `--demonstration-tables <its file>`): `gate_set.py draw-contradoc --leakage contradoc_leakage.json --input
   <pool file> --assignment <split file> --out contradoc_gate_ids.json`; `draw-scitab --leakage
   scitab_leakage.json --input <pool file> --out scitab_gate_ids.json` (for SciTab, v3's share held
   back first). The quick subset next, then the claim set at its size (D-S120 option A, D-454, D-458):
   whole ContraDoc groups until 230 documents, and whole SciTab papers until 352 claims whatever the
   class setting, counted as drawn, by the salt `20261109-D-S92:`, stopping at the first that reaches
   it. The draw reads no label and is run once. If either refuses (a pool that cannot reach the size),
   stop and report the counts. **No threshold, floor or rule is changed after any count is
   seen**; only Seckin may change one after that, in writing.
4. **Write the drawn records** in the development files' own format (ContraDoc: the fields of
   `external/contradoc/dev/ContraDoc.development.json`; SciTab: those of
   `external/scitab/dev/sci_tab.development.json`), claim set and quick subset each in its own file.
5. **Build the bundles** with the adapters, B3 and B1 in one build call per benchmark and set:
   `--max-context 32768 --output-allowance 2048 --token-counter benchmark/dryrun/token_counter.py`
   (sha256 `95e8c968fb5f762212ece1de04a75acf59852bbae3059ae1805c191cc8dccf5a`) `--b1-prompt
   benchmark/baselines/b1_prompt.json` (sha256
   `25a7d40ef1f7e90a6491501bf146611ac808efd900016bcf5f0ea53d8c4f29dd`) `--side holdout --development`,
   with `--assignment <split file>` for ContraDoc. Record each bundle's items file, manifest and answer
   key SHA-256. The token counter's digest `95e8c968...` is of the CRLF working copy, which is how G1's
   build read it (its git blob at 0fa199fc, LF, is `108040c9...`); `b1_prompt.json` is the same in both
   forms. So role B checks out with `core.autocrlf=true`, as on this machine, and confirms both digests
   on its working copy before building.
   **The declared builds (D-331, D-471; added 11 November, before any build).** The system's B3 bundles
   carry the declaration its narrow step is asked through, and B1's bundles do not, so each benchmark
   and set is built twice, into two folders, from the same input file and with the same options above:
   - **as shipped** (no further option): B1's bundles and prompts come from this build;
   - **declared**, the same command with one more option: SciTab `--rule-declaration "compare: cells"`
     (every claim's heading gains `[compare: cells]` and the rule's text is the claim alone, as the cell
     step reads it); ContraDoc `--rule-declaration "compare: passages"` (CONV-CDOC-01's heading gains
     `[compare: passages]`). B3's bundles come from this build. For example:
     `py -3.12 benchmark/adapters/scitab/adapter.py build --input <drawn claims file> --out <folder>_cells
     --max-context 32768 --output-allowance 2048 --token-counter benchmark/dryrun/token_counter.py
     --b1-prompt benchmark/baselines/b1_prompt.json --side holdout --development --rule-declaration
     "compare: cells"`.
   The option exists from lane/gate-attempts on (`common/bundle.BENCHMARK_DECLARATIONS`); a build of one
   benchmark refuses the other's declaration. **The cut is computed from the as-shipped rules in both
   builds (D-478, `common/bundle.shipped_rules`):** each document's budget and prompt overhead come
   from B1's prompt over the rules as a build with no declaration writes them, so under the token
   counter and limits above the declared build keeps exactly the parts, the cut and the `parts.json`
   of the as-shipped build. Role B builds from a tree that holds that change (lane/gate-attempts
   after D-478, or the loop branch once it is merged; a tree with the option but without the change
   writes another `parts.json` and fails the check below). Role B confirms, per benchmark and set,
   that the two builds hold the same document folders and that `items.json`, `parts.json`, every
   `answer_key.json` and every document file under `context/` are byte for byte the same in both
   (SHA-256), and reports any that is not, with nothing built from it; only `conventions/rules.md` may
   differ. The ids file names both bundle manifests per document.
6. **SciTab's class setting, after the draw** (D-380, D-458): count the gold classes of the drawn claim
   set through the scorer (`tools/score_corpus.py` item_table over its keys), write
   `scitab_class_counts.json` as `{"supports": n, "refutes": n, "not enough info": n}`, and run
   `gate_set.py class-setting --counts scitab_class_counts.json`, its result saved as
   `scitab_class_setting.json`. Under 2-class, add to that file `not_enough_info_ids`: the not-enough-info
   claim ids (source ids, ids only) of **both** the claim set and the quick subset; they leave at the
   freeze, about 250 claims of the claim set are scored, and the scored count is reported. The draw is
   never run again.
7. **Remove the drawn documents** from the sealed manifests and record the sealed side's new document,
   group and table counts.

## What goes to `_xfer\B_to_lead_dev\gate_D-S100\`

- `report\`: `contradoc_gate_ids.json`, `scitab_gate_ids.json`, the two leakage results, the class
  setting result and, under 2-class, the ids left out; a `REPORT.json` with every digest above, the
  commit, the counts of steps 1, 2, 3, 6 and 7, and the start and end times. Counts, ids and digests only.
- `held\`: the bundles, without their answer keys. **No agent opens this folder** until the lead has
  committed GATE_SET.md section 10 (the frozen digest and the counts) and the vekil leakage audit has
  read the counts and the ids; the lead then moves it to the development side and records the move.
- **Keys:** to `_xfer\B_to_lead_dev\gate_D-S100\keys\` only, which only `tools/score_corpus.py` reads.
- A line in `docs/loop/private/FOR_SECKIN.md` or `_handoff\B_D-S100_DONE.json` with `REPORT.json`'s
  SHA-256. Print no label.

## What the lead does after

Re-hashes every file against `REPORT.json`, fills `GATE_SET.md` sections 9 and 10, commits, has the vekil
leakage audit read the counts and the ids, then releases `held\`. The first read is B3 and B1 on the
quick subset, a steering read logged in `HELDOUT_OPENINGS.md`.
