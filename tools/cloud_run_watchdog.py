"""Operator-side termination watchdog. No provisioning capability; explicit arm only."""
from __future__ import annotations

import argparse
import ast
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from cloud_run_common import budget_deadlines, require, safe_metadata, write_json


def load_credential(credential_file=None):
    """Read only the named assignment, never import/execute a private config."""
    value = os.environ.get('LAMBDA_API_KEY')
    if credential_file is not None:
        try:
            tree = ast.parse(Path(credential_file).read_text(encoding='utf-8'))
            values = [n.value for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                      and any(isinstance(t, ast.Name) and t.id == 'LAMBDA_API_KEY'
                              for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
            require(len(values) == 1, 'credential assignment must be unique')
            value = ast.literal_eval(values[0])
        except Exception:
            from cloud_run_common import InvalidPreparation
            raise InvalidPreparation('local credential file unreadable or invalid') from None
    require(isinstance(value, str) and 16 <= len(value) <= 512 and
            not value.startswith(('TEST_', 'YOUR_')) and not any(c.isspace() for c in value),
            'valid local Lambda credential must be configured before provisioning')
    return value


def operator_preflight(credential_file=None, identity_file=None):
    import shutil
    import hashlib
    import subprocess
    require(shutil.which('ssh') and shutil.which('scp'), 'local OpenSSH client tools missing')
    require(shutil.which('curl.exe' if os.name == 'nt' else 'curl'), 'local curl transport missing')
    loaded = bool(load_credential(credential_file))
    require(identity_file is not None and Path(identity_file).is_file(), 'explicit local SSH private key file missing or inaccessible')
    public = Path(str(identity_file) + '.pub')
    require(public.is_file(), 'matching local SSH public key file missing or inaccessible')
    parts = public.read_text(encoding='utf-8').strip().split()
    require(len(parts) >= 2 and parts[0] in ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521'),
            'SSH public key format invalid')
    try:
        public_bytes = base64.b64decode(parts[1], validate=True)
    except Exception:
        from cloud_run_common import InvalidPreparation
        raise InvalidPreparation('SSH public key encoding invalid') from None
    require(bool(public_bytes), 'SSH public key is empty')
    validation = subprocess.run(['ssh-keygen', '-l', '-f', str(public)], capture_output=True, timeout=10)
    require(validation.returncode == 0, 'SSH public key is not valid for provisioning')
    return {'ssh_available': True, 'scp_available': True, 'curl_available': True, 'credential_loaded': loaded,
            'ssh_private_file_exists': True, 'ssh_public_file_exists': True, 'ssh_public_key_validated': True,
            'ssh_public_key_sha256': hashlib.sha256(public_bytes).hexdigest(),
            'ssh_agent_required_for_local_preparation': False, 'private_key_read_or_decrypted': False,
            'operator_provisioning_requirement': 'Select the existing Lambda identity or supply its public key during manual provisioning.',
            'credential_source': 'operator file' if credential_file else 'environment', 'provider_contacted': False}


class LambdaTermination:
    """Responses live in memory only. This class cannot create/start an instance."""
    def __init__(self, credential_file=None):
        self.credential_file = credential_file

    def request(self, path, body=None):
        # Keep this client restricted to observation and termination. In particular,
        # a caller cannot supply a different host or a provisioning endpoint.
        require((path == 'instances' and body is None) or
                (path == 'instance-operations/terminate' and isinstance(body, dict)
                 and set(body) == {'instance_ids'}
                 and isinstance(body['instance_ids'], list)
                 and len(body['instance_ids']) == 1
                 and isinstance(body['instance_ids'][0], str)
                 and re.fullmatch('[a-f0-9]{32}|[a-f0-9-]{36}', body['instance_ids'][0])),
                'provider request is not an allowed operation')
        executable = shutil.which('curl.exe' if os.name == 'nt' else 'curl')
        require(executable is not None, 'local curl transport missing')
        key = load_credential(self.credential_file)
        require(not any(c in key for c in '\r\n\0'), 'invalid provider credential')
        # The header travels through stdin, never argv, an environment variable,
        # a temporary file, or diagnostics. Escape curl's quoted config syntax.
        escaped = key.replace('\\', '\\\\').replace('"', '\\"')
        config = 'header = "Authorization: Bearer ' + escaped + '"\n'
        args = [executable, '--disable', '--silent', '--proto', '=https',
                '--connect-timeout', '10', '--max-time', '20', '--config', '-',
                '--write-out', '\n%{http_code}']
        if body is not None:
            args += ['--header', 'Content-Type: application/json', '--data-binary',
                     json.dumps(body, separators=(',', ':'))]
        args += ['https://cloud.lambda.ai/api/v1/' + path]
        try:
            response = subprocess.run(args, input=config, capture_output=True,
                                      text=True, timeout=25, check=False)
        except Exception:
            from cloud_run_common import InvalidPreparation
            raise InvalidPreparation('provider transport failed') from None
        require(response.returncode == 0, 'provider transport failed')
        payload, separator, status = response.stdout.rpartition('\n')
        require(bool(separator) and re.fullmatch('[0-9]{3}', status) is not None,
                'invalid provider HTTP response')
        require(200 <= int(status) < 300, 'provider HTTP request failed')
        try:
            value = json.loads(payload)
        except Exception:
            from cloud_run_common import InvalidPreparation
            raise InvalidPreparation('invalid provider JSON response') from None
        require(isinstance(value, dict) and 'data' in value and 'error' not in value,
                'invalid provider response')
        return value

    def instance(self, instance_id):
        values = self.request('instances')['data']
        require(isinstance(values, list), 'invalid provider instance list')
        items = [item for item in values if item.get('id') == instance_id]
        require(len(items) <= 1, 'ambiguous provider instance identity')
        if not items:
            return {'instance_id': instance_id, 'status': 'terminated'}
        item = items[0]
        kind = item.get('instance_type', {})
        specs = kind.get('specs', {})
        value = {'instance_id': item['id'], 'name': item.get('name'), 'type': kind.get('name'),
                 'gpu_type': kind.get('gpu_description'), 'gpu_count': specs.get('gpus'),
                 'region': item.get('region', {}).get('name'), 'status': item.get('status'),
                 'public_ip': item.get('ip'), 'hourly_rate': kind.get('price_cents_per_hour', 0) / 100,
                 'cpu': specs.get('vcpus'), 'ram_gib': specs.get('memory_gib'), 'storage_gib': specs.get('storage_gib')}
        return safe_metadata({k: v for k, v in value.items() if v is not None})

    def terminate(self, instance_id):
        # Deliberately discard the full termination response.
        self.request('instance-operations/terminate', {'instance_ids': [instance_id]})


def utc():
    return datetime.now(timezone.utc).isoformat()


def watch(provider, instance_id, rate, running_epoch, directory, sleep=time.sleep, now=time.time):
    directory = Path(directory)
    limits = budget_deadlines(rate, running_epoch)
    write_json(directory / 'WATCHDOG_ARMED.json', {'instance_id': instance_id, 'pid': os.getpid(),
               'armed_utc': utc(), 'hourly_rate': rate, **limits})
    requested = None
    while True:
        current = now()
        if current >= limits['soft_epoch']:
            write_json(directory / 'SOFT_BUDGET_REACHED.json', {'estimated_usd': (current-running_epoch)*rate/3600})
        if requested or current >= limits['terminate_epoch'] or (directory / 'TERMINATE_REQUEST').exists():
            if requested is None:
                requested = utc()
            try:
                state = provider.instance(instance_id)
                if state['status'] == 'terminated':
                    write_json(directory / 'TERMINATION_VERIFIED.json', {'instance_id': instance_id,
                        'termination_requested_utc': requested, 'termination_verified_utc': utc(),
                        'status': 'terminated', 'hourly_rate': rate, 'metadata': safe_metadata(state),
                        'estimated_total_usd': max(0, now()-running_epoch)*rate/3600})
                    return
                provider.terminate(instance_id)
            except Exception as exc:
                write_json(directory / 'TERMINATION_RETRY.json', {'instance_id': instance_id,
                    'error_type': type(exc).__name__, 'termination_requested_utc': requested,
                    'ceiling_at_risk': now() >= limits['ceiling_epoch']})
        write_json(directory / 'WATCHDOG_HEARTBEAT.json', {'epoch': now(), 'termination_requested': requested is not None})
        sleep(10)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', action='store_true')
    parser.add_argument('--instance-id', required=True)
    parser.add_argument('--hourly-rate', type=float, required=True)
    parser.add_argument('--running-epoch', type=float, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--credential-file', type=Path)
    args = parser.parse_args(argv)
    require(args.arm, 'watchdog requires explicit arm')
    require(re.fullmatch('[a-f0-9]{32}|[a-f0-9-]{36}', args.instance_id), 'invalid instance ID')
    load_credential(args.credential_file)
    watch(LambdaTermination(args.credential_file), args.instance_id, args.hourly_rate, args.running_epoch, args.directory)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'watchdog_failed': True, 'error_type': type(exc).__name__}))
        raise SystemExit(2)
