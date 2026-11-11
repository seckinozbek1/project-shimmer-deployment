# Development cases

**Exposed, development only.** Every case here is built from material that is in this
repository, with its expectations and earlier keys beside it. Anything that reads the
repository can read it. A result on a case here is never a held-out measurement and is
never evidence of recall on unseen material. These folders sit outside
`benchmark/corpora/`, so no existing test changes and the corpus checks (236, 239, 241,
243, 273) do not apply.

## The worked cases (D-S39)

Two demonstrations, first set for the 12 November milestone, now the 14 November package
(D-S126). They are not benchmark evidence. Each ran once on the loop's A10 on 8 November 2026
(D-332): both multi-round entries passed execution integrity, and both ordinary reviews failed
their output contracts (`semantic_incomplete`). The rerun on the product as it stands is
issue #213. Case 1's run input is `.docx` for its texts and Markdown for its notes;
case 2's is Markdown. Each folder holds `workload/`, which is what the sealer takes, with
`EXPECTED.md` beside it. The sealer refuses any folder holding a member outside `context/`,
`conventions/`, the targets file and the case manifest, so giving it the case folder itself
fails. Each builder writes the folder, and `--check` compares it. Beside `workload/` each case holds
`ordinary/`: the same members without `case_manifest.json`, the ordinary two-version review of
`docs/INPUT_FORMAT.md` section 12, built and checked with it so it is sealed as committed.

**`host_agreement_three_rounds`** (`build_host_agreement_case.py`). Synthetic: a seat agreement
between a fictional organisation and a fictional state, over three rounds, with each party's
position note per round. The run input in `workload/context/` is mixed, on purpose: the three
texts are `.docx` files with real tracked changes against the state before, and the six position
notes are Markdown. `--check` proves each `.docx`, read by `scripts/text_extract.py`, is that
round's text exactly, the one the manifest's spans are measured on, and that rejecting every
change gives the state before. This case is the one exception to section 12's "Write case
documents as Markdown": its `.docx` texts were first run in that 8 November launch.

**`draft_resolution_revision`** (`build_resolution_case.py`). Real public text: UN documents
A/C.2/74/L.34 and A/C.2/74/L.34/Rev.1, with `source/` holding the text extraction (typographic
quotation marks written straight, no word changed) and the builder declaring every repair.
Nothing is planted.

## negotiation_three_rounds

A live multi-round case (`docs/INPUT_FORMAT.md` section 12) over the three anonymised
offers in `benchmark/corpora/negotiation_r2_to_r3/` and
`benchmark/corpora/negotiation_r3_to_r4/` (loop S5 item 0.9, DS5-10). Only those
anonymised, tracked files are read (H6). The folder is in the test archive layout:

```
_review_targets.json   the last offer as target, the one before it as prior, both earlier offers as grounding
case_manifest.json     the case manifest (fixture false)
context/               the three offers, copied from the corpus files
conventions/           the corpus's own mandate, copied
```

The manifest declares three rounds (`r2`, `r3`, `r4`, sequence 2 to 4, the corpus
folders' own round names), one document each; two actors, `company` (whose offers the
documents are) and `union` (whose vote on each offer the documents report); one issue
per term of the corpus's fixed label schema plus one for the vote (fourteen); and 34
sources. Each term source quotes the term's whole label line as written, on the unit
that holds it (`pairing_map.split_units`); each vote source quotes the sentence that
reports the vote. A term a round does not state has no source in that round. Every
source is `accepted`, because each quotes its document exactly.

It is written by `build_negotiation_case.py` and never by hand:

```
py -3.12 -X utf8 benchmark/dev_cases/build_negotiation_case.py           # write the folder
py -3.12 -X utf8 benchmark/dev_cases/build_negotiation_case.py --check   # compare it with the build
```

The gate's proof is `scripts/dev_case_checks.py`: the sealer's own reader reads the
folder, the bound pipeline's `_load_corpus` loads the documents, the controller's
`validate_live_case_manifest` accepts the manifest and `multi_round.bind_sources` binds
every span; a span shifted by one character is refused by both; the folder equals the
build and its documents and conventions are byte copies of the corpus files.

**What it is for.** The first execution of the multi-round path on real (anonymised)
text: run health (outcome `reviewed`, activation `activated`) and the reuse of unchanged
units (`audit/round_reuse.json`). It is run as a multi-round Review with
`--multi-round --multi-round-manifest case_manifest.json`.

**What it does not carry.** No answer key. The corpus's own keys score the ordinary
two-version reviews (r2 to r3, r3 to r4), and a multi-round key (`docs/INPUT_FORMAT.md`
section 9, entries scoped by round and document) would have to be written from the
mandate by someone who has not seen a run; the repository's scorer does not read a
multi-round key yet (open item 17). Any quality figure from a run of this case is
reported apart and is never called a pass.

**Its ordinary review is not the corpus test.** The same members without
`case_manifest.json` make an ordinary review of the 31 October offer against the
19 October one, but with the 23 September offer as a second grounding file, which the
corpus folder `negotiation_r3_to_r4` does not have. Score an ordinary review against
the corpus key only when it is run from the corpus folder itself.

**What the documents say about themselves.** Two of the offers carry a correction note
in their opening text (figures the source reported and the file omitted, and a one-time
contribution restructured rather than withdrawn). The notes stay as they are: the files
are byte copies. A multi-round run shows the models the spans, never the documents, and
no span quotes a note.
