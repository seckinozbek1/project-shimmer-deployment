# BAKED REBUILD 2: the image on the console-audit tree

**The review itself remains unmeasured.** This step measures the image and the gate inside
it. No pipeline run was started and no language model was loaded.

## The rebuild

Two console commits landed after the last image (`60764ac` and `f619dfc`), so it was stale.
Rebuilt on the current tree: `shimmer:baked` `537feeea8fe6`, replacing `e00f0c4e6a5d`.

Proved from inside, network blocked and nothing mounted, that the new work is actually there:
`scripts/ontology_gnn_state.py` present, and `console.html` carrying `citationsHtml`,
`ontologyRelationsHtml`, `ontologyConflictsHtml`, `ontologyCandidatesHtml`,
`wireProvisionLinks` and the pairing map's new view-aware signature. `CHECKS: 215` inside the
image.

## The weight-layer cache miss, reproduced

The previous rebuild found that the layer reorder saved two of three weight layers and the
Qwen layer re-downloaded, with the cause not established. It happened again, and the timing
is near identical:

| layer | checkpoint | rebuild 2 | rebuild 3 (this one) |
|---|---|---|---|
| 11 | `BAAI/bge-m3` | CACHED | CACHED |
| 12 | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | CACHED | CACHED |
| 13 | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | 165.7 s, re-fetched | 165.5 s, re-fetched |

So it is **systematic, not a one-off**. What I ruled out this time, each by direct check:

- The three `RUN` blocks are structurally identical. Normalising away the model id and the
  echo strings, all three hash the same, so it is not a Dockerfile difference.
- A cache entry for the Qwen layer **does** exist (5.564 GB), and its properties match the
  other two: not mutable, not shared.
- No prune happened between builds.

The cause is still not established, and I am recording that rather than inventing one. The
honest statement stands: **the reorder saves two of the three weight layers, and the third
re-downloads on every source-only rebuild**, costing about 165 s. The claim that a
source-only rebuild reuses all three weights is wrong and should not be made.

## The offline gate inside it, network blocked, nothing mounted

```
docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<sha256 of a throwaway> shimmer:baked verify
```

```
PASS=209  WARN=0  SKIP=2  FAIL/ERROR=4  TOTAL=215     (about 370 s, image 537feeea8fe6)
```

The four failures are the documented source-only ones (01, 28, 31, 145); the two skips are
the network checks (15, 38) that `--offline` skips. **Check 214 passed inside the container**,
which is what this rebuild existed to establish: the console's new routes and sections are
exercised against the real FastAPI app inside an image with no network and nothing mounted.

## Against the last one

| | previous baked image | this rebuild |
|---|---|---|
| image | `e00f0c4e6a5d` | `537feeea8fe6` |
| gate total | 214 | 215 |
| PASS | 208 | 209 |
| SKIP | 2 | 2 |
| FAIL/ERROR | 4 | 4 |
| duration | about 346 s | about 370 s |

One extra pass, which is check 214. The failure and skip sets are identical in membership.
Nothing regressed.

---

BAKED REBUILD 2 COMPLETE (image `537feeea8fe6` on the console-audit tree, the new console work
verified present inside it, the offline gate with nothing mounted giving PASS=209 SKIP=2
FAIL/ERROR=4 of 215 with check 214 among the passes; the Qwen weight-layer cache miss
reproduced and three explanations ruled out, cause still unestablished and recorded as such;
the review itself remains unmeasured)
