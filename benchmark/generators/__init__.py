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

# A seed whose own draw cannot make a valid test is retried inside the build, from a
# sub-seed derived from the seed and the attempt number alone (wordlists.make_rng), so
# the retry sequence depends only on the seed. Attempt 0 is the seed's own draw: a seed
# that builds at attempt 0 gives exactly the bytes it gave before retries existed.
MAX_ATTEMPTS = 20


def build_spec(family, seed, attempt=0, **options):
    spec = FAMILIES[family].build(int(seed), attempt=attempt, **options)
    spec["attempt"] = attempt
    return spec


def generate(family, seed, **options):
    """Build and self-validate one test; raises bundle.ValidationError, writes nothing.
    A draw that cannot be built (ValueError) or that fails validation is retried with
    the next derived sub-seed, up to MAX_ATTEMPTS; the key's `generator.attempt` and
    the suite listing record the attempt that was kept."""
    failures = []
    for attempt in range(MAX_ATTEMPTS):
        try:
            return bundle.generate(build_spec(family, seed, attempt=attempt, **options))
        except (ValueError, bundle.ValidationError) as exc:
            failures.append("attempt %d: %s" % (attempt, str(exc).splitlines()[0][:200]))
    raise bundle.ValidationError("%s seed %s: no valid test in %d attempts:\n  %s"
                                 % (family, seed, MAX_ATTEMPTS, "\n  ".join(failures)))
