"""archive_closure: before any seal or launch, prove that every file a bundle's workload will run or import is
inside the project archive the instance gets, and refuse otherwise (GNN_TRAIN_6f48d5ed, 19 Nov 2026: the training
pass stopped on the instance because tools/ontology_training_graphs.py and tools/ontology_training_leakage.py were
not carried; docs/loop/stages/GNN_TRAIN_6F48_FAILURE.md).

The archive is read, never guessed:
  - a sealed bundle's execution_manifest.json in the launch folder: its project_files (exactly what was archived);
    an arm G bundle runs from its gate source, the whole bound tree;
  - before a seal: the bound commit's own sealer rule, read from that commit's tools/prepare_ordinary_final_run.py
    and tools/prepare_cloud_run.py by their constants (RUNTIME_PREFIXES, RUNTIME_FILES, ARCHIVE_EXTRAS, the named
    tools helpers, the gate check file rule) applied to `git ls-tree` of the commit. Nothing is imported.

The workload's entry files come from each request's argv: arm G runs scripts/verify_session1.py; arm B1 with
--replay-prompts runs benchmark/baselines/replay_prompts.py and the pass module whose SCHEMA equals the pass
file's "schema"; arm B1 without it runs benchmark/baselines/bare_model.py; any other arm runs scripts/pipeline.py.
In the replay dispatcher a per-pass lazy loader (`def _x(): import m; return m`, m imported nowhere else in the
file) other than the B1 pass module's belongs to another pass: what is reached only through it is latent. A
workload not run through the dispatcher (B3, B1 bare, arm G, the commit mode) hands no file to any pass, so when
it reaches replay_prompts.py by an import every loader there is latent (B3 reaches it through scripts/vllm_route.py
and vllm_replay.py; tools/build_auditor_training.py sits behind its auditor-training loader); every other import
of the dispatcher stays on the normal path and is refused when absent.

From the entries, Python files of the commit are followed by their import statements, literal
importlib.import_module names and "module:function" names declared in archived config JSON. Within a file only
the parts that run are read: every module-level statement (the __main__ block only for the entry run as a
script) and the top-level functions and classes reached from them or from the names the importer uses of it
(the attributes read through its alias, the names imported from it, or every name when the module object itself
is passed on or returned), so an import inside a function nothing calls is not followed. Attribute chains through
a second module (a.b.f) are read as a use of b only; a dynamic getattr reads the whole module. A module is resolved by name against the importing file's folder and the folders the runtime puts on its
path (SEARCH_DIRS); a name no file of the commit holds is the standard library or a package and is not ours.
A repository path written as a literal ending in .py (a file the code hashes or runs by path) must be archived
too; it is checked for presence and not followed. An import inside a try that catches ImportError or Exception is
optional: listed, never refused. Other literal repository paths absent from the archive are counted as notes.

Read-only: it reads git objects and the launch folder; it writes nothing. Prints paths of code files and counts.

    py -3.12 -X utf8 tools/loop/archive_closure.py folder LAUNCH_FOLDER [--repo REPO]
    py -3.12 -X utf8 tools/loop/archive_closure.py commit COMMIT --entry PATH [--entry PATH] [--repo REPO]

Exit 0: every request's closure is inside its archive; 1: a refusal (each missing file named); 2: unreadable input.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
SEALER = 'tools/prepare_ordinary_final_run.py'
CLOUD = 'tools/prepare_cloud_run.py'
SEARCH_DIRS = ('scripts', 'benchmark/baselines', 'benchmark/adapters', 'benchmark', 'tools', 'tools/loop',
               'tools/cloud_run', '')
OPTIONAL_CATCHES = ('ImportError', 'ModuleNotFoundError', 'Exception', 'BaseException')
REPO_PATH = re.compile(r'^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+$')
MODULE_FUNCTION = re.compile(r'^([A-Za-z_][A-Za-z0-9_.]*):[A-Za-z_][A-Za-z0-9_]*$')
NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0


def no_window():
    """The creation flags of every child process this tool starts (HIDDEN-A, check 292)."""
    return NO_WINDOW


class Unreadable(RuntimeError):
    """An input the check cannot read (a commit, a request file, a sealer)."""


class Tree:
    """The bound commit's file names and, on demand, file bytes, from the git object store."""

    def __init__(self, repo, commit):
        self.repo, self.commit = Path(repo), commit
        out = self._git('ls-tree', '-r', '--name-only', commit)
        self.names = set(out.decode('utf-8').splitlines())
        if not self.names:
            raise Unreadable('the commit %s holds no files in %s' % (commit, repo))
        self._cache = {}
        self._batch = None

    def _git(self, *args, data=None):
        proc = subprocess.run(['git', '-C', str(self.repo), *args], input=data, capture_output=True,
                              creationflags=no_window())
        if proc.returncode != 0:
            raise Unreadable('git %s failed: %s' % (args[0], proc.stderr.decode('utf-8', 'replace').strip()[:200]))
        return proc.stdout

    def _cat(self, name):
        """One file's bytes through a single `git cat-file --batch` process kept for the tree (beta item 28,
        OPEN_ITEMS 180: one `git show` per object, about 10,700 for a whole-tree bundle, made a pass take 15 to 20
        minutes). A name the commit does not hold is Unreadable, as `git show` was."""
        if self._batch is None:
            self._batch = subprocess.Popen(['git', '-C', str(self.repo), 'cat-file', '--batch'], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=no_window())
        try:
            self._batch.stdin.write(('%s:%s\n' % (self.commit, name)).encode('utf-8'))
            self._batch.stdin.flush()
            header = self._batch.stdout.readline().split()
        except OSError as exc:
            self.close()
            raise Unreadable('git cat-file failed: %s' % exc) from None
        if len(header) == 2 and header[1] == b'missing':
            raise Unreadable('git show failed: %s:%s does not exist' % (self.commit, name))
        if len(header) != 3 or not header[2].isdigit():
            self.close()
            raise Unreadable('git cat-file failed: unexpected answer for %s' % name)
        size = int(header[2])
        data = self._batch.stdout.read(size)
        self._batch.stdout.read(1)          # the line feed after the object
        if len(data) != size:
            self.close()
            raise Unreadable('git cat-file failed: %s ended after %d of %d bytes' % (name, len(data), size))
        if header[1] != b'blob':
            raise Unreadable('git show failed: %s:%s is a %s' % (self.commit, name, header[1].decode('ascii', 'replace')))
        return data

    def close(self):
        if self._batch is not None:
            proc, self._batch = self._batch, None
            try:
                proc.stdin.close()
                proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()

    def __del__(self):
        try:
            self.close()
        except Exception:     # noqa: BLE001 - interpreter shutdown
            pass

    def read(self, name):
        if name not in self._cache:
            self._cache[name] = self._cat(name)
        return self._cache[name]


