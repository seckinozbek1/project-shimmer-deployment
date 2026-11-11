# The bar for the judging path (D-S41, D-S42 C and M)

Written 2026-11-06, before any decision exists on a real model, and revised the same evening after its attack (3 CRITICAL, 10 SERIOUS, 10 MINOR, D-280). No reply or decision of this form has been read. It replaces `p2a_bar.json`'s thresholds for the decision form; that file's reach figures carry over. Development, exposed. Any change after a number is read is a new decision, stated as such. The figures below live in code (`choice_read`), the bar file names the inputs by digest, and the read refuses another figure.

## What is measured

- **Candidates.** The base model on C's path (Phi-4, `unsloth/phi-4-bnb-4bit`), then the trained model on the same prompts (T), bound by `prompt_id` and `user_sha256`, since an adapter changes the file's digest. Each is one row.
- **Items.** The 60 ContraDoc documents of `p2a_prompts.json`, their pairs as they stand, both orders; SciTab's 95 claims are built and the two of `g1_bar_items.json`'s `left_out` are dropped at reading, leaving J1's 93, Python's selected cells.
- **Comparator.** The same untrained model bare, B1, on the same items, rebuilt per half through the scorer from `external/s05/J1/read/labels/`, since the result file holds only aggregates. On each benchmark the group with the higher measure, a tie taking the group with reasoning; the other group is reported beside it. A group past D-241's abstain floor is no comparator. Compared with no published figure.
- **T's comparator is that same B1, by this decision.** The trained model has no bare run of its own, so "above B1" for T means above the untrained model, and D-S33's target is not read for T.
- **Scoring.** No rule changes. Labels go through `tools/score_corpus.py`, as B1's do. Silence is never detection. An ABSTAIN is written one way, each row keeps a `source` (top answer, threshold, tie, refusal), and a tie or a failed pass never reaches a label.

## Reading a decision

- **Pairs.** A pair is readable when both orders gave a decision. It is flagged when both orders have contradicts as their top answer with confidence at or above the threshold. A settled "cannot tell", a split between orders and a confidence below the threshold are not flagged, and are counted.
- **Documents.** FLAG when any pair is flagged. Else CLEAR when at least 95 percent of its pairs are readable, else ABSTAIN. CLEAR rests on the proposed pairs alone: a top-40 pair holds both marks on at most 14 of the 30 gold documents, so a CLEAR is a limit of the proposer as much as of the model. ABSTAIN counts wrong in accuracy.
- **Claims.** Holds, not met or cannot be settled, the top answer; confidence below the threshold reads as cannot be settled, `source` threshold. A claim Python's selection refused is ABSTAIN.
- **Unreadable.** A tie, a failed forward pass or a refused prompt.

## The split, the threshold and one read of half B

Documents are split once by SHA-256 of `20261106:` plus the document id, in hash order: ContraDoc 30 and 30; SciTab's 29 documents, the lower 15 half A, claims staying with their document. Gold per half and gold a top-40 pair can reach per half are counted through the scorer and reported before anything is read.

**Half A.** First the fixed answers are tested: the share of prompts with declared mass under .5 must be at most .2. If it is not, the candidate is `void`, half B stays closed, and the prompt may be changed by a new decision without spending it. Then the threshold is the value of .5, .6, .7, .8, .9, .95, .99, .999 with the best figure among those meeting item 2 and item 4 below with at least one flag: accuracy on ContraDoc, net breaking a tie; macro-F1 on SciTab; a tie takes the higher value. If no value qualifies, the result is "no usable threshold", a `drop`, and half B stays closed. A trained model sets its own threshold the same way. Its checkpoints are fixed before training, the last and at most three earlier, chosen on half A by the same figures, a tie taking the fewest steps.

**Half B is read once, for base and trained together.** T's data and recipe are frozen and sealed before the base model's half B is opened, so nothing read there can shape T. Until then the base model's report carries half A only and says so. If T does not run by the milestone, the base's half B is read alone, and that is stated. Every read of half B is counted in the result.

