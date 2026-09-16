# Canonical pilot handoff — 2026-09-16

Final state: **SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE**.

`FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`

Read [the results report](SECOND_TUNING_CANONICAL_PILOT_RESULTS.md) and `second_tuning_canonical_pilot/RECOMPUTED_RESULTS.json` before further work. Tested source was `a818d43ec38bafffbf9e57e124efaddabd6fcf57`; frozen V2 SHA-256 remains `bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d`.

Producer completed 120 updates. Checkpoint 60 fails the prospective gates (gap F1 .153846; accepted outcomes .20; over-refusal .803571). Checkpoint 120's adapter exists, but only 42/60 DEV outputs completed; do not select it, extrapolate its metrics, or complete evaluation without new authorization. Auditor was acquired but never trained or evaluated. No role selection exists.

The $2 soft-budget assessment projected $3.562710 to complete mandatory work with reserve, above the $3 hard ceiling. The process was stopped, evidence downloaded and hash-verified, and Lambda termination verified. Total billable-wall upper bound: 96.9835 minutes; cost upper bound: $2.085145. Provider inventory is empty; temporary SSH registration, local private/public keys and role permit files were removed.

The archive and both adapters remain locally under `docs/fix/second_tuning_canonical_pilot/`; archive SHA-256 is `647a437cc6c326ad1dc307e1a345d84d27f2be2d8189fcc9369c395ec2126469`. Small reviewed evidence is committed; large binary payloads are not. `producer_events.json` contains all 120 losses; frozen `loss_diagnostics.json` contains only the first 60 because the second evaluation never completed. VRAM peaks are sampled lower bounds, not final CUDA peak counters.

The authorization was consumed (`LAUNCH_INTENT.json`). Do not delete that record, relaunch, add a second instance, run folds 1–4, access protected data, change frozen V2, or push under this authorization. Protected receipts remain unconsumed. No continuation is recommended from this incomplete pilot. No configuration adaptation was made after observing outputs.

Local verification command: `python -B tools/analyze_second_tuning_pilot.py` (requires the retained archive). The initial runtime projection underestimated observed generation time; causal overhead has not been isolated. Any future execution needs explicit new scope and a credible budget based on measured runtime. The unrelated root `SHIMMER_HANDOFF.md` and `durable/` user content were left untouched.
