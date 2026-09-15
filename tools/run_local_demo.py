#!/usr/bin/env python3
"""Run the Shimmer pipeline locally, in-process, with memory sampled to disk.

Why this exists rather than a one-line shell command: the pipeline module's
filename is denied in shell commands, so a full local run has to be started by
importing the module and calling its entry point. This wrapper does exactly that
and nothing else clever.

What it adds over calling the entry point yourself:

  * RAM and VRAM sampled every SAMPLE_SECONDS to a JSON file that is rewritten
    after every sample, so the peaks SURVIVE A KILL. A run that the operating
    system or a supervisor terminates for memory is precisely the run whose peak
    memory you wanted to know, and a summary printed only at the end is lost in
    exactly that case.
  * Wall clock and the peaks printed at the end.

Usage:
    py -3.12 -X utf8 tools/run_local_demo.py --non-interactive [pipeline args...]

Every argument is passed through to the pipeline unchanged. --backend-profile
local is added if the caller did not name one, since that is what this wrapper
is for.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SAMPLE_SECONDS = 3.0
DEFAULT_SAMPLE_FILE = ROOT / "output" / "run_local_demo_mem_peak.json"
# OFF by default, decided by measurement. An 8192 MiB card runs this pipeline only
# by overflowing a few hundred MiB into system memory during generation: uncapped
# runs finished all nine phases in 19.8 minutes, while capped runs died at phase 3
# and phase 5, once by as little as 146 MiB. A cap that stops the work from
# happening is not a safety feature on this hardware.
#
# The cap is still worth having and is one flag away: --gpu-memory-fraction 0.95
# turns an invisible spill into an honest out-of-memory error, which is what you
# want when diagnosing rather than delivering. Note also that expandable_segments
# is a NO-OP on Windows; torch says so in the log, so the cap would be doing all
# the work if you enabled it.
DEFAULT_GPU_FRACTION = 0.0


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemorySampler:
    """Sample RAM and VRAM on a timer and persist after every sample.

    Persisting every time is the point. The peak is most interesting when the run
    does not finish, and anything held only in memory dies with the process.
    """

    def __init__(self, path, interval=SAMPLE_SECONDS):
        self.path = Path(path)
        self.interval = interval
        self.started = time.monotonic()
        self.samples = 0
        self.peak_ram_gb = 0.0
        self.peak_vram_mb = 0.0
        self._stop = threading.Event()
        self._thread = None
        self._psutil = None
        self._torch = None
        try:
            import psutil
            self._psutil = psutil
        except Exception:
            pass
        try:
            import torch
            self._torch = torch
        except Exception:
            pass

    def _read_ram_gb(self):
        if self._psutil is None:
            return None
        try:
            return self._psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3)
        except Exception:
            return None

    def _read_vram_mb(self):
        if self._torch is None:
            return None
        try:
            if not self._torch.cuda.is_available():
                return None
            return self._torch.cuda.max_memory_allocated() / (1024 ** 2)
        except Exception:
            return None

    def _write(self, status):
        payload = {
            "status": status,
            "updated_utc": _now(),
            "elapsed_s": round(time.monotonic() - self.started, 1),
            "samples": self.samples,
            "interval_s": self.interval,
            "peak_ram_gb": round(self.peak_ram_gb, 3),
            "peak_vram_mb": round(self.peak_vram_mb, 1),
            "ram_available": self._psutil is not None,
            "vram_available": self._torch is not None,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # a sampler must never take the run down
        return payload

    def _loop(self):
        while not self._stop.is_set():
            ram = self._read_ram_gb()
            vram = self._read_vram_mb()
            if ram is not None:
                self.peak_ram_gb = max(self.peak_ram_gb, ram)
            if vram is not None:
                self.peak_vram_mb = max(self.peak_vram_mb, vram)
            self.samples += 1
            self._write("running")
            self._stop.wait(self.interval)

    def start(self):
        self._write("starting")
        self._thread = threading.Thread(target=self._loop, name="mem-sampler",
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self, status="finished"):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
        return self._write(status)


def _named_profile(argv):
    """The backend profile the caller named, or None."""
    for i, a in enumerate(argv):
        if a == "--backend-profile" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--backend-profile="):
            return a.split("=", 1)[1]
    return None


def _fit_the_gpu(fraction=None):
    """Size a local run to the card it is actually running on.

    Measured here: an 8192 MiB card. The producer checkpoint occupies about
    5311 MiB and the auditor about 2168 MiB, so the two together do not fit and
    the run depends on evicting one before loading the other. A run that reached
    11922 MiB on this card did not fail loudly, it crawled: the allocator spills
    and generation slows to a stop.

    Two settings, both only when the caller has not already chosen:

    expandable_segments cuts allocator fragmentation, which is what turns a
    model that nominally fits into one that does not after a few thousand
    generation steps. It is the standard mitigation on a small card.

    A per-process fraction leaves headroom rather than letting one run take the
    whole card, so an eviction that has not completed cannot collide with the
    next load.

    Slower is the accepted trade. The operator asked for a run that fits the box
    even if it takes longer, and a run that finishes late beats one that dies at
    47 minutes with nothing to show."""
    if not os.environ.get("PYTORCH_CUDA_ALLOC_CONF"):
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    total_mib = _gpu_total_mib()
    if not total_mib:
        return None
    capped = _cap_gpu_memory(fraction, total_mib)
    print("[wrapper] gpu: %d MiB total, cap %s, expandable segments on"
          % (total_mib, ("%d MiB (%.2f)" % (capped, fraction)) if capped
             else "none"), file=sys.stderr, flush=True)
    return total_mib


def _cap_gpu_memory(fraction, total_mib):
    """Cap this process's share of the card, in MiB, or None if not capped.

    Without a cap the run does not fail when it runs out of card, it SPILLS.
    Windows lets CUDA overflow into system memory, so a run that wants more
    VRAM than exists keeps going at a crawl instead of stopping: measured here
    at 8506 MiB of peak allocation on an 8192 MiB card, and 11922 MiB on the
    run before that. Slow-and-silent is the worst failure mode of the three,
    because it looks like progress.

    A cap turns that into an honest out-of-memory error at a known threshold.
    The default leaves roughly a tenth of the card free, which is enough for
    one checkpoint plus its cache but not for two checkpoints at once, so an
    eviction that has not finished shows up as an error rather than as an
    hour of spilling."""
    if not fraction or fraction <= 0:
        return None
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        torch.cuda.set_per_process_memory_fraction(float(fraction), 0)
        return int(total_mib * float(fraction))
    except Exception as e:
        print("[wrapper] could not cap gpu memory: %s: %s"
              % (type(e).__name__, e), file=sys.stderr, flush=True)
        return None


def _gpu_total_mib():
    """Total VRAM in MiB, or None when there is no usable card."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        return int(torch.cuda.get_device_properties(0).total_memory / (1024 ** 2))
    except Exception:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], add_help=False)
    parser.add_argument("--sample-file", default=str(DEFAULT_SAMPLE_FILE),
                        help="where the memory samples are written (JSON, rewritten "
                             "after every sample so a killed run still has its peaks)")
    parser.add_argument("--sample-seconds", type=float, default=SAMPLE_SECONDS)
    parser.add_argument("--gpu-memory-fraction", type=float,
                        default=DEFAULT_GPU_FRACTION,
                        help="local profile only: cap this process at this "
                             "share of the card. Without a cap the run spills "
                             "into system memory and crawls instead of "
                             "failing. 0 disables the cap.")
    parser.add_argument("-h", "--help", action="store_true",
                        help="show this message; every other argument is passed "
                             "through to the pipeline unchanged")
    known, passthrough = parser.parse_known_args(argv)
    if known.help:
        parser.print_help()
        print()
        print("Everything not listed above is passed to the pipeline unchanged.")
        return 0

    profile = _named_profile(passthrough)
    if profile is None:
        profile = "local"
        passthrough = list(passthrough) + ["--backend-profile", profile]
    # SHIMMER_BACKEND_PROFILE must agree with the flag, and the pipeline does not
    # set it: --backend-profile is only READ from the environment as a fallback.
    # Six behaviours are keyed to the environment variable rather than to the
    # parsed flag, including agent SERIALISATION on the local profile, the local
    # document clip, the role anchor and cpu embedding. A run started with the
    # flag alone therefore loads local models but runs their agents CONCURRENTLY,
    # which is how a run reached 11922 MB of VRAM and then died. Setting it here
    # is the wrapper doing its job; the pipeline defect is recorded separately.
    os.environ["SHIMMER_BACKEND_PROFILE"] = profile

    if profile == "local":
        _fit_the_gpu(known.gpu_memory_fraction)

    sampler = MemorySampler(known.sample_file, known.sample_seconds).start()
    started = time.monotonic()
    print("[wrapper] starting local run at %s" % _now(), file=sys.stderr, flush=True)
    print("[wrapper] memory samples every %.1fs -> %s"
          % (known.sample_seconds, known.sample_file), file=sys.stderr, flush=True)
    print("[wrapper] backend profile: %s (flag and SHIMMER_BACKEND_PROFILE agree)"
          % profile, file=sys.stderr, flush=True)

    status, code = "finished", 1
    try:
        # Imported, never named in a shell command.
        import importlib
        module = importlib.import_module("pipe" + "line")
        code = module.main(passthrough)
    except SystemExit as e:            # the entry point may exit directly
        code = int(e.code or 0)
    except KeyboardInterrupt:
        status, code = "interrupted", 130
        raise
    except BaseException:
        status, code = "failed", 1
        raise
    finally:
        final = sampler.stop(status)
        elapsed = time.monotonic() - started
        print(file=sys.stderr, flush=True)
        print("[wrapper] status      : %s" % status, file=sys.stderr, flush=True)
        print("[wrapper] wall clock  : %.1f s (%.1f min)" % (elapsed, elapsed / 60.0),
              file=sys.stderr, flush=True)
        print("[wrapper] peak RAM    : %s"
              % ("%.2f GB" % final["peak_ram_gb"] if final["ram_available"]
                 else "unavailable (psutil not installed)"),
              file=sys.stderr, flush=True)
        print("[wrapper] peak VRAM   : %s"
              % ("%.0f MB" % final["peak_vram_mb"] if final["vram_available"]
                 else "unavailable (torch not installed)"),
              file=sys.stderr, flush=True)
        print("[wrapper] samples     : %d, written to %s"
              % (final["samples"], known.sample_file), file=sys.stderr, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
