# STEP W7 REPORT: ontology foundations

Only what night.md wrote for W7 was built. Everything not written there was left as
recorded open work. Run in the operator's re-ordered sequence (design doc, four convention
assignment commits, then W7), ahead of the W6 rerun, which waits on the operator tagging
the eight device rules; nothing in W7 depends on W6, and W7 a was written to run before W6
writes to the stores in any case.

## a. Archive and empty: NOT EXECUTED, blocked, the tool is built

The instruction: archive the ontology and GNN stores as a dated file outside the repository,
then empty them. The tool that does exactly that is built, `tools/archive_ontology_stores.py`
(zip every file under `ontology/stores/` into
`<repo parent>/shimmer-archives/ontology_stores_<UTC stamp>.zip`, read every member back and
compare its sha256 before anything is emptied, then truncate the JSONL stores to zero bytes
and remove the derived `graph.json` and `gnn_state.json`, which their modules rebuild from
an empty store). Its dry run produced the manifest below. Running it for real was refused
twice by the agent's tool permission layer (the action deletes files under the repository
and writes outside it), and that refusal is not something to work around: the operator runs
it, once, with

```
py -3.9 -X utf8 tools/archive_ontology_stores.py
```

Dry-run manifest at 11:27:43Z (nothing written, nothing removed):

| file | bytes | lines | sha256 |
|---|---|---|---|
| `gnn_state.json` | 27331 | 1032 | `63b62cb806c63add5a7933b3bdf4a18615f4f5bb7ba41f438f06affa6d83e710` |
| `graph.json` | 9378 | 245 | `c0c91e2735ef821055775c1dafacd6fac9a06db1c2fc349cafcce5037345628b` |
| `provisions.jsonl` | 2692 | 4 | `539b3900b59bbafb69df35518ec7e5eaede3843a50cd81d49940424bc81c0dfd` |

The stores are small in this repository: four provision records from one September 10 run
on a synthetic catalogue corpus (three unique ids; two records share `catalogue_records::REF-0067`
because two findings sat at one location, the id collision the storage layer below now
turns into an honest revision 2). The 549 records night.md speaks of are the private
repository's; this snapshot never carried them (`ontology/` has never been committed here:
`git ls-files ontology` is empty and `.gitignore`'s claim that the JSONL stores "are
tracked" was false and is corrected in this commit). Until the operator runs the tool, the
four old-shape records stay on disk and are INVISIBLE to every read, because they carry no
scope and the storage layer returns nothing that carries none; the first run after this
commit writes new-shape records beside them. Nothing is lost either way.

## b. Provenance: built

`scripts/ontology_store.py` defines the struct and the one function that mints it:
`provenance(time, agent, run, type)` returning exactly `{time, agent, run, type}`
(`PROVENANCE_FIELDS`). `ontology_capture.capture_provisions` stamps it on every provision
record, full and stub, from the real capture path:

- `time`: the capture timestamp (one per capture call, ISO 8601 UTC).
- `agent`: the agent whose Finding the amendment rests on. Amendments carried no agent at
  all before tonight (the master's amendment dict, `paired_review.py:1544-1560`, had none),
  so two small changes carry it: pipeline phase 6 stamps the envelope's own agent (the key
  of `upstream_findings`) onto each upstream Finding as it flattens them into
  `all_upstream`, only where absent, and `amendment_from_finding` copies `item["agent"]`
  onto the amendment it builds. A stub carries the agent of the amendment that referenced
  it. An amendment carrying no agent yields `agent: null`, visible, never invented.
- `run`: the run id.
- `type`: `PROVENANCE_TYPE_DOCUMENT` (`"document"`) for every record captured, because every
  record that has ever existed came from a document under review. `PROVENANCE_TYPE_RULE` is
  declared and left `None`, with the note in the module docstring: it is populated once the
  rule-derived path has been run and its record shape observed. `provenance()` REFUSES to
  mint any type but the document one, so nothing can guess the rule shape into existence.
  For the record: the trace found NO rule-derived capture path in this repository's code at
  all (the only capture reads the per-document amendments master), which is consistent with
  the instruction's own statement that the path has never been exercised.
- No confidence field, by decision; check 201 fails if one appears on a record or its struct.

## c. Isolation: the mechanism is built, the concept is not

