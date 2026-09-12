# Ledger: what the README must say, and what the image is behind on

Opened 2026-09-12. Kept because the operator moved the README pass and the image
rebuild to the end of a working run rather than before every commit (see README
section L, the discipline boundary at `9b4f027`). This is the record of what those
two deferred passes will have to catch up on, so neither has to be inferred from a
diff.

Two sections. **Owed before this run** is the backlog that already existed.
**This run** is appended to as each commit lands.

---

## Owed before this run started

Image last built at `139083a`. Seven commits have landed since. The image ships
`scripts/`, `config/`, `tools/` and `corpus_ingest/` only, so a commit touching
only `README.md` or `benchmark/` does not affect it.

| commit | what it changed | image affected |
|---|---|---|
| `dc6a271` | container figures recorded | no |
| `ce05cbd` | README figures pinned to their commit | no |
| `119bf60` | scorer checks a reason, not only a location; typed `claim` in the device key | **yes**: `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `015e062` | `quote` field on the contract; twin detector | **yes**: `config/agent_contracts.json`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `9b4f027` | advisory items withheld; typed amendments; deepening cap | **yes**: `scripts/agent_wrapper.py`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `b17c4be` | discipline boundary named | no |
| `44e3168` | quote required on absence claims, forward only | **yes**: `scripts/paired_review.py`, `scripts/pipeline.py`, `scripts/verify_session1.py` |

**Four of the seven affect the image.** The gate total moved 228 to 234 across
them, so the container figure recorded in the README (`PASS=215 SKIP=7 FAIL=6
TOTAL=228`, measured at `139083a`) is stale by six checks and will need
remeasuring, not editing.

**README items already owed from those seven:** none. Each of the seven carried
its own README pass at the time, under the pre-`9b4f027` discipline. The boundary
starts at `9b4f027`, and `b17c4be` and `44e3168` both updated the README in the
same commit. So the backlog for the README is empty and the backlog for the image
is four commits.

---

## This run

Appended as each commit lands. Format: what the README will have to say, and
whether the image is affected.

### A prediction to be checked against a real run

The quote requirement (`44e3168`) predicts that on the next run **14 judged
absence claims** (5 on the flawed twin, 9 on the clean, from the saved pairing
maps) will either carry a quote or be refused and recorded under
`absence_refused`. The 7 computed absences are Python's own arithmetic and need
no quote.

This is a falsifiable prediction about model compliance, recorded here rather
than left in a report so the next run can be checked against it. If the model
complies, `absence_refused` stays empty and 14 findings carry quotes. If it does
not, the refused count says how often, and the refusal reason says which.
