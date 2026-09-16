# V2 external data attribution

PAWS-Wiki Labeled Final: Google LLC. Source repository https://github.com/google-research-datasets/paws ; downloaded Parquet from https://huggingface.co/datasets/google-research-datasets/paws at revision `161ece9501cf0a11f3e48bd356eaa82de46d6a09`. Original documentation revision `02b29f3af1143620d1b7f352247e65c0bdd2ec18`.

Zhang, Yuan; Baldridge, Jason; He, Luheng. PAWS: Paraphrase Adversaries from Word Scrambling. NAACL 2019.

PAWS uses the Google custom dataset notice permitting use for any purpose, with acknowledgement requested and no warranty. The exact text is in `licenses/paws-LICENSE.txt`; it is not relabeled as CC-BY.

WikiAtomicEdits: Google Research, https://github.com/google-research-datasets/wiki-atomic-edits at `1f6769f2f9d93b6bf5acb091eb509b2be36e8e79`.

Faruqui, Manaal; Pavlick, Ellie; Tenney, Ian; Das, Dipanjan. WikiAtomicEdits. EMNLP 2018. https://aclanthology.org/D18-1028/

Marrese-Taylor, Edison; Reid, Machel; Matsuo, Yutaka. Variational Inference for Learning Representations of Natural Language Edits. AAAI 2021. https://doi.org/10.1609/aaai.v35i15.17598

Published sample: PEER v1.0, authors Edison Marrese-Taylor, Machel Reid and Yutaka Matsuo, DOI https://doi.org/10.5281/zenodo.4478267 (concept DOI 4478266). The downloaded archive MD5 matches the publisher record: `8bca47b0019ce1ec33d332a73d7b3b75`. Only `PEER/edits/insertions_deletions.jsonl` and its split-ID files were extracted/read; other PEER datasets were not inspected.

The PEER paper describes sampling about 150K English WikiAtomicEdits records and retaining 104K after cleaning. The authors tokenize sentences, align edits and replace some numbers with placeholders. V2 drops placeholder-bearing text and retains exact token arrays joined with single spaces. The operation is derived from one contiguous published insert/delete tag run and validated against before/after arrays, changed tokens, source and target. No atomic operation is reversed.

License records differ: the official WikiAtomic README links CC-BY-SA-4.0 but contains the unrelated wording “Query-wellformedness dataset”; the PEER Zenodo record declares CC-BY-4.0; the HF sample card says unknown. We preserve all notices and both full Creative Commons license texts. We do not silently treat these statements as equivalent, discard upstream ShareAlike attribution, or substitute repository code licensing. The HF card was used for provenance documentation only; actual sample bytes came from the authors’ Zenodo archive. This is a preparation/quarantine release, not a legal determination resolving the differing notices.

Modifications in V2: selection, symmetric PAWS orientation, single-space joining of published WikiAtomic token arrays, opaque identifiers, metadata separation, grouping and new splits. Text was not paraphrased, padded or generated. Original human PAWS labels and WikiAtomic edit operations are retained; no new annotation was performed.

Every external row retains the source-pool key, original row ID/split, canonical raw-row SHA-256, orientation/operation, source file/member, license record, and SHA-256 binding to `source_manifest.json`. That manifest binds the download manifest with source URLs, revisions, timestamps and file hashes. No upstream Wikipedia article IDs are invented.

`paws-train.parquet`: SHA-256 `8dc9ad3e5f30ad9a86b290fe236d528ef23a5751fec9a35d99cbacf68ba277cf`, 8433884 bytes, downloaded `2026-09-16T20:31:24.877704+00:00` from https://huggingface.co/datasets/google-research-datasets/paws/resolve/161ece9501cf0a11f3e48bd356eaa82de46d6a09/labeled_final/train-00000-of-00001.parquet?download=true.

`paws-dev.parquet`: SHA-256 `7760d829453764ba342a6f562809a8ed21c2c3eec3fd9ffa544089f145d42f6d`, 1230379 bytes, downloaded `2026-09-16T20:31:26.186051+00:00` from https://huggingface.co/datasets/google-research-datasets/paws/resolve/161ece9501cf0a11f3e48bd356eaa82de46d6a09/labeled_final/validation-00000-of-00001.parquet?download=true.

`paws-test.parquet`: SHA-256 `ae342ff12bb84b84b95f468abf5db6cb7c7bd578271299fe9c99be75b8132f4d`, 1235128 bytes, downloaded `2026-09-16T20:31:40.766580+00:00` from https://huggingface.co/datasets/google-research-datasets/paws/resolve/161ece9501cf0a11f3e48bd356eaa82de46d6a09/labeled_final/test-00000-of-00001.parquet?download=true.

`PEER.zip`: SHA-256 `2b628bee49ee2dfd7eb0e7103219799528060a79b6c641d09b0c11ebf25eb536`, 96028699 bytes, downloaded `2026-09-16T20:31:50.888570+00:00` from https://zenodo.org/api/records/4478267/files/PEER.zip/content.
