"""Seeded generators of synthetic test bundles in the published input format.

Standard library only. Never imports Shimmer's code: the audit that checks every
generated figure is this package's own (audit.py, textrules.py). See README.md.
"""
from . import bundle
from . import family_declaration
from . import family_ledger
from . import family_provisions
from . import family_result_sheet
from . import family_statement
from . import family_terms

FAMILIES = {
    "f1": family_result_sheet,
    "f2": family_declaration,
    "f3": family_statement,
    "f4": family_terms,
    "f5": family_provisions,
    "f6": family_ledger,
}


def build_spec(family, seed, **options):
    return FAMILIES[family].build(int(seed), **options)


def generate(family, seed, **options):
    """Build and self-validate one test; raises bundle.ValidationError, writes nothing."""
    return bundle.generate(build_spec(family, seed, **options))
