# External benchmark selection

Draft, loop stage S4. Research date 2026-10-27. Development results: pending S5.

This file records which third-party benchmarks Shimmer is evaluated on, why, and what B-dev needs to retrieve them (source address, version or commit, published checksums; IV.10a item 1). The split rules, mappings and statistics live in `docs/benchmarks/PREREGISTRATION.md`. The input format is `docs/INPUT_FORMAT.md`, version `input-format-v1-draft`, on branch `loop/s03`.

## Exposed and sealed

Every benchmark below is public. Its documents and labels are therefore exposed in two senses: a model may have seen them during training (see Contamination per candidate), and the development items B-dev passes to the lead are exposed by design and are only ever reported as development results. The holdout sample that role B draws in S8 is sealed: it never reaches the builder's disk, and only sealed results count as evidence.

**H17.** The builder opened no benchmark data in this stage: no data file, no dataset viewer, no row of any split. Every fact here comes from dataset cards, licence files, papers, READMEs and repository metadata, read by three read-only research subagents on 2026-10-27. Where they did not settle a fact the field says "not verified". No development item has reached the lead: the B-dev role session cannot run in this session (D-019), so adapters are written against documented schemas only. Where a field name or stored value is not documented outside the data, the adapter takes it from a named constant marked PROVISIONAL, never inferred: every adapter has some (preregistration section 12 item 5 lists them), and the CUAD and ContractNLI schemas are PROVISIONAL as a whole. One exposure from before the loop rules SummEdits out (D-019).

## Fit criterion (plan revision V6)

A candidate fits well when all five hold:

- (a) each item has a document (or a document-like source, such as a table with its caption) that is checked;
- (b) the decision is a check of that document against a stated claim, rule or requirement;
- (c) the label set maps by one documented rule to Shimmer's outputs (finding, absence, refusal, nothing found);
- (d) the labels were written by third parties;
- (e) it is an open download without H13 issues (no click, form, checkbox, login, request or account).

Fit grades (High, Medium-high, Medium, Medium-low, Low) are the research agents'. "Medium-low" also covers the two entries the research wrote as "Low-medium". Lacking a refusal class is not one of (a) to (e): it decides how a refusal is scored (an abstention, never correct), not whether a candidate fits. Each verdict names any of (a) to (e) that fails.

## Chosen benchmarks

| Benchmark | Domain | Source address | Version or commit | Published checksums | Document id for the split |
|---|---|---|---|---|---|
| ContractNLI | non-disclosure agreements | https://stanfordnlp.github.io/contract-nli/ ; paper https://aclanthology.org/2021.findings-emnlp.164 | site commit eced6528dd3c1d14d73f9a87df8f7bdbc03126f9 | not published; B-dev records SHA-256 of each file | `id` (PROVISIONAL; official split used, see below) |
| ContraDoc | news, stories, Wikipedia | https://github.com/ddhruvkr/CONTRADOC (file `ContraDoc.json`) | commit d1c42d1e433595dd6e98fab7b669722cdc050b1d | not published; B-dev records SHA-256 of each file | `unique id`; split by near-duplicate group (preregistration section 1) |
| CUAD v1 | commercial contracts | https://zenodo.org/records/4595826 (`CUAD_v1.zip`, DOI 10.5281/zenodo.4595826) | Zenodo record 4595826 | md5 c38f490a984420b8a62600db401fafd5 for `CUAD_v1.zip` (105.9 MB); B-dev verifies it and also records SHA-256 of each file | not documented outside the data; the unit is the contract, identified by the SHA-256 of its text |
| SciTab | scientific tables (arXiv computer science) | https://github.com/XinyuanLu00/SciTab | commit 217cfbd71ebf39ba26a0938f0d87a9fce560e0fe | not published; B-dev records SHA-256 of each file | document `table_id`; split key `paper_id` |
| FinDVer | financial filings (SEC 10-K and 10-Q) | https://github.com/yilunzhao/FinDVer | commit e8bb237def4ce555a606a45edba22666e31df248 | not published; B-dev records SHA-256 of each file | `report` (official split used, see below) |

