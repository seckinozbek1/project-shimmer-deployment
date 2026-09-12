# Built in stages, proven before the next is written.
# Stage 1 (below): base environment. Python, CUDA-enabled torch, and the rest
# of requirements.txt install cleanly on top of a CUDA runtime image.
# Stage 2 (further down): the model weights, behind --build-arg BAKE_WEIGHTS=true;
# false (the default) leaves them to a mounted volume at run time. This stage
# sits BEFORE the source stage on purpose (2026-09-11): a layer's cache key is
# its parent chain, so with the weights last every edit under scripts/ threw
# the three downloaded checkpoints away and pulled them again through the
# Docker Desktop proxy that has already dropped TLS on them twice. With the
# weights before the source, a source-only rebuild of the baked image reuses
# the weight layers and copies the new source on top of them.
# Stage 3 (further down still): source copied (scripts/, config/, tools/,
# corpus_ingest/, the three root markdown files), import path set.
# Stage 4 (last): the entry point (tools/entrypoint.sh),
# serve/run/verify, verify by default.

FROM nvidia/cuda:12.1.1-base-ubuntu22.04

# py -3.9 is the interpreter this project pins to (CLAUDE.md, requirements.txt).
# deadsnakes carries 3.9 for 22.04 (jammy), which Ubuntu's own repos do not.
# DEBIAN_FRONTEND=noninteractive + TZ so tzdata (a transitive dep here) never
# blocks the build on a timezone prompt; ENV, not a one-off RUN prefix, so it
# holds for every apt-get in this and later stages.
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.9 \
        python3.9-distutils \
        python3.9-tk \
        python3-pip \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Make `python3.9` the interpreter pip and later stages call as `python`.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1

# torch pinned to the CUDA 12.1 wheel explicitly, from PyTorch's own index: the
# default PyPI index resolves torch==2.5.1 to a CPU-only build on a base image
# with no torch already present, which would silently defeat --gpus all.
RUN python -m pip install --no-cache-dir \
        torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

# Stage 2: the model weights, two build modes behind one build argument.
#
#   docker build .                          -> BAKE_WEIGHTS=false (default):
#     small, fast dev build; weights are NOT downloaded; the image expects
#     them to arrive through a mounted volume at run time.
#   docker build --build-arg BAKE_WEIGHTS=true .
#     -> the three models are downloaded into the image, one RUN per model,
#     so a rented server's cold start never pulls several gigabytes.
#
# HF_HOME fixes the cache directory the huggingface/sentence-transformers
# libraries resolve to (neither embedding_store.py nor agent_wrapper.py passes
# a cache_dir of its own, so both read this same default). Setting it
# explicitly, rather than leaving it to default to $HOME, means the BAKE
# downloads below and an unbaked run's mounted volume are guaranteed to be
# the same path: `-v <host-cache>:/root/.cache/huggingface` at `docker run`
# time lands exactly where a baked image already has the weights, so the
# same check_local_model_availability() lookup succeeds either way.
ARG BAKE_WEIGHTS=false
ENV HF_HOME=/root/.cache/huggingface

# One layer per model, ordered least-frequently-changed first: the embedding
# model (shared across every domain, effectively fixed), then the auditor,
# then the producer, which config/local_models.json's own "why" field already
# documents as the one most likely to be swapped for a different checkpoint.
# Changing the producer id invalidates only this last layer; the embedding
# and auditor downloads are untouched and are not re-fetched. Each RUN is a
# no-op cache-hit under BAKE_WEIGHTS=false (huggingface_hub.snapshot_download
# is skipped entirely by the shell conditional, not merely made to fail
# fast), so the unbaked build pays nothing for these three lines beyond the
# constant cost of starting a shell.
#
# Retried up to 5 times with a growing pause: measured live, downloading
# through Docker Desktop's own HTTP(S) proxy (docker info: HTTP/HTTPS Proxy
# http.docker.internal:3128) produced repeated
# SSLZeroReturnError("TLS/SSL connection has been closed (EOF)") talking to
# huggingface.co, on both the first metadata request and mid-download,
# on two consecutive attempts. huggingface_hub already retries within one
# snapshot_download call for a partial download; this retries the WHOLE
# call, which is what a connection that dies before the first byte needs.
RUN if [ "$BAKE_WEIGHTS" = "true" ]; then \
        ok=0; \
        for i in 1 2 3 4 5; do \
            python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-m3')" && { ok=1; break; }; \
            echo "bge-m3 download attempt $i failed, retrying..." >&2; \
            sleep $((i * 5)); \
        done; \
        [ "$ok" = "1" ] || { echo "bge-m3 download failed after 5 attempts" >&2; exit 1; }; \
    fi

