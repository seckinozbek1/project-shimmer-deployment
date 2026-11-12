# Plan for the work after v1

> **Superseded in part (9 November 2026, D-371).** D-S92 makes the fresh read conditional on a pre-read gate (the whole system at least 10 points above B1 and at most 5 below the cloud reference, on held-out development items, in each paper's own metric, D-S99). The fresh read on 10 and 11 November happens only if that gate is passed. If not, the 12 November package states where the system stands against both bars and the work goes on. The hour-by-hour plan to the gate is in the return brief.

Rewritten whole on 2026-11-08 by the lead (D-321), as D-S51 and D-S56 ask and D-S69 item 2 repeats: each step appears once, in order, and names the Annex D entry it comes from and the decision that records where it stands. It replaces every earlier ordering in this file. Work that is finished, superseded or cancelled is in `DECISIONS.md` and in the request ledger, and is named once at the end of this file. Opus, medium effort (D-S11); routine lanes on the cheaper model where D-S27 item 1 allows, and everything listed in D-S27 item 2 on the strong one.

## The principle (D-S42)

Shimmer's governance and honesty layer stays as it is. What changes is everything a model-backed role sees and returns: **(a) context:** a short prompt with one narrow question, only the passages or cells Python selected for it, no agent contract text, no filled or worked example; **(b) output:** fixed answers read from the model's probabilities, no free text (D-S41, D-S62 item 3); **(c) the model:** trained for its task where training beats its untrained form (D-S57 item 3, D-S70 item 6). Since D-S57 and D-S70 this holds for every model-backed role, not the judge alone.

## Rules every step obeys

- **Parallel by default, accuracy never traded (D-S58, D-S71 items 2 and 3).** Every independent piece runs at once, in lanes and on as many loop instances as the plan needs (D-S95: no count limit; the total budget, its hard stop and reserves are the only limit, each instance under the reaper, its ledger line and its deadline); the same decoding, one declared hardware type within a comparison, every bar fixed before its read; no gate, checker round, records check or outside check skipped or merged. Before each step, one line says what runs at the same time and what waits.
- **Every optimisation runs itself until it succeeds (D-S71 item 1, D-S72, D-S73; D-323 to D-325).** Each attempt ends with its lesson in `docs/loop/LESSONS.md`; the next recipe cites the lessons it acts on and is built and launched without asking. A part stops only on success: a margin over its untrained form written before its first attempt, holding on a held-out part of the read development material, both attacked by a checker first, judged against the comparable published figure where one exists. An attempt without real progress goes to `FOR_SECKIN.md` with a push and the loop goes on. The fresh set and sealed material never feed a lesson.
- **Held tight (D-S74 item 1).** D-S73's bar is the programme's goal: every lane's plan states how its work moves the system toward it, and work that does not is named and justified in `DECISIONS.md`.
- **Before a merge:** the merge base merged into the lane in its own commit first; full gate and side gates on the merged result; three checker roles (completeness, adversarial, claims and hygiene) against the merge base; at most three rounds, then a tie-break (IV.4); `tools/loop/request_ledger_check.py` and `tools/loop/issue_deferral_check.py` run, their results recorded (D-S16 item 1, D-S24 item 4). Each merge is scored against the D-196 baseline with the same scoring, labelled a replay or a run (D-S26 item 3).
- **Before a launch:** the records consistency check (D-S15 item 7); forecast and per-run cap in `BUDGET.md` and the ledger (IV.3) with the storage forecast to the full finish date (D-S23 item 2; the storage cost as read on the provider's inventory, D-306); seven-day below 98 percent and five-hour below 70 percent, both read, and a launch waits when five-hour cannot be read (D-S21, D-S23 item 7a, D-176); reaper reading under 10 minutes old (IV.3); free disk above 30 GB (D-099); free memory measured; the asset copy declared (D-S50 item 2).
- **After a run:** purpose line and "exposed, no manifest" (Annex B.1); a seeded model-text review sample, the seed recorded before reading (B.1, S5 item 8), except where D-118 forbids it; scored against D-196 and labelled (D-S26 item 3); `BUDGET.md` actual against forecast; first failures shown beside any re-run (D-S14 item 6), and what cannot be fixed written to `FOR_SECKIN.md` (D-S14 item 7). Cloud runs never bring ontology stores back, said in each run's report (D-S62 item 6).
- **Telling the operator:** a push in the same turn as a `FOR_SECKIN.md` entry that asks, reports a result or figure, a stop, or the milestone not holding (D-S44), also sent to his assistant's session (D-S67), each result recorded beside its entry (D-S64). Every deferral, narrowing or drop of a request of his is told the same way in the same turn, never only in `DECISIONS.md` (D-S69 item 4), and names its issue on a marker line (D-S24 item 4).
- **Money (D-S47, D-S57 item 5, D-S72 item 4).** No step is shrunk to fit a limit; only the operator raises one, by a `budget_change` line. No cap per part, the total only: budget 250, hard stop 249, the 60 USD sealed floor (D-309). Each process has its share in the programme forecast (D-324); a process past half again of its share is told with a push and the rest rebalanced; the total passing 150 USD is told before it happens (D-S71 item 4).
- **Before a stage close:** the look-back sweep (D-S12 item 3b); the records consistency check (D-S15 item 7); the stage gate (D-S16 item 2); `REQUEST_<stage>.md` for the outside audit, up to 8 hours (D-S16 item 4); the `FOR_SECKIN.md` block of every `loop-deferred` issue opened or moved (D-S24 item 5); the stage report and `VERSIONS.md` (IV.4 item 6).
- **A pinned function** changes only through a newly appended amendment (IV.7). A change to `docs/OUTPUT_FORMAT.md` or `docs/INPUT_FORMAT.md` adds a draft hash row to `VERSIONS.md` and says whether the scorer reads the changed text; an `INPUT_FORMAT` change also regenerates the development suite and re-runs the adapter gate checks (S3a items 3 and 5).
- The local repository pushes nothing until S14 item 8 (D-192).

- **Usage limits (D-529, D-534):** the rescue-and-stop (98 percent until 18 November 11:00, 95 after) and the one question at 97 percent read the overall weekly figure (`seven_day_used_percentage`) only. A Fable-specific limit stops nothing: Fable work moves to Opus at high effort, and the switch gets one line in FOR_SECKIN.

## What "performs well" means (D-S32, D-S33, D-S34, D-S73)

Everything after v1 serves one goal with two halves, and neither alone ends the work: Shimmer ends as a product a stranger can install and use alone, and it performs well on the measured tasks.

**Four measures together (D-S33).** Better than a bare LLM, meaningful output, correct output, a reasonable time. A configuration becomes the product's default only when it meets all four on development material (D-S33 item 3). The targets are never lowered to meet a result. All use the `detection_dev` scoring, where silence is never detection, with false positives, document counts and decision counts beside every figure.

**1. Better than a bare LLM, and the published level (D-S33 item 2a, D-S73).** On SciTab and ContraDoc only; CUAD and ContractNLI were cancelled for poor fit on 4 November 2026, after their development scores were known (B3 detection 0; B1 0.593 and 0.529), and every report that mentions them says so (D-S34, D-226).

| Benchmark | Measure | D-196 baseline (R1 has since taken B3 to 0.0) | B1 tuned | Target |
|---|---|---|---|---|
| ContraDoc | judgement accuracy | 0.0 | 0.667 | above B1, and the comparable published figure reached (D-S73) |
| SciTab | macro-F1 | 0.208 | 0.475 | above B1, and the comparable published figure reached (D-S73) |

- **Above B1** means, on the same items, a higher figure with the 95 percent interval of the paired difference (bootstrap over documents) above zero, and flag precision above B1's by the same test; where B1 raises no false alarm, B3 raises none. B1 is run with the same model whenever the judging model changes (D-S33 item 2a), and B3 beats the higher of B1's groups.
- **The published level (D-S73, D-325).** A target table of agentic or tool-using systems on open or local models of comparable size, frontier figures apart as reference, each with system, model, size, metric, label set, split, size and source, is built by `target-table` and attacked for comparability before any further attempt launches (step 3 (f) below). Where the setting differs, it is said beside the figure and never called a like-for-like win; with no comparable figure, the bar is the untrained form and B1.
- **Already read (D-223):** SciTab (Lu et al., EMNLP 2023, Table 4), three-class macro-F1 zero-shot: GPT-4 64.80, InstructGPT 41.41, LLaMA-13B 37.18, Vicuna-7B 32.47, human 84.73; ContraDoc (Li et al., NAACL 2024, Table 2), binary accuracy on balanced data: GPT-4 53.8, PaLM2 52.0, LLaMAv2 50.5, GPT-3.5 50.1. Both sets are far larger than ours. The D-S38 item 5 readings (SciTab GPT-4 78.2 two-class; ContraDoc GPT-4o 0.68 in a 2026 study) are the operator's assistant's, to be verified at their sources by the target table.
- **Development cases** (the synthetic suite and the existing exposed tests): reason-confirmed recall of at least 0.8 and above B1's where B1 can be scored, no false positive on a clean twin, each catch attributed to the path that made it.
- **The computed path (D-S32 item 3):** Python's findings (`written_by: python`) scored apart from the model's on every benchmark and case where a computed finding is possible.
- **Cost and time** per document beside every score (D-S32 item 4).

**2. Meaningful output (D-S33 item 2b).** A finding says what is wrong, where and under which rule; a copied, empty or generic finding counts as no finding and is removed from B3's detection figure. A deterministic screen (empty text, no unit, no rule, the contract's example, the same sentence on different units) and a seeded read sample, the seed recorded first, are written before the fresh read (D-S70 item 1); at least 90 percent of the sample passes. B1 answers with a label, so this measure applies to B3 alone.

**3. Correct output (D-S33 item 2c).** Scored against the key; right and wrong findings side by side on every benchmark and case, never netted off.

**4. A reasonable time (D-S33 item 2d).** Wall time from input to deliverables on the configuration's own hardware, start-up and model load included, B1's beside it; a rented session's own overhead reported apart (D-233). Targets (D-S80, replacing the lead's earlier ones under D-S102 item 11), each per item on a WARM machine (models loaded): a document of about 5 pages in 2.5 minutes, one of about 20 pages in 7.5 minutes, a three-round negotiation case (all rounds) in 15 minutes, one benchmark question in 15 seconds; a rented machine from launch to ready (with the filesystem copy) in 7.5 minutes; and at most 5 times B1 on the same item and machine. The cold start (model loads) and the launch to ready are measured and reported apart from the warm figure. Each figure is stated twice, on the machine actually used and on the reference A10, each with its date (D-S80 item 3), and an item over twice its limit is marked "timed out" in the run's records and counted apart in every result, never hidden or dropped (D-S80 item 4). They are measured and reported, never a condition of success (D-S81); the measured figures are in `docs/loop/stages/TIME_BUDGET.md`.