def _constants(source, names):
    """{name: literal value} of module-level assignments in `source` (ast.literal_eval only)."""
    found = {}
    for node in _parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and (node.targets[0].id in names if not callable(names) else names(node.targets[0].id)):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return found


_PARSED = {}


def _parse(source, filename='<unknown>'):
    """ast.parse without the SyntaxWarnings of other files' escape sequences on stderr. The tree of each
    (source, filename) is parsed once and kept (D-856): the closure revisits a module whenever the names used from it
    grow, and re-parsing large modules each time made one whole-tree check take over 40 minutes. Callers only read
    the tree."""
    key = (source, filename)
    if key not in _PARSED:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _PARSED[key] = ast.parse(source, filename=filename)
    return _PARSED[key]


def _tool_helpers(source):
    """The tools helper modules the sealer adds by name: `for name in ('x.py', ...)` loops writing 'tools/'+name."""
    helpers = []
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple) \
                and all(isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value.endswith('.py')
                        for e in node.iter.elts) \
                and "'tools/'" in ast.unparse(node):
            helpers += ['tools/' + e.value for e in node.iter.elts]
    return helpers


def sealer_archive(tree):
    """The names the bound commit's sealer puts in the project archive, by its own constants."""
    want = ('RUNTIME_PREFIXES', 'RUNTIME_FILES', 'ARCHIVE_EXTRAS')
    sealer = tree.read(SEALER).decode('utf-8')
    rule = _constants(sealer, want)
    if set(rule) != set(want):
        raise Unreadable('the sealer at %s does not declare %s' % (tree.commit, ', '.join(sorted(set(want) - set(rule)))))
    named_like = _constants(tree.read(CLOUD).decode('utf-8'), ('RUNTIME_MODULES_NAMED_LIKE_CHECKS',)).get(
        'RUNTIME_MODULES_NAMED_LIKE_CHECKS', ())

    def gate_check_file(n):
        return ((n.endswith('_checks.py') and n not in named_like) or n.startswith('scripts/verify_')
                or '/fixtures/' in n)

    def named(n, p):
        return n == p or (p.endswith('/') and n.startswith(p))
    names = {n for n in tree.names
             if (n.startswith(tuple(rule['RUNTIME_PREFIXES'])) or n in rule['RUNTIME_FILES']
                 or any(named(n, p) for p in rule['ARCHIVE_EXTRAS'])) and not gate_check_file(n)}
    names |= {h for h in _tool_helpers(sealer) if h in tree.names}
    # Data the sealer adds by declaration: the restored decoding protocols and the frozen model files.
    try:
        policy = json.loads(tree.read('config/decoding_policy.json').decode('utf-8'))
        names |= {e['protocol'] for e in (policy.get('backends') or {}).values()
                  if e.get('status') == 'restored' and e.get('protocol') in tree.names}
        spec = json.loads(tree.read('config/final_models.json').decode('utf-8'))
        names |= {f['path'] for role in ('producer', 'auditor') for f in ((spec.get(role) or {}).get('files') or {}).values()
                  if isinstance(f, dict) and f.get('path')}
    except (Unreadable, ValueError, KeyError, TypeError, AttributeError):
        pass
    return names


