# Shimmer threat model

State: this HEAD, the `productization` branch after STEP 11 of the polish chain.
Written from what was verified in the code, with citations, not from intent.

**Scope note.** The `/polish` step that commissioned this document referred to
"the audit's section M table". No section M or N exists in the audit at this
HEAD: `docs/audit/REALITY_MAP_P1..P4_7372321.md` are sectioned numerically
(P4 runs 4.1 to 4.7). `NOT FOUND (searched: "^## ", "^### ", "threat", "§M",
"§N", "backup" across docs/audit/ and docs/fix/)`. This document is therefore
built from the audit's actual content, cited per row: the state and persistence
inventory (`REALITY_MAP_P4_7372321.md` 4.1), secrets (4.4), the egress inventory
(4.5), and what this chain verified directly in STEPs 7 to 11.

**What Shimmer is, for threat-modelling purposes.** A local, single-operator
document-processing swarm on one machine, optionally reachable by ONE named
collaborator through a token-gated FastAPI dock behind a temporary tunnel. It
spends real money per run on third-party model APIs, holds an append-only
governance record, and handles documents the operator may have declared
sensitive. It is not multi-tenant, has no user accounts, and does not run
unattended.

---

## 1. Assets, ranked by what their loss costs

| Asset | Where | Why it matters | Regenerable? |
|---|---|---|---|
| API keys | OUTSIDE the repository, via `$SHIMMER_CONFIG_PATH`, a sibling `../api_keys/config.py`, or the `.env_path` pointer (`REALITY_MAP_P4` 4.1 secrets row, 4.4) | direct financial loss and impersonation; a leaked key spends until rotated | rotate at the provider |
| Sensitive document content | `input/`, `output/runs/<run>/`, and in transit to `api.anthropic.com` / `api.openai.com` (`REALITY_MAP_P4` 4.5) | LAW-IV: a single leak is irreversible | no |
| Governance record | `durable/governance/` (model approvals, constitution-guard log, redaction waivers, sensitivity overrides, the LAW-IV exposure ledger, redaction format warnings; paths in `scripts/durable_paths.py:72-77`) | the only evidence of what was approved, waived or exposed, and by whom | **no** |
| The constitution | `config/constitution.json`, append-only, guarded by `scripts/constitution_guard.py` | the authority the whole system derives from | no |
| Cross-run learning | `ontology/stores/*.jsonl` (append-masters), `durable/learnings/`, `durable/reference/` | accumulated work; `graph.json` and `gnn_state.json` rebuild from the JSONL masters | masters: **no**. Derived: yes |
| The access token | in the operator's and the collaborator's hands; only its SHA-256 hash is in the server's environment | grants the ability to spend money and download deliverables | mint a new one |
| Deliverables | `output/runs/<run>/deliverables/` | the product | re-runnable at full cost |

The two **non-regenerable** trees are `durable/` and `ontology/stores/`. Until
STEP 11 there was no backup mechanism for them at all. There is now:
`scripts/backup_state.py` (see `docs/RUNBOOK.md` sections 10 and 11).

---

## 2. Trust boundaries

1. **Operator to system.** The operator is SOVEREIGN under LAW-0. The guard
   never hard-blocks the operator; it confirms and proceeds, or logs and
   proceeds. This is deliberate and load-bearing: a guard that cages the
   operator inverts LAW-0. It also means the operator is trusted, and an
   operator mistake is inside the trust boundary, not outside it.
2. **Agents to governed structure.** Agents can NEVER amend governed structure.
   A signature-carrying agent DELTA is refused and routed to the operator
   (`scripts/constitution_guard.py`). Agents propose; the operator ratifies.
3. **Network to server.** Everything except `GET /health` and the console shell
   `GET /console` requires a Bearer token whose SHA-256 matches
   `SHIMMER_TOKEN_HASH` (`scripts/server.py:273-276`, gate check 104).
