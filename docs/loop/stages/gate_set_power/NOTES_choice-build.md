# choice-build notes, 9 November 2026

These notes record where the gate set work stood at the D-S122 stop.

## lane/gate-set

- Merged into the loop branch at 0fa199fc (D-459), after gate-leak-audit's PASS on 68282e67. 72 proofs in `scripts/gate_set_checks.py`, run by check 325.
- The role B request names the code commit 0fa199fc. Two of its inputs are not built yet, and both need the lead side:
  - `fingerprints.json.gz`, which needs bge-m3 on an idle GPU. Run `fingerprint --count` first for the forecast.
  - `cosine_step.json`, made by `gate_leakage.py cosine-step` on development material.
- `external/s05/GATE/exclude_ids.json` (a0bfa6d8) is built.

## lane/choice-2 (3407b0e3)

- Clean-worktree runs:
  - at 8472ffb9: either_test 10/10, fresh_test 42/42;
  - at 3407b0e3: system_test 68/68.
- Waiting for choice2-check's recheck before the lead merges.
- Open, with me, before the fresh read: rebuild `external/s05/D-S56/fresh_prompts.json` under the merged config, and update `system_test.FRESH_PROMPTS_SHA256` (choice2-check gap 1).

## Incidents

- INC-035: reads of four `items.json` files under D-S56 (ids only). Recorded and closed by the guard.
