# STEP DOCKER REPORT: the image rebuilt, and the first offline test inside it

**Built without measurement of the review itself. The image now carries every fix from
10 and 11 September; whether those fixes are correct is not known until a run on the VM
scores them. What this step measured is the container: whether it starts, and whether the
gate passes inside it with no network.**

## Why

The image `shimmer:local` predated every fix of the last two days (built 40 hours before
this step, at the docker branch's own commit). The offline claim, that the gate runs inside
the container with no network, had never been tested.

## What the rebuild found, in order

1. **The container could not start.** `exec tools/entrypoint.sh: no such file or directory`.
   The working copy of `tools/entrypoint.sh` had CRLF line endings (a Windows checkout with
   autocrlf; git's index held LF), so the kernel looked for an interpreter named
   `/bin/sh\r`. Fixed at both ends: `.gitattributes` pins `*.sh` and the entrypoint to LF on
   every checkout, the working copy was converted, and the Dockerfile strips a trailing CR
   before setting the executable bit, so any checkout builds a starting container.
2. **No local model could load inside the image.** With the container started, the network
   blocked and the host's model cache mounted, check 193 (the real local loader never
   reaches the network when cached) failed: `Using a device_map ... requires accelerate`.
   The package was present on the working machine only transitively and was never in
   `requirements.txt`, so a fresh install had no way to place a 4-bit checkpoint on the
   card. `accelerate==1.10.1` is now pinned, with the reason. Any `run` in the container
   would have died at its first local call; that had never been observed because the
   container had never been run.
3. **One gate check depended on a benchmark corpus file the image does not ship.** Check
   197 read `benchmark/corpora/device_log_review/conventions/device_conventions.md` for
   its corpus assertions and for its neutralise-and-restore proof. The image copies
   `scripts/`, `config/`, `tools/` and `corpus_ingest/` only. The corpus assertions now run
   wherever the file exists and are named absent otherwise, and the proof runs on a
   synthetic `[required]` heading every tree has. Nothing the check proved is lost where the
   corpus is present; on the host it still asserts the corpus's eight rules and CONV-D03's
   bracket severity.

## The first offline test, as it ran

`docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<sha256 of a throwaway
token> -v C:\Users\secki\.cache\huggingface:/root/.cache/huggingface shimmer:local verify`
(the entrypoint's `verify` is `verify_session1.py --offline`).

First run, after the entrypoint fix and before 2 and 3:

```
PASS=202  WARN=0  SKIP=2  FAIL/ERROR=6  TOTAL=210     (525 s)
```

The six: 01, 28, 31 and 145, which are the documented source-only failures (the image ships
no `input/`, `output/`, `durable/`, `prompts/`, `snapshots/` or `tests/`; README section L
lists exactly these four for a fresh checkout); 193 (finding 2 above); 197 (finding 3). The
two skips are checks 15 and 38, the two that touch the network, skipped by `--offline` as
documented.

Second run, after the fixes:

```
PASS=204  WARN=0  SKIP=2  FAIL/ERROR=4  TOTAL=210     (873 s, image 96120189c5ec)
```

The four failures are exactly the documented source-only ones (01, 28, 31, 145); the two
skips are 15 and 38 as documented. Check 193 passed with the network blocked at the socket
and the weights read from the mounted cache ("every from_pretrained call in the real loader
carries local_files_only=True and loads successfully with the network genuinely blocked");
check 197 passed with its corpus site named absent. Nothing else in the container's gate
differs from the host's (`output/docker_offline_verify2.log` beside
`output/docker_offline_verify.log` for the first run).

## What the offline claim now rests on

Inside the container, with the network blocked, every check that loads a model loaded it
from the mounted cache, and every check that could pass in a source-only tree passed. The
claim holds for the gate. It has not been tested for a review run inside the container (the
standing rule forbids a run on this machine), so "the review runs offline in the container"
is not claimed here; only "the gate does".

## Not changed, recorded

- The baked image (`shimmer:baked`, 31.9 GB, weights inside) was not rebuilt: its weight
  layers sit after the source layers in the Dockerfile, so a source change re-downloads the
  three checkpoints through the Docker Desktop proxy that has already failed on TLS twice.
  Rebuilding it, or building it on the VM where the download is direct, is the operator's
  call before the move. The unbaked image plus the mounted cache is what compose runs.
- `websockets`, used only by the throwaway `tools/console_preview.py --screenshots`, is not
  in `requirements.txt`; the helper is not part of the product and is not needed in the
  image.
- The image ships neither `benchmark/` nor `input/`; a corpus reaches the container through
  the `./input` mount after `tools/stage_corpus.py` on the host, as before.

## Gate result on the host

```
PASS=208  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=210
```

`output/docker_gate1.log`, run once at this HEAD, after the container's own run finished
(the two must never share the card). No check added; 197 changed and still passes on the
host with its corpus site run; the same two source-only failures (01 and 145).

---

STEP DOCKER COMPLETE (image `shimmer:local` 96120189c5ec rebuilt from the current tree;
three defects found and fixed by the rebuild; the gate passes inside the container with no
network beyond the documented source-only failures and the two documented skips; the review
itself remains unmeasured)