4. **System to model providers.** Prompts, and therefore document text, leave
   the machine on every cloud call (`REALITY_MAP_P4` 4.5). This is the boundary
   LAW-IV governs, and the one the outbound masking layer exists to police.
5. **Local model.** The Qwen redactor runs in-process via `transformers`, on
   local hardware. No Ollama, no HTTP model server (`REALITY_MAP_P4` 4.5, both
   `NOT FOUND` rows).

---

## 3. Threats, current mitigation, residual risk

Ordered by residual risk, highest first.

### T1. Token compromise leads to spend and data exfiltration
**Residual risk: HIGH (accepted for a pilot).**

One shared bearer token, no accounts, no expiry, no per-caller attribution, no
rate limiting. Anyone holding it can submit runs that spend the operator's API
budget and can download any completed run's deliverables through
`GET /results/{run_id}`.

Mitigated: the token is never stored, only its SHA-256; comparison is
constant-time (`hmac.compare_digest`); the token is never placed in a URL and
the console keeps it in page memory only (gate check 109 proves the served HTML
leaks no token, key pattern or environment value); the auth boundary fails
CLOSED with no hash configured; upload caps bound a single submission
(`SHIMMER_MAX_UPLOAD_FILES`, `_MB`, `_TOTAL_MB`, gate checks 93 and 113); jobs
run one at a time, so a flood queues rather than fanning out.

Not mitigated: revocation is "restart the server with a new hash". There is no
audit trail tying a submission to a person. See section 5.

### T2. Sensitive content reaching a provider on a run the operator believed was protected
**Residual risk: MEDIUM-HIGH, and the reason the system refuses such runs.**

The full LAW-IV outbound masking layer is BUILT and WIRED (INFRA-041, ten call
sites in `scripts/pipeline.py`) but NOT ACTIVATED: `LAYER_ACTIVE` is `False`, so
every wired call site no-ops. Corrected in STEP 9; the module's own docstring
used to claim it was unwired, which understated the wiring and overstated the
protection at the same time.

Mitigated: a sensitive run HARD-STOPS rather than proceeding. Requesting one
while the layer is inactive exits 6 (`refused_sensitivity_layer_inactive`); the
operator must consciously pass `--sensitivity-layer-inactive-override` to
declare THIS run non-sensitive, and every use is written to the governance
ledger. Redaction likewise refuses to act on engine defaults: with no compiling
operator rule the run hard-stops unless `--no-redaction-override` is passed, and
that waiver is logged. An approved span is not "applied" until VERIFIED ABSENT
by a post-apply grep gate; a survivor BLOCKs (exit 5) rather than shipping.
`may_use_web` is enforced at the search boundary (gate check 42).

Not mitigated: while the layer is inactive, a run the operator declares
non-sensitive sends document text to cloud providers in full. That is the
posture, stated plainly in `README.md`. Activation is an operator DELTA.

### T3. Loss or corruption of the governance record and learning state
**Residual risk: MEDIUM (was HIGH before STEP 11).**

`durable/` and `ontology/stores/` are non-regenerable, live on one machine, and
several of their files are gitignored, so version control is not a backup
(`REALITY_MAP_P4` 4.1: `model_approvals.json`,
`constitution_guard_log.jsonl`, four `learnings/*.json` and `graph.json` are all
explicitly ignored). A disk failure, a mistaken `--reset-snapshot`, or a bad
restore loses the record of what was approved, waived or exposed.

Mitigated: `scripts/backup_state.py` copies both trees plus the three governed
config files to an operator-named destination and records a SHA-256 per file;
`--verify` re-hashes and reports MODIFIED, MISSING and EXTRA (gate check 119
proves a same-length tamper is caught, so the hash is doing the work).
`snapshot_manager` operates only on the RESETTABLE subdirs
(`cache, learnings, reference`), never on `global` or `governance`
(`durable_paths.RESETTABLE_SUBDIRS` / `PRESERVED_SUBDIRS`). Restore is a
documented manual copy, not a script that can overwrite live state on one
command.

