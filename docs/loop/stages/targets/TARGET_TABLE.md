# Target table for D-S73: SciTab and ContraDoc

Built 2026-11-08 (18:13 UTC) by a research lane; revised 18:32 UTC for the 8 gaps table-check
found. Every figure below was read in the source's own text (PDF text, extracted locally) at the
table named; none is copied from a secondary mention. Where a figure is DERIVED (arithmetic on the
source's own numbers) it says so. No benchmark data file, dataset card viewer or dataset row was
opened, and no Shimmer item list or key was read: the class counts of Shimmer's sets come from the
scorer later, not from this lane.

Shimmer's settings used for the comparability column:
- SciTab: three classes (supported, refuted, not enough info), whole table plus claim, macro-F1,
  on G1's 93 scored development claims (95 listed; `benchmark/baselines/g1_bar_items.json`, digest
  prefix b082d594), not all 1,224. No published figure is on those 93 claims, so no row is SAME;
  the best possible mark is CLOSE.
- ContraDoc: one yes/no decision per document (contains a self-contradiction or not), accuracy,
  whole documents, on three sets: half A (30 documents), half B (30) and the fresh set (100).
  Published figures are on all 891 documents, so no row is SAME.
- Shimmer's models, all 4-bit: judge Phi-4 (14B), producer Qwen2.5-7B (7B), auditor roles
  Phi-3.5-mini (3.8B). That is about 25B parameters across three open models, quantised. The bar
  row is chosen against that.

Reporting rule for every Shimmer figure set beside this table (class balance changes what
accuracy means):
- each set's class counts (SciTab: supported, refuted, NEI; ContraDoc: contradictory and
  non-contradictory), taken from the scorer;
- balanced accuracy beside plain accuracy (ContraDoc), and per-class F1 beside macro-F1 (SciTab);
- a 95% interval on every figure. On 93 claims or 30 to 100 documents the interval is wide, so a
  difference from the bar is claimed only when the interval excludes the bar.

Comparability marks: SAME (same metric, label set, input and set of items), CLOSE (state the
difference), NOT (not comparable).

Group: (a) open or local model, multi-step or tool-using system; (a0) open model, single prompt
baseline; (b) frontier model, reference only; (c) the benchmark paper's own baselines.

## SciTab (Lu et al., EMNLP 2023)

The benchmark paper evaluates on all 1,225 claims (Table 1; later papers count 1,224:
457 supported, 411 refuted, 356 NEI). There is no train/dev/test split in the benchmark paper; the
2-class setting drops the NEI claims. Shimmer scores 93 of these claims (above), so every row that
would otherwise be SAME is marked CLOSE (items: 93 vs all). The published figures give no class
counts for Shimmer's 93; their balance against the full set's 37/34/29% is for the scorer to report.

