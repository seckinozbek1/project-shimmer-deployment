# Real negotiation data with known outcomes: desk search (D-845, Seckin 20 November 2026 14:42)

Read only, no download, no spending; by a helper for the lead, 20 November 2026 about 14:50 +0300. Sources are linked for every claim.

## Candidates

| Candidate | Unit and size | Fate per proposal | Parties | Licence | Work to build items | Leakage |
|---|---|---|---|---|---|---|
| EP, War of Words II (Zenodo 4525015, https://zenodo.org/records/4525015, code https://github.com/indy-lab/war-of-words-2) | about 200k amendments with original and amended paragraph text, justification, committee, vote date, EP7 and EP8 | `accepted` true or false (changed and dropped not separated) | MEP, group (9), nationality, rapporteur flag | CC BY 4.0 | low to medium | text medium (PDFs public since 2009), labels low (niche) |
| EP, Tadorne/amendments on Hugging Face (from Zenodo 3757714, https://zenodo.org/records/3757714) | about 450k edits per the paper, no text, no group | `accepted` true or false | MEP ids and names | card says EUPL-1.1, source is CC BY 4.0 (conflict) | medium | low |
| UK Parliament Bills API (https://bills-api.parliament.uk/swagger/v1/swagger.json) | amendments per bill stage, live | 14 decision values (Agreed, Negatived, Withdrawn, NotMoved and others) | sponsors with party | Open Parliament Licence v3.0 | medium | controllable by session date |
| QUILL (https://quillproject.net, https://quill.uvu.edu/about/) | a few hundred amendments per collection (for example NI Forum 1996 to 1998: 204 documents, 213 amendments, 1,301 decisions) | adopt, reject, drop, postpone, refer | delegations, people | none found; permission needed | high | high for 1787 |
| US Congress API (https://github.com/LibraryOfCongress/api.congress.gov) | amendments with actions | read from action text | sponsor, party | public domain (assumed) | medium to high | medium |
| UNGA-DM (https://sites.google.com/view/christopher-kilby/datasets) | 22k decisions 1946 to 2023 | passed or failed, no text | states | not stated | high | medium |
| CaSiNo, DealOrNoDeal, CraigslistBargain | 1k to 7k dialogues | final deal only | two sides | CC BY 4.0, CC BY-NC, unknown | high (no documents, no numbered proposals) | high |
| LLM-Deliberation (https://github.com/S-Abdelnabi/LLM-Deliberation) | synthetic multi-party games | deal per issue | 6 to 7 parties | MIT | high | high |

No public corpus of real contract redlines with outcomes was found (CUAD and ContractNLI carry no edits; RedlineBench is synthetic).

## Recommendation

1. EP War of Words II: the only source joining proposal text, a fate label, named parties and groups under a redistributable licence. Closer look about half a day; needs a 1.1 GB download (operator's word). Check language, the definition of `accepted`, grouping by dossier, and how a two-way label maps to three fates.
2. UK Bills API: best three-way fates, party per sponsor, full text, clear licence; recent sessions allow items after a model's training cutoff. Closer look about half a day on two or three recent bills.

Skip QUILL unless permission is sought; skip the dialogue sets for this purpose.
