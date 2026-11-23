# Shimmer limitations

What Shimmer does not do, and the limits on what its results show. This text was moved
from the README on 19 November 2026 (D-816); the short [README](../README.md) links here.
What it does is in [METHOD.md](METHOD.md), and every result with its conditions is in
[RESULTS.md](RESULTS.md).

## Limitations

- The alpha is the current state of the code, not a release that reached its targets (see [the first results](RESULTS.md#first-results-november-2026)). Expect gaps and changes.
- The cloud model and the bare model were each measured once, on a limited set of items. On the ContraDoc and SciTab steering subsets (40 documents and 78 claims), Shimmer and the two references were scored on the same items, but in different runs and on different dates (the references on 13 November 2026, Shimmer in runs of 18 November 2026 on code from before that night's fixes). Under the project's own rules that Shimmer run (quick subset 0127b080) does not count: it is void on integrity, with many items undecided, and it is below both bars. On the negotiation pilot, the bare-model figure comes from older saved answers without the Python step, and the cloud-model figure covers 14 of the 18 items. Elsewhere Shimmer and the two references were not measured on the same items. Re-measuring both on the same items is planned after the full release.
- It is a prototype. Coverage depends on the corpus: Python can check only rules
  whose fields and scope the document and the conventions make usable.
- Model output can be incomplete, wrongly cited or self-contradictory. Read the
  marked model findings as unchecked.
- A finished process or a downloadable ZIP does not prove complete coverage.
  Check missing evidence, capped replies, failed contracts and unjudged rules
  before you accept a result.
- Accuracy on unseen documents rests on few items. On 21 November 2026 the system was
  scored on untouched items (items not used to build or tune it): ContraDoc 0.875
  on 8 documents, with a chance test p of 0.249, so luck alone could give it; SciTab
  0.846 on the 13 of 15 claims it answered (0.733 if the 2 unanswered count as wrong),
  read again from the same answers after a reader fault was fixed, with the coverage
  rule loosened by the project owner after the result was seen; on 31 synthetic
  negotiation items, conflict 0.955, open point 0.393 and stance 0.299. On the 20 of
  those items the cloud model also answered, the system's open point 0.407 and stance
  0.330 are about equal to the cloud model's 0.381 and 0.295.
  See [RESULTS.md](RESULTS.md#first-results-on-untouched-items-21-november-2026). The final test set
  has not been run.
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
  lies between two nodes. The alpha and the beta use the knowledge graph without a
  network. A model that looks at node pairs, and any further network attempt, is
  planned for the full release.

## Switched off in the alpha

Some parts of Shimmer are built or planned but are not used in the alpha. Each line says why, and what happens instead. The scores were measured with these parts off, unless a line says otherwise.

- Institution finder: off by default since 13 November 2026, because its job has no use yet and no other part reads its output. Nothing takes its place. The operator can switch it on for one run. The 54 alpha development items ran with it off.
- Fact-checker: withheld from every run since 19 September 2026, because every item it returned in three test runs was wrong. Nothing takes its place. It stays registered, so it can be switched back on.
- Masking of personal data: built but off. Switching it on needs the operator's approval, and its tests are planned for the beta. Instead, a run marked sensitive is refused. A run starts only if the operator declares it not sensitive, and that choice is logged.
- Table tool: the alpha code still has it switched on, although a test on 38 tables did not meet its 90 percent bar (4 ended incomplete). It is used only for rules that compare table cells. The SciTab score was measured with this code, so it is not proof that the tool works.
- Operator red lines: in the alpha, the operator can give them. They were tried only on practice items, with sample red lines we wrote. Finding red lines inside texts without the operator is planned for the beta. Until then nothing does it.
- Difference check: built but off as shipped, and the pipeline does not call it, so a run does not show these changes. Wiring it into the run needs a re-seal, which comes after the alpha. Its threshold was set on its own small practice set.
- "What if" step in the negotiation game: not in the alpha. It was placed in the beta on 20 November 2026, and the alpha scope was frozen the same day. Nothing takes its place.
- Graph network (GNN): off, because two attempts failed bars written before any figure. Instead, the ontology uses the plain knowledge graph. Any further attempt is for the full release.
- ContraDoc low-confidence rule: not in the headline score. Adding it to the headline is planned for the full release. A separate line, with unsure pairs counted and labelled, is shown beside the headline.
- Speed measurement: not done yet. It is planned for the beta, and no speed claim is made.
- Review desk: no key is needed, but only on this computer. This is a free local trial, and security work comes in the beta. Keyless mode opens every protected route of the server to this computer, not only the desk. Other computers need the token.
- Review desk language: the desk and its guide are in English only in the alpha. A short Turkish guide to a first review already exists ([GUIDE_TR.md](GUIDE_TR.md)).
- Local drafting without a provider: built, but not yet proven end to end. Under Cloud, drafting uses a provider model instead.

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
- Show accuracy on a final test set. The untouched-item figures of 21 November 2026
  are few, the ContraDoc figure is within what luck alone could give, and the SciTab
  coverage rule was loosened after the result was seen ([RESULTS.md](RESULTS.md#first-results-on-untouched-items-21-november-2026)).

## Privacy, in one line

While the masking layer ships switched off, Shimmer protects private content by
refusing a sensitive run, not by masking it; the full statement is in
[THREAT_MODEL.md](THREAT_MODEL.md#privacy-law-iv).
