# The negotiation part of the final test: real-item count and the synthetic-item method (D-692 items 5 and 6)

16 November 2026, written by a planning helper for the lead, before any item is counted, built or made. Nothing
was downloaded, opened or spent. Inputs read: D-605, D-613, D-644, D-652, D-671, D-692, D-695 in
`docs/loop/DECISIONS.md`; `NEG_ADVISOR_PLAN.md`, `NEG_PLAN_AMENDMENTS.md`, `NEGOTIATION_CORPORA.txt`,
`NEG_ADVISOR_POWER.json`; `NEG_DRAFT_BENCH_PLAN.md` as of 4208da0b; CLAUDE_REFERENCE NEG-ADVISOR-A,
NEGOTIATION-MEASURE-A, GATE-LEAKAGE-A; issues #262, #271, #294; standing order 90.

## 1. Real items: what is known, and how the rest is counted

**What may not count.** The pilot's 24 items (set `6a8af3c7...`, 18 headline P items and, by D-613's
first hand-back, 6 LLM-Deliberation games) are development now (D-695). D-692 item 5 keeps public health in
development and pilot this round, so every WHO source is out of the final test: INB, the IHR working group
(WGIHR) and the PABS annex (IGWG).

| Source (where named) | Status on record | New items it can give |
|---|---|---|
| Plastics treaty INC-5.1, INC-5.2 (D-605, plan section 2) | not built: role N session 1 refused it, terms forbid compiling and derivative works (D-613) | **not recorded** |
| Plastics treaty INC-2 to INC-4 (bench plan 3.4) | candidate, UNEP terms unread | **not recorded** |
| BBNJ IGC-3 to IGC-5 (reserve) | not built, same refusal (D-613); un.org terms read 15 Nov: personal, non-commercial, no compiling | **not recorded** |
| UN business and human rights treaty, OEIGWG (OHCHR) | candidate, four or more round pairs reported, terms unread | **not recorded** |
| UN cybercrime convention, Ad Hoc Committee (UNODC) | candidate, terms unread | **not recorded** |
| TradeVerse (WTO), War of Words (EP) | scouted; a statement or a binary outcome, not a draft round; data licences not found | 0 in this item form |
| LLM-Deliberation games (MIT) | 6 used in the pilot; authored games public since 2023, not real negotiations | not counted as real; unused games not recorded |

**So the real share of the 32 is unknown: anywhere from 0 to 32.** Two facts bound it. The only process built
so far, INB over 13 sessions, gave 15 then 18 items, short of its 20 because few parties held two positions on
record. D-652 admits a source whose terms forbid redistribution for measurement only (links and scorer
published, never texts), which reopens INC and BBNJ if their terms allow research processing; role N's
session 1 predates that ruling.

**How it is counted (standing order 90, role N, Claude usage, 0 USD, about 1.5 hours, counts only).** Per
candidate source, in role N's own folder: (1) read and record the terms in `SOURCES.md`, admitted, admitted
for measurement only (D-652), or refused; (2) list the dated round texts and the round pairs (k, k+1) whose
article blocks the parser splits; (3) per pair, count the parties or coalitions with two or more positions on
record (ENB or submissions) on articles of the excerpt, as section 3 of the advisor plan defines a persona;
(4) items = personas summed over pairs, under the plan's per-process cap; (5) a leakage precheck (section 2,
step 5). Hand back per source: pairs, personas, survivors. The lead then proposes the split (R real, 32 - R
synthetic) and its cost, and waits for Seckin's word.

## 2. The method for synthetic items

