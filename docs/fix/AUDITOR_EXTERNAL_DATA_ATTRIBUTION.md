# External Auditor dataset attribution

The transformed external text is attributed to Salesforce and the cited dataset authors under CC-BY-4.0. This data license is separate from repository code licensing. Changes made here: reversible formatting, exact executable replacement, exact span deletion, and adjacent insertion. No endorsement by the upstream authors is implied.

License: https://creativecommons.org/licenses/by/4.0/ ; the full legal text and dataset cards are preserved in `tuning/auditor_external_relation_v1/licenses/`.

## Salesforce/summexecedit

Publisher: Salesforce. License: CC-BY-4.0. Revision: `d71ee27582afae29b1459b518229d9266ed4c8b2`.
Repository: https://huggingface.co/datasets/Salesforce/summexecedit
Paper: [SummExecEdit: A Factual Consistency Benchmark in Summarization with Executable Edits](https://arxiv.org/abs/2412.13378).
Authors: Onkar Thorat, Philippe Laban, Chien-Sheng Wu.
Downloaded rows: 4241; unique normalized underlying documents: 216.
Raw SHA-256: `f7ba6dece8322db94dbe86eb003a47a3e1fb90668e451be7414237e4d8313600`.
Downloaded at: `2026-09-16T19:55:53.254562+00:00`.
Raw schema: `{"doc": "str", "doc_id": "str", "domain": "str", "edit_type": "str", "edited_summary": "str", "explanation": "str", "model": "str", "original_summary": "str", "original_text": "str", "replace_text": "str", "sample_id": "str"}`.
Use: Executable spans only.

## Salesforce/summedits

Publisher: Salesforce. License: CC-BY-4.0. Revision: `ce0c479aaf59259abb6b67e42248b2f49004b7d5`.
Repository: https://huggingface.co/datasets/Salesforce/summedits
Paper: [LLMs as Factual Reasoners: Insights from Existing Benchmarks and Beyond](https://arxiv.org/abs/2305.14540).
Paper identity is linked from the official Salesforce factualNLG repository.
Downloaded rows: 6348; unique normalized underlying documents: 216.
Raw SHA-256: `21e34593330020d02b7d92f4651fdcc550f7d79a2f899392f106fd816c215a89`.
Downloaded at: `2026-09-16T19:55:56.053834+00:00`.
Raw schema: `{"doc": "str", "domain": "str", "edit_types": "list", "id": "str", "label": "int", "seed_summary": "str", "summary": "str"}`.
Use: Future source pool only; no relation rows emitted.

Every external row carries dataset, publisher, revision, license and link, citation, upstream row ID, upstream document ID, canonical document hash, original-row hash, source hash, upstream edit type/model, and a modification notice. `document_registry.jsonl` preserves row-hash/document-group lineage for both downloaded sources. SummEdits has no doc_id field; its registry retains null upstream doc_id and a content-derived document hash rather than inventing an upstream identifier.

The upstream datasets include model-generated summaries/edits. No new model generation, LLM annotation, per-row agent labeling, or paraphrasing was performed in this preparation task. Upstream factual-consistency labels and explanation text were not used as Shimmer relation labels.

The official HF cards both declare CC-BY-4.0. The separate factualNLG code repository displays Apache-2.0; that code license was not substituted for the downloaded HF data license. Its README is retained only in ignored raw documentation storage, with a download hash in the license manifest.
