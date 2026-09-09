# Corpus ingestion-contract fixtures

Synthetic, invented content. None of these are real cases. They exist so the
verify gate can EXECUTE `validate_contract.py` and prove it both accepts a
conforming bundle and catches a malformed one.

## conforming/

A tiny valid bundle. The validator must exit 0 (PASS) on this directory.

- `case_alpha-2021.md`: English body, structured into paragraphs.
- `case_beta-2024.md`: Arabic (RTL, non-ASCII) body, to prove non-Latin bodies
  are accepted. The non-ASCII content lives INSIDE the file, never in its name.

The year is hyphen-delimited (`-2021`, `-2024`), not underscore-glued: the repo's
date cascade uses word-boundary-anchored year patterns, and an underscore is a
word character, so only a delimited year resolves at the authoritative tier-1.
- `_corpus_ingest.json`: two matching entries. One uses `status: verified` with a
  non-empty `url`; the other uses `status: unverified` with an empty `url`, which
  the contract allows (a `url` may be empty only when the status is not
  `verified`).

## malformed/

A copy with deliberate PLANTED violations. The validator must exit non-zero and
must report each named check below.

| # | File / entry | Planted defect | Named check that must fire |
|---|--------------|----------------|----------------------------|
| 1 | `case_alpha-2021.md` entry | `role` is `operational`, not `context_grounding` | `role_is_grounding` |
| 2 | `case_gamma-2021.md` entry | `date` year is 2019 but the filename year is 2021 | `date_year_matches_filename` |
| 3 | `case epsilon 2023.md` | filename contains spaces, so the stem is not ASCII-safe | `filename_ascii_safe` |
| 4 | `case_zeta-2020.md` entry | sidecar names this `.md`, but the file is absent | `bijection_missing_file` |
| 5 | `case_beta-2024.md` entry | `source_verification.status` is `verified` but `url` is empty | `source_verification_valid` |

Defect 4 also makes `file_exists` fire for the same entry (a missing file fails
both checks); the gate keys on `bijection_missing_file` as the planted signal.
All other fields in the malformed bundle are valid, so each planted defect is
isolated to a single named check (apart from the file_exists overlap noted).