def sealer_support(tree):
    """The runner's support files (tools/<name>.py, placed beside the runner on the instance), from the
    sealer's support_names list."""
    for node in ast.walk(_parse(tree.read(SEALER).decode('utf-8'))):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List) \
                and any(isinstance(t, ast.Name) and t.id == 'support_names' for t in node.targets):
            return {'tools/' + e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value.endswith('.py')}
    return set()


def _optional_nodes(module):
    """ids of import nodes inside a try whose handlers catch an import failure."""
    optional = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Try):
            catches = set()
            for h in node.handlers:
                if h.type is None:
                    catches.add('BaseException')
                for t in ([h.type] if not isinstance(h.type, ast.Tuple) else h.type.elts) if h.type else ():
                    catches.add(t.id if isinstance(t, ast.Name) else getattr(t, 'attr', ''))
            if catches & set(OPTIONAL_CATCHES):
                for stmt in node.body:
                    optional.update(id(n) for n in ast.walk(stmt))
    return optional


def _docstrings(module):
    ids = set()
    for node in ast.walk(module):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


ALL = frozenset({'*'})   # every name of a module is used (an entry, a module object passed on, a star import)


def _is_main_block(node):
    return isinstance(node, ast.If) and isinstance(node.test, ast.Compare) \
        and '__main__' in ast.unparse(node.test) and '__name__' in ast.unparse(node.test)


