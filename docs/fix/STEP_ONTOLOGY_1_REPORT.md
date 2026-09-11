# ONTOLOGY JOB 1: the store gets a reader

**Built, not measured, and it cannot be measured yet.** The ontology store is empty in this
repository: `ontology/stores/provisions.jsonl` is zero bytes at this commit. The only writer
is run-end capture, and no run has been made since the store was scoped at night W7. Every
assertion below is proved on fixture records in a tempdir, never on real content. The first
real content arrives on the first run after the move to a GPU box. Nothing here is known to
be useful on real content; it is known to be correct on fixtures. No pipeline run was
started and no model was loaded at any point in this job.

## The gap this closes

`ontology/stores/` has been written at the end of every run since build B1 and read back by
nothing. `graph.json` and `gnn_state.json` are derived from it and consumed by no agent, no
phase and no deliverable. The README already said so. What it could not say was what the
store actually held, because there was no way for anyone to look.

A store nobody can inspect is indistinguishable from a store that is silently broken. That
is the whole case for this job, and it is a modest one.

## What was built

**A reader module**, `scripts/ontology_reader.py`. Read-only: nothing in it writes any store
file. It opens the scoped store through the existing storage layer (never the file), and
answers provenance:

- `provenance_summary(store)`: counts over the whole scope (provisions, stubs, records
  without provenance, superseded revisions still live, log events), counts by agent, by rule
  and by run, and a per-provision list.
- `provision_history(store, id)`: every revision of one provision, oldest first. This is
  what makes the supersession the storage layer has recorded since W7 legible to a human for
  the first time.
- `render_text(...)`: the plain-text rendering the inspector prints.
- `main(...)`: the operator's inspect-at-any-point path.

The per-provision rows carry identifiers and provenance only, never a provision's own text.
That boundary is a named constant (`SUMMARY_FIELDS`) rather than a convention each caller
applies by hand, and the gate check asserts a planted passage never reaches any output.

**Two routes**, in the pattern of `/harness` and `/rules/{rule_id}`, both token-gated and
neither run-scoped, because the store is cross-run by construction:

- `GET /ontology`: the whole summary. An empty store is a `200` with zero counts and an
  empty list, not a `404` and not an error, which is the state of every store today.
- `GET /ontology/provisions/{provision_id:path}`: one provision's revisions, oldest first.
  A `404` for an unknown id, because "this store has never held that provision" and "that
  provision has one revision" are different facts a caller must be able to tell apart. The
  id is the capture hook's composite `<document_id>::<ref_id>`, which carries a colon pair,
  so it is matched as a path parameter.

**A console section**, `ontologyStoreHtml`, on the Agents page (the cross-run page, beside
the harness, rather than any one run's page), in the established disappears-when-empty
pattern: `if (!body || !body.provision_count) return "";`. Today it renders nothing on every
installation, because every store is empty. That is the pattern working, not a defect.

**The inspector**, which is decision 5's "a way for a human to inspect what is held at any
point". It needs no server, no run and no model:

```
py -3.9 -X utf8 scripts/ontology_reader.py
py -3.9 -X utf8 scripts/ontology_reader.py --json
py -3.9 -X utf8 scripts/ontology_reader.py --provision "<document>::<REF-0001>"
```

On this repository it prints, correctly and usefully, that the store is empty and that an
empty store means no run has finished since it was created rather than that anything is
broken.

## What this reading is good for, and what it is not

The operator asked for this to be said plainly and not oversold. Three things it is good
for, all modest:

1. **Attribution after the fact.** Who said this, under what rule, when, in which run. That
   is an audit answer, not an analytical one.
2. **Coverage.** Which rules and which agents the store has ever seen, so a rule that has
   never produced a captured provision becomes visible. That usually means the rule never
   fired, not that it always passed.
3. **The store stops being write-only.** Which is the point of the job.

What it is **not**, stated as plainly: it is not retrieval, not relevance, not a cross-run
signal any review draws on, and it makes no past finding easier to find while a review is
running. It reads the provenance of decisions already made. **The long-range case is
untouched by it**: a term defined at the start of a document and used at the end needs
relations BETWEEN provisions, which the store does not hold. That is job 2, and job 2 does
not inherit any claim from this one.

## The check, and its neutralise-and-restore proof

Check 210, `the ontology store has a reader`. Its body (`_ontology_reader_body`) runs the
real storage layer, the real reader and the real FastAPI app against a fixture store in a
tempdir. It asserts:

- an empty store summarises as zero provisions and renders text that says EMPTY;
- a filled store counts by agent, by rule and by run over the CURRENT revision only (the
  superseded revision's agent is absent from the counts, the current one present);
- a record written under another scope never reaches this scope's summary;
- a planted passage of provision text reaches neither the JSON summary, nor the text
  rendering, nor the route's response body;
- history returns both revisions oldest first, each carrying its own agent;
- `GET /ontology` is 401 without a token and 200 with one, serving the fixture's counts;
- `GET /ontology/provisions/{id}` serves both revisions and 404s on an unknown id;
- `console.html` still carries the section, its holder, its fetch and its empty guard.

**Neutralise:** `ProvisionStore.current` is replaced by one that ignores the scope (reading
every scope's records from the live file, which is the defect the storage layer exists to
prevent).

```
neutralised -> FAIL: a record written under another scope reached this scope's summary
restored    -> PASS
```

Both results are in this report because the check reports them itself: the shipped run
passes, the neutralised run must FAIL or the check fails itself, and the restored run must
pass again.

Run alone, before the full gate:

```
PASS  the ontology store has a reader: an empty store reads as empty, a filled one
      summarises by agent, rule and run over the CURRENT revision only, another scope's
      records are never visible, a provision's own text never leaves the reader, history
      returns every revision oldest first, GET /ontology and GET /ontology/provisions/{id}
      serve them (401 without a token, 404 for an unknown id), and console.html carries the
      disappears-when-empty section; neutralise (scope filter ignored) FAILS, restore PASSES
```

## README, checked start to finish against the tree

Not only the sections this job touched. Four things had gone stale or would have:

1. The route table lacked both new routes. Check 167 fails in both directions and did fail
   until the rows were added; the row path must be the registered path
   (`/ontology/provisions/{provision_id:path}`), which is what the check compares.
2. The check count said 210. It is 211. Two places said it (section L's opening and the
   fresh-clone paragraph); both corrected.
3. Section L's coverage sentence stopped at check 209; check 210 is now named, with the
   reason it is fixture-proved.
4. The `scripts/` line of the tree block did not name the ontology store or its reader.

The ontology paragraph in section G was rewritten: it previously said "nothing in the
pipeline reads either back", which is still true of the review path and is now said that way
precisely ("no phase of a review reads any of it back"), followed by what the new reader is,
the three ways to reach it, what it is good for, what it is not, and the unmeasured caveat.

Checks 116 and 167 both pass.

## Not built, recorded

- Nothing reads the store during a review, and this job does not change that. The reader is
  for a human, after the fact.
- `graph.json` and `gnn_state.json` still have no reader. This job covers provisions only,
  which is where provenance lives.
- The console section is untested against a browser in this job (no screenshot): it is
  asserted by source presence and by the route it consumes, the same way the W8 sections
  were asserted at first.

---

ONTOLOGY JOB 1 COMPLETE (the store has a reader: a module with an inspector, two routes, a
console section; provenance only, scope enforced on the read path, supersession legible,
empty stores honest; check 210 with neutralise and restore; built without measurement
because every store is empty and the first content arrives on the first run after the move)