The scope is enforced at the storage layer, not by a filter the caller must remember. A
`ProvisionStore` is opened under a scope, bound once at construction (an empty scope is
refused), and every read it can perform (`current()`, `superseded()`, `history()`,
`log_entries()`) filters on that scope inside the layer; the only all-scopes read is private
and exists so compaction can write other scopes' records back untouched. Every record
written is stamped with the scope by the layer (a caller-supplied `scope` is overwritten,
`STORAGE_FIELDS`). A record carrying no scope, or another scope, is returned by nothing. The
proposal accumulator (`delta_proposals.jsonl`) is read and rewritten per scope through
`read_accumulator` / `write_accumulator`, the other scopes preserved on every rewrite.
`build_graph` reads provisions ONLY through the store under a `scope` argument and records
the scope it was built from; the GNN state records the graph's scope.

The identifier defaults to one value, `DEFAULT_SCOPE = "default"`, and is bound in exactly
one place, pipeline phase 8 (`oge_scope = ontology_store.DEFAULT_SCOPE`, passed to
`capture_run` and `build_graph`), which is where a real engagement identifier will be bound
later. No engagement concept was invented: no config key, no flag, no per-client directory.
The mechanism is built and the concept is not.

Proved as the instruction asks: check 200 writes under one scope, reads under another and
asserts nothing comes back (two scopes, an unwritten third, the default, and a bare unscoped
line written behind the layer's back; the accumulator; the real `capture_run` twice under two
scopes; `build_graph` under one of them).

## d. Dual track: built

