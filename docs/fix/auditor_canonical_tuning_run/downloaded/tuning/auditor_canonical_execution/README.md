# Auditor canonical execution binding

This is an execution package for the unchanged frozen canonical Auditor V2,
authorized by attachment `ea56d7c9-febe-421d-9f5d-817905c15c81`. It is not a new
dataset design. `source_binding.json` binds the original mixed-role dataset,
canonical split, Auditor config, frozen release and exact 300 exported Auditor
row identities. Producer rows and all noncanonical folds are excluded from the
remote bundle. The frozen source release remains unchanged.

Canonical TRAIN/DEV are 240/60, balanced 48/12 per relation class. Run exactly
120 optimizer updates, with durable checkpoints and fresh complete DEV at 60
and 120. Seed 7, rank8/alpha16/dropout0.05, AdamW LR1e-4, two passes, objective,
tokenizer, prompts, ceilings (1056 sequence/192 generation), and every quality
gate remain frozen. Initial adapter is fresh; no historical adapter is loaded.

The scoped runtime adapts only role, cap and checkpoint metadata from V2.1 and
removes its historical traced-reference and checkpoint120-specific harness.
State restoration, nullable configuration handling and cache observation
mechanisms retain the original AST/bytes, verified by offline tests. The
actual pinned base is LlamaForCausalLM despite its Phi naming. Real model/cache
compatibility must pass on the one authorized A10; no runtime rescue/retry.

No Auditor control IDs existed in V2. Before launch this binding fixes one
canonical DEV ID per relation class, choosing the first in frozen DEV order,
and runs two optimized duplicate passes plus two cache probes at each
checkpoint. All prompt/token/decoded/semantic/stop results must match. All
timings must be positive and finite. No Producer-specific speed gate or
historical observer-removal ratio is imposed. Full DEV uses 60 fresh outputs.
Total generation calls: 144. Quality eligibility and tie-break come directly
from the original selection_rules.json. Adapter tie-break uses the original
hash of the adapter/config hash mapping, not an altered ranking rule.

Evaluation state and RNG are fingerprinted and restored before the second
training pass. Raw rows are flushed and fsynced before scoring. CUDA training
telemetry and per-second CPU/GPU/RAM telemetry are persisted, with sampling in
a separate process. No Producer model, protected targets, other folds, or
governance-system execution is reachable through the authorized worker scope.
Shared pure contract/semantic helper modules are included without any benchmark
datasets or Producer model/data payloads.

Maintained Auditor encode, contract, metric, grouped split and canonical-plan
primitives are exercised locally. The old aggregate dry-run entry point is
not invoked because it also enumerates Producer/folds1-4 and opens protected
metadata. Frozen hashes are checked separately, using the already preserved
metadata receipts for protected artifacts. No protected target is opened.

One Lambda Cloud gpu_1x_a10 only; prefer us-east-1; no substitute or second
instance. Query current price before launch. Soft/hard budgets are $1.50/$3;
reserve ten minutes for collection/teardown. Conservative planning assumes
15-minute setup, 10-second updates and 6 output tok/s with every output at cap,
plus ten-minute reserve: 7308 seconds, $2.6187 at $1.29/hour. The 6 tok/s value
is a planning assumption, not measured Auditor performance or a quality gate.
Measured remaining-work projections run at each durable boundary and again
after the soft budget. A separate local watchdog enforces termination before
the hard ceiling. Any inability to complete validly yields INDETERMINATE.

Archive download and local SHA verification precede termination. Confirm empty
inventory and remove ephemeral SSH registration/keys before long local analysis.
No push. Producer LoRA remains closed; Producer checkpoint168 is preserved and
unexecuted. No protected evaluation or subsequent governed system test is
authorized by this run.