Not mitigated: nothing SCHEDULES a backup. If the operator does not run it, it
does not happen. There is no off-site copy unless the destination folder is one.

### T4. Prompt injection through a submitted document
**Residual risk: MEDIUM.**

Documents under review are untrusted text, and they are placed directly into
agent prompts. A document can attempt to instruct an agent.

Mitigated structurally rather than by filtering: agents cannot amend governed
structure (T2 boundary 2), so a successful injection cannot change the
constitution, the registry or a model binding. Auditors are always a different
model family from producers (LAW-III, gate check 87), so one compromised family
does not self-certify. The verifiability gate downgrades an affirmative finding
that cites nothing to UNCERTAIN, flagged and kept. Every finding must cite a
CONV-* and a REF-*. Web access is per-agent gated (`may_use_web`).

Not mitigated: an injection can still degrade OUTPUT QUALITY (a fabricated
finding that carries a plausible citation), and it can attempt to induce an
agent to include content the operator would not have chosen. Nothing scans
document text for injection patterns, and doing so is not obviously a good
trade.

### T5. Cost blow-out
**Residual risk: MEDIUM-LOW.**

Every run spends real money; a loop or a retry storm spends more.

Mitigated: a pre-run projection is printed and, interactively, requires
confirmation; per-call cost is recorded with `phase` and `doc_id` dimensions and
totalled live; `config/pricing.json` prices Opus, Sonnet and Haiku as distinct
rows (before STEP 4 all Claude tiers were billed at Sonnet rates), gate check
114 now asserts the values are dated, complete per backend, non-zero for cloud
rows and strictly ordered by tier; an unknown model id is costed at the most
expensive known row for its backend and logged as a warning, never at zero;
`SHIMMER_PROVIDER_TIMEOUT_S` bounds a single call and `SHIMMER_RUN_TIMEOUT_S`
bounds a whole run; document concurrency is bounded by `--max-concurrent-docs`;
rate-limit retries are bounded (two for Claude, one for GPT) and logged as
`rate_limit_retry`.

Not mitigated: there is no spend CAP that aborts a run mid-flight when a
threshold is crossed, and no per-submitter budget. A collaborator with the token
can queue runs.

### T6. Secret leakage into the repository, a log or a report
**Residual risk: LOW.**

Mitigated: keys live outside the repository by design and are read through a
fixed allowlist; provider error strings are scrubbed before they reach a
`CallResult` or the cost log (gate check 95 embeds a synthetic key and asserts
`[REDACTED_KEY]`); `.gitignore` carries belt-and-braces patterns
(`**/config.py`, `**/*key*`, `**/*secret*`, `**/*credential*`, `**/.env*`,
`api_keys*/`); `scripts/guard_secrets.py` scans the staged diff; structured log
events are bounded by construction to a snake_case name plus whitespace-free
`key=value` pairs, and gate check 112 asserts that over every call site, so
document or prompt text cannot be smuggled into a log line; a contract-violation
dump under a sensitive run persists a SHA-256 and a length, never the raw text
(gate check 100); `GET /health` is proven to leak no `SHIMMER_` value, path or
hash (gate check 105).

Not mitigated: the pre-commit hook that runs the secret guard is **NOT
installed** in this clone (`core.hooksPath` unset, `.git/hooks/pre-commit`
absent, verified in STEP 10). Until `git config core.hooksPath .githooks` is
run, the guard only runs when someone remembers. Also: full prompts are not
logged, but a provider retains what it receives under its own policy.

### T7. Path traversal or upload abuse through the dock
**Residual risk: LOW.**

Mitigated: a caller-supplied `run_id` is validated against the server's own mint
format BEFORE any path is built, on every route that accepts one (gate check
94 proves `../..` returns 404); uploaded filenames are reduced with
`Path(name).name` so a name like `../../x` cannot escape the staging directory;
the three upload caps reject before any file is written, and the file-count
check runs before `mkdtemp` so a rejected over-count submission creates no
staging directory at all (gate checks 93, 113); an orphaned staging directory
for a job that is no longer running is removed at server import (gate check 91);
the ingestion-contract validator runs on every submission before anything enters
`input/context/`.

