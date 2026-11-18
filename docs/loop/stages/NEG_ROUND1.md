# Negotiation advisor, round 1 of improvement (standing order 102, D-707; bar D-709, NEG_BAR.md)

Lane neg-round1, 16 November 2026. Development only: the 24 pilot items (set 6a8af3c7..., development since D-695),
their 18 headline (P) items for M1 to M10, the saved answers of the arms pass (role N `runs/arms_answers_s25.json`,
`runs/cloud_answers_s25.json`, `judge_answers_s25.json`). Counts and aggregates only; no item text, label or
per-item row is in this repository. No model was run, nothing was launched, 0 USD. Every look and change is in
NEG_ITERATION_LOG.md.

## 1. Where M1 and M4 are lost (18 headline items, 179 proposals)

Each proposal of the key, by the first step at which the arm's answer for it is lost.

| Step | B1 | System | Cloud (14 items, 134) |
|---|---|---|---|
| No JSON object read (a brace in place of a bracket, 1 reply) | 6 | 0 | 0 |
| The model wrote no entry for the proposal (reply not truncated: every reply closed, far under 2,048 tokens) | 112 | 127 | 0 |
| An entry written, its id dropped by the parser (`17-1` for `P-17-1`, ANSWER-FORM-A forbids a prefix rule) | 0 | 20 | 0 |
| Withheld by the system's audit or checks | n/a | 0 | n/a |
| Conflict field unread | 0 | 0 | 0 |
| Answered, conflict wrong | 26 | 10 | 24 |
| Answered, conflict right | 35 | 22 | 110 |

- **Coverage is the first cause.** The system gave a piece for 32 of 179 proposals, B1 for 61. Nothing was cut off.
  The reply format allowed a proposals list of any length, and the 7B model stopped after a few entries. The
  constraint in D-672 (new runs) enumerated the ids but did not require each one.
- **The prompt and the conflict rule are not at fault for what was answered.** The key's conflict depends on
  structure alone for 106 of the 179 proposals: no persona position applies, so the label is `not_stated`. The
  check holds exactly, 106 of 106. The other 73 need a stance's meaning: 61 `no_conflict`, 12 `conflict`. Every
  answer either model gave on those 73 was `no_conflict` or `not_stated`. Neither local arm found a single
  `conflict`.
- **Answered pieces' stances:** system 32 of 32 `accept`, B1 60 of 61 `accept`. That accounts for M4: an
  accept scores only on `kept` (57 of 179). System M4 0.006 is 1 hit in 179, because 147 proposals have no stance.
- **Decoding and dropped answers:** no truncation, no stance or conflict value dropped for form. The parser drops
  ids for the system (20 of 25 drops, the drop share 10.3 percent) and the reply for B1 (1).
- **M3 at 0.0** (both local arms): the key holds only `bracketed` and `dropped` here. Both are structural (proposals
  on the table, or the previous round's index), and neither model wrote them for the right articles.

## 2. What was fixed, and the figures on development before and after (k=2 composition, saved answers)

**Fix 1: the system's Python step** (`tools/score_neg_advisor.py` `system_python`, check 450). It applies to the
system arm before the withholding and never reads the key. It sets what the item's positions on record decide by
the plan's own rules: `not_stated` where no persona position applies (87 filled, 6 set, 4 model answers refused
where a position applies); `dropped` and the structural state where `binding` is impossible (95 filled, 23 set,
8 refused, 23 left to the model); and an alignment party taken off where either side has no applicable
position (58). The model's answer is kept beside each. A stance is never read (WORDS-A).

