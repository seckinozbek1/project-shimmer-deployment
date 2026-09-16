"""Required future remote handoff, with injected evidence/teardown operations.

This module has no provider client or model loader. The separately authorized
controller supplies callbacks that persist evidence and collect/terminate.
"""
from eval_runtime import owned_configuration_fields

def run(session, model, torch_api, persist, collect_and_terminate):
    """Run once after verified load, before cache probe; abort on any failure."""
    inventory = []
    try:
        inventory = [dict(module_index=index, attribute=name, is_none=value is None,
                          type=type(value).__module__+'.'+type(value).__qualname__)
                     for _,name,value,index in owned_configuration_fields(model)]
        receipt = session.preflight_context(model, torch_api)
        persist(receipt)
        return receipt
    except BaseException as exc:
        try:
            persist(dict(name='REAL_RUNTIME_CONTEXT_PREFLIGHT', passed=False,
                         decision='NO_GO', owned_config_fields=inventory,
                         error_type=type(exc).__name__, generation_calls=0))
        finally:
            collect_and_terminate()
        raise