| # | Group | System | Model (size) | Metric, labels | Items | Setting notes | Figure | Mark | Source |
|---|---|---|---|---|---|---|---|---|---|
| S1 | (a) | MACE, Planner + Executor + independent Verifier (Pm+Em+Vm′) | "LLama-8B" (version not stated) for Planner and Executor, "GPT-20B" verifier (not named further); 28B total (paper's Table 4) | macro-F1, 3-class | 1,224 claims, all | zero-shot CoT agents, temp 0, up to 8 rounds, table as HTML; no code execution stated; "does not focus on ... long tables or context window limits"; models via Together.ai; preprint, no venue, two decimals, single run | 0.65 | CLOSE: same metric and labels; items all 1,224 vs Shimmer's 93; two open models (8B + 20B), the verifier a separate 20B model, so not an 8B system | MACE, Table 3 (Sec. 4.3, primary: Ll-8B row, Pm+Em+Vm′ column); restated in Table 6 (Sec. 4.4.1) |
| S2 | (a) | MACE Pm+Em+Vm (one model in all three agents) | "LLama-8B" (8B) | macro-F1, 3-class | 1,224 | as S1 | 0.45 | CLOSE (preprint, as S1) | MACE, Table 3 |
| S3 | (a) | MACE Pm+Em+Vm′ | "Mistral-7B" + "GPT-20B" verifier (27B total) | macro-F1, 3-class | 1,224 | as S1 | 0.58 | CLOSE | MACE, Tables 3 and 6 |
| S4 | (a) | MACE Pm+Em+Vm′ | "Qwen-72B" + "GPT-20B" | macro-F1, 3-class | 1,224 | as S1 | 0.67 | CLOSE | MACE, Tables 3 and 6 |
| S5 | (a) | MACE Pm+Em+Vm′ (paper's "SOTA") | "Qwen-235B" (version not stated) + "GPT-20B" | macro-F1, 3-class | 1,224 | as S1 | 0.71 | CLOSE | MACE, Tables 3 and 6, Sec. 4.4.1 |
| S6 | (a0) | single model, CoT (MACE's baseline) | "Qwen-235B" | macro-F1, 3-class | 1,224 | GPT-4o used to extract the final verdict from the output | 0.73 (higher than MACE's 0.71 with the same model) | CLOSE (verdict read by GPT-4o) | MACE, Table 3 |
| S7 | (a0) | single model, CoT (MACE's baseline) | "LLama-8B" | macro-F1, 3-class | 1,224 | GPT-4o verdict extraction | 0.53 (0.44 without CoT) | CLOSE (verdict read by GPT-4o) | MACE, Table 3 |
| S8 | (a0) | single model, CoT | "Mistral-7B" | macro-F1, 3-class | 1,224 | GPT-4o verdict extraction | 0.49 (0.40 without CoT) | CLOSE | MACE, Table 3 |
| S9 | (a0) | single model, CoT / no CoT | "Qwen-72B" | macro-F1, 3-class | 1,224 | GPT-4o verdict extraction | 0.62 / 0.68 | CLOSE | MACE, Table 3 |
| S10 | (a) | ProTrix, Plan-then-Reason, SQL tool executed | Llama-2-7B fine-tuned on TrixInstruct (6k; SciTab not in training) | "three-class F1" (macro not said explicitly), 3-class | not stated | large tables truncated to fit context (4,096 training length); label read from concluding sentence | 45.0 | CLOSE: truncation, F1 type and item count not stated, fine-tuned | ProTrix, Table 1 (p.6) and Table 10 (p.16), Sec. 3.2 |
| S11 | (a) | ProTrix-Coder | CodeLlama-7B fine-tuned | as S10 | not stated | as S10 | 41.2 | CLOSE | ProTrix, Table 1 |
| S12 | (a) | Llama-3-ProTrix | Llama-3-8B fine-tuned | as S10 | not stated | as S10 | 41.3 | CLOSE | ProTrix, Table 10 |
| S13 | (a) | prompting methods run by ProTrix authors: StructGPT / Plan-and-Solve / CoT | Llama-2-7B-chat | as S10 | not stated | as S10 | 30.5 / 31.4 / 36.6 | CLOSE | ProTrix, Table 10 |
| S14 | (a) | PAL / ReAct / ARC | CodeLlama-7B-Instruct | as S10 | not stated | as S10 | 30.2 / 15.3 / 29.5 | CLOSE | ProTrix, Table 10 |
| S15 | (a) | TabV4FC: TAPEX table-to-text, then LLM verifies on table + description | Qwen2.5-72B-Instruct | macro-F1, 3-class (micro 47.22) | 1,224 (paper says "test sets") | zero-shot; adds a generated description | 45.20 | CLOSE: input adds a generated table description | Luu Thanh Son, JAIST doctoral thesis, Table 3.11 (thesis p.61) |
| S16 | (a) | TabV4FC | Llama-3.3-70B-Instruct | macro-F1, 3-class | 1,224 | as S15 | 34.49 | CLOSE | same, Table 3.11 |
| S17 | (a) | TART: fine-tuned table formatter + tool maker + explanation generator, Python tools | Llama2-7b / Llama3-8b / CodeLlama-7b / DeepSeek-7b | ACCURACY, label set not stated | SciTab "testing set", size not stated; 690 SciTab claims used for training | fine-tuned on SciTab | 53.4 / 47.2 / 44.9 / 47.8 (DirectQA, no TART, Llama3-8b: 82.0) | NOT: accuracy, trained on SciTab, split and labels unstated | TART, Table 1 (p.6), Table 6 |
| S18 | (b) | TART with GPT-4 (2 in-context examples) | GPT-4 | accuracy, labels not stated | as S17 | as S17 | 63.6 | NOT | TART, Table 1 |
| S19 | (b) | GPT-4 end-to-end | GPT-4-1106-preview | "three-class F1", 3-class | not stated | as S10 | 57.1 | CLOSE (frontier reference) | ProTrix, Table 1 |
| S20 | (c)(b) | GPT-4 zero-shot | GPT-4 (version not stated) | macro-F1, 3-class | 1,225 | whole table linearised; zero-shot | 64.80 | CLOSE (frontier reference; items 1,225 vs 93) | SciTab, Table 4 (p.7) |
| S21 | (c)(b) | GPT-4 in-context (3 examples) / +CoT | GPT-4 | macro-F1, 3-class | 1,225 | 3 hold-out demonstrations | 63.21 / 62.77 | CLOSE (in-context) | SciTab, Table 4 |
| S22 | (c)(b) | GPT-4 zero-shot / in-context | GPT-4 | macro-F1, 2-class (NEI dropped) | supported + refuted only | | 78.22 / 77.98 | NOT (2-class) | SciTab, Table 4 |
| S23 | (c) | InstructGPT zero-shot / in-context / +CoT | text-davinci-003 (175B) | macro-F1, 3-class | 1,225 | | 41.41 / 41.58 / 42.60 | CLOSE (items) / CLOSE / CLOSE | SciTab, Table 4 |
| S24 | (c) | PoT (Python interpreter) | InstructGPT (175B) | macro-F1, 2-class only | supported + refuted | in-context | 63.79 | NOT (2-class) | SciTab, Table 4 |
| S25 | (c) | best open model, 3-class zero-shot | Flan-T5-XL (3B) | macro-F1, 3-class | 1,225 | | 38.05 | CLOSE (items) | SciTab, Table 4 and Sec. 4.2 |
| S26 | (c) | other open models, 3-class zero-shot: Flan-T5-XXL 11B / Vicuna-7B / Vicuna-13B / LLaMA-7B / LLaMA-13B / Alpaca-7B | as named | macro-F1, 3-class | 1,225 | | 34.91 / 32.47 / 29.63 / 32.26 / 37.18 / 27.59 | SAME | SciTab, Table 4 |
| S27 | (c) | best open model, 3-class in-context | Vicuna-13B | macro-F1, 3-class | 1,225 | 3 demonstrations | 35.16 | CLOSE | SciTab, Table 4 |
| S28 | (c) | best open model, 2-class zero-shot | Vicuna-7B | macro-F1, 2-class | | | 63.62 | NOT | SciTab, Table 4 |
| S29 | (c) | human annotator | one trained annotator | macro-F1, 3-class / 2-class | 60 / 40 sampled claims, balanced | | 84.73 / 92.40 (text says 92.46) | NOT (sample) | SciTab, Table 4 and Sec. 4.1 |

Excluded: SciTabAlign (Ho et al., Findings of EMNLP 2025) scores label prediction on a cleaned
2-class subset of 372 claims; not comparable, figures not recorded.

Findings on the starting points:
- "GPT-4 about 78 on the two-class setting": confirmed, 78.22 zero-shot (S22); the 3-class figure,
  the one Shimmer's setting matches, is 64.80 (S20).
- "MACE, an 8B model, roughly level with GPT-4 near 65 on three classes": confirmed as 0.65 (S1),
  but the 0.65 configuration is NOT an 8B system: its verifier is a separate 20B model ("GPT-20B",
  28B in total). The same 8B model in all three agents gives 0.45 (S2), below its own single CoT
  prompt, 0.53 (S7).
- MACE's comparison table (its Table 6) mixes sources: its "TART (GPT-4) 0.64" is TART's ACCURACY
  63.6, not a macro-F1; its "ProTrix 0.43" matches none of ProTrix's own SciTab figures (45.0, 41.2,
  41.3); its "Vicuna-13B 0.35" is SciTab's in-context figure while its "GPT-4 0.65" is the zero-shot
  one. Its "SOTA 0.71" is below its own Qwen-235B CoT baseline, 0.73 (S6).

**Comparable bar, SciTab: 0.65 macro-F1, 3-class (S1 alone).** MACE Pm+Em+Vm′: an 8B planner and
executor with a separate 20B verifier, MACE Table 3 (Sec. 4.3), Ll-8B row, Pm+Em+Vm′ column. Reach
it and aim to pass it.
- Why S1: it is the published multi-step system on open models nearest Shimmer's size. S1 is two
  open models, 28B in all; Shimmer is three open models, about 25B in all, but 4-bit, with a 14B
  judge as its largest model, against S1's 20B verifier.
- Why not S9 (one Qwen-72B prompt with no CoT, 0.68): it is a single model about three times
  Shimmer's largest, it is not multi-step, and its verdict was extracted by GPT-4o. So it is not a
  system of Shimmer's kind or size. It does bear on the claim, though: a single 72B prompt already
  edges past S1. Passing 0.65 shows that small open models in a multi-step system match a 28B
  multi-step system, not that they beat what a larger single model does.
- Comparability, CLOSE not SAME: Shimmer's 93 claims vs all 1,224; MACE is a two-decimal, single-run,
  unreviewed preprint figure served by Together.ai, with model versions not named and full precision
  presumed (not stated); Shimmer is 4-bit. Pass only if the 95% interval on 93 claims lies above
  0.65; otherwise report "level with" or "below".

Frontier reference, on its own line: GPT-4 zero-shot 64.80 macro-F1, 3-class, all 1,225 claims
(SciTab Table 4, S20). It is not the bar.

Context: a stricter single-model reading near 8B is 0.53 (S7, verdict read by GPT-4o), and in a
peer-reviewed paper 45.0 (ProTrix, S10, on truncated tables). The open-model ceiling published is
0.71 to 0.73 at 235B (S5, S6).

## ContraDoc (Li, Raheja and Kumar, NAACL 2024)

The dataset is 449 self-contradictory and 442 non-contradictory documents, 891 in all, 100 to 2,200
tokens each (paper Sec. 3). The benchmark paper defines no train, development or test split and
evaluates all 891 (all three tasks zero-shot, default decoding). Shimmer scores three subsets:
half A (30 documents), half B (30) and the fresh set (100). No published figure is on those items,
so the closest rows are CLOSE. No document in ContraDoc needs truncating at 32k tokens, so
whole-document input is the same on both sides.

The accuracy used is Tan et al.'s, defined in their Appendix H ("Full Experiment Results"):
accuracy = (1/|D|) Σ 1{y_i = ŷ_i} over all data points D. Sec. 3 lists the classification metrics
and points there. The benchmark paper uses "standard Precision, Recall, F1 score, and Accuracy"
(Sec. 4.1.1) with no formula given. Both papers' sets are near balance (449 positive, 442
negative), so plain and balanced accuracy differ little on them. On Shimmer's sets the gap depends
on their counts, which the scorer reports.

| # | Group | System | Model (size) | Task, metric | Items | Setting notes | Figure | Mark | Source |
|---|---|---|---|---|---|---|---|---|---|
| C1 | (a0) | Direct prompting: judgement plus quoted evidence, JSON | LLaMA3.2-90B (Llama 3.2 90B; vision family, text input) | document-level yes/no, accuracy | 891 (all) | temp 0; one call | 0.681 | CLOSE: items (891 vs Shimmer's 30 / 30 / 100); single prompt, the equal single-call figure beside C4 | Tan et al. 2026, v2 Table 5 (p.13); v1 Table 3 (p.10) |
| C2 | (a) | Self-consistency, majority vote over repeated direct prompts | LLaMA3.2-90B | accuracy | 891 | temp 0.5; number of samples not found in the text | 0.637 | CLOSE | Tan et al. 2026, v2 Table 5 |
| C3 | (a) | Self-criticism, "If-or-Else" (assess confidence, revise if not) | LLaMA3.2-90B | accuracy | 891 | multi-step | 0.577 | CLOSE | Tan et al. 2026, v2 Table 5 |
| C4 | (a) | Redact-and-retry + constrained filter (RnR+CF): judge, redact the quoted evidence, retry, filter; multi-step, the same model in every call | LLaMA3.2-90B | accuracy (Appendix H) | 891 | 3.50 retries on average (Table 5); the classification is the first call's by design, so accuracy equals C1 | 0.681 | CLOSE: items (891 vs 30 / 30 / 100); the agentic source of the bar | Tan et al. 2026, v2 Sec. 4 (Algorithm 1), Sec. 5.2, Table 5 (p.13) |
| C5 | (a0) | Direct prompting | LLaMA3-70B | accuracy | 891 | temp 0; in v1 only, dropped from v2 | 0.601 | CLOSE | Tan et al. 2026, v1 Table 3 |
| C6 | (b) | Direct prompting / self-consistency / self-criticism / RnR+CF | GPT-4o | accuracy | 891 | as C1 to C4 | 0.680 / 0.744 / 0.765 / 0.680 | CLOSE (frontier reference) | Tan et al. 2026, v2 Table 5 |
| C7 | (c)(b) | Binary judgement ("Yes" or "No" only) | GPT-4 (gpt-4-0613) | accuracy | 891 | zero-shot, default decoding | 53.8% | CLOSE (items) | ContraDoc, Table 2 (p.7) |
| C8 | (c) | Binary judgement | LLaMAv2 (Llama-2-Chat-70B) | accuracy | 891 | as C7 | 50.5% | CLOSE (items) | ContraDoc, Table 2 |
| C9 | (c) | Binary judgement: GPT-3.5 (gpt-3.5-turbo-0613) / PaLM2 (text-bison) | as named | accuracy | 891 | as C7 | 50.1% / 52.0% | CLOSE (items) | ContraDoc, Table 2 |
| C10 | (c)(b) | Judge then Find (yes/no, then quoted evidence) | GPT-4 | accuracy DERIVED as TP rate + TN rate | 891 | rates are over the whole set (caption) | 65.8% (19.6 + 46.2) | CLOSE (derived) | ContraDoc, Table 4 (p.8) |
| C11 | (c) | Judge then Find | LLaMAv2 70B / GPT-3.5 / PaLM2 | accuracy DERIVED, TP + TN | 891 | as C10 | 49.1% / 57.5% / 53.5% | CLOSE (derived) | ContraDoc, Table 4 |
| C12 | (c) | Judge then Find, real accuracy on positives R-acc(pos) | GPT-4 / LLaMAv2 | yes AND evidence hit, positives only | 449 | evidence task | 35.6% / 13.8% | NOT (evidence task) | ContraDoc, Table 4 |
| C13 | (c) | Top-k evidence (k=5), Evidence Hit Rate | GPT-4 / PaLM2 / GPT-3.5 / LLaMAv2 | evidence task | 449 positives | told a contradiction exists | 70.2% / 48.2% / 42.8% / 20.4% | NOT (evidence task) | ContraDoc, Table 3 (p.7) |
| C14 | (c) | Human, Judge then Find | annotators | rates on a balanced subset | 150 | | TP 18.0%, TN 43.3% (derived accuracy 61.3%) | NOT (subset, derived) | ContraDoc, Table 5 (p.8) |

Notes:
- The "GPT-4o about 0.68 in the benchmark paper" starting point is wrong as to source: the
  benchmark paper tests GPT-4, not GPT-4o. GPT-4o's 0.680 is Tan et al. 2026 (C6), direct prompting.
- Tan et al. 2026 is from American Express research staff: a published method on arXiv (v1 6 Jan
  2026, v2 8 Apr 2026, no venue named), not a company product, so it is listed. Its document-level
  accuracy is near 0.68 for both a frontier and an open model with one prompt; its multi-step
  methods raise GPT-4o (0.744, 0.765) and lower LLaMA3.2-90B (0.637, 0.577).
- A secondary leaderboard (sota2.com, "ContraDoc (test)") lists these figures under a "test" split
  that no source defines; the papers use all 891 documents.
- No published agentic or tool-using system on an open model below 70B reports document-level
  ContraDoc accuracy that I could find.

**Comparable bar, ContraDoc: 0.681 binary judgment accuracy (2 classes, document level) (corrected D-388).** Source: C4, the multi-step
redact-and-retry system (RnR+CF) on one open model, LLaMA3.2-90B, all 891 documents, Tan et al.
2026 v2 Table 5, accuracy as defined in their Appendix H. C1, the same model with one judge-and-quote
prompt, gives the same 0.681: C4 keeps the first call's classification. Reach it and aim to pass it.
- Sizes: the bar is one 90B model; Shimmer is three 4-bit models of 14B, 7B and 3.8B. No published
  multi-step open-model figure at Shimmer's size exists. The 70B single-prompt figure is 0.601 (C5)
  and LLaMAv2-70B's is 50.5% (C8). Passing 0.681 with smaller models is the claim to aim at; it is
  not a like-for-like match.
- Against half A and half B (30 documents each): CLOSE on task, metric and input; items 30 vs 891.
  A 95% interval on 30 documents spans roughly plus or minus 0.17 around 0.68, so neither half can
  show a pass or a fall short against 0.681 on its own. Report each with its interval and class
  counts, as development figures only.
- Against the fresh 100 (separately): CLOSE on task, metric and input; items 100 vs 891, drawn
  from the same 891-document pool (the bar's items may include them). Plus or minus about 0.09 at
  100. This is the set on which a claim of reaching or passing 0.681 can be stated, and only when
  its interval lies above 0.681. Report plain and balanced accuracy and the positive and negative
  counts.
- Frontier reference, on its own line: 0.765 (GPT-4o self-criticism, C6). Floor: the benchmark
  paper's own figures (GPT-4 53.8% binary, LLaMAv2-70B 50.5%).

## Leaderboards searched

| Leaderboard | Benchmark | What it returned |
|---|---|---|
| Papers with Code, https://paperswithcode.com/dataset/scitab | SciTab | 302 redirect to https://huggingface.co/papers/trending; the site is gone, no rows |
| sota2.com (wizwand.com redirects there), https://sota2.com/research/sota/fact-verification-on-scitab | SciTab | 14 rows, macro-F1 only, no label setting stated, all dated 2026.04. They reproduce MACE's Table 6 (MACE 71 / 67 / 65 / 58; GPT-4 65; TART 64; GPT-4+CoT 63; ProTrix 43; InstructGPT+CoT 43; InstructGPT 42; Vicuna-13B 35; PASTA 33; Ll-13B 33; Alpaca-7B 29). They carry MACE's mislabels (TART's accuracy as macro-F1) and name MACE's components "Pm + Em + Vm", where the rows are Pm+Em+Vm′, with the 20B verifier. No figure taken from it. |
| sota2.com, https://www.sota2.com/research/sota/document-contradiction-detection-on-contradoc-test | ContraDoc | 15 rows from Tan et al. (DP, RnR, RnR+CF, RnR+UF on GPT-4o, LLaMA3.2-90B, LLaMA3-70B; top accuracy 68.1) under a "test" split no source defines. The benchmark paper's own GPT-4 rows are not listed. No figure taken from it. |
| web search for an official SciTab or ContraDoc leaderboard | both | none exists; the benchmark repositories (github.com/XinyuanLu00/SciTab, github.com/ddhruvkr/CONTRADOC) were found in results but not opened |
