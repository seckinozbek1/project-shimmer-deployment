"""Optional future out-of-process resource sampler. Never imports Torch/PEFT.

Only --cpu-only is used by local effect tests. No generation-thread callbacks.
CUDA allocated/reserved/high-water counters belong in caller boundary events.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time


def run(pid, output, stop_file, cpu_only=False):
    import psutil
    process = psutil.Process(pid)
    with Path(output).open('x', encoding='utf8') as stream:
        while not Path(stop_file).exists() and process.is_running():
            try:
                sample = dict(epoch=time.time(), rss=process.memory_info().rss,
                              cpu_percent=process.cpu_percent(), host_ram_used=psutil.virtual_memory().used)
                if not cpu_only:
                    value = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
                    sample['gpu'] = value.stdout.strip() if value.returncode == 0 else None
                stream.write(json.dumps(sample) + '\n')
                stream.flush()
            except (OSError, psutil.Error):
                break
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--cpu-only', action='store_true')
    args = parser.parse_args()
    run(args.pid, args.output, args.stop_file, args.cpu_only)