**Sources.**
1. Perez et al., Discovering Language Model Behaviors with Model-Written Evaluations, 2022. https://arxiv.org/abs/2212.09251
2. Zhu et al., DyVal: Dynamic Evaluation of LLMs for Reasoning Tasks, ICLR 2024. https://arxiv.org/abs/2309.17167
3. Wu et al., AntiLeakBench: Preventing Data Contamination by Automatically Constructing Benchmarks, ACL 2025. https://arxiv.org/abs/2412.13670
4. Xu et al., Benchmark Data Contamination of Large Language Models: A Survey, 2024. https://arxiv.org/abs/2406.04244
5. Benchmarking LLMs Under Data Contamination: A Survey from Static to Dynamic Evaluation, 2025. https://arxiv.org/abs/2502.17521
6. Lee et al., Deduplicating Training Data Makes Language Models Better, ACL 2022. https://arxiv.org/abs/2107.06499
7. Gururangan et al., Annotation Artifacts in Natural Language Inference Data, NAACL 2018. https://arxiv.org/abs/1803.02324
8. Panickssery, Bowman and Feng, LLM Evaluators Recognize and Favor Their Own Generations, NeurIPS 2024. https://arxiv.org/abs/2404.13076
9. Li et al., Preference Leakage: A Contamination Problem in LLM-as-a-judge, 2025 (ICLR 2026). https://arxiv.org/abs/2502.01534
10. Bean et al., Measuring What Matters: Construct Validity in LLM Benchmarks, NeurIPS 2025. https://arxiv.org/abs/2511.04703

**Design: the answer comes from a structure, the model only writes the prose** (DyVal [2], Perez [1]). A seeded
Python sampler draws each item's latent card: fictional parties and coalitions, articles, bracketed proposals,
each party's positions and declared red lines, and each proposal's fate in round k+1 (kept, changed, removed,
open), with class shares fixed in the sampler, never copied from the pilot's shares. Fictional states and a
fictional treaty, marked synthetic in every file, also keep the author inside the provider's policy (D-613's
author agent was stopped on reconstructions of real agreements). Being invented after every model's cutoff,
the items cannot sit in training data (AntiLeakBench [3]); the leakage pass still runs, because a model can
echo real treaty text it was trained on [4, 5].

**Steps, and who runs each.**

| Step | Who | What it receives, and never receives |
|---|---|---|
| 1. Sampler and its proofs | a lane, fixtures only | the item schema (advisor plan section 3); no item |
| 2. Draw cards, seed chosen at run time | role S (new separated author role) | the sampler; the lead never learns the seed |
| 3. Render round k, round k+1 and position quotes from each card | role S's generator | its card and a format brief only. Never: any pilot, development or real final item, `benchmark/`, any key or rubric, Shimmer's prompts (`benchmark/baselines/neg_advisor_prompt.json`, `scripts/`), role folders. Its path allowlist is the proof #294 asks for |
| 4. Label independently | role V (labeller, separate session and family) | the rendered item and round k+1, never the card. It maps positions to articles and marks red lines by the plan's procedure; Python computes fate by the plan's diff. An item whose labels differ from its card is dropped and counted; agreement (kappa) handed back |
| 5. Leakage and deduplication | role B (`gate_leakage.py check`, `freeze_negotiation_set.py`) | the lead's fingerprint of the generator's brief and the rendered items; counts and ids only |
| 6. Cue-only check | role V, in its folder | labels and items; aggregates out |
| 7. Freeze with real items | role N | the set's SHA-256, counts per part, synthetic count |

**Family separation.** `config/agent_registry.json` runs Qwen2.5 (Alibaba) and Phi-3.5 and Phi-4 (Microsoft)
under the local profile the final test uses; its api profile names Claude (Anthropic) and GPT-4o (OpenAI);
bge-m3 (BAAI) embeds. Generator: **Claude** (Anthropic), which D-692 item 6 allows on this account's usage
and which no arm of the final test runs (the cloud reference is not run again, D-692 item 4). Labeller: a
third family, so the labeller does not favour its own family's text [8, 9]: an open-weight **Llama** (Meta),
**Gemma** (Google) or **OLMo** (AI2) instruct model on Lambda, never Qwen or Phi, which share a family with the
system under test, and never through an external API key (D-644). Model ids are read live; bare aliases only.

