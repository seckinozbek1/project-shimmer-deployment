# Shimmer limitations

What Shimmer does not do, and the limits on what its results show. This text was moved
from the README on 19 November 2026 (D-816); the short [README](../README.md) links here.
What it does is in [METHOD.md](METHOD.md), and every result with its conditions is in
[RESULTS.md](RESULTS.md).

## Limitations

- Version 1.0 is not yet released (see [the first results](RESULTS.md#first-results-november-2026)). The current code is a development state, close to a pre-alpha: expect gaps and changes.
- The cloud model and the bare model were each measured once, on a limited set of items. On the ContraDoc and SciTab steering subsets (40 documents and 78 claims), Shimmer and the two references were scored on the same items, but in different runs and on different dates (the references on 13 November 2026, Shimmer in runs of 18 November 2026 on code from before that night's fixes). Under the project's own rules that Shimmer run (quick subset 0127b080) does not count: it is void on integrity, with many items undecided, and it is below both bars. On the negotiation pilot, the bare-model figure comes from older saved answers without the Python step, and the cloud-model figure covers 14 of the 18 items. Elsewhere Shimmer and the two references were not measured on the same items. Re-measuring both on the same items is planned after version 1.1.
- It is a prototype. Coverage depends on the corpus: Python can check only rules
  whose fields and scope the document and the conventions make usable.
- Model output can be incomplete, wrongly cited or self-contradictory. Read the
  marked model findings as unchecked.
- A finished process or a downloadable ZIP does not prove complete coverage.
  Check missing evidence, capped replies, failed contracts and unjudged rules
  before you accept a result.
- No figure shows accuracy on unseen documents.
- "Domain-agnostic" holds only in a narrow sense: no domain vocabulary is written
  in the code (it is declared in `config/domain_vocabulary.json`), and the
  pipeline has run on development material from several fields. The results
  differ widely from one field to another.
- Shimmer's cloud backend (provider models) has no figure on the results page; the
  cloud model figures there are references only. Every measured Shimmer run so far
  used open-weight models on a rented GPU.
- The FACT_CHECKER agent is withheld from every run that uses the shipped
  `config/review_scope.json` (`withheld_audit_agents`), because on an earlier test
  every item it returned in three runs was wrong. It stays registered, so the checks between model
  families are unchanged.
- The ontology has no learned update method. Two attempts with a graph neural
  network were tried and failed their bars, which were written before any figure
  (D-820). First, a network trained on a declared training set showed no gain over
  the reference on any of 5 seeds (GNN_TRAIN_R2, 19 November 2026). Second, a
  relation-aware redesign lost to a logistic regression over path counts on all 40
  development graphs for link prediction: mean reciprocal rank 0.34 to 0.42,
  against 0.73 to 0.75 (lane gnn-redesign, 20 November 2026). The likely cause is
  that the network scores each node separately, while the pattern it had to find
  lies between two nodes. Versions 1.0 and 1.05 use the knowledge graph without a
  network. A model that looks at node pairs, and any further network attempt, is
  planned for version 1.1.

## What it does not do

- Mask sensitive content in flight. See [Privacy](THREAT_MODEL.md#privacy-law-iv).
- Serve more than one operator. See [Access](THREAT_MODEL.md#access-one-operator).
- Offer a proven local Draft. Draft mode writes a memo with the drafter model of
  the chosen backend (a provider model under Cloud, a local model under Local, with no
  provider call), then reviews it; local Draft is not yet proven end to end.
- Resume a stopped run from the middle.
- Feed what it stores across runs (the ontology) back into a review. The one
  exception is the operator's own stored answers to external-rule conflicts, read
  only when `input/external_rules/` exists.
- Show any accuracy on unseen documents. Nothing measured so far can.

## Privacy, in one line

While the masking layer ships switched off, Shimmer protects private content by
refusing a sensitive run, not by masking it; the full statement is in
[THREAT_MODEL.md](THREAT_MODEL.md#privacy-law-iv).