RUN if [ "$BAKE_WEIGHTS" = "true" ]; then \
        ok=0; \
        for i in 1 2 3 4 5; do \
            python -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/Phi-3.5-mini-instruct-bnb-4bit')" && { ok=1; break; }; \
            echo "Phi-3.5-mini download attempt $i failed, retrying..." >&2; \
            sleep $((i * 5)); \
        done; \
        [ "$ok" = "1" ] || { echo "Phi-3.5-mini download failed after 5 attempts" >&2; exit 1; }; \
    fi

RUN if [ "$BAKE_WEIGHTS" = "true" ]; then \
        ok=0; \
        for i in 1 2 3 4 5; do \
            python -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/Qwen2.5-7B-Instruct-bnb-4bit')" && { ok=1; break; }; \
            echo "Qwen2.5-7B download attempt $i failed, retrying..." >&2; \
            sleep $((i * 5)); \
        done; \
        [ "$ok" = "1" ] || { echo "Qwen2.5-7B download failed after 5 attempts" >&2; exit 1; }; \
    fi

# ZERO-C: a downloaded .bin is not loadable by the pinned runtime torch.
# Prepare safetensors offline using a patched CPU-only reader, then discard that
# build-only installation. Keep this AFTER all downloads so converter edits do
# not invalidate their cache. No model is changed and no inference runs here.
COPY scripts/model_weights.py /tmp/shimmer_model_weights.py
RUN if [ "$BAKE_WEIGHTS" = "true" ]; then \
        python -m pip install --no-cache-dir --no-deps --target /tmp/shimmer_safe_torch \
            torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
        && PYTHONPATH=/tmp/shimmer_safe_torch python /tmp/shimmer_model_weights.py --model BAAI/bge-m3 \
        && rm -rf /tmp/shimmer_safe_torch; \
    fi

# Stage 3: source, on top of the weights. Only the paths named below; no .git, no
# .claude, no benchmark/keys, no virtual environment (none of those exist in
# the build context to begin with, per .dockerignore, but the COPY list below
# is explicit regardless of what .dockerignore does or does not catch).
WORKDIR /app

COPY scripts/ ./scripts/
COPY config/ ./config/
COPY tools/ ./tools/
COPY corpus_ingest/ ./corpus_ingest/
# Declared synthetic inputs used by checks 236, 238 and 239. Their behavior
# must be executable in the product image as well as the source checkout.
COPY benchmark/fixtures/rule_condition_fixture.md benchmark/fixtures/severity_effect_fixture.md benchmark/fixtures/external_rules_fixture.json ./benchmark/fixtures/
COPY README.md CLAUDE.md genesis.md ./
# Also at /app/requirements.txt, not only /tmp: gate check 118 (every
# module-level third-party import under scripts/ is ==pinned) reads it from
# the repo root, same as it would on a real checkout.
COPY requirements.txt ./

# Refuse populated usage-derived stores in the image; never clear host state.
RUN python scripts/ship_gate.py

# pipeline.py and server.py each insert scripts/ and the repo root onto
# sys.path THEMSELVES once they are running (ROOT = parent.parent of their own
# file), but that self-bootstrap only takes effect after Python has already
# located and executed the module. A bare `import pipeline` needs scripts/ on
# PYTHONPATH before that point; the repo root covers corpus_ingest (M1) once
# pipeline's own insert runs. Set here rather than relied on implicitly, since
# earlier work found a bare import fails without it.
ENV PYTHONPATH=/app/scripts:/app

# Stage 4: the entry point. One command decides what the container does
# (serve/run/verify, verify by default); everything else is rejected with a
# message naming the three. tools/entrypoint.sh is already inside the image
# from the `COPY tools/` above; it needs the executable bit, and its line
# endings normalised: a Windows checkout with autocrlf turned the script into
# CRLF, the kernel then looked for an interpreter named "/bin/sh\r" and the
# container failed at start with "no such file or directory" (found at the first
# offline test of the image, 2026-09-11). .gitattributes pins the file to LF as
# well; this line holds for any checkout regardless.
RUN sed -i 's/\r$//' tools/entrypoint.sh && chmod +x tools/entrypoint.sh
ENTRYPOINT ["tools/entrypoint.sh"]