def _regions(module, used, as_script):
    """The parts of a module that run when `used` names of it are used: every module-level statement
    (the __main__ block only when the file runs as a script) and each top-level function or class reached
    from them or from `used`, through the names it references."""
    defs = {n.name: n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    stmts = [n for n in module.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and (as_script or not _is_main_block(n))]
    if '*' in used:
        return stmts + list(defs.values())
    todo = set(used) | {x.id for s in stmts for x in ast.walk(s) if isinstance(x, ast.Name)}
    reached = set()
    while todo:
        n = todo.pop()
        if n in defs and n not in reached:
            reached.add(n)
            todo |= {x.id for x in ast.walk(defs[n]) if isinstance(x, ast.Name)} - reached
    return stmts + [defs[n] for n in sorted(reached)]


def references(name, source, used=ALL, as_script=False):
    """(edges, literal .py paths, other literal repo paths) of the parts of one Python file that run when
    `used` names of it are used. An edge is (module, level, optional, names of it used)."""
    try:
        module = _parse(source, filename=name)
    except SyntaxError:
        return [], [], []
    optional, docs = _optional_nodes(module), _docstrings(module)
    nodes = [x for region in _regions(module, used, as_script) for x in ast.walk(region)]
    attr_of, bare = {}, set()
    attribute_values = {id(x.value) for x in nodes if isinstance(x, ast.Attribute)}
    for x in nodes:
        if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name):
            attr_of.setdefault(x.value.id, set()).add(x.attr)
        elif isinstance(x, ast.Name) and id(x) not in attribute_values:
            bare.add(x.id)

    def uses(alias):
        """The names of an imported module used through its alias: every name when the alias itself is
        passed on or returned (a module object), else the attributes read from it."""
        return ALL if alias in bare else frozenset(attr_of.get(alias, ()))
    edges, code_paths, other_paths = [], [], []
    for node in nodes:
        opt = id(node) in optional
        if isinstance(node, ast.Import):
            for a in node.names:
                edges.append((a.name, 0, opt, uses(a.asname) if a.asname else
                              (uses(a.name) if '.' not in a.name else ALL)))
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            star = any(a.name == '*' for a in node.names)
            edges.append((base, node.level, opt, ALL if star else frozenset(a.name for a in node.names)))
            edges += [((base + '.' if base else '') + a.name, node.level, opt, uses(a.asname or a.name))
                      for a in node.names if a.name != '*']
        elif isinstance(node, ast.Call) and ast.unparse(node.func) in ('importlib.import_module', 'import_module') \
                and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            edges.append((node.args[0].value, 0, opt, ALL))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs \
                and REPO_PATH.match(node.value):
            (code_paths if node.value.endswith('.py') else other_paths).append(node.value)
    return edges, code_paths, other_paths


def resolve(module, level, importer, names):
    """The commit's file names that `import module` from `importer` can mean (empty: not ours)."""
    here = str(PurePosixPath(importer).parent)
    here = '' if here == '.' else here
    if level:
        base = PurePosixPath(importer).parent
        for _ in range(level - 1):
            base = base.parent
        dirs = ['' if str(base) == '.' else str(base)]
    else:
        dirs = [here] + [d for d in SEARCH_DIRS if d != here]
    parts = module.split('.') if module else []
    found = []
    for d in dirs:
        stem = '/'.join(p for p in [d] + parts if p)
        for cand in (stem + '.py', stem + '/__init__.py'):
            if cand in names:
                found.append(cand)
    return found


def config_imports(tree, archive):
    """(module, function) of the "module:function" names declared in archived config JSON (importlib at call time)."""
    mods = set()

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            m = MODULE_FUNCTION.match(v)
            if m:
                mods.add((m.group(1), v.split(':', 1)[1]))
    for n in sorted(archive):
        if n.startswith('config/') and n.endswith('.json'):
            try:
                walk(json.loads(tree.read(n).decode('utf-8')))
            except (ValueError, UnicodeDecodeError):
                continue
    return mods


def lazy_loader_modules(source):
    """Module names of a file's `def _x(): import m; return m` loaders (a dispatcher's per-pass modules): the
    loader returns the module object itself, and a module the file also imports anywhere else is on the normal
    path, never a loader's."""
    loaders, loader_nodes = set(), set()
    module = _parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and len(node.body) == 2 and isinstance(node.body[0], ast.Import) \
                and isinstance(node.body[1], ast.Return) and isinstance(node.body[1].value, ast.Name) \
                and len(node.body[0].names) == 1 \
                and node.body[1].value.id == (node.body[0].names[0].asname or node.body[0].names[0].name):
            loaders.add(node.body[0].names[0].name)
            loader_nodes.add(id(node.body[0]))
    elsewhere = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import) and id(node) not in loader_nodes:
            elsewhere.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            elsewhere.add(node.module or '')
            elsewhere.update(((node.module + '.') if node.module else '') + a.name for a in node.names)
        elif isinstance(node, ast.Call) and ast.unparse(node.func) in ('importlib.import_module', 'import_module') \
                and node.args and isinstance(node.args[0], ast.Constant):
            elsewhere.add(node.args[0].value)
    return loaders - elsewhere