**Deduplication (Lee [6]; the project's rules, the stricter of each).** Against the pilot set, the development
material (the `NEGOTIATION_CORPORA.txt` list, the negotiation measurement's frozen set, `benchmark/dev_cases`),
the gate sets, the real final items and the real processes' round texts role N holds: exact hash; any shared
8-word run (GATE-LEAKAGE-A); 5-gram Jaccard 0.5 or more on passages of 20 words or more (advisor plan
section 8); bge-m3 cosine 0.90 or more (the stricter of 0.90 and 0.92); same source or group. Within the
synthetic set, a pair at cosine 0.90 or more keeps one. The generator's brief is checked against Shimmer's
prompts the same way. An item over a threshold is regenerated once from a fresh card, then dropped and counted.

**Not solvable from surface cues (Gururangan [7]).** A cue-only baseline, a bag-of-words logistic regression
over the proposal text alone (no round context, no positions), plus length and bracket-count features, with
5-fold cross-validation grouped by item. If its macro-F1 on fate or conflict beats the majority class by 0.10
or more, or its 95 percent bootstrap lower bound is above the majority class, the batch is re-rendered once
with the cue removed, then dropped. A learned diagnostic, not a keyword table (WORDS-A untouched).

**Per-item provenance**, `PROVENANCE.jsonl` in role S's folder, its digest in `FREEZE.json`: item id,
`synthetic: true`, sampler code SHA-256, seed, card SHA-256, generator family and live model id, date,
decoding settings, brief SHA-256, reply SHA-256, regeneration count, labeller family and model id, label
agreement, leakage maxima (8-word, 5-gram, cosine), cue-check batch result.

**What the lead never sees:** a card, a seed, an item, a label, a per-item result or a provenance row. It sees
counts, digests, kappa, leakage counts and the cue check's aggregates. **Validity (Bean [10]):** synthetic
figures are reported apart from real ones, each with its n, their answers stated as from construction.

## 3. Cost and time (forecast; nothing spent)

Assumptions: S = 32 - R synthetic items, made at twice S to absorb drops; A10 at 1.68 USD an hour (1.29 times
1.3, the plan's rate, re-read before use); about 10 positions an item, about 3 s a label call.

| Step | Hours | USD |
|---|---|---|
| Real-item count (role N) | 1.5 | 0 (Claude usage) |
| Sampler, proofs, fingerprint of the brief (lane) | 3 | 0 |
| Generation, 2S items (role S, Claude usage) | 2 to 3 | 0 (via API instead, Sonnet at 2 and 10 per million tokens, about 0.09 an item: 5.5 at S = 32) |
| Labeller on Lambda, 640 calls at S = 32, setup and model fetch | 1 | 1.7 (cap 2.5) |
| Leakage pass, bge-m3 (laptop, or a Lambda embedding job) | 0.5 to 1 | 0 to 0.5 |
| Cue check (laptop CPU) | 0.25 | 0 |
| Real items' build and validator pass (role N, bench plan's estimate) | 8 to 12 | 0.9 |
| Freeze | 0.5 | 0 |

**Total about 2.6 to 3.6 USD** across separate moves, none above 3 USD alone; at S = 16 the labeller falls to
about 1.0 USD. About 17 to 22 hours of work, shorter where steps overlap, inside the code freeze of 18
November 11:00 (D-703) if the count starts tonight.

## 4. Open questions for Seckin

1. **The labeller's family.** Recommended: an open-weight model of a family Shimmer does not use (Llama,
   Gemma or OLMo) on Lambda, about 1.7 USD. The alternative, a separate Claude session, costs nothing but
   shares the generator's family.
2. **Link-only sources.** Recommended: yes, admit INC and BBNJ for measurement only under D-652, if role N
   finds their terms allow research processing; texts are never redistributed.
3. **Reporting synthetic items in the final test.** D-671 item 3 kept synthetic items out of the final test;
   D-692 item 5 lets them in, labelled. Recommended: D-692 governs, with the real-only figure as the headline,
   the synthetic-only figure apart, and the pooled 32 as a labelled secondary line.
