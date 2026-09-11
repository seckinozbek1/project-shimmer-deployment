# ONTOLOGY JOB 4: the GNN as a candidate finder

**Built, not measured.** No candidate set has been scored against anything. The ontology
store is at zero bytes, so the only graphs this has ever run on are the fixtures built for
the test. Nothing here is known to be useful; it is known to be correct on fixtures. The
operator scores the deterministic baseline and this finder on the long-range corpus after the
move and chooses between them then, with the baseline setting the bar because it already
found the long-range reference on a fixture.

**No pipeline run was started and no language model was loaded.** Per the operator's
clarification, the standing rule is about the 7B and 3.5B models and the hour-long runs that
take the card. What ran here is a graph autoencoder over a dozen nodes: the forward and
backward pass took about five seconds on the first call and the candidate ranking twelve
milliseconds, both on CPU in the gate.

## The correction, recorded first because the brief carried the error

The operator's own words: "I have been saying for weeks that the GNN resets its weights every
run. It does not."

It does not. `gnn_update` loads any prior state, restores the persisted encoder and decoder
weights when the feature dimensions match, keeps a high-water mark of the node ids it has
already trained on, backpropagates only over nodes new since that mark, and persists the
updated mark. The feature width is constant across runs by construction (deterministic
feature hashing into fixed buckets), which is exactly what keeps a persisted weight matrix
valid. **Weights accumulate.** What is absent is the Tier-2 signal: recurrence of proposals
and findings across runs, verification verdicts, precedent, all of which stay empty until
runs populate them. The engine learns nothing because there is nothing yet to learn from, not
because it forgets.

That correction is now recorded in three places a reader will find it: the README's ontology
section, the job 2 report whose brief carried the error, and here. The check asserts the
behaviour directly, so the claim cannot drift back: a second update over the same graph has a
zero delta and byte-identical weights.

## The standalone test, run first as instructed

A fixture graph with enough structure that a candidate set is a meaningful thing to produce:
two documents, three conventions, seven provisions of deliberately varied shape (a hub with
three cross-references, leaves, two stubs carrying no rule), and real edges.

| step | result |
|---|---|
| first update | 12 nodes, 17 edges, delta 12, loss 0.1117, about 5 s |
| second update, same graph | delta 0, weights byte-identical, `n_updates` unchanged |
| state | `trained_count` 12, weights persisted |
| candidate finder | 14 candidates from 7 provisions in 0.012 s, weights read from the persisted state |
| determinism | the same graph and state produce the identical candidate set |
| exclusion | excluding one known pair removes exactly it |

**The ranking discriminates, and by how much is worth stating.** On the varied fixture the
scores span 0.9327 to 1.0000 with eleven distinct values. The ordering is structurally
sensible: the two hubs pair with each other, the two stubs pair with each other, and a
hub-to-stub pair ranks lowest. The narrow spread is a real property of ranking on structure
alone in a space fit to reconstruct its own input, and it is reported here rather than
discovered later by someone reading a cosine of 0.99 as strong evidence. On a first fixture
whose provisions were structural twins the scores were identical at 1.0000, which is correct
behaviour for identical structure and is why the check now requires at least three distinct
scores on a varied graph.

## What was built

**`scripts/ontology_candidates.py`**, which reuses the existing encoder rather than adding a
second model: `gnn_update` already persists an encoder over the Tier-1 graph, and a separate
scorer would mean two things that must agree about what a node is. The finder runs a forward
pass only, writes no state, and never trains: a candidate finder that trained would be a
second writer of the same weights.

- `embed_nodes` reports whether the weights came from a persisted state or a deterministic
  initialisation, because a candidate set ranked by fresh weights is even less than one
  ranked by persisted ones and the difference must never be invisible.
- `find_candidates` proposes pairs of **provisions** only. Proposing that a document relates
  to a convention is not the question decision 9 asks and would bury the pairs that matter.
  One row per unordered pair, never two; a node is never its own candidate; fewer than two
  provisions yields nothing.
- `exclude_pairs` keeps the deterministic baseline's own relations out, so the mechanisms are
  compared by what each finds that the other does not.
- `state_summary` is the read path's source and reports the absent Tier-2 signal as a field,
  not as prose.

**Two routes**, `GET /ontology/gnn` and `GET /ontology/candidates`, both token-gated, neither
run-scoped. An out-of-range `top_k` is a 400 rather than a silent default. A state never
written is a 200 with `exists: false`.

**A console section** on the Agents page. It is the one section here that does **not**
disappear when its subject is absent, and that is deliberate: "no state yet" is itself the
fact a reader needs, and an empty space would read as "there is nothing to say about the
GNN" when the truth is "the GNN has nothing to say".

## The honesty qualifier, and why it is structural rather than editorial

With no Tier-2 signal the ranking rests on graph structure alone: node type, degree, edges.
That sentence is not a caveat in a document. It is a field in the return value
(`ranked_on`), beside `learned_relevance: false` and `tier2_signal: empty`, on every path out
of the module including the empty-candidate-set case and the state summary. No consumer can
render a candidate set without it, which is the same discipline the override rate uses.

The reviewer-facing console wording says it without jargon: the model has learned nothing and
that is expected rather than broken, it keeps its weights between runs so it does not forget,
what is missing is the signal, and anything it suggests rests on how things are connected
rather than what they mean.

## The check, and its neutralise-and-restore proof

Check 213. It runs the real update path and the real finder on the fixture graph, then both
routes through the real FastAPI app and the console source.

**Neutralise:** `RANKED_ON_STRUCTURE` is replaced by a learned-relevance claim.

```
neutralised -> FAIL: ranked_on must say plainly what the ranking rests on
restored    -> PASS
```

The first version of that assertion was too weak: it looked for the phrase "learned
relevance", which a false claim also contains. It now additionally requires the qualifier to
**deny** learned relevance, and a subtler false claim ("ranked on graph structure with
learned relevance applied") was tested against it and fails:

```
subtler false claim -> FAIL: ranked_on mentions learned relevance without denying it
```

That is worth recording: the first check would have passed a claim that said the opposite of
the truth while containing the right words.

## README, checked start to finish against the tree

- Both routes added to the table (check 167 now agrees at 24 routes).
- The check count corrected from 213 to 214 in the two places that state it.
- Check 213 named in section L's coverage list.
- The `scripts/` tree line naming the candidate finder.
- The GNN correction recorded in section G, as its own paragraph.
- A new section G paragraph on the finder, what it proposes, and what the ranking rests on.

## Not built, recorded

- **No model call consumes a candidate set yet.** The graph narrows; the deciding call is the
  next piece, and it is not built here. What this produces is the input to it.
- **Nothing writes a Relation record from a candidate.** A candidate is a proposal, and
  promoting one to a relation without a decision would be exactly the assertion this module
  refuses to make.
- **The pipeline does not call the finder.** The routes and the CLI are the entry points; a
  phase-8 call site waits until there is a graph with real content to run on.
- The score spread on structure alone is narrow (0.93 to 1.00 on the fixture). Whether that
  spread separates anything useful is a measurement question, unanswered.

---

ONTOLOGY JOB 4 COMPLETE (the GNN candidate finder built on the persisted encoder, tested
standalone on a structured fixture before any wiring, then wired to two routes and a console
section with a read path for the state including the absent Tier-2 signal; the ranking rests
on graph structure alone and says so on every path out; check 213 with neutralise and
restore, strengthened after the first assertion proved too weak to catch a false claim; the
operator's correction about weight persistence recorded in the README, the job 2 report and
here; built without measurement, and the baseline stays beside it for the operator to choose
after scoring)