**How ContraDoc fits, against SciTab (D-S34 item 3, D-226).** SciTab is a claim against one table, three classes per claim, with figures in cells where a computed check could reach. ContraDoc is one document of prose (100 to 2,200 tokens) under one rule naming no field, its contradiction between two passages either of which is fine alone, a yes or no per document near chance even for GPT-4. Of its eight contradiction types only Numeric has a computed check's shape, and none reaches one today. So SciTab is where the computed path could show something; ContraDoc tests the model and the passage pair step (INFRA-047).

**The standalone product (D-S32 item 5).** A clean install from the public repository on a fresh machine, the console as the way in, one worked case from input to deliverables a stranger can follow, a short guide in English and Turkish, and a plain statement of what Shimmer does well and what it does not, each claim backed by a measured figure. S11 and S14 do not close without it.

## The order to 12 November (D-S51, D-S53, D-S56, D-S57, D-S70)

D-S51 sets this order for the work up to 12 November and replaces D-S42 items 1 and 2 for it; D-S53 makes it one package with the training in it; D-S56 is the reference design for every model-backed role; D-S70 moves the confirmatory read to after every part. Measured before it: the judging path on C base, T and half B, `drop` for every candidate (D-291 to D-294).

1. **The filesystem** (D-S50 items 1 and 2, D-S51 step 1). **Done:** verified on the provider's inventory, 12.02 GiB used and no capacity field, `docs/DEPLOYMENT_RESOURCES.md` and D-262 corrected (D-306); `lane/fs-read` merged with four loop instances (D-308, D-310); the asset copy declared on every bundle sealed since.
2. **The worked cases on the shipped configuration, the first launch** (D-S39, D-S51 step 2, D-S62 item 7, D-295). **Running:** four B3 entries re-sealed with the asset copy (D-310), launched as `dev-cases` (D-311); it seeds the copy, gives the demo real results and is the fallback package.
3. **In lanes, at the same time, no launch of their own** (D-S51 step 3):
   - (a) **The fresh test set** (D-S46 item 1, D-S63 item 2): 100 documents built (D-314, D-315), its bar attacked, 13 gaps closed in code (D-316), the prompts built (D-320); rebuilt for the system's labels on the pipeline's own records (D-322). It stays unread until step 9.
   - (b) **Positions toward or away** (D-S46 item 2, D-S70 item 4): three attack rounds left a gap computed only where two quotes differ in their figure alone, 0 of 16 worked-case rows (D-317, D-319); each issue's unit is now declared in the case manifests, read as declared syntax, rebuilt and re-scored by `movement-check` by 11 November 12:00 (D-322; open item 93 closes then). A bound edit, carried by the step 5 seal.
   - (c) **Round-3 suggested wording** (D-S46 item 3) with its rubric written first, scored by a checker who did not build it, on `lane/cases-1`.
   - (d) **The demo**, "Demo: no installation, saved examples" (D-S48, D-S50 item 3), built on step 2's results, opened cold by a checker; the online copy only on the operator's yes.
   - (e) **The cloud way in**, "On a rented cloud machine" (D-S49 item 3, D-301): forecast, measured progress, actual time and cost, shutdown; a loop launch through the bound wrapper during the loop (D-S62 item 9).
   - (f) **The target table** of comparable published systems for SciTab and ContraDoc (D-S73 item 1, D-325), attacked for comparability before any further attempt launches.
   - (g) **The cloud reference** (D-S35, D-S33 item 1, D-S70 item 5): one labelled run of the paid Anthropic model on development items already read, never the fresh set, its share 15 USD; a lane plans it first, no paid call before the plan is checked (D-322); reported beside B1 and the system, never as Shimmer's.
   - (h) **The live view of exposed runs** (D-S66): after `dev-cases` ends, a tracked read-only reader beside `tools/ordinary_final_progress.py`; sealed runs counts and timings only.
