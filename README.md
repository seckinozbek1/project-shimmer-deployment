# Project Shimmer

Shimmer reviews documents against rules that a person writes down. It reads the
documents, compares their figures and fields with those rules and with reference
material, and proposes cited amendments for a person to accept or reject. It never
edits a source document, and every step leaves a record a reader can inspect.
It also advises on multi-round negotiation drafts.

- Several agents built on models from different families check each other.
- Python decides every check that arithmetic or a field can decide; a model is
  asked only where Python cannot.
- A constitution read at run time governs the agents; only the operator can amend it.
- A finding a model wrote stays visible and marked as not checked by Python. It
  never becomes an amendment.

**Status: v1, a development prototype, published on GitHub on 2 November 2026.**
Version 1.0 is not released yet.

## First results

These are first results on development and validation material. The final test
set has not been run, and no figure here shows accuracy on unseen documents.

| Task | Set | Shimmer | Bare model / cloud model (references only) |
|---|---|---|---|
| Contradictions (ContraDoc) | 15 development documents | contradiction F1 0.615 | not measured on these items |
| Contradictions (ContraDoc) | 40-document steering subset, older code | accuracy 55.0 % (26 of 40 undecided); does not count (void on integrity), below both bars | 52.5 % / 90.0 % |
| Table claims (SciTab) | 47 development claims | macro-F1 0.776 (2 classes), 0.517 (3 classes) | not measured on these items |
| Table claims (SciTab) | 78-claim steering subset, older code | 0.190 (every claim undecided); does not count (void on integrity), below both bars | 55.8 / 81.7 |
| Negotiation advice | 18-item development pilot | conflict macro-F1 0.629 (was 0.419); conflict class 0 | 0.217 / 0.648 (14 items) |

Under the project's own rules the steering-subset run (quick subset 0127b080) does
not count: it is void on integrity, with many items left undecided, and it is well
short of both bars (at least 10 points above the bare model, at most 5 below the
cloud model). Every measured Shimmer run so far used local open-weight models; the
cloud model figures are references only.

Shimmer found none of the negotiation pilot's 12 conflicts. The cause is found and
a fix is built; it is not measured yet. Sources, dates and conditions for every
figure: [docs/RESULTS.md](docs/RESULTS.md).

## Where to start

- What Shimmer does, how a review runs, the constitution and agents: [docs/METHOD.md](docs/METHOD.md)
- Install, hardware and cost: [docs/INSTALL.md](docs/INSTALL.md)
- First review, step by step: [English](docs/GUIDE_EN.md), [Turkish](docs/GUIDE_TR.md); every task: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- Results, testing rules and how to reproduce them: [docs/RESULTS.md](docs/RESULTS.md)
- Limitations, privacy and access: [docs/LIMITATIONS.md](docs/LIMITATIONS.md), [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- Agents, output files, server routes and settings: [docs/RUNTIME_REFERENCE.md](docs/RUNTIME_REFERENCE.md)
- Contributing: [CLAUDE.md](CLAUDE.md) and the founding design, [genesis.md](genesis.md)

## Citation and licence

Cite with [CITATION.cff](CITATION.cff). MIT licence ([LICENSE](LICENSE)). Version:
[VERSION](VERSION); changes: [CHANGELOG.md](CHANGELOG.md).
