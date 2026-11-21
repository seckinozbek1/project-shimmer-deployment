# Negotiation round 3: an "open" room fate answer and unanchored positions (D-863, D-864)

21 November 2026, lane A for the lead. Prepared only: nothing was launched, sealed, requested or spent; no role
session started; no answer key, card, role folder or part 1 or part 2 item was opened. The diagnosis (development
sets only, system side) is summarised in D-864; this note records what was built.

## 1. Why

Round 2's `room_fate` (NEG_ROUND2_M4_M10.md) asks "kept, changed or removed" and maps only `changed` to counter, the
one stance M10 (`tools/score_neg_advisor.py` `open_point_prediction`) reads as movable. The key's movable class is
`open` plus `changed`, and `open` (still bracketed in the next round's text, about 70 percent of the movable class by
the declared sampler) had no answer: a text left on the table unchanged was "kept", scored settled. Movable answers
fell from 79 of 152 to 17 (c4pilot_1) and 66 of 114 to 7 (c4val_1_a). And the question showed each position with the
chain's own compare read ("read: against / fits / aside"): with no "against" the answer was "kept" in 156 of 156
cases over four runs.

## 2. The change (benchmark/baselines/neg_advisor.py)

- `room_fate_answers` admits one fourth answer setting counter (`ROOM_FATE_SHARED`); accept and reject stay set
  exactly once. Refused: a fifth answer, a duplicate label, an answer with no or an undeclared stance, a fourth answer
  setting accept or reject, a template not naming every label. The labels are the config's (WORDS-A).
- New switch `room_unanchored` (false as shipped, boolean, needs `room_fate`): `{room}` shows each touched position as
  "- party, round n: quote" without the "read:" line. Off, every question is byte for byte round 2's.
- First tokens on the producer's tokenizer (Qwen2.5-7B-Instruct, the cached unsloth bnb-4bit copy) are whole words:
  kept 97920, changed 17353, removed 45756, open 2508, all distinct.
- The scorer (`tools/score_neg_advisor.py`) is not changed: M10 and M4 are read as declared. No controller-bound file
  is touched.

## 3. The round 3 config (outside the repository, as round 2's)

`neg_advisor_prompt_r3.json`: round 2's measurement copy `neg_advisor_prompt_r2.json` (SHA-256
a54aa84a074b1f28451f8b870152c9f795bf8026959f88c91ce61957d46b96ed) with only these changes: `room_unanchored` true,
`room_fate_answers` kept accept, changed counter, removed reject, open counter, `room_fate_text` reworded (the
positions with no read label, then the four definitions: kept agreed as written and no longer in dispute, changed
reworded, removed dropped from the text, open still in dispute and may change in the next round; the answer
instruction last), `room_fate_note`, and `r3_note` in place of `r2_note`. Every other switch as in round 2.

- File SHA-256: aa7af8cc4083e284a3943ac847a6affa1c18c167dffd12b2bb68b8e2247f167c (set as the launch folder's
  config digest, as `R2_CONFIG_SHA256` is in NEG_r2_devpilot's launch.py).
- `config_sha256` written into the prompts files: d33cb2811861dff1b80894eba6255c71b0e433f7a3df5b8cf168c7636d5ff539.

## 4. Development prompts, rebuilt (`neg_advisor.py rebuild --prompts --config --out`)

From the round 2 development prompts files (no keys), same prompt and item ids, `rebuilt_from` each source's SHA-256:

| Output | Source | Prompts | SHA-256 |
|---|---|---|---|
| NR_r3dev_pilot_prompts.json | NEG_r2_devpilot/inputs/NR_r2dev_pilot_prompts.json | 24 | 3534a29d38fe07b3e40cdcacefc95dab53fb6e2712676c3f33a9ac3076a4a3b1 |
| NR_r3dev_val_a_prompts.json | NEG_r2_devval/inputs/NR_r2dev_val_a_prompts.json | 20 | cf371ea8a324f928e3c848e7b5d5c779a18557015e2169ca545f87b0cca8aa9e |
| NR_r3dev_val_b_prompts.json | NEG_r2_devval/inputs/NR_r2dev_val_b_prompts.json | 20 | 0c41795015743eceebf4793fe17ae8a0330b8941117da2aeb44d777c01e37122 |

## 5. Check 686 (tools/neg_round2_m4m10_checks.py)

Four proofs added (12 in all) and five neutralisations (7 in all), each failing its proofs, restored, passing:
`r2_unchanged` (the switch declared false and not declared ask, step and compose the same), `open_counter` (an open
proposal is a counter with its wording asked, both orders), `unanchored` (no "read:" label, every position still
shown, other steps unchanged), `r3_refusals` (duplicate, undeclared stance, no stance, fourth accept or reject, fifth
answer, unnamed label, non-boolean switch, switch without room_fate). Run with 22, 174, 356, 450, 466 to 468, 490 to
494, 515, 516, 518, 531 to 533, 535, 539 to 543, 651, 652, 686 and 688: all PASS.

## 6. Order (D-864, D-710)

Development runs on c4pilot_1 and c4val_1 (both halves) under the round 3 config; adopted only if M10 rises and no
bar figure falls beyond its interval; only then part 2 (31 items) is read once, through launch folders and the chain,
inside the 15 USD cap (D-863). Each bundle is sealed fresh from a commit holding this change.