Five adapters, five document domains (P20). ContractNLI was added after the operator accepted its terms of use (decision D-S3, 27 October 2026); SummEdits was proposed earlier and is rejected as exposed (D-019, below). The priority list (fit, then measured cost per scored decision) is pending S5; ContractNLI ranks first by fit. S8 aims to seal at least three benchmarks in priority order under the preregistration's sizing and cut rules; if fewer than three qualify, the number sealed is what those rules give, the reason is recorded, and the shortfall is met together with B's synthetic tests (preregistration section 2). Where a chosen benchmark is reachable from more than one address, B-dev uses only the one in this table.

**ContractNLI (D-S3).** Licence CC BY 4.0, with a LICENSE file. Access: click-through terms of use on the download page, accepted by the operator on 27 October 2026 (decision D-S3); it is downloaded only by role B, under that acceptance. Split: the official `dev` split (61 agreements) is the development set and the official `test` split (123) the holdout pool; `train` (423) is not used. 17 fixed hypotheses per agreement, labels Entailment, Contradiction and NotMentioned, evidence spans for Entailment and Contradiction (paper). The field names of the release are not documented outside the data, so the adapter's whole schema is PROVISIONAL. LegalBench's ContractNLI tasks are drawn from ContractNLI's test set, so the two are not independent: a model that has seen LegalBench has seen ContractNLI test items. LLM-AggreFact stays out: the operator did not accept its terms.

**ContraDoc (V7).** The repository's own LICENSE file is Apache-2.0. The arXiv page shows CC BY-NC-SA 4.0; that notice covers the paper, not the data. Conclusion: the data is used under Apache-2.0 and no NC term applies to it. Upstream sources (V1): CNN/DailyMail (Apache-2.0 per its card), NarrativeQA (fetched by script; licence not stated), WikiText (CC BY-SA; its card is self-conflicting). None is NC or ND.

**CUAD (V18).** The CC BY 4.0 licence is stated on Zenodo and on Hugging Face; the GitHub repository has no LICENSE file. There is no official development split: the paper splits 80/20 by contract and the Hugging Face release has a train split only (QA form: 22,450 train rows; another figure of 4,182 test rows conflicts with "train only": not verified). The hash rule therefore applies. The `title` field appears to be the contract filename, but the card does not define it, so the contract is identified by the SHA-256 of its text. Zenodo is chosen over the Hugging Face copy because it publishes a checksum. PROVISIONAL until the schema of the zip's contents is confirmed from documentation.

**SciTab.** A table with its caption is the document; each claim is checked against it; "not enough info" maps to a refusal. Repository MIT; the data licence is not stated separately (recorded as such). No official split: the paper holds out 5 tables (25 claims) as in-context examples. Documented fields: `id` (claim), `table_id`, `paper_id`, `label`.