`provisions.jsonl` is the live store; `provisions_log.jsonl`, beside it, is the immutable
log. Writing a record whose id is already current in the scope SUPERSEDES it: the new record
gets `revision` = previous + 1 and `supersedes` = the previous `record_id`; `current()`
returns only the highest revision per id, so a superseded entry is excluded at the storage
query layer and no caller can get one back through the read path. Every supersession appends
a `supersede` event to the log with both record ids and both revisions. `compact()` moves
the superseded revisions of the scope out of the live store and into the log (each with
`event: compacted` and `moved_at`), rewriting the live file with the current records of the
scope and every other scope's records untouched. The log has exactly one writer
(`_append_log`) and it only appends; check 202 asserts the log bytes before compaction are a
prefix of the bytes after, and that no line of the module pairs `log_path` with a rewriting
call. `history(id)` spans live and log. Deletion, when built, is logged the same way (the
method's docstring says so); nothing logs a deletion today because nothing deletes.

On the real capture path, re-capturing the same master supersedes instead of duplicating:
`capture_run` reports `provisions_superseded` (and `stubs_skipped`: a stub for an id whose
current record is a full one is not written, so a later run that only references a
provision cannot supersede what an earlier run captured of it, the preference the graph
used to apply at read time and no longer needs to). The pipeline's phase 8 log line now
reads `oge_capture scope=... provisions_appended=... provisions_superseded=... stubs_skipped=...`.

## e. Supersede built, delete not

`ProvisionStore.supersede(id, record)` is the explicit form (refuses an id with nothing
current, since a supersession of nothing is a plain write). `ProvisionStore.delete(id)` is
declared and raises `NotImplementedError` with the reason: the user-facing deletion case is
an operator decision not yet finalised. Check 202 fails if delete stops refusing.

## What changed

- `scripts/ontology_store.py` (new): scope, provenance, dual track, supersede, the declared
  delete, the scoped accumulator functions. Stdlib only, no model calls.
- `scripts/ontology_capture.py`: records carry provenance; `capture_run` writes through
  the store under a `scope`; the accumulator helpers delegate to the store's scoped
  functions; the module writes no store file itself any more.
- `scripts/ontology_graph.py`: provisions read through the store under `scope`; the graph
  carries `scope`; provision nodes carry `provenance` and `revision` (SAFE metadata, no
  content; the GNN's allowlisted feature builder ignores them by construction). The old
  read-time dedup (prefer non-stub, then latest `captured_at`) is gone: the store's
  `current()` is the one rule.
- `scripts/ontology_gnn.py`: the state's old `scope` string ("machinery-not-learning ...")
  is renamed `claim`, and `scope` now carries the graph's storage scope. Nothing read the
  old key (checks 62 to 64 still pass unchanged).
- `scripts/paired_review.py`: `amendment_from_finding` carries the Finding's `agent`.
- `scripts/pipeline.py`: `import ontology_store`; phase 6 stamps the envelope agent onto
  each upstream Finding; phase 8 binds `oge_scope`, passes it to `capture_run` and
  `build_graph`, and logs scope and supersession counts.
- `scripts/verify_session1.py`: checks 200, 201, 202 (below); check 143's OGE-section
  window is now bounded by the section's own closing line instead of 2500 characters (the
  scope binding and the longer log line pushed `build_graph` past the old window; the
  assertion itself, both calls fed the same `oge_sensitive`, is unchanged); checks 59 and
  60 write their provision fixtures through the store instead of raw lines (a raw line with
  no scope is invisible by design, so the fixtures had to be written the way the pipeline
  writes).
- `tools/archive_ontology_stores.py` (new, see a).
- `README.md` (section G: the stores paragraph and the storage layer; section L: the check
  total, 203), `CLAUDE.md` (key paths), `.gitignore` (the false "tracked" comment
  corrected; the log file is inside the same untracked directory).

## Gate checks added, each proved by neutralise, fail, restore, pass

Check 200, scope. Neutralised by replacing the layer's in-scope read with an all-scopes read:

```
('FAIL', "scope-a read returned ['doc::R1', 'doc::R2', 'doc::R3', 'doc::R4'], not only its own two records")
```

Restored: `PASS`.

Check 201, provenance. Neutralised by replacing `provenance()` with one returning an empty
struct:

```
('FAIL', "docA::REF-0001 provenance fields [] are not exactly ['agent', 'run', 'time', 'type']")
```

Restored: `PASS`. The check also executes `amendment_from_finding` on a Finding carrying an
agent and asserts the pipeline's phase 6 stamp is still in the source.

Check 202, dual track. Neutralised by replacing `current()` with an unfiltered in-scope read
(every revision returned):

```
('FAIL', "current() did not return only the highest revision: [{'id': 'doc::X', ... 'revision': 1, 'supersedes': None ...}, {'id': 'doc::X', ... 'revision': 2, 'supersedes': 'bd5513ad...' ...}]")
```

Restored: `PASS`. Each check runs its body three times (shipped, neutralised, restored) and
reports all three in its own PASS line, so the proof is executed on every gate run, not
only recorded here.

Every ontology check that existed (57 to 64, 72 to 74, 119, 143, 175) passes on the new
layer.

## Gate result

```
PASS=201  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=203
```

`output/w7_gate1.log`. The baseline before this step was PASS=198 FAIL/ERROR=2 TOTAL=200;
three checks added, three more passes, WARN unchanged at 0, the same two pre-existing
failures (check 01, missing `prompts/` and `snapshots/`; check 145, missing
`tests/fixtures/planted_figure_hashes.json`). Wb holds: FAIL count unchanged, SKIP 0, WARN
at the baseline, PASS the red line plus the checks added.

## Not in scope tonight, not started, recorded as open

Making the GNN learn; the candidate finder; the long-range mechanism; curation interfaces;
developer defaults; the two rule sets; any convention hierarchy. Also open, found on the
way: `ontology/SCHEMA.md`, cited by all three module docstrings as the ratified schema, does
not exist in this repository (the code is the only specification); the store paths are three
duplicated module constants with no config key; `backup_state.py`, `compose.yaml` and the
RUNBOOK name `ontology/stores` as a whole tree, which still holds (the log lives inside it).

## Alternatives not taken (C5: the option that changes least)

A per-scope directory (`ontology/stores/<scope>/`) would isolate by the file system as well
as by the field; it would also move every store path, every ignore rule, the backup tree,
the compose mount and the RUNBOOK restore procedure, for a concept that does not exist yet.
A field on every record, enforced in one layer, changes least and can be moved to
directories when an engagement binds a real identifier. Superseded records could have been
rewritten in place with a `superseded_by` field; instead the live store stays append-only
between compactions and the query layer computes currency, so no write ever mutates an
earlier line.

---

STEP W7 INCOMPLETE: (a) archive-and-empty is built and dry-run verified but NOT executed
(refused by the tool permission layer; the operator runs the one command above); (b), (c),
(d) and (e) are built, gate-proved by checks 200 to 202 and committed.
