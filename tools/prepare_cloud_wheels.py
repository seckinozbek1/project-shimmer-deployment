"""Acquire/build the exact Linux runtime on the operator machine, never a GPU node.

Public package downloads are explicit (--download). No credentials or provider APIs
are used. langdetect's pure-Python wheel is built locally; everything else must have
a compatible published wheel. No version substitutions are permitted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from cloud_run_common import write_json
from prepare_cloud_run import ASSETS, pins, validate_wheels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/cloud_wheels/linux_cp312'))
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args(argv)
    locked = pins(ASSETS / 'runtime.lock')
    if not args.download:
        print(json.dumps({'download_started': False, 'packages': len(locked), 'output': str(args.output),
                          'instruction': 'Run with --download on the local operator machine before provisioning.'}))
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith('PIP_') and
           not any(term in k.upper() for term in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))}
    env['PIP_CONFIG_FILE'] = os.devnull
    steps = []
    # Keep public package error messages in memory only; retain exit codes/names.
    with tempfile.TemporaryDirectory(prefix='shimmer-wheels-') as tmp:
        requirements = Path(tmp) / 'download.lock'
        requirements.write_text(''.join(f'{name}=={version}\n' for name, version in sorted(locked.items()) if name != 'langdetect'))
        command = [sys.executable, '-m', 'pip', '--disable-pip-version-check', 'download', '--no-cache-dir',
                   '--no-deps', '--only-binary=:all:', '--python-version', '312', '--implementation', 'cp',
                   '--abi', 'cp312', '--abi', 'abi3', '--abi', 'none', '--index-url', 'https://pypi.org/simple',
                   '--extra-index-url', 'https://download.pytorch.org/whl/cu121', '--dest', str(args.output.resolve()),
                   '-r', str(requirements)]
        for platform in ['manylinux_2_35_x86_64', 'manylinux_2_34_x86_64', 'manylinux_2_31_x86_64',
                         'manylinux_2_28_x86_64', 'manylinux_2_27_x86_64', 'manylinux_2_24_x86_64',
                         'manylinux_2_17_x86_64', 'manylinux2014_x86_64', 'manylinux2010_x86_64',
                         'manylinux1_x86_64', 'linux_x86_64']:
            command += ['--platform', platform]
        result = subprocess.run(command, env=env, capture_output=True)
        steps.append({'step': 'download_exact_linux_wheels', 'exit_code': result.returncode})
        if result.returncode:
            # Classify failures without retaining index URLs or arbitrary error text.
            messages = result.stderr.decode(errors='replace')
            import re
            missing = re.findall(r'No matching distribution found for ([A-Za-z0-9_.+-]+==[A-Za-z0-9_.+-]+)', messages)
            error_types = sorted(set(re.findall(r'^([A-Za-z]+(?:Error|Exception)):', messages, flags=re.M)))
            write_json(args.output / 'WHEEL_PREPARATION.json', {'ready': False, 'steps': steps, 'unavailable_exact_pins': missing,
                       'network_failure': 'Connection' in messages or 'ProxyError' in messages, 'error_types': error_types})
            print(json.dumps({'ready': False, 'steps': steps, 'unavailable_exact_pins': missing, 'error_types': error_types}))
            return 2
        result = subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check', 'wheel',
                    '--no-deps', '--no-build-isolation', '--no-cache-dir', '--index-url', 'https://pypi.org/simple',
                    '--wheel-dir', str(args.output.resolve()), 'langdetect==' + locked['langdetect']], env=env, capture_output=True)
        steps.append({'step': 'build_pure_python_langdetect_locally', 'exit_code': result.returncode})
        if result.returncode:
            write_json(args.output / 'WHEEL_PREPARATION.json', {'ready': False, 'steps': steps})
            print(json.dumps({'ready': False, 'steps': steps}))
            return 2
    try:
        wheels = validate_wheels(args.output, locked)
    except Exception as exc:
        write_json(args.output / 'WHEEL_PREPARATION.json', {'ready': False, 'steps': steps, 'validation_error_type': type(exc).__name__})
        print(json.dumps({'ready': False, 'validation_error_type': type(exc).__name__}))
        return 2
    write_json(args.output / 'WHEEL_PREPARATION.json', {'ready': True, 'steps': steps, 'wheels': wheels})
    print(json.dumps({'ready': True, 'wheels': len(wheels)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
