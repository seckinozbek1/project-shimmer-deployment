# Beta pre-registration (D-955 P4; drafted from B5_merged.md of 23 Nov 2026)

Written 25 November 2026, before any item of any beta set is generated and before any beta result is read. Targets come first; results come after. It sits beside `NEG_BAR.md` and `C_BAR.md` and follows the same rule: a bar may be raised, never lowered, and any change after a number is read is a new decision, stated as such. Where this file differs from the B5 draft, D-955 wins; the differences are listed in the last section.

Rule config SHA-256: config/neg_synth.json 6c02171dd00f349f1557b87354d5055c8b70c0ad425cedb7b73e2f9d1c6e2007; config/neg_synth_generator.json 945d9193c7e7a62c052c75f9fdbd6c901909d3c22055848efaafa919be24da6f (rule commit 7a289f0a on the freeze branch)

(The line above is the hash of the same-family rule's config. The lead fills it at the freeze, before the first generation launch.)

## 1. The 0.60 negotiation target and the key check

- The 0.60 targets for M10 and M4 (NEG_BAR, D-709) stay as written. They are never lowered. Pages say "0.60 reached" or "0.60 not reached" in plain words.
- The answer key is checked first, before any beta measurement, by two blind labelling rounds on a development sample of about 40 items, following the multi-agent-annotation-review method. Each round uses two different Claude models; Fable is not used. Open items after a round are settled by two Opus agents and marked "agent decision" in the record.
- Plain statement: Claude models also sit in the tested system and in the cloud comparison. The key check is therefore not independent of Claude, and the report says so.
- Agreement is Cohen's kappa on the M10 and M4 labels (the existing 0.60 rule). If kappa is below 0.60 on M10 or on M4, the 0.60 target for that measure is unreachable by construction. It is reported as such and is never lowered.

## 2. The beta claim beside the alpha, on the same measure

Read on the validation set (section 4), with M1, M10 and M4 each reported as follows:

- Beta: above chance, at least 0.10 above B1, and at most 0.10 below the cloud model on the same items (the D-842 form).
- Alpha beside beta: the frozen alpha system is re-run on the new validation set, and its figures sit next to the beta's on the same measure. The cost of this re-run is priced before launch (STEP-COST-A) and is not started until priced.
- The alpha's old untouched figures (M1 0.955, M10 0.393, M4 0.299 on 31 items, D-928) are shown beside it, labelled as a different set (real items, not the made validation set). They are never pooled with the new figures.

## 3. Chance tests and intervals (unchanged from the draft)

- Interval: 95 percent BCa paired cluster bootstrap; cluster = item (negotiation), table (SciTab), document (ContraDoc) (GATE-SCORE-A).
- Chance: `tools/chance_test.py` label permutation, at least 10,000 shuffles, seed 20261121 (D-872). Shuffle within each item so the test respects the cluster. The comparison script and the negotiation scorer use the same chance test (the gap found in D-931). Against B1 and the cloud: paired by item.
- Level: the k-th committed reading of a claim at 1 - 0.05/2^k, split over that reading's named claims (D-395). Proposed claims per validation reading: system against B1 on M1, M10, M4.
- SciTab's beta headline is the declared macro-F1, not the alpha's accuracy over answered.

## 4. Sets and sizes

- Validation: 80 items, at least 20 per party structure, both record kinds, one frozen set, one look per round. Pilot: 40 items, opened once, then joins development. Development: as many as made.
- Indicator only: every per-structure and per-class reading; M4 against B1 or the cloud below about 60 to 100 items; M7. ContraDoc and SciTab 10-point bars are indicator only on any beta validation set; only the closed final sets (230 and 363, D-879) can carry them, and they stay closed in the beta.
- No negotiation final test yet. Its source is chosen later, from real items. Made (synthetic) items are never the final test and are never called "final test" or "untouched".
- Every set already read (the alpha's 31 untouched items, the 24-item pilot, the 15 SciTab claims, the 8 ContraDoc documents) is development from now on and is not reused as a beta test.
- Every new set records generator model, seed, card, freeze hash, and passes the leakage check against all development material before first use (NEG-SYNTH-A, GATE-LEAKAGE-A).

## 5. Generator, labeller and the generation trial

- Generator: OLMo, the copy already sealed on the rented file system. Its family is named here, before generation.
- Labeller: OLMo, in a separate blind sealed pass; the labeller never sees the generator's prompt or metadata. Generator and labeller share a family. This is stated plainly in every report on these sets: the label check is not independent of the generator's family, and it is allowed only under the narrow rule of D-955 (separate sealed passes). This is why the key check of section 1 uses Claude labellers and not OLMo.
- Generation trial: 24 items made by the OLMo generator first. It is a generation trial only. It is not the pilot set and is not scored for any claim.
- Switch threshold: the validator pass rate on the 24 trial items is the share of generated items that pass every validator check on the first generation (structure, party structure computed from declared parties, red line source present, dedup, surface-cue check), counted before any regeneration. If this rate is below 0.70, the generator switches to the declared fallback, Granite 8B, and the trial is repeated once with it. The threshold is fixed now and is not changed after the trial.
- Why 0.70: B6 describes the validators (dedup, cue check, label compare) but gives no pass-rate figure, so this is a judgement. The reasoning: validation needs 80 items and pilot 40 (120 in all) from a budget of about 400 to 455 cards, which is roughly 3 cards per kept item; a first-pass rate under 0.70 means regenerations (counted) would exceed that card budget and the 5 USD step line, and costs more than moving to the smaller fallback model.

## 6. Empty answers (unchanged from the draft)

- An empty piece is tagged "empty" with its reason; counts by reason in every score report, ids in a listing file; the next validation or pilot rechecks each earlier empty (now_answered, still_empty, not_in_this_run).
- Scores are unchanged: empties count as wrong where they already do. Beside every headline: "N of M empty (x percent)" and, where it differs, the answered-only figure named as such.
- Refusals stay and are never loosened after a result: 5 percent coverage (D-871), 50 percent oddity alarm (D-929), 10 percent negotiation drop share (NEG_BAR). "withheld" is counted apart from silence.
- Target for "fixed": zero still_empty, and an empty share at or below 2.5 percent.

## 7. Time rule and what voids it

- This file is committed, with its hash, and pushed to the private backup before any new set is generated. Its hash and time go into DECISIONS.md. The first generation launch names that hash or is refused. A set frozen before the commit is refused by the scorer.
- A measure is reported "not pre-registered" if: a target, test, level, set role or empty rule changes after any item of a new set exists; a set is read more often than its role allows or a validation result picks a threshold; a made set is called the final test; a refusal line is loosened after its result; the scorer or chance test changes after a set is frozen without a recorded re-score; the commit is not an ancestor of the first generation commit or the file's hash differs at scoring time.
- Counts and re-simulated power may be filled in later without voiding. The rule config hash line at the top is filled at the freeze and does not void.

## 8. Changes from B5_merged.md (all from D-955 unless marked)

1. Key check: now two blind labelling rounds, two different Claude models each, no Fable, open items settled by two Opus agents marked "agent decision"; the draft said two independent labellers. Claude presence in the tested system is stated.
2. Kappa below 0.60 on M10 or M4 now explicitly means 0.60 is unreachable by construction and is never lowered.
3. Beta-beside-alpha claim added: frozen alpha re-run on the new validation set (priced first), old 31-item figures beside it as a different set, never pooled. The draft compared only against B1 and the cloud.
4. Questions to the operator are removed: sizes fixed at validation 80, pilot 40; no negotiation final test yet.
5. Generator and labeller added: OLMo generator, OLMo labeller in a separate blind pass, same family stated.
6. 24-item generation trial (not the pilot) with a 0.70 pass-rate threshold switching to Granite 8B added; 0.70 is the author's judgement (no basis in B6).
7. Rule config SHA-256 line added, filled at freeze.