**Fix 2, new runs only: one advice entry per proposal** (`advice_schema`: a fixed tuple in the excerpt's order,
each id fixed; reasons at most 8; the grammar's new `tuple` and `max_items` nodes in `scripts/schema_decoding.py`).
It removes the coverage loss and the 20 id drops at the source. It needs a re-seal (bound files) and a new pass.

**Diagnostic: M1's two parts** (M1s structural, M1m meaning), computed the same way for every arm. Without them,
a gain from Python could be mistaken for judgement.

| Figure (bar D-709) | Target | System before | System after fix 1 | B1 | Cloud (subset) |
|---|---|---|---|---|---|
| M1 | >= 0.60, lower > 0.33 | 0.149 [0.076, 0.249] | **0.419 [0.354, 0.620]** | 0.217 | 0.648 |
| M1s (structural, diagnostic) | | 0.218 | 1.000 | 0.203 | 0.916 |
| M1m (meaning, diagnostic) | | 0.129 | 0.129 | 0.274 | 0.558 |
| M10 | >= 0.60 | 0.109 | 0.109 | 0.207 | 0.507 |
| M4 | >= 0.60 | 0.006 | 0.006 | 0.061 | 0.396 |
| M7 recall / precision | >= 0.80 / >= 0.70 | 0.700 / 0.609 | 0.700 / 0.609 | 0.893 / 0.606 | 0.833 / 0.661 |
| M8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.918 |
| Drop share | <= 10 percent | 10.3 percent (25) | 10.3 percent (25) | 0.4 percent (1) | (20 drops) |
| M2 | report | 0.367 | 0.457 | 0.373 | 0.369 |
| M3 | report | 0.000 | 0.916 | 0.000 | 0.615 |
| M5 | report | 0.164 | 0.164 | 0.370 | 0.492 |

Intervals are 95 percent BCa over items (2,000 resamples). The pilot's old bar line 1 (system above B1 by 0.10)
reads true after fix 1. That is a development figure, made after looking at these items, and it is no result. The
whole gain is structural: M1m is unchanged, and on the meaning part the system stays below B1. The drop share is
the count of dropped fields over fields read plus dropped. A reply lost whole counts as 1.

**Tried and rejected (counterfactual, not built):** the approach list computed from the system's own alignment
(aligned somewhere, opposed nowhere): M7 0.393 precision / 0.267 recall, worse than both figures above.

**Measured, needing a decision (not applied):** reading `17-1` as `P-17-1` (a prefix rule, which ANSWER-FORM-A
forbids) would raise system M1 to 0.502 and M1m to 0.253 after fix 1. Fix 2 makes it unnecessary for new runs.
Reading B1's brace-for-bracket reply would recover 6 B1 proposals (B1 is not run again, D-671).

## 3. What the bar needs that Python cannot give (expected effects, on these 18 items' class mix)

- **M1:** with fix 2 and the model's own tendency (every positioned proposal `no_conflict`), M1 would be 0.637,
  just over 0.60, with the `conflict` class at F1 0. The bar can then be met without finding one conflict, because
  only 12 of 179 proposals are conflicts. **For the operator:** consider a floor on M1m or on the conflict class's
  F1 (a rule change, not made here).
- **Conflict detection itself:** the stance of each persona position (support, oppose, accept) is a narrow
  meaning question (CHOICE-A over three declared answers, the CASE-QUESTIONS-A pattern). Python then computes
  `conflict` (any oppose among the applicable positions), `binding` (an earlier accept) and the decided part of
  alignment by the plan's rules. Its accuracy is measurable on development against the build's validated stances
  (mapping kappa 0.96). If it reads 85 percent of stances right, M1m is expected near 0.8 and M1 near 0.85 (an
  estimate, not measured).
- **M4 and M10 cannot be reached by any stance rule built from conflict.** On these items: all accept gives
  M4 0.318 / M10 0.444, all reject 0.480 / 0.444, reject-on-conflict (key conflict) 0.352 / 0.444,
  counter-on-conflict 0.302 / 0.423. Both measure whether the advice foresees the next round's fate (kept 57,
  changed 36, removed 86). That takes a forecast: a narrow per-proposal question over kept, changed or removed,
  from the whole item, with the stance set from it. The expected effect is unknown until measured. Without that
  forecast, M4 at 0.60 and M10 at 0.60 are out of reach in this round.
- **M7:** recall 0.70 against 0.80. B1 reaches 0.893 recall at the same precision. A party list from the decided
  stances (aligned on every decided proposal) is the candidate once those stances exist. Built from the model's
  own alignment it was worse (above).

## 4. Lambda plan (Shimmer arm only, D-692; nothing launched; each step under 3 USD)

Rate basis: the arms pass ran 52 minutes for 1.12 USD (D-632), about 1.3 USD an hour.

| Step | What | Before launch | Expected time | Cap |
|---|---|---|---|---|
| L0 | Full gate on Lambda for this branch (test_18i of check 356 imports torch and could not run on the laptop; check 450 passes on the laptop) | merge into the lead branch | with the lead's next gate | the gate's own ceiling |
| L1 | System advice pass on the 24 development items under fix 2 (tuple schema), the derived audits, then the Python step at score time | re-seal (scripts/schema_decoding.py and benchmark/baselines/neg_advisor.py changed); role N builds the prompts for `system_advice` only; **decide the allowance**: 2,048 tokens is tight for 19 entries (about 1,900 estimated, more with counter wording). 4,096 is recommended for this group (a form change, the operator's or lead's call) | 45 to 70 min | 2.0 USD |
| L2 | Position-stance pass: one CHOICE-A question per position (support, oppose, accept), about 262 positions, short prompts, on the system's auditor family | build the form and its reader with proofs (laptop, fixtures, about 1 hour); declare the threshold (0, top answer, as for the judge) | 15 to 25 min | 1.0 USD |
| L3 | Fate-forecast pass: one CHOICE-A question per proposal (kept, changed, removed) with the item's context, stance set from it | build after L1 and L2 are read; written with its bar before any read | 20 to 35 min | 1.5 USD |

Stop rules for each step: refuse on a reply that runs to the cap (counted), or on any infrastructure failure
counted apart (D-451). The figures above are read on development only. The validation set is read once, only
when development reaches the D-709 bar.

