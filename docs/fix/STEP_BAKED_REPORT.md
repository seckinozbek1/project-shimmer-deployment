# STEP BAKED REPORT: the baked image built here, with the weights inside

**Built without measurement of the review itself. What this step measured is the image:
that it builds on this machine through the Docker Desktop proxy, that the three checkpoints
are inside it and resolve with no network and no mount, and how the gate behaves inside it
with nothing mounted. Whether the review those weights serve is correct is not known until a
run scores it; the last scored run predates every change of 10 and 11 September.**

## Why now

The operator's instruction: build the image here, baked, with the weights inside; the VM is
not happening yet, so nothing is deferred to it. The previous baked image (`5ccafc767222`,
built 40 hours earlier at the docker branch's own commit) carried none of the fixes of 10 and
11 September, and the STEP DOCKER report had left it unbuilt because its weight layers sat
after the source layers, so every source change re-downloaded the three checkpoints through
a proxy that had already dropped TLS on them twice.

## One change to the Dockerfile: the weights before the source

A layer's cache key is its parent chain. With stage 4 (the weights) after stage 2 (the
source), every edit under `scripts/` invalidated the three download layers. The stage order
is now: base environment, weights (behind `BAKE_WEIGHTS`), source, entry point. The three
`RUN` blocks, the `ARG` and the `HF_HOME` `ENV` moved up unchanged; the header comment
records why. A source-only rebuild of the baked image now reuses the weight layers and
copies the new source on top of them; the unbaked build is unaffected (its three `RUN`
lines are shell no-ops in either position). This build could not benefit from the reorder
itself, because `requirements.txt` changed at `a3c666f` (the `accelerate` pin), which sits
below the weights in either order; the next source-only rebuild will.

## The build, as it ran

```
docker build --progress=plain --build-arg BAKE_WEIGHTS=true -t shimmer:baked .
```

Started 18:30:50 local, detached (`Start-Process`, stderr to
`output/docker_build_baked.log`). Layers 1 to 10 cached (base, apt, torch, requirements).
The three downloads, each through the proxy, each with the five-attempt loop:

| layer | checkpoint | time | size in the image |
|---|---|---|---|
| 11 | `BAAI/bge-m3` (30 files, including the onnx and sparse variants the snapshot carries) | 103.6 s | 4.58 GB |
| 12 | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | 82.9 s | 2.27 GB |
| 13 | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | 160.2 s | 5.56 GB |

The proxy produced its usual per-file retries (`MaxRetryError` on a handful of small files,
each recovered by huggingface_hub's own retry inside one `snapshot_download`); no attempt
of the outer loop failed, so no layer was retried whole. Source layers copied in under a
second each; the image was exported and tagged `shimmer:baked` (`06c18f74b356`) about
fifteen minutes after the start.

A note on the log filter: the Dockerfile's own `RUN` text is echoed into the build log and
contains the words "download failed after 5 attempts", so a monitor that greps the log for
the failure message fires the moment the layer starts. The second monitor excluded lines
containing `echo`.

## The weights are inside: proved, not assumed

Run with `--network none`, no volume, no GPU, the entry point overridden to `python`:

```
HF_HOME /root/.cache/huggingface
hub dirs: ['.locks', 'models--BAAI--bge-m3', 'models--unsloth--Phi-3.5-mini-instruct-bnb-4bit',
           'models--unsloth--Qwen2.5-7B-Instruct-bnb-4bit']
BAAI/bge-m3                              local_files_only OK  4.59 GB
unsloth/Phi-3.5-mini-instruct-bnb-4bit   local_files_only OK  2.27 GB
unsloth/Qwen2.5-7B-Instruct-bnb-4bit     local_files_only OK  5.56 GB
```

`snapshot_download(..., local_files_only=True)` resolved each of the three ids to a snapshot
directory inside the image, which is the same lookup the real loader makes.

## Size, stated both ways because Docker states it both ways

`docker images` prints two figures per image: `shimmer:baked` 31.9 GB disk usage and 13.1 GB
content size, `shimmer:local` (unbaked) 9.73 GB and 3.26 GB; `docker image inspect` reports
the content size, 13.05 GB and 3.26 GB. The per-layer history sums to about 18.9 GB
uncompressed (torch 5.17 GB, the three weight layers 12.41 GB, apt 269 MB, requirements
773 MB, source under 6 MB). The 31.9 GB the old baked image was quoted at in the STEP DOCKER
report is that same disk-usage column, which the rebuilt image also reports; there is no
unexplained difference between the two images.
The build cache holds 21.5 GB, of which 20.7 GB
is reclaimable; nothing was pruned, that being the operator's disk to decide about.

## The offline gate inside the baked image, nothing mounted

```
docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<sha256 of a throwaway> shimmer:baked verify
```

This is the first gate run where the container had no host cache at all: the unbaked run of
`a3c666f` mounted the host's cache, so it proved the loader and not the bake. The result and
its comparison with that run are in the section below.

## Gate result

```
PASS=204  WARN=0  SKIP=2  FAIL/ERROR=4  TOTAL=210     (about 510 s, image 06c18f74b356, nothing mounted)
```

`output/docker_baked_verify.log`. The four failures are 01, 28, 31 and 145, the documented
source-only ones (no `input/`, `output/`, `durable/`, `prompts/`, `snapshots/` or `tests/`
in the image); the two skips are 15 and 38, the network checks `--offline` skips. Check
193 (the real local loader with the network blocked at the socket) passed against the baked
weights, and check 197 passed with its corpus site named absent. The line is identical to
the mounted run of `a3c666f` (PASS=204 SKIP=2 FAIL/ERROR=4), which is the point: the image
now stands on its own weights. It also ran in roughly 510 s against that run's 873 s, the
difference being that the weights are read from the image's own layers rather than through
the Windows filesystem mount. The stderr carries the same hundred or so `MaxRetryError`
lines as the mounted run (sentence-transformers asking the hub for `modules.json` and its
neighbours under `--network none`, then using the cache), 66 here against 96 there; they are
noise, not failures, and the run that emitted them passed.

## What the baked image is not

- It has not run a review. "The review runs offline in the container" is not claimed; the
  gate does, and the weights resolve.
- It carries the source of this working copy at build time, which includes the README and
  Dockerfile edits of this step but not this report (docs/ is not copied).
- It was built through the development machine's proxy; a rented machine's build would go
  direct and the retry loops would simply not fire.

---

STEP BAKED COMPLETE (image `shimmer:baked` `06c18f74b356` built here with the three
checkpoints inside, each resolving with no network and no mount; the offline gate inside it
with nothing mounted gives PASS=204 SKIP=2 FAIL/ERROR=4 of 210, the documented four and two;
the Dockerfile's weight layers now precede the source; the review itself remains unmeasured)
