# Project Shimmer

Shimmer reviews documents against rules that a person writes down. It reads the
documents, compares their figures and fields with those rules and with reference
material, and proposes cited amendments for a person to accept or reject. It never
edits a source document, and every step leaves a record a reader can inspect.
It also advises on multi-round negotiation drafts.

- Several agents built on models from different families check each other.
- Python decides every check that arithmetic or a field can decide; a model is
  asked only where Python cannot.
- A finding a model wrote stays visible and marked as not checked by Python. It
  never becomes an amendment.
- The instruction finder (INST_FINDER) is optional, off by default, and under
  development.

How a review runs, the constitution and the agents: [docs/METHOD.md](docs/METHOD.md).

## Current state (alpha, 21 November 2026)

"Alpha" here means the current state of the code. It is not a release that met its
targets. The alpha did not meet its targets, which were:

- the system at least 10 points above the bare model;
- the system at most 10 points below the cloud model;
- every negotiation measure at least 0.60.

These are first results; the final test set has not run yet. Each headline figure
below was scored once, on untouched items, with thresholds written before the look;
the SciTab information-only figure was read again after a reader fault was fixed. The
untouched comparison against the bare and the cloud model is not yet measured and is
in progress, so nothing here says whether the system is ahead of or behind either.

| Task | Untouched set | Result |
|---|---|---|
| Contradictions (ContraDoc) | 8 documents, 6 groups | 0.875, interval 0.625 to 1.0; not distinguishable from chance (permutation p 0.249) |
| Table claims (SciTab) | 3 papers, 4 tables, 15 claims | no headline score |
| Negotiation advice | 31 items, 197 proposals | conflict detection 0.955 (interval 0.924 to 0.980, p 0.0001); open point detection 0.393; stance matches fate 0.299 |

- SciTab has no headline score because the coverage rule (at most 5 percent of
  items unanswered) was not met: 13 of 15 claims were answered. For information
  only, not a headline: accuracy 0.846 on the 13 answered claims, interval 0.769 to
  1.0. This is a small set.
- In negotiation, open point detection (0.393) and stance matches fate (0.299) are
  below the 0.60 target. Conflict detection is the only measure above it.
- Left for the beta: the table tool refusal, the step output cap, two known faults
  (C23, C40), and a larger SciTab set.

Sources, dates and conditions for every figure, and the rules for testing:
[docs/RESULTS.md](docs/RESULTS.md), [docs/LESSONS.md](docs/LESSONS.md). Limits and
privacy: [docs/LIMITATIONS.md](docs/LIMITATIONS.md), [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## How to start

- Install, hardware and cost: [docs/INSTALL.md](docs/INSTALL.md)
- First review, step by step: [English](docs/GUIDE_EN.md), [Turkish](docs/GUIDE_TR.md); every task: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- The review desk, one plain page for a single review: [docs/DESK_GUIDE.md](docs/DESK_GUIDE.md).
  Keyless for local trial only (loopback); a non-local address needs the token.
- Agents, output files, server routes and settings: [docs/RUNTIME_REFERENCE.md](docs/RUNTIME_REFERENCE.md)
- Contributing: [CLAUDE.md](CLAUDE.md) and the founding design, [genesis.md](genesis.md)

## Citation and licence

Cite with [CITATION.cff](CITATION.cff). MIT licence ([LICENSE](LICENSE)). Version:
[VERSION](VERSION); changes: [CHANGELOG.md](CHANGELOG.md).