def closure(tree, archive, entries, present=(), dispatcher=None, handler=None):
    """{'followed', 'missing', 'missing_named', 'optional_missing', 'latent', 'notes'} from the entry files.

    `present` names files the instance holds beside the archive (the runner's support files, never followed).
    In the `dispatcher` (replay_prompts.py) a lazy loader's module other than the `handler` belongs to another
    pass: what is reached only through it is latent, reported and never refused (that pass's launch refuses it).
    With no handler (a workload that runs no pass, B3 among them) every loader's module is latent."""
    have = set(archive) | set(present)
    missing, missing_named, optional_missing, latent, notes = {}, {}, {}, {}, set()
    used = {True: {}, False: {}}      # strength -> {file: names of it used}
    queue = []

    def visit(path, is_strong, names):
        known = used[is_strong].get(path, frozenset())
        grown = ALL if ('*' in names or '*' in known) else known | names
        if path in used[is_strong] and grown == known:
            return
        used[is_strong][path] = grown
        queue.append((path, is_strong))
    for e in entries:
        if e not in archive:
            missing.setdefault(e, set()).add('(entry)')
        else:
            visit(e, True, ALL)
    declared = sorted(config_imports(tree, archive))
    scripts = set(entries[:1])
    while queue or declared:
        lazy = set()
        if declared:
            name, is_strong, code_paths, other_paths = 'config', True, [], []
            edges = [(m, 0, False, frozenset({f})) for m, f in declared]
            declared = []
        else:
            name, is_strong = queue.pop()
            names = used[is_strong][name]
            if not is_strong and name in used[True] and ('*' in used[True][name] or names <= used[True][name]):
                continue
            source = tree.read(name)
            edges, code_paths, other_paths = references(name, source, names, as_script=name in scripts)
            if name == dispatcher:
                lazy = lazy_loader_modules(source)
        for module, level, opt, names_used in edges:
            cands = resolve(module, level, name, tree.names)
            if not cands:
                continue
            edge_strong = is_strong and not (module in lazy and handler not in cands)
            if any(c in present and c not in archive for c in cands):
                continue
            inside = [c for c in cands if c in archive]
            if not inside:
                target = optional_missing if opt else (missing if edge_strong else latent)
                target.setdefault(cands[0], set()).add(name)
                continue
            for c in inside[:1]:
                visit(c, edge_strong, names_used)
        for p in code_paths:
            if p in tree.names and p not in have:
                (missing_named if is_strong else latent).setdefault(p, set()).add(name)
        notes.update(p for p in other_paths if p in tree.names and p not in have)
    for k in list(latent):
        if k in missing or k in missing_named:
            del latent[k]
    for k in list(optional_missing):
        if k in missing:
            del optional_missing[k]
    return {'followed': sorted(used[True]), 'latent_followed': sorted(set(used[False]) - set(used[True])),
            'missing': {k: sorted(v) for k, v in sorted(missing.items())},
            'missing_named': {k: sorted(v) for k, v in sorted(missing_named.items())},
            'optional_missing': {k: sorted(v) for k, v in sorted(optional_missing.items())},
            'latent': {k: sorted(v) for k, v in sorted(latent.items())},
            'notes': sorted(notes)}


