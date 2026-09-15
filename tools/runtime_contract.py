"""Stdlib-only runtime bootstrap. Safe to start with an older image Python.

Only the queried absolute compatible executable may run repository source.
No provider, model, installation or network operation is implemented here.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.abc
import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


class RuntimeContractError(ValueError):
    pass


def contract_path():
    local = Path(__file__).parent / 'cloud_run/runtime.json'
    return local if local.is_file() else Path(__file__).with_name('runtime.json')


def load_contract(path=None):
    value = json.loads(Path(path or contract_path()).read_text(encoding='utf-8-sig'))
    if value.get('schema_version') != 1:
        raise RuntimeContractError('Unsupported runtime contract schema')
    major, minor = value['python_compatibility']['major'], value['python_compatibility']['minor']
    expected = '>=%d.%d,<%d.%d' % (major, minor, major, minor + 1)
    if (value['python_compatibility']['constraint'] != expected or
            value['python_profiles']['experiment'] != expected or
            value['python_profiles']['sealed_reference'] != '==' + value['python'] or
            tuple(map(int, value['python'].split('.')[:2])) != (major, minor)):
        raise RuntimeContractError('Inconsistent runtime contract')
    return value


def compatible(version, contract=None, profile='experiment'):
    contract = contract or load_contract()
    if profile not in contract['python_profiles']:
        raise RuntimeContractError('Unknown Python runtime profile')
    requirement = contract['python_compatibility']
    if tuple(version[:2]) != (requirement['major'], requirement['minor']):
        return False
    return profile != 'sealed_reference' or tuple(version[:3]) == tuple(map(int, contract['python'].split('.')))


def assert_current(profile='experiment', contract=None):
    contract = contract or load_contract()
    if not compatible(sys.version_info, contract, profile):
        raise RuntimeContractError('Python required %s; observed %s at %s' % (
            contract['python_profiles'][profile], '.'.join(map(str, sys.version_info[:3])), sys.executable))
    return {'executable': os.path.abspath(sys.executable), 'version': list(sys.version_info[:3]), 'profile': profile}


QUERY = "import sys,json,os; print(json.dumps({'version':list(sys.version_info[:3]),'executable':os.path.abspath(sys.executable)}))"


def candidates(contract=None, root=None):
    contract = contract or load_contract()
    version = contract['python_compatibility']
    minor = '%d.%d' % (version['major'], version['minor'])
    values = []
    if root is not None:
        values += [(str(Path(root) / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')),)]
    values += [(sys.executable,)]
    # Inspect every PATH directory, not just the first image-default alias.
    for directory in os.get_exec_path():
        for name in ('python' + minor, 'python3', 'python'):
            path = Path(directory) / (name + '.exe' if os.name == 'nt' else name)
            try:
                if path.is_file():
                    values.append((str(path),))
            except OSError:
                # Windows Store aliases can be present but inaccessible.
                # Keep inspecting real candidates instead of selecting that alias.
                continue
    if os.name == 'nt' and shutil.which('py'):
        values.append((shutil.which('py'), '-' + minor))
    return list(dict.fromkeys(values))


def resolve(candidate_commands=None, *, profile='experiment', contract=None, runner=subprocess.run, root=None):
    contract = contract or load_contract()
    observed = []
    for command in candidates(contract, root) if candidate_commands is None else candidate_commands:
        command = (command,) if isinstance(command, str) else tuple(command)
        try:
            result = runner([*command, '-I', '-S', '-B', '-c', QUERY], capture_output=True, text=True, timeout=15)
            value = json.loads(result.stdout)
            version = value['version']
            executable = value['executable']
            if result.returncode or not Path(executable).is_absolute() or len(version) != 3 or any(type(n) is not int for n in version):
                raise ValueError('Invalid interpreter response')
            observed.append({'candidate': command[0], 'version': '.'.join(map(str, version))})
            if compatible(version, contract, profile):
                # A launcher/alias can point somewhere else. Query the returned executable too.
                check = runner([executable, '-I', '-S', '-B', '-c', QUERY], capture_output=True, text=True, timeout=15)
                actual = json.loads(check.stdout)
                if check.returncode or actual != value:
                    raise ValueError('Interpreter identity changed')
                return dict(value, profile=profile, required=contract['python_profiles'][profile], observed=observed)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            observed.append({'candidate': command[0], 'status': 'unavailable_or_invalid'})
    raise RuntimeContractError('Python required %s; no compatible executable; observed %s' % (
        contract['python_profiles'][profile], json.dumps(observed)))


def command(selection, *args):
    if not Path(selection['executable']).is_absolute():
        raise RuntimeContractError('Resolved Python executable must be absolute')
    return [selection['executable'], '-B', *map(str, args)]


def source_check(root, *, profile='experiment', contract=None):
    """Compile actual bytes using this interpreter, then import the real probe graph."""
    contract = contract or load_contract()
    selected = assert_current(profile, contract)
    root = Path(root).resolve()
    files = sorted(p for folder in ('scripts', 'tools', 'corpus_ingest')
                   for p in (root / folder).rglob('*.py') if '__pycache__' not in p.parts)
    if not files:
        raise RuntimeContractError('Source preflight: no Python source found')
    for path in files:
        try:
            compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
        except SyntaxError as exc:
            raise RuntimeContractError('Source compile failed: %s:%s (%s)' % (
                path.relative_to(root), exc.lineno, type(exc).__name__)) from None
    # These imports should stay lightweight. Refuse accidental model/pipeline work.
    class BlockHeavy(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in {'torch', 'transformers', 'sentence_transformers', 'pipeline', 'multi_round'}:
                raise RuntimeContractError('Source import preflight attempted heavy module: ' + fullname)
    blocker = BlockHeavy()
    sys.meta_path.insert(0, blocker)
    sys.path[:0] = [str(root / 'scripts'), str(root / 'tools'), str(root)]
    imported = []
    try:
        imports = list(contract['critical_imports'])
        if profile == 'experiment':
            imports += contract['experiment_entrypoint_imports']
        for name in imports:
            try:
                module = importlib.import_module(name)
                if not Path(module.__file__).resolve().is_relative_to(root):
                    raise RuntimeContractError('Import resolved outside transferred source: ' + name)
                imported.append(name)
            except Exception as exc:
                raise RuntimeContractError('Source import failed: %s (%s)' % (name, type(exc).__name__)) from None
    finally:
        sys.meta_path.remove(blocker)
    return dict(selected, compiled_files=len(files), imports=imported, source_preflight_passed=True)


def subprocess_check(selection, root, *, dependencies=False, runner=subprocess.run, contract_file=None):
    args = ['-I', *([] if dependencies else ['-S']), str(Path(__file__).absolute()), '--profile', selection['profile'],
            '--contract', str(Path(contract_file or contract_path()).absolute()),
            '--dependencies' if dependencies else '--source', str(Path(root).absolute())]
    result = runner(command(selection, *args), capture_output=True, text=True, timeout=90)
    try:
        value = json.loads(result.stdout)
    except ValueError:
        raise RuntimeContractError('Runtime/source preflight subprocess failed without a valid report') from None
    if result.returncode or value.get('error'):
        raise RuntimeContractError(value.get('error', 'Runtime/source preflight failed'))
    if dependencies:
        if not isinstance(value.get('missing'), list) or value.get('dependencies_ready') is not (not value['missing']):
            raise RuntimeContractError('Dependency preflight did not establish readiness')
    elif value.get('source_preflight_passed') is not True:
        raise RuntimeContractError('Source preflight did not establish compatibility')
    return value


def dependency_check(root, contract=None):
    """Check declared versions before imports. Never repair/upgrade a mismatch."""
    contract = contract or load_contract()
    lock = Path(root) / 'tools/cloud_run/runtime.lock'
    if not lock.exists():
        lock = Path(root) / 'runtime.lock'
    versions = {}
    for line in lock.read_text().splitlines():
        if '==' in line and not line.startswith('#'):
            name, version = line.split('==', 1)
            versions[name.lower().replace('_', '-')] = version
    missing, mismatched, installed = [], [], {}
    for package, module in contract['core_dependencies'].items():
        expected = versions[package]
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            continue
        installed[package] = actual
        if actual != expected:
            mismatched.append({'package': package, 'required': expected, 'observed': actual})
    if mismatched:
        raise RuntimeContractError('Dependency version mismatch: ' + json.dumps(mismatched))
    for package, module in contract['core_dependencies'].items():
        if package not in missing:
            try:
                importlib.import_module(module)
            except Exception as exc:
                raise RuntimeContractError('Dependency import failed: %s (%s)' % (package, type(exc).__name__)) from None
    return {'missing': missing, 'installed': installed, 'dependencies_ready': not missing}


def remote_resolver_command(profile='sealed_reference', contract=None):
    """Version-only SSH bootstrap, generated from the local authoritative contract.

    This shell fragment is data for a future authorized controller, never run here.
    No source, package install or model download is required to resolve Python.
    """
    contract = contract or load_contract()
    version = contract['python_compatibility']
    condition = 'v[:2] == %r' % [version['major'], version['minor']]
    if profile == 'sealed_reference':
        condition += ' and v == %r' % list(map(int, contract['python'].split('.')))
    check = ("import sys,json,os\nv=list(sys.version_info[:3])\n"
             "if not (" + condition + "):\n"
             " sys.exit(" + repr('Python required ' + contract['python_profiles'][profile] + '; observed ') +
             " + '.'.join(map(str,v)) + ' at ' + sys.executable)\n"
             "print(json.dumps({'executable':os.path.abspath(sys.executable),'version':v}))")
    names = 'python%d.%d python3 python' % (version['major'], version['minor'])
    return ('for candidate in ' + names + '; do candidate_path=$(command -v "$candidate") || continue; '
            '"$candidate_path" -I -B -c ' + shlex.quote(check) + ' && exit 0; done; '
            'echo ' + shlex.quote('Python required ' + contract['python_profiles'][profile] + '; no compatible interpreter') + ' >&2; exit 2')


def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
        raise RuntimeContractError('External action forbidden during runtime/source preflight: ' + event)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--contract', type=Path)
    p.add_argument('--profile', choices=('experiment', 'sealed_reference'), default='experiment')
    p.add_argument('--resolve', action='store_true')
    p.add_argument('--path-only', action='store_true')
    p.add_argument('--candidate', action='append')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--source', type=Path)
    p.add_argument('--dependencies', type=Path)
    args = p.parse_args(argv)
    try:
        contract = load_contract(args.contract)
        if args.resolve:
            result = resolve(args.candidate, profile=args.profile, contract=contract, root=args.root)
        else:
            result = assert_current(args.profile, contract)
            if args.dependencies:
                def dependency_network_guard(event, args):
                    if event in {'socket.connect', 'socket.getaddrinfo'}:
                        raise RuntimeContractError('Network forbidden during dependency preflight')
                sys.addaudithook(dependency_network_guard)
            else:
                sys.addaudithook(no_network)
            if args.source:
                result = source_check(args.source, profile=args.profile, contract=contract)
            if args.dependencies:
                # Native package imports may start helper processes; still no network allowed.
                result = dependency_check(args.dependencies, contract)
        print(result['executable'] if args.path_only else json.dumps(result))
        return 0
    except (RuntimeContractError, OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr if args.path_only else sys.stdout)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
