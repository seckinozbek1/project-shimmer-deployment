"""Isolated artifact-to-API proofs; no pipeline or provider is started."""
from __future__ import annotations

from contextlib import nullcontext, ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch


def exercise():
    from fastapi.testclient import TestClient
    from agent_activation import ActivationAudit
    from effect_proof import prove_effect, ProofFailure
    from run_context import for_run_dir
    from run_completion import RunCompletion
    from startup_submit_checks import _isolated_server
    import routing_view

    with tempfile.TemporaryDirectory(prefix="shimmer_routing_ui_") as tmp, ExitStack() as stack:
        root = Path(tmp)
        server = _isolated_server(root)
        run_id = 'a' * 32
        ctx = for_run_dir(root, server.RUNS_DIR / run_id)
        audit = ActivationAudit(ctx, ['PROCESSOR', 'REDACTOR', 'STYLE_GUARDIAN', 'EDITOR_DG'])
        called = audit.decision('PROCESSOR', eligible=True, activated=True,
                                reason='reference_scheduled', source_phase='3-4')
        audit.update(called, actual_call=True, call_id='fixture_call', state='execution_failure',
                     outcome='contract_violation', truncated=True, recovered=False)
        audit.decision('REDACTOR', eligible=False, activated=False,
                       reason='sensitivity_layer_inactive', source_phase='9')
        audit.decision('STYLE_GUARDIAN', eligible=True, activated=False,
                       reason='no_assigned_or_untagged_rules', source_phase='5.5')
        completion = RunCompletion(ctx)
        completion.reached_end(document_count=1, amendment_count=0)
        completion.finish(0)
        access = secrets.token_urlsafe(24)
        stack.enter_context(patch.dict(os.environ, {'SHIMMER_TOKEN_HASH': hashlib.sha256(access.encode()).hexdigest()}))
        headers = {'Authorization': 'Bearer ' + access}
        client = TestClient(server.app)
        url = '/runs/' + run_id + '/activation'
        assert client.get(url).status_code == 401
        assert client.get('/runs/' + 'b' * 32 + '/activation', headers=headers).status_code == 404
        response = client.get(url, headers=headers)
        assert response.status_code == 200
        valid = response.json()
        assert valid['recorded'] and valid['activation_mode'] == 'dense'
        assert [s['state'] for s in valid['agent_states']] == [
            'execution_failure', 'ineligible', 'eligible_inactive', 'phase_not_reached']
        assert valid['agent_states'][0]['actual_calls'] == 1
        assert valid['completion']['state'] == 'completed'
        statuses = {}
        for status, code in [('completed', 0), ('blocked', 5), ('failed', 1), ('failed_timeout', None)]:
            statuses[status] = server._run_record({'run_id': run_id, 'status': status,
                                                   'exit_code': code}, ctx.run_dir)

        def observe():
            return client.get(url, headers=headers).json()

        def check():
            return ('PASS' if observe() == valid else 'FAIL', 'artifact projection')

        proof = dict(name='activation_reader_reaches_http', validate=lambda: True,
                     observe=observe, check=check)
        prove_effect(**proof, neutralise=lambda: patch.object(routing_view, 'read_activation',
                     return_value={'recorded': False, 'availability': 'not_recorded'}))
        try:
            prove_effect(**proof, neutralise=nullcontext)
        except ProofFailure as exc:
            assert exc.category == 'NO_OBSERVED_EFFECT'
        else:
            raise AssertionError('no-op accepted')

        original = audit.path.read_bytes()
        cases = {}
        for name, content in [('invalid', '{'),
                              ('mismatch', json.dumps(dict(audit.data, run_id='b' * 32))),
                              ('invalid_aggregate', json.dumps(dict(audit.data, agent_states=[])))]:
            audit.path.write_text(content, encoding='utf-8')
            cases[name] = observe()
            assert not cases[name]['recorded'] and cases[name]['activation_mode'] is None
        audit.path.unlink()
        cases['missing'] = observe()
        assert cases['missing']['availability'] == 'not_recorded'
        audit.path.write_bytes(original)
        assert observe() == valid
        preparation = audit.decision('PROCESSOR', eligible=True, activated=True,
                                     reason='reference_scheduled', source_phase='3-4')
        audit.update(preparation, state='pre_dispatch_failure')
        cases['preparation'] = observe()
        assert cases['preparation']['agent_states'][0]['actual_calls'] == 1
        assert cases['preparation']['decisions'][-1]['actual_call'] is False
        cases['completion_states'] = {}
        for name, code, error in [('running', None, None), ('stopped', 5, None),
                                  ('failed', 1, ValueError()), ('interrupted', None, KeyboardInterrupt())]:
            marker = RunCompletion(ctx)
            if name != 'running':
                marker.finish(code, error)
            projected = observe()
            assert projected['completion']['state'] == name
            cases['completion_states'][name] = projected
        # Citation consumer uses this run's own index; no current/global substitute.
        (ctx.audit_dir() / 'reference_index.json').write_text(json.dumps({'entries': [
            {'ref_id': 'REF-0001', 'document_id': 'fixture', 'document_name': 'fixture.md',
             'location': {'paragraph': 1}, 'text_excerpt': 'Synthetic source passage.'}]}), encoding='utf-8')
        reference = client.get('/runs/' + run_id + '/references?ref_id=REF-0001', headers=headers)
        assert reference.status_code == 200
        assert reference.json()['references'][0]['text_excerpt'] == 'Synthetic source passage.'
        assert client.get('/runs/' + run_id + '/references?ref_id=REF-9999', headers=headers).status_code == 404
        return {'valid': valid, **cases, 'reference': reference.json(), 'statuses': statuses}


def check():
    exercise()
    return 'PASS', 'real activation writer -> authenticated HTTP; unknown/malformed/mismatched records, failures/non-calls, completion and citations; mutation fails, restoration passes, no-op refused'


if __name__ == '__main__':
    import sys
    result = exercise()
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(json.dumps(result), encoding='utf-8')
    print('PASS: isolated routing API consumer proofs')