4. **Every model-backed role as an agent, its roles from measurement, trained until it beats its untrained form, calibrated** (D-S55 to D-S57, D-S59, D-S70 items 2 and 6, D-S72; D-299, D-302, D-303, D-313, D-320, D-324). In parallel lanes, each part's success rule written and attacked before its next attempt (D-324):
   - the judge: JUDGE registered (INFRA-049), on its own Phi-4 block (D-320); training attempt 2e built, sealed with no fresh question, measured on read development items only (D-320, D-322);
   - the producer backend: the broad roles narrowed (INFRA-050), the PROCESSOR candidate against checkpoint 168 (168 stays unless beaten), the base-against-168 replay on the other roles and the EDITOR_CLERK constraint replay (D-303, D-S23 item 7 (d));
   - the auditor backend: VERIFIER as a fixed-choice question per Python-built pair, PRACTICE_AUDITOR's narrow questions, the rule check with `rule_not_met` (INFRA-051, D-318), Auditor896 calibrated, the VERIFIER-versus-Auditor896 measurement on read pairs and `pair_fidelity` (D-307 item 3, D-313), answering open items 47 and 48 (D-302);
   - the ontology and the GNN: locked by default, candidate versions in a scratch store, the GNN's first signal measured against the ranker, D-S13 item 11 folded in (D-S60, D-S61, D-S62 item 6, D-304, D-305);
   - the roles' order as a declared dependency graph on the existing scheduler (D-S59, D-302) and the role-to-model map in `config/agent_registry.json` from measurement, one table (D-S57 item 2);
   - the governance lane: INFRA-049, INFRA-050 and INFRA-051 applied on `lane/gov` (D-313, D-318), merged with the lanes that use them and the gate.