def _flag(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


def _pass_module(tree, schema):
    """The benchmark/baselines module declaring the pass schema in a module-level SCHEMA* constant (a string,
    or a tuple of strings); None when no module or more than one declares it."""
    hits = []
    for n in sorted(tree.names):
        if n.startswith('benchmark/baselines/') and n.endswith('.py') and schema.encode('utf-8') in tree.read(n):
            consts = _constants(tree.read(n).decode('utf-8'), lambda k: k.startswith('SCHEMA'))
            if any(v == schema or (isinstance(v, (tuple, list)) and schema in v) for v in consts.values()):
                hits.append(n)
    return hits[0] if len(hits) == 1 else None


def entries_for(tree, argv, folder=None):
    """The entry files a request's workload runs, from its argv (module docstring)."""
    arm = _flag(argv, '--arm')
    if arm == 'G':
        return ['scripts/verify_session1.py']
    if arm == 'B1':
        prompts = _flag(argv, '--replay-prompts')
        if prompts is None:
            return ['benchmark/baselines/bare_model.py']
        entries = ['benchmark/baselines/replay_prompts.py']
        path = Path(prompts)
        if not path.is_file() and folder is not None:
            path = Path(folder) / 'work' / Path(prompts).name
        try:
            schema = json.loads(path.read_text(encoding='utf-8')).get('schema')
        except (OSError, ValueError, AttributeError) as exc:
            raise Unreadable('the replay prompts file %s is unreadable: %s' % (Path(prompts).name, type(exc).__name__))
        module = _pass_module(tree, schema) if isinstance(schema, str) else None
        if isinstance(schema, str) and module is None:
            # Without the pass module its own branch would be read as another pass's: refuse, never weaken.
            raise Unreadable('no single benchmark/baselines module at %s declares the pass schema %r'
                             % (tree.commit[:8], schema))
        return entries + ([module] if module else [])
    return ['scripts/pipeline.py']


REPLAY = 'benchmark/baselines/replay_prompts.py'


def dispatch(entries):
    """(dispatcher, handler): for a B1 replay entry list the dispatcher and the pass module its file is handed
    to; for any other workload the dispatcher with no handler, since it runs no pass (module docstring)."""
    if entries and entries[0] == REPLAY:
        return entries[0], (entries[1] if len(entries) > 1 else None)
    return REPLAY, None


def _launch_constant(folder, name):
    src = (Path(folder) / 'launch.py').read_text(encoding='utf-8')
    value = _constants(src, (name,)).get(name)
    if not isinstance(value, str):
        raise Unreadable('%s/launch.py declares no %s' % (Path(folder).name, name))
    return value


def bundle_manifest(folder, name):
    """The sealed bundle's execution_manifest.json for request `name` in the folder, if one is there."""
    hits = sorted(p for p in Path(folder).glob('**/%s/execution_manifest.json' % name))
    return hits[0] if hits else None


def check_request(repo, commit, request, folder=None):
    argv = list(request.get('argv') or [])
    manifest_path = bundle_manifest(folder, request.get('name')) if folder else None
    source = 'sealer rule at %s' % commit
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        commit = manifest.get('source_commit') or commit
        source = 'sealed manifest %s' % manifest_path.relative_to(folder).as_posix()
    tree = Tree(repo, commit)
    try:
        if _flag(argv, '--arm') == 'G':
            archive, source = set(tree.names), source + ' (arm G runs from the whole bound tree)'
        elif manifest_path is not None:
            archive = set(manifest.get('project_files') or {})
        else:
            archive = sealer_archive(tree)
        if manifest_path is not None:
            present = {'tools/' + n for n in (manifest.get('support_files') or {}) if n.endswith('.py')}
        else:
            present = sealer_support(tree)
        entries = entries_for(tree, argv, folder)
        dispatcher, handler = dispatch(entries)
        result = closure(tree, archive, entries, present, dispatcher, handler)
    finally:
        tree.close()
    result.update(name=request.get('name'), commit=commit, archive_source=source, archive_files=len(archive),
                  entries=entries)
    return result


def report(result):
    bad = bool(result['missing'] or result['missing_named'])
    lines = ['%s %s: %s, %d archived files; entries %s; %d files followed' % (
        'REFUSED' if bad else 'COMPLETE', result['name'], result['archive_source'], result['archive_files'],
        ', '.join(result['entries']), len(result['followed']))]
    for key, label in (('missing', 'imported, not in the archive'), ('missing_named', 'named by path, not in the archive'),
                       ('optional_missing', 'optional import (inside a try), not in the archive, not refused'),
                       ('latent', 'reached only through another pass, not in the archive, not refused')):
        for path, by in result[key].items():
            lines.append('  %s: %s (from %s)' % (label, path, ', '.join(by[:3]) + (' ...' if len(by) > 3 else '')))
    if result['notes']:
        lines.append('  notes: %d other literal repository paths are not archived (data names, not refused)'
                     % len(result['notes']))
    return bad, '\n'.join(lines)


def _cache_key(repo, commit, request, folder):
    """D-856: the SHA-256 of everything check_request reads: this module's source, the commit, the request, the
    sealed manifest (if any) and the replay prompts file (if any). The tree at a commit never changes."""
    import hashlib
    h = hashlib.sha256()
    h.update(Path(__file__).read_bytes())
    h.update(('%s\n%s\n' % (Path(repo).resolve(), commit)).encode('utf-8'))
    h.update(json.dumps(request, sort_keys=True).encode('utf-8'))
    manifest_path = bundle_manifest(folder, request.get('name')) if folder else None
    h.update(manifest_path.read_bytes() if manifest_path is not None else b'-')
    prompts = _flag(list(request.get('argv') or []), '--replay-prompts')
    if prompts:
        path = Path(prompts)
        if not path.is_file() and folder is not None:
            path = Path(folder) / 'work' / Path(prompts).name
        h.update(path.read_bytes() if path.is_file() else b'-')
    return h.hexdigest()


def check_folder(folder, repo=REPO, cache_dir=None):
    """Every request of the folder checked. With `cache_dir` (the launch chain's, D-856) a result is reused when
    its cache key (_cache_key) is unchanged; the proofs never pass one."""
    folder = Path(folder)
    commit = _launch_constant(folder, 'COMMIT')
    requests = json.loads((folder / 'requests.json').read_text(encoding='utf-8')).get('requests') or []
    if not requests:
        raise Unreadable('%s/requests.json names no request' % folder.name)
    if cache_dir is None:
        return [check_request(repo, commit, r, folder) for r in requests]
    cache_dir = Path(cache_dir)
    out = []
    for r in requests:
        key = _cache_key(repo, commit, r, folder)
        hit = cache_dir / ('%s.json' % key)
        if hit.is_file():
            out.append(json.loads(hit.read_text(encoding='utf-8')))
            continue
        result = check_request(repo, commit, r, folder)
        cache_dir.mkdir(parents=True, exist_ok=True)
        hit.write_text(json.dumps(result, default=sorted), encoding='utf-8')
        out.append(json.loads(hit.read_text(encoding='utf-8')))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='archive_closure.py', description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='mode', required=True)
    f = sub.add_parser('folder')
    f.add_argument('folder')
    f.add_argument('--repo', default=str(REPO))
    c = sub.add_parser('commit')
    c.add_argument('commit')
    c.add_argument('--entry', action='append', required=True)
    c.add_argument('--repo', default=str(REPO))
    args = ap.parse_args(argv)
    try:
        if args.mode == 'folder':
            results = check_folder(args.folder, args.repo)
        else:
            tree = Tree(args.repo, args.commit)
            try:
                archive = sealer_archive(tree)
                r = closure(tree, archive, args.entry, sealer_support(tree), *dispatch(args.entry))
            finally:
                tree.close()
            r.update(name='entries', commit=args.commit, archive_source='sealer rule at %s' % args.commit,
                     archive_files=len(archive), entries=args.entry)
            results = [r]
    except (Unreadable, OSError, ValueError) as exc:
        print('archive_closure: unreadable: %s' % exc)
        return 2
    refused = False
    for r in results:
        bad, text = report(r)
        refused |= bad
        print(text)
    return 1 if refused else 0


if __name__ == '__main__':
    sys.exit(main())
