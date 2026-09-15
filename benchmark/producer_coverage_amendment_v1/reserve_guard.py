"""Prevent the observed easy-reserve fallback in future selections.
The frozen attempted selection and reviews remain immutable; this does not rerun them.
"""
import select_population as selector

def compliant_reserve(rows,requested,initial=()):
    return selector.choose([r for r in rows if r['features']['substantive']],requested,initial)