5. **The cases again,** with step 3 (b) and (c), launched from the cloud way in, times per part measured with the copy's MATCH (D-S51 step 5, D-S49 item 4), starting no later than 11 November 12:00 on the best configuration measured by then, every component not yet improved named (D-S62 item 8).
6. **The clean install** following the English guide literally on a fresh rented machine, also the proof of "On your own computer with a strong graphics card", time measured (D-S46 item 4, D-S49 item 2, D-S51 step 6).
7. **The package** (D-S39, D-S51 step 7): the demo rebuilt on step 5's results, the guides in English and Turkish with the measured times of all three ways in, and the capability statement with the figures already measured, which parts were improved and which not yet, and that the confirmatory test comes after (D-S70 item 3). The table role is said to be measured on read development items only (D-S62 item 10). The outside check (D-S40) reads it; with no answer in `audit/` by 12 November 12:00 it ships with the check stated as pending (D-S62 item 11).
8. **9 November, FOR_SECKIN with a push** (D-S42 item 5, D-S46 item 5, D-S49 item 5, D-S51 step 8, D-S57 item 6): which of steps 4 to 7 hold by 12 November; what does not goes on after it.

## The confirmatory read (D-S70 items 1 to 3 and 6, D-S72, D-S73)

9. **The fresh set, read once,** by the full system as shipped, every model-backed role at its best measured state, against B1 on the same 100 documents; the judge-alone and untrained figures descriptive only (D-S70 item 1, D-322). It waits until every part of step 4 has met its success rule (D-S70 items 2 and 6, D-S72 item 2), whether that is before or after 12 November; no cut-off forces it (D-S70 item 3). Its power at the out-of-sample effect is .40 to .47 at 100 documents, the most licensed fresh material there is, so a failure is reported as "not shown at this size", never "no effect", with both power figures (D-316). Result in `FOR_SECKIN.md` with a push, beside the comparable published figure (D-S73 item 3).
9b. **The technical report** (D-S74 items 2 to 5), part of the package and finished after step 9: what Shimmer is and why it is built this way, the benchmarks and why they fit, the measurement protocol, results against B1, the untrained forms and the comparable published systems with uncertainty, ablations, limits, cost and time, how to reproduce. Before drafting, a comparability rule (same metric, same item set or a declared subset, same scorer, integrity passed) is written and applied to every earlier run, and only what passes it is compared; the development path is told as measured ablations, nothing smoothed. A reviewer-style checker and the outside check of D-S40 read it before it ships.

## After 12 November, in order (D-S42 item 3, D-S51 step 8, D-S69 item 3)

Each item here was parked or moved by the loop; `FOR_SECKIN.md` 2026-11-08 21:13 gives the operator each place or a drop proposal, and nothing is dropped without his answer.