## The verdict, per benchmark, on half B

`void` first: fewer than 95 percent of prompts readable, or fewer than 90 percent of documents with every pair readable.

`keep` needs every one of:

1. above B1, strictly: ContraDoc accuracy, with ABSTAIN wrong, and net at least B1's; SciTab macro-F1, **and macro-F1 again from the top answers with no threshold,** so that moving doubtful claims into the third class cannot supply the rise;
2. at most 80 percent of documents or claims flagged;
3. chance tail at most .0125 for the flags (`doc_judge.chance_tail`): four looks, two candidates on two benchmarks, J1's practice;
4. precision at least B1's: SciTab on the half, where B1 raises at least 5 flags there; ContraDoc against B1's whole-sample .75 on 8 flags, since B1 raises under 5 on the half. SciTab with under 5 B1 flags on the half has no precision gate there, and says so; on half A that whole-sample figure is B1's, whose gold includes half B, used as a comparator only. Where B1 raises no false alarm, the candidate raises none (D-S33);
5. ContraDoc only: at least 3 `placed`, `placed_share` as D-276 set it (two times `partner` at least the flags on two-mark documents), and net above the Python-only control's on the same count of flags, on half B only, reported as a single draw.

Otherwise `drop` for that benchmark. "No usable threshold" is a `drop`.

**A trained model.** Its `keep` also needs item 1 against the base model on the same half; the base's figure is computed even if the base is `void` or `drop`. Any statement that training helped needs the exact sign test on the items where the two disagree, at .0125. A strict rise without it is reported as a rise, and no more.

**The target is D-S33's and is not read here.** It needs the 95 percent interval of the paired difference in accuracy (ContraDoc) or macro-F1 (SciTab), bootstrap over documents, above zero, on a sample sized before it is read, and flag precision above B1's. These samples were not sized for it, and SciTab's half has 14 or 15 clusters. A `keep` says the candidate goes on; it never says the target is met. Item 4's "at least" is a mark for going on, not D-S33's "above".

**Power, stated.** At .0125 with 15 gold in 30, six flags must all be right. A real but modest judge can fail item 3. That is accepted: a false go costs more here than a missed one, and the failure is reported with its counts.

## Reported beside every verdict

Right and false flags, abstentions, unreadable count, ties, declared mass (median, share under .5), logits dtype, right counts by `source`, F1 of each class, agreement between orders, flagged pairs per document, pairs on the mark, the contradict rate on clear documents, confidence by decile against accuracy on claims and on a document's top pair (the lower of its two orders), `selected_by` counts, seconds per prompt, cost. Stated plainly: what the judge was trained on and that the benchmarks were not in its training data.

## Two trained candidates (the operator's licence rule, D-281)

The adapter that may be published is trained only on the permissive-licence mix; the share-alike mix is for development measurement only, and its adapter is never published or packaged. So T is two candidates, `permissive_mix` and `dev_mix`, read together in the one read of half B, under one recipe digest, each by this bar. **Written before any number:** the permissive mix is `clearly_worse` when it loses `keep` on a benchmark where `dev_mix` has it, or is lower on half B by at least 3 documents' accuracy on ContraDoc or .05 macro-F1 on SciTab. If it is, the operator is told before anything is published. The second bar's digest is committed in a decision before half B is opened, so its time has a record.

## What this cannot show

Half B holds 30 ContraDoc documents and 14 or 15 SciTab documents, about 46 claims, so a `keep` is a development signal. These items were read by earlier decisions, J1 among them, and Phi-4 was chosen on them. The ranker scored AUC .491 against gold (D-276), so pairs are a broad net and the judge carries the selection. The measured model is not yet the shipped one (D-276). **The measured selection is not the product's:** the replay selects cells once on the whole document with the claim stripped, the product per unit with the rule's whole text, so a single table can take `whole_table` where the measurement refused, and one claim can ask several tables. A `keep` here does not carry to the product path until it is measured again. None of this is a figure for a person's own machine.
