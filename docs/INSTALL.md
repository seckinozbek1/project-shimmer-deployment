# Installing Shimmer

How to install Shimmer, and what a run needs in hardware and costs. This text was moved
from the README on 19 November 2026 (D-816); the short [README](../README.md) links here.
The first review after installing is in the [quickstart](USER_GUIDE.md#11-quickstart).

## Install

A short guide from install to reading a finding is in [English](GUIDE_EN.md) and
[Turkish](GUIDE_TR.md); the [operator guide](USER_GUIDE.md) covers each task, the console views and
the cloud mode. `tools/clean_install_check.py` checks a clean install with no model,
GPU or provider key.

Shimmer needs Python 3.12 (3.12.x; the sealed cloud profile pins 3.12.3, see
[tools/cloud_run/runtime.json](../tools/cloud_run/runtime.json)) and the packages in
[requirements.txt](../requirements.txt). The local backend also needs the configured
Qwen and Phi model files in the model cache, and a CUDA runtime. The bge-m3
embedding model is fetched from the network on first use when it is not cached.
The desktop starter installs nothing. The menu launchers install packages but not
the review models; their readiness check fetches the redactor's Qwen weights only
when `SHIMMER_QWEN_PULL=1` is set. The manual Windows steps below were run on a
fresh clone on 1 November 2026 (Windows 11, an 8 GB NVIDIA card): the packages
installed and torch saw CUDA after the third step. They are run again, with the
full gate, on a new fresh clone of the tree that carries this page; that result
is recorded in the loop's S10 report, not here.

**Manual install (Windows).** These are the steps `shimmer.bat` runs, from the
repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
# only on a machine with an NVIDIA GPU, when torch reports no CUDA:
.venv\Scripts\python.exe -m pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

On Linux or macOS, use `python3.12 -m venv .venv` and `.venv/bin/python` in the
same commands.

**Windows, menu launcher.** `shimmer.bat` creates `.venv`, checks that its Python
matches the runtime contract, runs `pip install -r requirements.txt`, installs the
CUDA build of torch when `nvidia-smi` finds a GPU and torch has no CUDA, asks for
the backend, runs the readiness check and shows a menu (review, chat, server,
gate, import). `SHIMMER_SKIP_INSTALL=1` skips the install and the torch step.

**Linux and macOS shell.** `./shimmer.sh` does the same as `shimmer.bat`, and in
Git Bash on Windows it uses an existing Windows `.venv` (`.venv/Scripts`).

**Windows, desktop console.** From the checkout, once the packages are installed:

```powershell
.\start_shimmer.bat
```

It finds a compatible Python (`tools/resolve_python.bat`), checks prerequisites,
starts the local server and opens the console in the browser. Use **Copy access
token** to connect the browser. Keep the starter window open and use **Stop
Shimmer** to stop the server; closing the browser leaves the server running.

**Container.** The [Dockerfile](../Dockerfile) builds an image with an external model
cache (the default), or with the weights baked in (`--build-arg BAKE_WEIGHTS=true`).
The entry point ([tools/entrypoint.sh](../tools/entrypoint.sh)) takes `serve` (the
server, on port 8000), `run` (one review, through `tools/run_local_demo.py`) or
`verify` (the gate with `--offline`, the default when no command is given). The
server refuses to start without `SHIMMER_TOKEN_HASH`, the SHA-256 hash of an
access token, and one of the gate's checks needs it too; `python scripts/server.py`
with no hash set prints a one-line command that makes a token and its hash. From the repository root:

```powershell
docker build -t shimmer:local .
# the offline gate: no network, nothing mounted
docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<hash> shimmer:local verify
# the server, with the host's model cache mounted where the image looks for it
docker run --rm --gpus all -p 8000:8000 -e SHIMMER_TOKEN_HASH=<hash> -v <host model cache>:/root/.cache/huggingface shimmer:local serve
```

These commands come from the Dockerfile and the entry point; none of them has been
run in the loop that prepared v1, because the image build is waiting for disk
space (the last image build and offline gate were on 11 September 2026, on older
code). Without the weights baked in or a cache mounted, the checks that load a
model fail for lack of weights. [compose.yaml](../compose.yaml) records the server and
review services with every mount (`input/`, `config/`, `durable/`,
`ontology/stores/`, `output/runs/` and the model cache, `HOST_HF_CACHE`); it runs
the image named `shimmer:local` and does not build it.

**Provider keys** (only for the cloud backend, Draft under Cloud included) live
outside the repository. Shimmer looks for them through `$SHIMMER_CONFIG_PATH`, then a sibling
`../api_keys/config.py`, then the path named in a repository-root `.env_path`
file. Never put a key in the repository.

## Hardware and cost

These are measured figures, not estimates, except the laptop line, which is the
operator's recorded observation.

- **Rented GPU.** Every measured Shimmer run so far used one NVIDIA A10 (24 GB) instance in
  us-east-1 at 1.29 USD an hour, read from the provider at each launch.
- **GPU memory.** An earlier ordinary run (v12, September 2026) peaked at 11.96 GB
  of 24 GB (`docs/fix/ORDINARY_FINAL_V12_RUN_RESULTS.md`). A bare-model run on a
  full-length financial filing peaked at 18.6 GiB (base) and 20.9 GiB (tuned)
  allocated (launch L4b, decision D-077 in `docs/loop/DECISIONS.md`). A replay of
  auditor prompts peaked at 21.89 GB allocated (D-132, D-134). In one launch (L8),
  ten VERIFIER prompts of 44,467 to 54,657 tokens ran out of GPU memory on the A10
  before their first token; the prompt shown to VERIFIER was made smaller after
  that (D-114).
- **Time per document.** From 4.4 minutes (the mean of three SciTab tables) to
  109.2 minutes (the one CUAD contract) for Shimmer, and 0.9 to 13.4 minutes for
  the bare model, on the instance, model loading included. See the
  [summary table](RESULTS.md#summary-development-exposed); each figure's run is on
  the results page.
- **Cost.** Instance time only, at the rate above: for example 2.73 USD for the two
  ContractNLI agreements and 4.57 USD for the 20 suite bundles. Each launch also
  spent about 15 minutes on setup, and each entry about 2 minutes. The loop's
  spending record is [docs/loop/BUDGET.md](loop/BUDGET.md).
- **Laptop.** The project's standing rule (in [CLAUDE.md](../CLAUDE.md)) records that
  on the development laptop (an 8 GB GPU) a single local run cost one to three
  hours and the machine paged memory at 15 GB of RAM. No run artifact backs those
  two figures. Full runs therefore go to a rented GPU.