10. **Step 4's attempt series goes on** for any part not yet successful (D-S45 item 7, D-S52, D-S70 item 6, D-S72), then step 9.
11. **Honesty items before version 3 (D-S23 item 5, D-178).** A strong-model lane. 16 defect 2 (#28) and 34 (#41), reverted by D-220: a design measured on a replay of the D-196 material, no launch, keeping hyphen ranges and counting a date or identifier cell as filled (16), the readers' own number forms and an exemption for computed relations (34). 16's defect 5 is a scorer change and needs III.2 step 3's attack. The column case of 22 is open item 88. 49 (#104) stays open: reading a row's value is P2 (b)'s link (D-266). Done: 22 (D-224, D-229), 25 (D-215), 31 (D-265), 45 (D-218), 16 defects 1 and 3 (D-215, D-224), #189 (D-228 to D-230).
12. **The v1 issues left open (D-182, D-184),** each in the S11 milestone: #134 done (D-269); #37 parts 1, 2 and 4 done (D-268), part 3 after a run that gives its `not_finding_shaped` count, part 5 at P5's attack; #169 by a measurement; #106 (open item 51) after the auditor lane's answer to open item 47.
13. **L14d (D-S23 item 4, D-S13 item 6d, open items 66 and 67).** A real review and a real draft from the launcher menu on the loop's instance, about 130 minutes, about 3.6 USD; the draft's local weights chosen by measurement from the producer lane's role map, recorded and told in one line; open item 67 closes on whether a memo is in fact cut (its interim mark is in, D-267).
14. **Moved runs (D-S14 items 2 and 5).** The 56 rename probes L9a and L9b, re-sealed on the final code, and the third re-run of the three entries still failing (`f3_s3102_vwmj`, `f1_s1101_cvjx`, `f1_s1102_mstx`) on the auditor lane's code, with the replays behind open items 47 and 48; `cuad_527255a5c970` is on a cancelled benchmark and its drop is put to the operator. Run side by side (D-S95: no instance limit; the budget rule decides). L13 is not run: its CUAD part went with CUAD (D-226) and its FinDVer part is step 17's question. **D-118's read limit holds** for any FinDVer and CUAD entry.
15. **S6 (`S06_PLAN.md`, written and checked before it starts).** The open-item sweep and its count line, test-change requests, performance; `loop/s06c` and its D-059 correction merged or retired with the ontology lane's measurement (D-S23 item 7 (e)); every class B row of the deferral sweep with its step (D-S23 item 6); the departures P-01, P-09, P-11, P-12 and P-14 each given an end date or a reason (D-S23 item 7 (g)). Then S7's final pass over what S6 added (Part V, #112). D-S13 item 6e, the chat window in plain-language mode, tried again when 6 GB is free; otherwise it stays on the operator's list.
16. **P5. Version 3 freezes and the sealed evaluation (S8) runs, on SciTab and ContraDoc** (D-S13 item 10, D-S26 item 4, D-S34 item 4, D-S30 item 4). Only after development detection has risen on its benchmarks or the operator says otherwise, the development scores written to `FOR_SECKIN.md` first. Only if a new version is still allowed: no holdout sample drawn, no sealed result (D-S12 item 5); if not, S8 keeps the frozen sizes and the reason goes to `DECISIONS.md` and `FOR_SECKIN.md`. The named preregistration is amended openly before any sealed material is opened, with D-S34's reason, the fact that the scores were known, and the 38 groups moved to development (ContraDoc's sealed side 660 documents, D-314). `detection_dev` as its starting point; labels from silence reported apart; benchmark-mode and as-shipped numbers side by side (D-S13 item 9). A cost measurement of the two benchmarks on the code to be frozen first, then re-sized by S4e item 2 within S8's allocation. Open item 71's corrections and open item 83's key fields before C0 run 5; `lane/s05-prereg3` (`da569f0`) read as a source and reworked, not merged as it stands; at most three C0 runs; a fresh checker attack; the freeze; the hash in `VERSIONS.md` and the role hash records; nothing merges after the freeze (D-S18 item 6b). The development suite regenerated with version 3's material (#180, D-232, D-270, D-S31 item 2). **S8 (`S08_PLAN.md`):** before S8b, decide by the role rules how many instances run (D-S95: no count limit, the budget rule decides; D-S17 item 2's reason line now applies only if the role rules choose fewer than the plan needs). Its report states what open items 36 and 41 require and that the benchmark-mode rule was chosen after development scores were seen (D-S13 item 9).
17. **S8-later (D-S23 item 3, D-S13 item 7).** Only FinDVer is left (CUAD-claim cancelled, ContraDoc moved into version 3, D-226). Run with its own preregistration, freeze and seal, its development dry runs first, or dropped: put to the operator, with the reasons in `FOR_SECKIN.md` (its documents miss the 60-minute target; the judge's training mix holds its family, D-313).
18. **S9, then S10 and S11 passes.** `HARDWARE_AND_DEPLOYMENT.md`; the README and results page with the held-out results beside the development ones; the Docker image and its offline gate (S10 item 2), closing `loop-s10-v1-open` and `loop-s11-v1-open`.
19. **S14 (`S14_PLAN.md`).** As Part V, plus: the sweep over S0 to S13 (D-S12 item 3c); the filesystem's monthly cost (D-S13 item 1, D-306); `start_shimmer.bat` brought up to date last (D-S13 item 6a); the answer on whether public benchmarks are a fair test (D-S13 item 14); the user's own-key cloud path proved after the loop ledger closes, the guide saying which was proved (D-S62 item 9); the README-only fresh-clone proof as the last step before the report (D-S22 item 5); `main` merged and pushed (D-S5 item 3); the hash comments after the final force push (D-S8 item 6); `.claude/settings.json` restored as the very last step (D-S2). S12 stays with the operator (D-S17 item 3).

## Speed-ups without loss of accuracy, in every stage (D-531, Seckin 14:36, 12 November)

Standing: every stage looks for methods that shorten time without costing accuracy, and this plan is adapted to them without waiting for Seckin to raise each one. The method:
1. A small test, not a large one, showing that outputs or accuracy are unchanged.
2. If they are, the method is adopted where it is most effective. If they are not, the slower way stays, and the reason is recorded.
3. Extra cost is acceptable unless it is a cliff, within the existing caps.
4. Nothing changes under the sealed 14 November measurement in the middle of it. A speed-up proven output-identical may go in before the seal; anything else waits until after the read.
First candidates, from TIME_BUDGET.md "The biggest causes":
- **(a) Batch PRACTICE_AUDITOR's independent (unit, rule) calls on the GPU,** instead of one by one. They take 60 to 89 percent of the wall time on rule-heavy documents, at 12 to 15 s each. Small test: replay a few dozen saved judging prompts one at a time and batched under deterministic decoding, and compare the replies byte for byte.
- **(b) The long single generations** (VERIFIER 422 s, CITATION_RESOLVER 188 s, PROCESSOR 26 to 48 percent). Look for prefill or KV-cache reuse, early stop on a closed envelope, or splitting into independent calls, each with a byte-identity or validator-identity test.
- **(c) Independent parts side by side on several Lambda machines** (D-499: up to two at once), and the image start of 12 minutes (D-509) on every launch.
- **(d) The 3.1 to 4.1 min hash of the filesystem copy at launch**, now avoided when the image layers MATCH (D-509).

## Look back: where finished stages could have been faster (D-532)

Written 12 November 2026 by lane `speed-lookback` from counts and timings only (TIME_BUDGET.md, LESSONS.md, DECISIONS.md, and the controllers' `*_timing.json` files under `external/`; no item data, key or sealed material was opened). Nothing here reruns a finished stage: a finished stage is never rerun only to make it faster (D-532). "Reruns" marks work that will run again, where D-531's method applies first: a small test, accuracy unchanged, then adopt. A saving is a figure computed from the measured times; where only a bound can be stated from the measurements, it says so and names the test that measures the real factor. Cost: an A10 is about 1.3 USD an hour (0.43 USD for 20 minutes, D-509). Everything below is on the A10 unless stated, because no faster type has a measured reference pair (D-S96 item 2).

### Top five by saving

| # | Item | Saving | Reruns |
|---|---|---|---|
| 1 | The fingerprint embedding (item 4) | about 15 h of the rate-bound part | yes, for every new release or gate set |
| 2 | Two recipes in one training session (item 2) | about 6.3 h of T_TRAIN, about 2.3 h of AUD_TRAIN5 | yes, for the next attempts |
| 3 | The laptop gate (item 1) | about 2 h per gate, already adopted | yes, every push |
| 4 | Uploads and launch to ready (item 6) | about 50 min per launch, already adopted; 4.3 USD and one training lost on 9 November | yes, outside us-east-1 only |
| 5 | Batched PRACTICE_AUDITOR judging calls (item 3) | up to about half of the 60 to 89 percent of a rule-heavy review's wall time, if batching halves the per-call time; the real factor is not measured | yes |

### 1. Gate runs: the laptop against Lambda

- **What ran.** The pre-push gate, 346 checks. On the laptop with the card shared: two full runs plus the embedding on the 8 GB card (L-13); check 320 alone took 45 minutes (D-498); the export run crashed at check 310 (Tcl_AsyncDelete, twice that afternoon) and restarted from check 0.
- **Measured.** Laptop: more than 2.5 hours (the G_FULL2 entry of 12 November, 03:30). Lambda G_FULL2 (arm G, A10): 33 minutes wall, 0.71 USD, the 346 checks in 674 s of gate time (`external/gate/G_FULL2/ordinary_workload_timing.json`, 713 s for the workload). Around the gate: filesystem copy probe 259 s and copy into place 223 s (`asset_copy_probe_timing.json`, `asset_copy_use_timing.json`), seal to launch about 6 minutes.
- **Faster method.** Already adopted for pushes (D-496, D-501). Remaining:
  - (a) The image start (D-509: workload 12 minutes after launch) removes the probe and the copy, about 8 minutes.
  - (b) Retry the first ssh readiness probe once: G_FULL3 died on a 20 s probe and cost 8 minutes and 0.17 USD (D-530). The controller is a bound file, so this is a re-seal, not a free change.
  - (c) Resume a crashed gate from its last finished check (D-495 rule 3, needs code).
  - (d) CPU-only checks hide the card with `CUDA_VISIBLE_DEVICES=-1`, since an empty value deletes the variable on Windows (the 00:05 entry after D-502).
- **Small test.** (a) The same export commit gives the same per-check PASS, FAIL and SKIP rows as G_FULL2, compared check by check as the parity run did. (b) A forced timeout on a fake provider, then success on the retry. (c) Kill a gate at check N and compare the resumed rows with an uninterrupted run.
- **Expected saving.** Laptop to Lambda: at least 2 hours a gate (150 minutes against 33), already taken. Image start: about 8 minutes. Splitting checks over two machines would save at most 337 s of the 674 s and costs a second launch of about 12 minutes to the workload, so it does not pay at this size; recorded, not recommended.
- **Reruns.** Yes, every push.

### 2. The trainings

| Run | Workload | Upload | Source |
|---|---|---|---|
| T_TRAIN, judge, two recipes (716 updates each) | 44,921 s (12.5 h) | 3,820 s | `external/s05/T/T_TRAIN` timing files |
| AUD_TRAIN5, auditor, two mixes (750 and 737 updates, six passes of 789 decisions) | 16,291 s (4.5 h) | 10,675 s (shared) | `external/s05/AUD/AUD_TRAIN5` |
| T2E_TRAIN_F, judge 2e, one recipe (710 updates) | 18,332 s (5.1 h) | 3,906 s | `external/s05/T2E/T2E_TRAIN_F` |
| P3_TRAIN_B, producer attempt 1, one recipe | 25,496 s (7.1 h) | 10,347 s (shared) | `external/s05/P1/P3_TRAIN_B` |

- **Faster method.**
  1. A session that runs two independent recipes one after the other (T_TRAIN, AUD_TRAIN5) runs them on two instances at once. There is no instance limit (D-S95) and the budget rule decides. Same work, same cost per hour, one more launch (about 0.4 USD with the image).
  2. Half and full checkpoints come from one training, so there is nothing to split there.
  3. The evaluation passes (AUD_TRAIN5's six passes of 789 decisions; the C base choice form measured 0.36 s a prompt) can be batched, with the batch size fixed per run.
  4. A faster machine type for training. Not measured: no reference pair exists, so no factor is known.
- **Small test.**
  - (1) Train one recipe alone for 20 updates, and the same recipe as the second of a pair: the loss values and the adapter digest after 20 updates must be equal (same seed, deterministic mode, as the decoding gate sets it).
  - (3) Replay 100 saved evaluation prompts one at a time and in batches of 4: per-label probabilities within 1e-3 and the same argmax on every prompt. Byte identity (D-531 (a)) applies to generated text.
  - (4) The reference pair of three items (D-S82 `machine_effect`); a trained score may move across GPU generations, and the type then stays out.
- **Expected saving.** (1) T_TRAIN: 12.5 h to about 6.3 h wall; AUD_TRAIN5: 4.5 h to about 2.3 h; cost within a few cents of the same. (3) Not separable from the records: the workload time is not split into training and passes, so the first step of the test is to read the pass timestamps from the evidence. (4) Unmeasured.
- **Reruns.** Yes, for any later judge, auditor or producer attempt with two recipes or mixes. Finished runs are not repeated.

### 3. Measurements and launches (L-series, C1, VER, the cases)

- **What ran.** Reviews of under a minute to 114 minutes each. PRACTICE_AUDITOR's judging calls take 89 percent of ContractNLI's wall time (195 to 272 calls at 12 to 15 s) and 83 to 89 percent of CUAD's (410 calls), and 60 to 65 percent of the case reviews (76 and 64 calls). Each review loads models cold three times, 30 to 37 s, plus about 22 s of boot and indexing (D-100): about 50 s a document. C1 ran 25 entries, L12 37, L12b 13 (TIME_BUDGET.md).
- **Faster method.**
  1. Batch the independent (unit, rule) judging calls on the GPU (D-531 (a)). Each is already independent.
  2. Keep the models resident across the entries of a batch session, so the cold loads and boot happen once, not per entry.
  3. Run independent documents on several instances at once (D-499, D-S95), at 12 to 15 minutes of launch each.
  4. The VERIFIER 422 s and CITATION_RESOLVER 188 s generations: stop on a closed envelope and reuse the prefill (D-531 (b)).
- **Small test.**
  - (1) Replay 30 to 50 saved judging prompts one at a time and in batches under deterministic decoding and compare replies byte for byte.
  - (2) Three saved items run cold and warm: replies and findings byte-identical.
  - (3) The same entry on one instance and in a split: output-identical entries; a sealed comparison keeps one machine type (D-389).
  - (4) Replay the 8 saved VERIFIER prompts (R2c) with the early stop: valid replies unchanged.
- **Expected saving.**
  - (2) About 50 s an entry: C1 about 21 minutes, L12 about 31 minutes, L12b about 11 minutes, had they been warm. This is TIME_BUDGET's own estimate and no warm run exists.
  - (1) A bound from the measured shares: if batching halves judging time, a CUAD review (113.7 min, 83 to 89 percent in judging) saves up to about 47 to 51 minutes and a ContractNLI review (35.7 to 90.2 min) up to about 16 to 40 minutes. The real factor comes from the test.
  - (3) Wall time divides by the number of instances, less 12 to 15 minutes of launch each, at the same GPU hours.
  - (4) Not measurable in seconds from the records: 4 of the 8 VERIFIER replies still ran to 4,096 tokens.
- **Reruns.** Yes for further measurements of these kinds. The sealed 14 November read takes none of them until proven output-identical (D-531 item 4).

### 4. The fingerprint embedding of 11 and 12 November

- **What ran.** bge-m3 over 486,252 records for the leakage fingerprints (D-525), on the 8 GB laptop card.
- **Measured.**
  - First run, file order, batch of 16: about 7.5 rows a second (D-510); 61,440 rows by 03:01 on 12 November; 7.1 GB dedicated plus 1.3 GB spilled to shared memory (D-519).
  - Second run, sorted by length, batched by size, memory capped: 160,352 rows in 25 minutes, 170 rows a second on short records (170 to 255 as gate-prep reported them), 10 a second on the first long records (D-519).
  - Long tail: about 10 rows a minute (0.17 a second, 5 to 6 s a record, D-521); only 6,237 records exceed 6,000 characters.
  - Read pass 2 h 11 min (D-499). The end estimate slipped four times (L-14) because it divided by an average rate over rows of different length. Final file 13:38 (D-525).
- **Faster method.**
  1. Sort by length and cap memory from the first row, so nothing spills. It was found after 61,440 rows.
  2. Estimate from the characters left per length class (L-14, already a rule).
  3. For the long tail, batch records of similar length by token count and keep them off shared memory. On a 24 GB card the 8,192-token window fits several records at once.
  4. Cache vectors by record content hash and the read pass by file digest, so a later release embeds only new or changed records (the second read found 212 of 42,823 development files changed, D-525 deviation 3).
  5. Run the read pass in parallel over files.
- **Small test.** As D-525 deviation 1 did: the new method's vectors equal the old method's on a sample (200 records of each length class; cosine at least 0.9999 per row and the same ranking at the .86 threshold). For caching, the digest of unchanged rows is identical.
- **Expected saving.** Item 1: the 424,812 rows after the first 61,440 would have taken 15.7 h at 7.5 a second and about 0.8 h at 170 a second (calculated from D-510 and D-519): about 15 h. Items 3 and 4: the tail cannot be bounded from the records (D-521 measured 5 to 6 s a record, L-14 about 2.5 s a record on the 595 left); on a rerun, caching makes the cost proportional to the new records. A Lambda route did not end sooner in November (D-521: 30 minutes at best, with a launch, an upload and three audits), and that stands for the same job.
- **Reruns.** Yes, for every release D-S100 checks. The 486,252 vectors are not recomputed to prove any of it.

### 5. Builds and seals

- **Measured.** G_FULL2: seal 02:44:27, reverify 02:44:56, assets 02:47:27, preflight 02:48:33, launch intent 02:50:46, about 6 minutes (file times of its logs). M1 (the image, seeding) 36 minutes and 0.77 USD, M2 (image only) 20 minutes and 0.43 USD (D-509).
- **Faster method.** Seals are already minutes. The cost is the re-seal that every change to a bound controller file forces (CLAUDE.md lists a dozen such changes). Group controller edits so a stage re-seals once.
- **Small test.** None needed; the seal's own `local_control_hashes` check refuses a stale bundle.
- **Expected saving.** About 6 minutes and the lead's attention per avoided re-seal; not measured per stage.
- **Reruns.** Yes.

### 6. The uploads of 9 November

- **Measured.** 22.25 GB from this machine: 3,800 to 3,906 s alone (5.8 MB/s: C base, T_TRAIN, T2E_TRAIN_F); 10,347 and 10,675 s for the two uploads that shared the link (about 2 MB/s); a third passed the controller's 10,800 s scp limit at 76.2 percent (D-354). Lost: `dev-t2e-train`, about 4.02 USD with no training, then `T2E_TRAIN_E` at the 300 s copy probe, 0.28 USD (D-356). The probe took 259 s on the 22.25 GB copy at G_FULL2.
- **Faster method.**
  1. No upload when the filesystem copy MATCHes (probe plus copy 5 to 7 minutes), and no archive at all when the image layers MATCH (12 minutes to the workload, D-509).
  2. When an upload is unavoidable, stagger the launches by more than one upload time (L-8).
  3. Download the asset archive from its source onto the instance and verify it by the sealed digest, instead of sending it over the laptop's 5.8 MB/s link.
- **Small test.** (3) The archive hash on the instance equals the sealed digest; the controller's own `archive_integrity` is already that test.
- **Expected saving.** Item 1: about 50 minutes a launch against the 63-minute upload. Item 2: the 4.3 USD and the lost training. Item 3: bounded by the instance's download speed, not measured.
- **Reruns.** Only a launch outside us-east-1 or one with a changed archive.

### Not listed, and why

- The ssh readiness fragility, the copy probe's fixed deadline and the scp limit are bound-controller constants. Changing them is a re-seal of every bundle and is its own decision (D-356, D-530).
- Machine types above the A10 are claimed nowhere, since none has a measured reference pair; the pair itself is a small test that could come first (D-S96 item 2, D-382 item 1).
- The warm column of TIME_BUDGET.md is an estimate until a warm run exists.

## Budget

Budget 250 USD, hard stop 249, the 60 USD sealed floor (D-S63 item 4, D-309); 104.26 spent by the reaper at D-323. The programme's shares (D-324): judge 9.6, auditor 7.5, producer and its roles 21.2, cloud reference 15, cases 6.2, the fresh read 22 (range 15 to 30), install and package 5. Steps 13 and 14 get their forecasts when placed (L14d about 3.6; L9a and L9b about 12.3 and 12.8 by their 31 October forecasts, to be measured again; the third re-run about 7.3 with its replays). `BUDGET.md` is updated before each launch with the storage forecast to the full finish date.

## Removed from this plan, each named once (D-S38 item 2)

- **"The performance work (D-S38)" section and its C, T, M, D (D-S42):** C, T and M ran and were measured, `drop` for every candidate (D-291 to D-294); D became steps 2 and 5 to 7.
- **P3, calibration as its own step after 12 November (D-S37 item 3):** folded into step 4, every part calibrated on read development items (D-S54 item 1, D-S56 item 3, D-S70 item 2).
- **The cloud reference as an open line (D-S35, #39 in the old text):** now step 3 (g).
- **"The sized test by 10 November 22:00" (D-S45 item 5, D-S51 step 4, D-S54 item 3, D-S62 item 2):** replaced by step 9, with no cut-off (D-S70 item 3, D-322).
- **D-316's "the test is of the judge alone":** withdrawn (D-S70 item 1, D-322).
- **The 15 USD cap per attempt (D-S45 items 4 and 7):** no cap per part, the total only (D-S72 item 4, D-324).
- **The GNN Lambda run of S6c (D-S13 item 11, D-150):** folded into step 4's ontology lane (D-S60 items 2 and 3).
- **The old numbering (steps 4 to 8, 11 to 13 of D-260; the top order's 1 to 9 of D-298):** replaced by the numbers above; a decision before D-321 that cites "step N" means the old number.