### T8. A governed change slipping through without ratification
**Residual risk: LOW.**

Mitigated: the amendment guard intercepts any attempt to modify or delete an
existing `amendments[]` entry or a seed law from any code path; the only allowed
change is appending a new id, and `verify_amendment_append` requires the next id
(no reuse, no gaps, no renumbering), `operator_approved`, and a clean signature
scan. `check_genesis_integrity` requires genesis Part I to mirror the guarded
seed laws, so a tampered immutable core is flagged. The operator-approval relay
never evaluates the decision it carries (gate check 107). Gate check 77 exercises
the whole route.

Residual: the signature scan is a FLAG for operator attention, with false
positives and false negatives. It is not a complete semantic guarantee and is
not claimed as one.

### T9. Supply chain
**Residual risk: LOW-MEDIUM.**

Mitigated: every dependency is now pinned to an exact version, including the
FastAPI stack that more than twenty gate checks depend on (STEP 10; before it,
`fastapi`, `uvicorn[standard]` and `python-multipart` were unpinned and a fresh
clone resolved them to whatever was newest that day). Gate check 118 asserts
every module-level third-party import under `scripts/` resolves to a pinned
entry. Model ids are read live from the provider and never hardcoded; a
deprecated model STOPS the run for operator approval rather than auto-swapping.

Not mitigated: no hash pinning (no `--require-hashes`), no lock file, no SBOM,
no vulnerability scanning. Model WEIGHTS are downloaded from Hugging Face on
first use with no pinned digest.

### T10. A gate check that passes for the wrong reason
**Residual risk: LOW, actively worked.**

The gate is the only automated proof this project has, so a check that passes
vacuously is worse than no check. STEP 8 replaced check 102's timing proxy with
a deterministic tripwire on the actual network and model-loading entry points,
plus a negative control proving the tripwire fires. STEP 8 also added the check
that builds the pipeline's real `ArgumentParser`, which immediately found that
`--operator-channel` was registered twice, so `argparse` raised at construction
and **the pipeline could not start at all** while the gate reported 113 of 113
passing. Several checks added in this chain carry explicit negative controls for
exactly this reason.

Residual: coverage is not completeness. Check 118 sees module-level imports
only; check 112 bounds log call sites statically, not at runtime; the signature
scan is a flag, not a proof. Each of those limits is stated where it lives.

---

## 4. Out of scope, deliberately

- **A hostile operator.** LAW-0 makes the operator sovereign; the design does
  not defend against the person it obeys.
- **Multi-tenancy.** No accounts, no isolation between callers, no per-tenant
  data separation. One operator, one collaborator.
- **Physical access to the machine.** Full disk encryption, screen locking and
  device security are the operator's environment, not this repository's.
- **Provider-side retention.** What Anthropic or OpenAI does with a received
  prompt is governed by their policy, not by this code. The only control here is
  not sending it.
- **Denial of service.** A single-worker queue behind a temporary tunnel is
  trivially floodable by anyone with the token. Accepted for a pilot.
- **Network interception.** The tunnel provides HTTPS; the local bind is plain
  HTTP on `SHIMMER_HOST`. Binding `0.0.0.0` without a tunnel exposes the dock on
  the LAN in the clear; use `127.0.0.1` when not tunnelling.

---

## 5. The one sentence to keep in view

A single shared bearer token behind a temporary tunnel, on one operator's
machine, with no accounts, no revocation short of a restart, no request
attribution and no scheduled backup, is a PILOT POSTURE: it is sound for one
named collaborator over a link the operator opens and closes deliberately, and
it is NOT a customer deployment posture. Real customer use needs per-user
identity, revocable credentials, request attribution, a spend cap, off-site
backups and a deployment that outlives a laptop. None of that is built, and none
of it should be inferred from the presence of a token gate.
