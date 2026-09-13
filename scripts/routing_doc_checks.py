"""Small executable claims, not a prose snapshot or quality certificate."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tempfile
from unittest.mock import patch


def check():
    import build_agent_harness as builder
    import run_context
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    registry = json.loads((root / 'config/agent_registry.json').read_text(encoding='utf-8'))
    names = set(registry['agents'])

    def roster(text):
        table = text.split('| Agent |', 1)[1].split('Gate/trigger keys', 1)[0]
        return set(re.findall(r'^\| `([A-Z][A-Z_]+)` \|', table, re.M))

    assert len(names) == 18 and roster(readme) == names
    altered = readme.replace('| `PROCESSOR` |', '| `OMITTED_AGENT` |')
    assert roster(altered) != roster(readme), 'NO_OBSERVED_EFFECT'
    assert roster(altered) != names
    assert roster(readme) == names
    tree = ast.parse((root / 'scripts/pipeline.py').read_text(encoding='utf-8'))
    profile = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and isinstance(n.value, ast.Dict)
                   and any(isinstance(t, ast.Name) and t.id == '_LOCAL_PROFILE' for t in n.targets))
    resolver = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_resolve_local_models')
    namespace = {'Path': Path, 'json': json}
    exec(compile(ast.Module(body=[resolver], type_ignores=[]), '<actual local resolver>', 'exec'), namespace)
    profile = namespace['_resolve_local_models'](profile, root)
    for line in readme.splitlines():
        if not line.startswith('| `'):
            continue
        columns = [c.strip() for c in line.split('|')[1:-1]]
        name = columns[0].strip('`')
        if name in names:
            reg = registry['agents'][name]
            assert columns[3] == '`%s` / `%s`' % (reg['backend'], reg['model'])
            assert columns[4] == '`%s` / `%s`' % profile.get(name, (reg['backend'], reg['model']))
    option = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_argument'
                  and n.args and isinstance(n.args[0], ast.Constant)
                  and n.args[0].value == '--activation-profile')
    default = next(ast.literal_eval(k.value) for k in option.keywords if k.arg == 'default')
    assert default == 'dense' and '`--activation-profile dense` is the default' in readme
    for basename in list(run_context.DELIVERABLE_FILENAMES.values()) + [
            run_context.RUN_SUMMARY_NAME, run_context.DRAFT_MEMO_NAME, run_context.IDENTITY_FILENAME]:
        assert basename in readme, basename
    # Generate in a throwaway root: never rewrite operator configuration to test it.
    with tempfile.TemporaryDirectory(prefix='shimmer_harness_parity_') as tmp:
        isolated = Path(tmp)
        (isolated / 'config').mkdir()
        for name in ['agent_registry.json', 'agent_contracts.json']:
            (isolated / 'config' / name).write_bytes((root / 'config' / name).read_bytes())
        with patch.object(builder, 'ROOT', isolated):
            generated = builder.build()
        checked_in = json.loads((root / 'config/agent_harness.json').read_text(encoding='utf-8'))
        assert generated == checked_in, 'generated harness drift'
        changed = dict(checked_in, schema_version='fixture mismatch')
        assert changed != generated
    return 'PASS', 'all 18 README roster entries and resolved Cloud/Local models, CLI dense default, canonical deliverable names and isolated regenerated harness match; omitted roster and changed harness rejected'