**FinDVer (V17).** Size: 2,100 claims per the ACL PDF (testmini 600, test 1,500). No published size is used: counts are taken from the pinned files and reported. Conflicting figures: arXiv v1 gives 2,400 (testmini 700, test 1,700) and the ACL abstract gives 4,000. 523 filings, about 4 claims per filing (another reading gives 4.6). Length: about 40,000 tokens on average (paper); another reading gives a median of about 42,000 words, which does not agree with that mean: not verified. Labels: entailed or refuted only (with an explanation and context indices). There is no "not enough info" class, so a Shimmer refusal maps to an abstention, reported as coverage and never counted as correct. Split: testmini is the development split. Test labels were released publicly on 2026-07-14 with an MIT licence, so the contamination guard the paper relied on is gone. Item id `example_id`; document id `report` (the filing's file name). Whether the pinned commit includes the released test labels: not verified; B-dev confirms it before freeze, and the preregistration (section 1) says what happens if it does not. Whether a filing appears in both testmini and test: not verified (the preregistration handles it).

**SummEdits (V1; rejected, see the exposure flag).** Release licence: the repository is Apache-2.0; the Hugging Face card (https://huggingface.co/datasets/Salesforce/summedits) states CC BY 4.0, research only. Neither is NC or ND. The ten domains, by the names an earlier project record uses (`docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md`): billsum, ectsum, news, podcast, qmsumm, sales_call, sales_email, samsum, scitldr, shakespeare.

- Dropped: **podcast** (upstream Spotify podcast data, request-only and discontinued December 2023); **samsum** (upstream SAMSum, CC BY-NC-ND 4.0; recorded in `FOR_SECKIN.md`).
- Kept (8), with upstream licence: billsum (not stated); ectsum (not stated); news (not stated); qmsumm (not stated); sales_call (not stated); sales_email (not stated); scitldr (not stated); shakespeare (not stated). The research found no click, form, request, NC or ND term for these, but did not read each upstream licence. (Moot while SummEdits is rejected, D-019.)
- Eight domains would have been enough on licence grounds. The domain field's name is not documented outside the data, and there is no source-document id field.
- **Exposure flag.** Before the loop, a project task downloaded the SummEdits and SummExecEdit releases (Hugging Face revision ce0c479aaf59259abb6b67e42248b2f49004b7d5 for SummEdits) and the repository tracks derived files from that work under `tuning/auditor_external_relation_v1/`. The project record states the two releases share the same 216 source documents, that the derived candidate was quarantined, and that no model was trained on it. The builder's own repository therefore holds converted SummEdits documents, so every SummEdits item is exposed (Annex A, 11.0) and no SummEdits result could be sealed evidence. Decision D-019: SummEdits is rejected. The domain record above is kept for a later run that would use it for development only.

## All 17 candidates

Fields follow S4a. "Fit" applies the V6 criterion.

### 1. ContractNLI
- What: document-level natural language inference on non-disclosure agreements, with evidence spans.
- Size: 607 NDAs x 17 fixed hypotheses.
- Document, length: NDAs from EDGAR and PDFs; mean about 2,254 tokens (336 to 11,503).
- Decisions per document: 17.
- Labels, spans: Entailment, Contradiction, NotMentioned; evidence spans for Entailment and Contradiction.
- Splits: 423 / 61 / 123 (train, dev, test).
- Official metric: accuracy, F1 (Contradiction), F1 (Entailment); evidence mAP and precision at 80 percent recall.
- Licence: CC BY 4.0, with a LICENSE file.
- Access: click-through terms of use on the download page (H13); accepted by the operator on 27 October 2026 (decision D-S3); downloaded only by role B under that acceptance.
- Evaluation use: permitted by the licence; the terms are accepted (D-S3).
- Contamination: public NDAs; LegalBench's ContractNLI tasks are drawn from its test set, so they are not independent of it.
- Fit: High; meets (a) to (e) since D-S3. Chosen.
- Source: https://stanfordnlp.github.io/contract-nli/ ; paper https://aclanthology.org/2021.findings-emnlp.164
- Version: site commit eced6528dd3c1d14d73f9a87df8f7bdbc03126f9.
- Checksums: not published; B-dev records SHA-256 of each file.

### 2. CUAD v1
- What: lawyer-supervised clause annotation of commercial contracts, 41 categories.
- Size: 510 contracts; over 13,000 labels.
- Document, length: EDGAR commercial contracts, a few to over 100 pages (9,283 pages in all).
- Decisions per document: 41.
- Labels, spans: answer spans per category (33 yes or no type, 8 entity type); an empty answer means the clause is absent.
- Splits: no official development split (paper 80/20 by contract; Hugging Face train only).
- Official metric: AUPR, precision at 80 and 90 percent recall, span match at Jaccard >= 0.5.
- Licence: CC BY 4.0 (Zenodo, Hugging Face); no GitHub LICENSE file.
- Access: open (Zenodo; Hugging Face not gated).
- Evaluation use: permitted.
- Contamination: none stated; public, widely circulated contracts.
- Fit: Medium; meets (a) to (e). Chosen.
- Source: https://zenodo.org/records/4595826 ; https://huggingface.co/datasets/theatticusproject/cuad ; https://huggingface.co/datasets/theatticusproject/cuad-qa ; https://ar5iv.labs.arxiv.org/html/2103.06268
- Version: Zenodo record 4595826; a Hugging Face commit 67faa0e6023b04fcaae6cc09497ab00e5d63a2a2 was also recorded (which of the two Hugging Face repositories it belongs to: not verified).
- Checksums: md5 c38f490a984420b8a62600db401fafd5 (`CUAD_v1.zip`).

### 3. MAUD
- What: merger agreement understanding, multiple-choice questions on deal points.
- Size: 152 agreements, 39,231 examples.
- Document, length: pre-extracted passages, not whole agreements; length not verified.
- Decisions per document: about 92 per agreement as reported (39,231 examples over 152 agreements would be about 258: not verified).
- Labels, spans: multiple choice; spans not verified.
- Splits: 25,827 / 6,753 / 6,651.
- Official metric: minority-class AUPR.
- Licence: CC BY 4.0. Access: open (Hugging Face, GitHub). Evaluation use: permitted.
- Contamination: none stated.
- Fit: Low; fails (a) (no whole document under review).
- Source: https://huggingface.co/datasets/theatticusproject/maud ; https://github.com/TheAtticusProject/maud
- Version: not verified. Checksums: not verified.

### 4. LegalBench ContractNLI tasks
- What: 14 binary tasks derived from ContractNLI.
- Size: small; exact counts not verified.
- Document, length: single clauses.
- Decisions per document: 1.
- Labels, spans: binary (Contradiction and NotMentioned merged); no spans.
- Splits: small; not verified.
- Official metric: balanced accuracy.
- Licence: CC BY 4.0. Access: open. Evaluation use: permitted.
- Contamination: drawn from ContractNLI's test set, so not independent of ContractNLI.
- Fit: Medium-low; fails (a) (a clause, not a document).
- Source: https://huggingface.co/datasets/nguha/legalbench ; https://hazyresearch.stanford.edu/legalbench
- Version: Hugging Face commit 6b4b377 (short form; full hash not verified). Checksums: not verified.

### 5. LegalBench rule-application tasks
- What: applying a stated legal rule to a short fact pattern (for example abercrombie, diversity, hearsay).
- Size: tiny; not verified.
- Document, length: short fact patterns.
- Decisions per document: 1.
- Labels, spans: an outcome plus an explanation; no spans.
- Splits: tiny; not verified.
- Official metric: balanced accuracy; the application is graded by hand.
- Licence: CC BY 4.0 for the tasks named; some LegalBench families are NC. Access: open. Evaluation use: permitted for CC BY 4.0 families.
- Contamination: none stated.
- Fit: Low; fails (a) and (c) (hand-graded explanations).
- Source: as item 4. Version: not verified. Checksums: not verified.

### 6. ContraDoc
- What: self-contradiction detection in whole documents; clean documents measure false alarms.
- Size: 449 documents with one human-verified self-contradiction each and 442 with none.
- Document, length: news (CNN/DailyMail), stories (NarrativeQA), Wikipedia (WikiText); about 100 to 2,200 tokens.
- Decisions per document: 1.
- Labels, spans: contradictory or not; for contradictory documents the evidence sentence, reference sentences, a contradiction type (8 types) and a scope (intra, local, global).
- Splits: none (zero-shot).
- Official metric: judgement accuracy, precision, recall, F1; Evidence Hit Rate (BERTScore above 0.98); judge-then-find.
- Licence: Apache-2.0 LICENSE file in the repository (see V7 note above).
- Access: open (`ContraDoc.json` in the repository). Evaluation use: permitted.
- Contamination: none stated; built on public web text that models may have seen.
- Fit: Medium; meets (a) to (e). Chosen. One decision per document makes it expensive per scored decision.
- Source: https://github.com/ddhruvkr/CONTRADOC ; https://arxiv.org/html/2311.09182v2
- Version: commit d1c42d1e433595dd6e98fab7b669722cdc050b1d. Checksums: not published.

### 7. LLM-AggreFact
- What: claims checked against grounding documents (supported or not), aggregated from 11 subsets.
- Size: dev 30,420, test 29,320 rows.
- Document, length: grounding documents from the subsets; length not verified.
- Decisions per document: not verified.
- Labels, spans: label 1 means supported; no spans.
- Splits: dev, test.
- Official metric: balanced accuracy at threshold 0.5.
- Licence: CC BY-ND 4.0 (ND).
- Access: gated; access requires a click and sharing contact information (H13).
- Evaluation use: evaluation only; the card forbids pretraining and fine-tuning on it.
- Contamination: rows carry a 64-character canary (`contamination_identifier`).
- Fit: Medium on (a) to (d); fails (e). Gated.
- Source: https://huggingface.co/datasets/lytang/LLM-AggreFact ; https://arxiv.org/abs/2404.10774
- Version: README commit 981dfd0bd8e58e7238a9ab92b2e6ea44bce918e4. Checksums: not verified.

### 8. SummEdits
- What: edited summaries checked for factual consistency against their source document, 10 domains.
- Size: 6,348 edited summaries (an earlier project record reports 216 distinct source documents; not verified from the card).
- Document, length: summaries with their source documents; length not verified.
- Decisions per document: about 12 to 21 edited summaries per source document as derived earlier (6,348 over 216 documents would be about 29: not verified).
- Labels, spans: consistent or inconsistent; spans not verified.
- Splits: none.
- Official metric: balanced accuracy.
- Licence: repository Apache-2.0; Hugging Face card CC BY 4.0, research only; upstream per domain above.
- Access: open. Evaluation use: permitted (research use).
- Contamination: seed documents come from training portions of upstream datasets; public web text; prior project exposure (above).
- Fit: Medium; meets (a) to (e) for the 8 kept domains. Rejected: exposed (D-019).
- Source: https://github.com/salesforce/factualNLG ; https://huggingface.co/datasets/Salesforce/summedits ; https://arxiv.org/abs/2305.14540
- Version: commit b95184aba5f3bd2a3eb36fb1897c9b6394ca0207. Checksums: not published.

### 9. AIReg-Bench
- What: EU AI Act technical documentation excerpts rated for compliance.
- Size: 120 annotated excerpts.
- Document, length: synthetic, model-written excerpts; length not verified.
- Decisions per document: 1 (one Article per excerpt).
- Labels, spans: 1 to 5 compliance and plausibility scores from 3 graders; no spans.
- Splits: not verified. Official metric: not verified.
- Licence: Hugging Face card CC BY 4.0; the GitHub repository has no licence (conflict).
- Access: open. Evaluation use: unclear while the licences conflict.
- Contamination: the excerpts are model-generated.
- Fit: Medium-low; fails (d) in part (model-written documents) and (c) (ordinal scores).
- Source: https://github.com/camlsys/aireg-bench ; https://huggingface.co/datasets/camlsys/AIReg-Bench ; https://arxiv.org/abs/2510.01474
- Version: commit 846d5cc075ad424a2d31dd20e34a7c5fe836f157. Checksums: not verified.

### 10. DocNLI
- What: document-level natural language inference built on public datasets.
- Size: not verified.
- Document, length: mostly under 150 words, many 150 to 900.
- Decisions per document: not fixed.
- Labels, spans: not verified. Splits: not verified. Official metric: not verified.
- Licence: BSD-3-Clause (repository). Access: data on Google Drive (whether sign-in is needed: not verified); repository archived 2025-05-01.
- Evaluation use: not verified.
- Contamination: built on public sets.
- Fit: Low; could not be verified.
- Source: https://github.com/salesforce/DocNLI. Version: not verified. Checksums: not verified.

### 11. FACTS Grounding public
- What: grounded long-form generation, judged by language models.
- Size: 860 examples.
- Document, length: up to 32,000 tokens.
- Decisions per document: 1.
- Labels, spans: none; responses are judged by models.
- Splits: public set only; a private split protects the leaderboard.
- Official metric: model-judged grounding score.
- Licence: CC BY 4.0. Access: open, not gated. Evaluation use: permitted.
- Contamination: the private split guards the leaderboard, not this set.
- Fit: Low; fails (b), (c), (d) (a generation task, no document check).
- Source: https://huggingface.co/datasets/google/FACTS-grounding-public. Version: not verified. Checksums: not verified.

### 12. TabFact
- What: statements checked against Wikipedia tables.
- Size: about 118,000 statements over 16,573 tables; 92,283 / 12,792 / 12,779.
- Document, length: short Wikipedia tables.
- Decisions per document: about 7.1 per table.
- Labels, spans: entailed or refuted; no spans.
- Splits: train, dev, test as above.
- Official metric: accuracy.
- Licence: MIT (repository); one reading gives CC BY 4.0. Access: open. Evaluation use: permitted.
- Contamination: the blind test reuses training tables.
- Fit: Low; meets (a) to (e), but adds nothing over SciTab (the same check of a claim against a table, on short Wikipedia tables) and its blind test reuses training tables (V6). Its lack of a refusal class is not the reason: FinDVer lacks one too and is chosen, because it brings long filings and arithmetic.
- Source: https://github.com/wenhuchen/Table-Fact-Checking
- Version: commit 2ab782ba42b5808076ac91fec846473aa5315a79. Checksums: not verified.

### 13. SciTab
- What: claims about scientific results checked against a table and its caption.
- Size: 1,225 claims; number of tables not verified.
- Document, length: one table with its caption, from arXiv computer science papers.
- Decisions per document: about 6.16 per table as reported (the number of tables is not verified).
- Labels, spans: supports, refutes, not enough info; spans not verified.
- Splits: none official (25 demonstration claims from 5 tables).
- Official metric: macro-F1.
- Licence: repository MIT; data licence not stated. Access: open JSON. Evaluation use: permitted under the repository licence.
- Contamination: none stated.
- Fit: Medium; meets (a) to (e). Chosen.
- Source: https://github.com/XinyuanLu00/SciTab ; https://arxiv.org/html/2305.13186v3
- Version: commit 217cfbd71ebf39ba26a0938f0d87a9fce560e0fe. Checksums: not published.

### 14. FEVEROUS
- What: claim verification over Wikipedia text and tables.
- Size: 87,026 claims.
- Document, length: the whole of Wikipedia (December 2020), up to 3 evidence sets per claim.
- Decisions per document: claim-centred; no document under review.
- Labels, spans: supports, refutes, not enough info; evidence sets.
- Splits: test blind (unlabelled).
- Official metric: FEVEROUS score.
- Licence: data CC BY-SA 3.0; code Apache-2.0. Access: open. Evaluation use: permitted.
- Contamination: Wikipedia text is in most training sets.
- Fit: Low; fails (a) (open-domain retrieval over all of Wikipedia, V6).
- Source: https://fever.ai ; https://github.com/Raldir/FEVEROUS
- Version: commit 32b68ce4e33c53f34ae2e6d88b51cd073ab85ab6. Checksums: not verified.

### 15. FinQA
- What: numerical reasoning questions over earnings reports.
- Size: 8,281 question and answer pairs.
- Document, length: an earnings-report page with a table.
- Decisions per document: about 2.9 per report.
- Labels, spans: numeric answers with reasoning programs.
- Splits: private test; others not verified.
- Official metric: execution accuracy, program accuracy.
- Licence: MIT (repository); one reading gives CC BY 4.0. Access: open. Evaluation use: permitted.
- Contamination: a test leak was fixed in 2022.
- Fit: Medium-low; fails (b) and (c) (free numeric answers, no verdict).
- Source: https://github.com/czyssrs/FinQA
- Version: commit 0f16e2867befa6840783e58be38c9efb9229d742. Checksums: not verified.

### 16. TAT-QA
- What: questions over financial-report tables with surrounding paragraphs.
- Size: 16,552 questions over 2,757 contexts.
- Document, length: one table plus paragraphs.
- Decisions per document: about 6.0 per context.
- Labels, spans: span and arithmetic answers.
- Splits: not verified.
- Official metric: exact match, F1.
- Licence: CC BY 4.0 (README); MIT (repository sidebar). Access: open. Evaluation use: permitted.
- Contamination: test labels released January 2024.
- Fit: Medium-low; fails (b) and (c).
- Source: https://github.com/NExTplusplus/TAT-QA
- Version: commit 870accc41953dcde885aabeb963d94aabdc0fbc3. Checksums: MD5 published on the site (values not recorded).

### 17. FinDVer
- What: verifying claims against long financial filings, many needing arithmetic.
- Size: 2,100 claims per the ACL PDF (conflicting figures above).
- Document, length: SEC 10-K and 10-Q filings, January to April 2024; about 40,000 tokens on average (paper); a median of about 42,000 words in another reading, inconsistent with that mean (not verified); 523 filings.
- Decisions per document: about 4.
- Labels, spans: entailed or refuted, with an explanation and context indices (evidence paragraphs).
- Splits: testmini (development), test.
- Official metric: accuracy. One subset (FDV-Know in the paper; the stored subset value is PROVISIONAL) needs knowledge beyond the filing.
- Licence: MIT. Access: open. Evaluation use: permitted.
- Contamination: test labels public since 2026-07-14.
- Fit: Medium-high; meets (a) to (e); no refusal class. Chosen.
- Source: https://github.com/yilunzhao/FinDVer ; https://aclanthology.org/2024.emnlp-main.818.pdf ; https://arxiv.org/abs/2411.05764
- Version: commit e8bb237def4ce555a606a45edba22666e31df248. Checksums: not published.

## Rejected and deferred

- **LLM-AggreFact**: gated access and a no-derivatives licence (H13, ND). The operator did not accept its terms; it stays out.
- **MAUD**: pre-extracted passages, no whole document under review.
- **LegalBench ContractNLI tasks**: derived from ContractNLI's test set, so not independent of ContractNLI; binary; no spans; single clauses.
- **LegalBench rule-application tasks**: short fact patterns; the application is graded by hand; some families NC.
- **AIReg-Bench**: licence conflict between its card and its repository; small; synthetic, model-written documents; ordinal scores.
- **DocNLI**: the research could not verify its size, labels or metric; repository archived.
- **FACTS Grounding public** (V5): a model-judged generation task, with no document check.
- **TabFact** (V6): nothing added over SciTab, and its blind test reuses training tables.
- **FEVEROUS** (V6): open-domain retrieval over all of Wikipedia, no single document under review.
- **SummEdits**: exposed. The repository already tracks converted SummEdits documents from a task before the loop (`tuning/auditor_external_relation_v1/`), so its items cannot be sealed (Annex A, 11.0; D-019).
- **FinQA, TAT-QA**: free-text or numeric answers with no clean mapping to verdicts.

## Gated candidates (H13)

- **ContractNLI**: click-through terms of use on the download page; accepted by the operator on 27 October 2026 (D-S3), so it is chosen, and only role B downloads it.
- **LLM-AggreFact**: gated by a click and contact details; CC BY-ND 4.0; evaluation only. Not accepted.

The loop accepts no terms itself: ContractNLI's were accepted by the operator (D-S3). Both are recorded, with their exact terms, in the operator's private notes (`FOR_SECKIN.md`, section on the two benchmarks that need an acceptance); LLM-AggreFact stays there as a candidate for a later run. Those notes also list every NC or ND item found: LLM-AggreFact (ND), the NC LegalBench families, and SummEdits' samsum upstream (NC and ND).

## Dry-run results (development)

Pending S5. Results here will be labelled development (exposed items) and never counted as evidence.
