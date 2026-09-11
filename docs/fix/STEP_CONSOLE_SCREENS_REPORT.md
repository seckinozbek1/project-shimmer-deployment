# CONSOLE: the missing screens, and the citation surface

**Built, not measured.** Everything here is proved on fixtures in tempdirs and against the
stubbed preview server. No pipeline run was started and no language model was loaded. The
ontology store in this repository is empty; the preview seeds fixture content into a local
store and that store is now gitignored, which it was not before this step.

## The audit, first

Three read-only lenses went through `console.html` (2682 lines) against the rules the
operator set: reachability, pattern conformance and both views, and qualifiers on numbers.
Fourteen findings came back and I verified every one against the code before touching
anything. Rule 6 passed outright (all four call outcomes are distinguishable, and the fifth
case, a valid reply with nothing irregular, is not conflated). Rule 2 passed almost
everywhere, with the GNN state correctly the one deliberate always-visible exception.

This commit closes the three missing screens and the two sharpest qualifier defects. The
remaining audit findings (the Agents page reviewer wording, the pairing map's missing
reviewer view, the two filtering defects, and the unreached `not_judged` / `reattributed` /
provision-history surfaces) are named at the end and are the next commit.

## Finding 4, treated as the most serious thing on the list

A finding's citations are what make it checkable. `source_refs` reached the console on every
finding and every amendment and were rendered **nowhere in either view**: zero hits for
`REF-` in 2682 lines. A reader had nothing to do but trust the sentence.

It is built as a **path**, not a field on a row:

- `GET /runs/{run_id}/references` serves the passages from the run's own
  `audit/reference_index.json`, which every run already writes and nothing served. `ref_id`
  returns one; an id the run never cited is a `404`, because "this run never cited that" and
  "that passage is empty" are different facts.
- In the console, each `REF-*` under a finding is a link in the same underline-on-hover
  vocabulary rule links already use. Opening it fetches that one reference and shows the
  passage in place. Nothing loads until a reader asks, so a list of fifty findings does not
  become fifty passages.
- Attached to **both** views, the reviewer's as "Rests on:" and the developer's as
  `source_refs:`, which the check pins at exactly two call sites.
- A `WEB-REF` is shown as an id without a link, because the index holds corpus passages and a
  link that goes nowhere is worse than a plain id.

Visible in `console_audit_shots/run_findings_human.png`: each finding now carries
"Rests on: REF-0012", and opening it shows the passage.

## Findings 11 and 12, the failure the GNN section exists to prevent, inside it

**12, the zero that means no step ran.** `last_loss` is `0.0` when *no backward pass
happened* (`denom == 0`, the honest nothing-new case), not when reconstruction was perfect.
Rendered as "Reconstruction error: 0" it is the strongest-looking evidence of learning the
page could show, in the one section whose purpose is to deny learning happened. Not fixed by
relabelling: the page now says which of the two it is. With no new nodes the reviewer view
reads "not measured this run, because no new nodes arrived to fit", the developer view reads
`0.0 (no backward pass; last_delta_size=0)`, and a following line states that the figures
above are carried over from the last run that had something to fit. A value the state never
recorded reads "not recorded" rather than the literal word `null`.

**11, two numbers that cannot reconcile.** `model_calls` is an all-phase total; the settled
figure beside it derives from review-phase calls only. Side by side with no qualifier the
larger number reads either as the floor being wrong or as each pair costing several calls.
The caption now says "all phases" on the number and states plainly that the two are not meant
to reconcile, and why.

## A real defect the screenshots found that no source read would have

After the new sections were wired, the GNN section rendered **nothing**, on the one section
required to stay visible when its subject is absent. The cause was three layers down:
`GET /ontology/gnn` imported `ontology_candidates`, which imports torch at module scope;
torch's import path calls `subprocess.Popen`, which the preview harness stubs; the route
500'd and the console dutifully cleared the section.

Reading a JSON file of counts should never have required a tensor library. `state_summary`
and the one qualifier string now live in `scripts/ontology_gnn_state.py`, which imports
nothing heavier than `json`, and `ontology_candidates` re-exports them so there is one
definition rather than two that must agree. The check asserts the module's **imports** by AST
rather than its text, because the docstring names torch to explain why it does not import it.

This is the class of failure that only shows itself in the rendered page, which is the
argument for proving the console against a running server rather than by reading the source.

## The other two missing screens

**Relations.** `relation_summary` was a finished read path whose only callers were three gate
assertions: the records job 2 writes had no route and so no surface. `GET /ontology/relations`
serves them, and the console renders a pair found by both mechanisms first and in bold, with
both reported directions beneath it, so agreement is legible rather than inferred.

**Conflict decisions, both halves.** Job 3 refused, listed and remembered, but there was no
way to answer. `POST /ontology/conflicts/{conflict_id}/answer` is that half, in the same
file-backed pattern the approval channel uses and with the same two constraints: it writes
the answer and nothing else, and the response says recorded, never resolved. Three answers,
not two. An unrecognised answer is a 400 and is never stored. The console shows the answered
conflicts with both sides named and the override rate **with its caveat printed from the
response body**, never retyped, and a null rate reads as "no answers yet" rather than as zero.

**Evidence classification** is served by `POST /runs/{run_id}/evidence`, which classifies from
the run's own artifacts and **never opens an answer key**: the caller supplies the expected
entries, which is the only thing a key contributes, and there is no parameter through which a
key path could be passed. Each row carries the `basis` naming the artifact behind every step,
so a classification can be checked rather than believed.

## A gitignore gap this surfaced

The ignore file's comment claimed the JSONL ontology stores were untracked, and no rule
actually ignored them. A console preview run seeds fixture provisions into the real store, so
those fixtures were stageable and could have been committed as if they were a real run's
content. `ontology/stores/*.jsonl` is now ignored and the store is back to zero bytes.

## The check, and its neutralise-and-restore proof

Check 214 runs the four routes through the real app on tempdir fixtures, asserts the console
consumes all four in both views, and pins the two qualifier fixes.

**Neutralise:** the reference index is emptied, so a citation resolves to nothing.

```
neutralised -> FAIL: the citation must resolve to the passage itself
restored    -> PASS
```

The first version of an assertion in this check was itself wrong in an instructive way: it
looked for the string "import torch" in the state module and fired on the docstring sentence
explaining why torch is *not* imported. It now walks the AST.

## Proof against the running server

`tools/console_preview.py --screenshots docs/fix/console_audit_shots`, the same stubbed-server
harness the console was proved with before, extended here to seed a reference index and the
ontology store so the new sections have something true to show, plus a screenshot anchored at
the ontology sections (the Agents page is far taller than the existing 2600 px crop). Eight
screenshots, both views.

## Still open, the next commit

- The Agents page reviewer view prints file paths and JSON field paths for five of nine parts
  on all 18 agents (audit finding 7), visible in `agents_human.png`.
- The pairing map has no reviewer wording at all (finding 9).
- `ontologyStoreHtml` drops four counts from the reviewer view; `amendmentRefusalsHtml`
  filters in both directions (findings 8 and 10).
- `not_judged`, `reattributed`, `unmatched_units` and provision history remain unreached
  (findings 3 and 5).

---

CONSOLE SCREENS COMPLETE (the citation surface built as a path from a finding to its passage,
relations and conflict answers and evidence classification reachable, the GNN zero and the
non-reconciling call count both made to say which is which, a torch-free state read that
fixes a section which silently disappeared, a gitignore gap closed; check 214 with neutralise
and restore; eight screenshots against the stubbed server; nothing measured)