## 5. The M1m floor (proposal of 20:40, now decided as D-712)

Proposal as put to the operator: on these items M1 reaches 0.637 with every positioned proposal answered
`no_conflict`, the `conflict` class at F1 0. A floor on the conflict class (or on M1m) closes that. Decided by
D-712 (Seckin 20:49): a floor of 0.60 on F1 of the conflict class under M1 and under M1m, and a floor on the
class that matters under every averaged figure (NEG_BAR.md, "The class that matters", committed 65b77dbf before
any new scoring). On the pilot's saved answers every local floor reads 0.0, except M4's `kept` (system 0.018,
B1 0.193). The cloud reference meets only M4's `kept` floor (0.75): conflict F1 0.222, movable F1 0.250.

## 6. Second task: D-711, D-712 and D-713 (built, 0 USD)

- **D-711, never invent:** `basis: on_record | inferred` with a quote-checked line. An inferred claim without
  a position is set aside and never scored. `record_kind` and `masked_party` are declared at build. Every bar
  figure is reported per kind, and a bar reading is refused without both kinds (check 466). On the pilot's
  saved answers (no basis written, so every entry counts as on record): 64 on-record claims with no position
  behind them (6 conflicts, 58 alignment parties), all already refused by the Python step. The bar reading is
  refused, because no pilot item declares a kind.
- **D-712, class floors:** check 467; NEG_BAR.md lists M1 to M10 with the class each floors.
- **D-713, two methods, declared and off by default** (check 468, fake generate):
  1. `reason_first`: a `rationale` field after `id`, before the labels, at most 300 characters. Both readers
     keep it apart; no figure reads it. The instructions add one sentence.
  2. `stepwise`: the chain per proposal is what it changes (copied from the proposal and checked there), then
     the stance of each position the mapping puts on it (support, oppose, accept), then a red line (asked only
     on a marked persona position), then an open point (yes or no), then wording for a counter. Each answer is
     checked before the next; a refused answer ends that proposal's chain. Python composes the conflict (any
     oppose, or a red line crossed), the stance (counter on an open point, reject on a conflict, else accept)
     and the alignment by the plan's rule. This folds in L2 (the stance of each position) and L3 (the open
     point, which is M10's class and drives M4's stance).
  The `stepwise` chain runs through an injected `ask`. The replay pass has no sequential chain yet: building
  it as derived prompts in rounds (as the audits are derived) is step S0 below. S0 built by lane/replay-methods
  (18 November 2026, check 515): neg_advisor.run asks the chain on the resident model, one prompt's steps in
  order (generated steps within the method's declared `max_new_tokens`, 512; choice steps at its declared
  `choice_threshold`, 0), one reply record a step, and `answers` composes the reply again from the saved steps.

### Lambda measurement plan for D-713 (development sets only; nothing launched; each step at most 5 USD)

Rate basis about 1.3 USD an hour (D-632). One re-seal batch covers every bound change of this lane:
scripts/schema_decoding.py, benchmark/baselines/neg_advisor.py and neg_advisor_prompt.json.

| Step | What | Before launch | Expected time | Cap |
|---|---|---|---|---|
| S0 | Laptop: the chain in the replay pass (each step a derived round of prompts from the checked answers of the last; CHOICE-A for stance, red line and open point) with proofs | none | about 2 hours, 0 USD | 0 USD |
| M-plain | system_advice, method plain, on each development set (fix 2, the tuple schema) | re-seal; role N's prompts for system_advice only; allowance decided (4,096 recommended) | 45 to 70 min a set | 2.0 USD a set |
| M-reason | the same, method reason_first | the method declared in config | 50 to 80 min a set | 2.5 USD a set |
| M-step | method stepwise: about 180 changes asks, about 260 stance choices, a few red-line choices, about 180 open-point choices, wording for counters | S0 merged | 30 to 60 min a set | 2.0 USD a set |

The development sets: the pilot (24 items, development since D-695) and at least one more (D-710 item 2, two
sets for any adoption); the new sets need items of both record kinds (D-711 item 3).

M-plain's allowance (D-725, 18 November 2026): 4,096 new tokens, declared as `advice.methods.plain.max_new_tokens`
in neg_advisor_prompt.json and read by `neg_advisor.advice_allowance` when a prompt is built and loaded (check 518);
reason_first has the same 4,096 as `advice.methods.reason_first.max_new_tokens` (D-740), so the methods are compared
to M-plain at equal allowances; B1 and stepwise keep `advice.max_new_tokens` (2,048), stepwise its per-step 512.
Fix 2 is commit 55d9c840.

**Adoption rule (D-713, D-710):** a method is adopted only if, on at least two development sets, it moves the
bar figures and class floors toward the bar on both record kinds, lowers none beyond its interval, and does not
raise the dropped-answer rate. Time and USD are reported beside it. Every look and every method tried goes in
NEG_ITERATION_LOG.md before its figures are read.
