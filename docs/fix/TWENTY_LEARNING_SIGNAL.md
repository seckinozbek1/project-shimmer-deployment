# TWENTY: the learning signal, 2026-09-13

Keep the GNN as a candidate finder measured against the deterministic baseline.
There is a third source of narrow supervision here: independently executable
structural and arithmetic rules. There is no demonstrated third source combining
scale, independent truth and labels for the GNN's actual provision-pair relevance
task. This recommendation does not authorise a new training component. The
operator retains that decision.

The current engine can fit a representation. `ontology_gnn.gnn_update` minimises
reconstruction error between its output and the same safe feature matrix it
received, on new node rows. It restores compatible weights and a node-ID high-water
mark. It does not optimise a human verdict, relation label or review-correctness
target. A lower reconstruction loss or moving weights is evidence of fitting that
objective, not of improved review judgments. OperatorDecision nodes reach the
graph, but neither their decision nor their topic is in the feature allowlist,
and their node type is outside the fixed vocabulary. More verdict rows alone
would not change the training objective or give the model those labels.

The candidate finder reads the encoder, ranks structural similarity, and emits
`learned_relevance: false`. Its score is not a calibrated probability of a true
relation. A learned representation can be useful for retrieval without being a
truth assessor; usefulness still needs a comparison on the intended task.

The current read-only inventory is more limited than the old volume figures
suggested. There are 22 provision rows and 17 log events, but the actual scoped
current-record reader returns five records; revisions and events are not extra
independent examples. There is one raw DeltaProposal. The stored graph has two
nodes and one edge; the persisted GNN metadata names 21 trained IDs over two
updates. These snapshots do not establish a coherent labelled evaluation set.
No answer-key contents were read. Evidence is in `output/twenty_signal_inventory.json`.

The 78 rows in the apparent operator-decision ledger are all exact matches for
check 107's synthetic approval fixture: 39 approvals and 39 denials for the two
fixed fixture run IDs, with its fixed rationale, topic, subject and decision date.
There are zero independently human-authored examples identified in that ledger.
Even authentic model-swap approvals would not automatically label provision-pair
relevance. The earlier estimate of roughly one verdict per run describes a
potential collection rate, not this file's usable training population.

Tracing those rows found a fixture leak: check 107 used a temporary run directory
while the new durable verdict writer still used the real project root. The check
now isolates both roots, verifies its local ledger and joins the writer before
cleanup. An independent enforcement mutation changes denial to approval before
the changed check fails. A safe sentinel reproduces the old out-of-fixture write,
and restoration prevents it. Existing append-only rows are preserved and explicitly
excluded from this assessment; this item creates no training dataset from them.
The live ledger's pre-item hash is checked after the proofs and full gate.

The candidate sources answer different questions:

| Candidate | What it can support | Why it is not the missing general truth source |
|---|---|---|
| Python arithmetic, date windows, exact field presence and unambiguous references | Reliable labels for the declared computation when parsing, units, scope and reference inputs are independently validated | These are narrow oracle tasks. Training on them distils the baseline; it does not establish prose interpretation or unknown relation correctness. |
| Controlled synthetic variants checked by those oracles | Many positive, negative and boundary cases for the same narrow task | Quantity does not add independence. Related variants must remain in one evaluation partition; the existing self-authored corpus/key error shows why author review alone is insufficient. |
| Baseline cross-reference edges and graph structure | Retrieval examples and structural consistency | An edge is what the extractor found, and a missing edge is not a verified negative. Reconstructing it can reproduce the extractor's misses. |
| Repeated findings, amendments and DeltaProposals | Candidate priorities and evidence to inspect | Repetition can amplify the same error. A contract-valid or schema-valid record is well formed, not thereby true; VETCH already demonstrated the distinction. |
| Authoritative reference documents and external rules | Facts, standards and bounds after provenance, applicability and extraction are checked | Source authority is not a labelled verdict on each document unit or candidate pair. There are no external-rule input files in this checkout, and no automatic discovery path. |
| Redaction reference labels and five-voter agreement | The separately calibrated redaction decisions they were authored for | Different target and granularity. Agreement is not independent human ground truth for ontology relations. |
| Benchmark answer keys | A held-out measurement surface | Small, partly self-authored and already exposed to development choices. Consuming them as training labels would spend their evaluation value. No key was opened for this answer. |
| Accepted edits, adjudicated conflicts and reviewer labels | Potential future task-specific supervision with a subject and reason | Not a currently demonstrated volume source. A run-level acceptance is not a label for every candidate, and unreviewed candidates cannot be called negatives. |
| Another model or a stronger ensemble | A teacher that may help rank candidates | It supplies model judgments, not independent truth. Distillation is a useful possible objective, but it must be named as such. |

The teacher distinction is consistent with the original
[knowledge-distillation work](https://arxiv.org/abs/1503.02531), which trains a
smaller model from a teacher's outputs. Applying that idea to Shimmer would be a
new experiment in imitation, not evidence that the teacher's conclusions are true.

The next useful measurement is the existing finder against `relation_extract`'s
deterministic baseline at a fixed candidate/reviewer budget. Keep the baseline's
known relations, inspect the finder's additional pairs, and independently judge
both positives and negatives. Report recall and precision at that budget,
additional confirmed relations, missed baseline relations, review calls, runtime
and refusals. Preserve document families, their versions, duplicates and synthetic
variants within one partition; split before deriving training examples or graph
features. Tune on a separate development set, keep the final set untouched, and
give uncertainty across documents/corpora rather than treating many pairs from one
document as independent trials. Fair comparisons across splits and training
procedures matter for GNNs, as demonstrated by
[Shchur and colleagues](https://arxiv.org/abs/1811.05868).

Pursue a learned relevance component only if this comparison shows repeatable
additional value, enough adjudicated labels for the actual target, usable permitted
features, and a maintained independent test set. Otherwise keep the finder modest,
or leave it unused if its review cost exceeds its contribution. No measured gain,
calibrated probability, human training corpus or ready-to-train sample threshold
is claimed here. No GNN architecture, feature vocabulary, model, dependency or
authority policy changes in this item.
