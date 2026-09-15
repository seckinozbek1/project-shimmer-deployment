"""Explicit bounded-experiment provider actions. Only allowlisted data leaves this module."""
import json
import re
import shutil
import subprocess

from cloud_run_common import InvalidPreparation, require, safe_metadata
from cloud_run_watchdog import LambdaTermination, load_credential


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}|[a-f0-9-]{36}', value), 'invalid provider identifier')
    return value


def label(value):
    require(isinstance(value, str) and len(value) <= 128 and re.fullmatch(r'[A-Za-z0-9 ._()+-]+', value), 'invalid provider label')
    return value


def project_response(endpoint, raw):
    """Endpoint-specific allowlists; unknown fields and every unneeded subtree drop."""
    if endpoint == 'instance-types':
        result = []
        for value in raw.values():
            kind = value['instance_type']; specs = kind['specs']
            if specs.get('gpus') != 1:
                continue  # This controller can only rent a single-GPU instance.
            metadata = safe_metadata(dict(type=kind['name'], gpu_type=kind['gpu_description'],
                gpu_count=specs['gpus'], cpu=specs['vcpus'], ram_gib=specs['memory_gib'],
                storage_gib=specs['storage_gib'], hourly_rate=kind['price_cents_per_hour']/100))
            result.append(dict(metadata=metadata, architecture=label(kind.get('architecture','x86_64')),
                regions=[label(r['name']) for r in value['regions_with_capacity_available']]))
        return result
    if endpoint == 'images':
        return [dict(id=identifier(v['id']), family=label(v['family']), version=label(v['version']),
                     architecture=label(v['architecture']), region=label(v['region']['name'])) for v in raw]
    if endpoint == 'ssh-keys':
        return [dict(id=identifier(v['id']), name=label(v['name'])) for v in (raw if isinstance(raw,list) else [raw])]
    if endpoint == 'instance-operations/launch':
        require(len(raw['instance_ids'])==1, 'launch did not return exactly one instance')
        return dict(instance_ids=[identifier(raw['instance_ids'][0])])
    # DELETE and termination responses contain no necessary information.
    return {}


class LambdaExperiment(LambdaTermination):
    def request(self, endpoint, body=None, method=None):
        if endpoint in ('instances','instance-operations/terminate'):
            require(method is None, 'invalid method')
            return super().request(endpoint, body)
        deleting=endpoint.startswith('ssh-keys/') and method=='DELETE' and body is None
        if deleting:identifier(endpoint.split('/')[1])
        require(deleting or (endpoint in ('instance-types','images','ssh-keys') and method is None)
                or (endpoint=='instance-operations/launch' and method is None), 'provider operation not allowed')
        if endpoint=='instance-operations/launch':
            require(isinstance(body,dict) and set(body)=={'region_name','instance_type_name','ssh_key_names','quantity','name','image'}
                    and body['quantity']==1 and len(body['ssh_key_names'])==1, 'exactly one bounded launch required')
        stage='transport'
        try:
            executable=shutil.which('curl.exe') or shutil.which('curl')
            require(executable is not None, 'curl unavailable')
            value=load_credential(self.credential_file)
            config='header = "Authorization: Bearer '+value.replace('\\','\\\\').replace('"','\\"')+'"\n'
            args=[executable,'--disable','--silent','--proto','=https','--connect-timeout','10','--max-time','20','--config','-','--write-out','\n%{http_code}']
            if method:args+=['--request',method]
            if body is not None:args+=['--header','Content-Type: application/json','--data-binary',json.dumps(body)]
            response=subprocess.run(args+['https://cloud.lambda.ai/api/v1/'+endpoint],input=config,capture_output=True,text=True,timeout=25)
            payload,sep,status=response.stdout.rpartition('\n')
            require(response.returncode==0 and sep and status in ('200','201','204'), 'provider request failed')
            if status=='204':return {'data': {}}
            stage='response parsing'
            raw=json.loads(payload)
            require(isinstance(raw,dict) and 'data' in raw and 'error' not in raw, 'provider response failed')
            stage='allowlist projection'
            projected=project_response(endpoint,raw['data'])
            del raw,payload,response
            return {'data':projected}
        except Exception:
            # Never propagate a library exception or a raw response through an error.
            raise InvalidPreparation('provider experiment request failed during '+stage) from None
