# STEP BAKED REBUILD: the image on the current tree, and what the layer reorder actually saved

**The review itself remains unmeasured.** This step measures the image and the gate inside
it, nothing else. Every mechanism from 10 and 11 September, the four ontology jobs included,
is proved on fixtures and has never been scored by a run. No pipeline run was started and no
language model was loaded.

## Why

`shimmer:baked` was built at 18:30 this evening and four commits landed after it (the
ontology chain, jobs 1 to 4), so the image was stale again. The Dockerfile's weight layers
now sit before the source layers, so the expectation going in was that a source-only rebuild
would reuse all three downloaded checkpoints.

## What the reorder actually saved, stated precisely because it is not what was expected

Two of the three weight layers were cache hits. The third re-downloaded.

| layer | checkpoint | first build (18:30) | this rebuild (20:30) |
|---|---|---|---|
| 11 | `BAAI/bge-m3` | 103.6 s | CACHED |
| 12 | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | 82.9 s | CACHED |
| 13 | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | 160.2 s | 165.7 s, re-fetched |

Layer 13's log shows the fetch progressing from 0 to 100 percent over eleven files, so it
genuinely re-downloaded rather than verifying a cache. All three weight layers ARE present in
the build cache afterwards (4.395 GB, 5.564 GB and 7.302 GB), and no cache prune happened
between the two builds (`Reclaimable: 0B`, 25 entries, 27.08 GB).

**Why layer 13 missed is not established.** Two theories were tested and both failed: a
timing race between the builds is ruled out (the first build's log closed at 18:45 and this
one started at 20:30), and a Dockerfile difference is ruled out (the three RUN blocks are
identical in form, differing only in the model id). What is recorded is the observation, not
a cause. The honest summary of the reorder is therefore: **it saved two of three weight
layers on this rebuild, about 186 seconds of download, and the claim that a source-only
rebuild reuses the weights holds for two layers and did not hold for the third.** A third
build would show whether layer 13 now caches; it was not run, because the operator asked for
one rebuild.

## The rebuild, as it ran

```
docker build --progress=plain --build-arg BAKE_WEIGHTS=true -t shimmer:baked .
```

Started 20:30:55, image tagged about fourteen minutes later. Layers 1 to 12 cached or
instant, layer 13 re-fetched in 165.7 s, the source layers (14 to 21) in under two seconds
combined, and the export of the 31.9 GB image took 365.1 s, which dominates a source-only
rebuild.

New image: `shimmer:baked` `e00f0c4e6a5d` (the previous was `06c18f74b356`).

## The new source is inside, proved rather than assumed

Run with `--network none`, no volume:

```
new modules: {'ontology_reader.py': True, 'relation_extract.py': True,
              'ontology_conflicts.py': True, 'ontology_candidates.py': True}
relation config: True
CHECKS in image: 214
```

All four ontology modules, the operator-declared relation pattern config, and a gate that
knows about the four checks added after the last image. That is the point of the rebuild.

## The offline gate inside it, network blocked, nothing mounted

```
docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<sha256 of a throwaway> shimmer:baked verify
```

```
PASS=208  WARN=0  SKIP=2  FAIL/ERROR=4  TOTAL=214     (about 346 s, image e00f0c4e6a5d, nothing mounted)
```

The four failures are the documented source-only ones (01 directory structure, 28 and 31 for
the absent `input/`, 145 for the absent `tests/` fixtures); the two skips are the network
checks (15, 38) that `--offline` skips. **All four ontology checks passed inside the
container**: 210 (the store's reader), 211 (the deterministic relation baseline), 212 (the
conflict memory) and 213 (the GNN candidate finder), which is what this rebuild existed to
establish.

## Against the last one

| | previous baked image (18:45) | this rebuild (20:48) |
|---|---|---|
| image | `06c18f74b356` | `e00f0c4e6a5d` |
| gate total | 210 | 214 |
| PASS | 204 | 208 |
| SKIP | 2 | 2 |
| FAIL/ERROR | 4 | 4 |
| duration | about 510 s | about 346 s |

**The four extra passes are the four ontology checks**, which did not exist when the previous
image was built. The failure set and the skip set are byte-identical in membership: the same
four source-only failures and the same two network skips. Nothing regressed, and nothing that
failed before passes now for the wrong reason.

The run was faster than the previous baked gate (346 s against 510 s). That is not a claim
about the new code: gate durations on this machine vary with what else holds the card and
with page cache state, and the previous figure was itself measured on a machine that had just
finished a 31.9 GB image export. The two numbers are recorded, not explained.

---

STEP BAKED REBUILD COMPLETE (image `shimmer:baked` `e00f0c4e6a5d` rebuilt on the current
tree with the four ontology commits and the 214-check gate inside it; the offline gate with
the network blocked and nothing mounted gives PASS=208 SKIP=2 FAIL/ERROR=4 of 214, the same
four source-only failures and two network skips as before, the four extra passes being checks
210 to 213; the layer reorder saved two of three weight layers and the third re-downloaded,
recorded as observed and not explained; the review itself remains unmeasured)
