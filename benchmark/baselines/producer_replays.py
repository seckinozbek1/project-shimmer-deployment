"""The producer backend's two replays of D-S57 (lane producer): their prompts files
and their bars, written before any run. No model; reads saved reply records only.

  roles (D-S57 items 1 and 3: the tuned producer against its own base on the other roles)
      py -3.12 benchmark/baselines/producer_replays.py roles --records-root external/s05 \
          --runs L7,L8,L10,L11,L12,L12b --per-agent 30 --out <dir>
    In final mode every local_producer role runs on the tuned producer, checkpoint 168's adapter
    included (agent_wrapper._load_local), though 168 was trained on PROCESSOR's compact
    extraction only. This takes, for each other producer role with saved prompts (ROLE_AGENTS),
    its distinct saved prompts (one call per prompt digest), every one whose call the run refused
    and then the rest in the order of SHA-256 of SEED plus the digest, up to --per-agent, and
    writes <dir>/replay_prompts.json as a roles file (replay_prompts.py extract --checkpoints
    tuned,base: each prompt on both checkpoints) with <dir>/call_ids.json and <dir>/bar.json.

  editor-clerk (D-S57 item 1: EDITOR_CLERK's envelope constraint on the model; DECODING-B)
      py -3.12 benchmark/baselines/producer_replays.py editor-clerk --records-root external/s05 \
          --runs L7,L8,L10,L11,L12,L12b --out <dir>
    Every distinct saved EDITOR_CLERK prompt, labelled `valid`, `failed` (a contract violation)
    or `stamped` (accepted only by the removed K8 kind stamp, read as
    tools/envelope_decoding_measure.py reads it), as an envelope file (extract --agents
    EDITOR_CLERK), with <dir>/call_ids.json and <dir>/bar.json (R2's rules A to D, D-117).

Both read only identifiers, digests, outcomes and the observation log's normalisation marks;
never a prompt's or a reply's text (replay_prompts.extract copies the prompt text into the
prompts file, as for R1 and R2). A folder under benchmark/keys/ is never read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT / "scripts"), str(HERE), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replay_prompts  # noqa: E402

SEED = "20261108:producer-roles:"
# The producer roles other than PROCESSOR whose prompts B3 runs saved (L7 to L12b). STYLE_GUARDIAN,
# AMENDMENT_DRAFTER, EDITOR_HEAD_OF_UNIT and EDITOR_HEAD_OF_SECTION have no saved local call.
ROLE_AGENTS = ("ARCHIVIST", "CITATION_RESOLVER", "EDITOR_CLERK", "INST_FINDER", "LEGAL_ANALYST", "SPEECH_ACT_TAGGER")
FAILED = "contract_violation"
# The level every sign test of these bars is read at (D-235's, as for C and T).
LEVEL = 0.0125


def folders(records_root, runs):
    """Every model_replies folder under each named run, in run order then path order."""
    found = []
    for run in runs:
        base = Path(records_root) / run
        if not base.is_dir():
            raise ValueError("no run folder " + str(base))
        found += sorted(p for p in base.rglob("model_replies") if p.is_dir())
    if not found:
        raise ValueError("no model_replies folder under the runs named")
    return found


def stamped_calls(folder):
    import envelope_decoding_measure
    return envelope_decoding_measure.stamped_calls(folder)


def distinct_calls(found, agents):
    """{(agent, prompt digest): {call_id, folder, status}} for the agents' local_producer calls
    whose rendered prompt was saved, the first call of each digest kept; status `failed` when any
    call of that digest was refused, `stamped` when one was accepted only by the kind stamp."""
    import reply_records
    kept = {}
    for folder in found:
        replay_prompts._refuse_keys(folder)
        outcomes = reply_records.outcomes(folder)
        stamped = stamped_calls(folder)
        for row in reply_records.records(folder):
            payload = row.get("payload") or {}
            if (row.get("backend") != "local_producer" or row.get("agent") not in agents
                    or payload.get("form") != "rendered_prompt" or not isinstance(payload.get("text"), str)):
                continue
            key = (row["agent"], payload.get("sha256"))
            status = ("failed" if outcomes.get(row.get("call_id")) == FAILED
                      else "stamped" if row.get("call_id") in stamped else "valid")
            entry = kept.setdefault(key, {"call_id": row.get("call_id"), "folder": str(folder), "status": status})
            rank = {"valid": 0, "stamped": 1, "failed": 2}
            if rank[status] > rank[entry["status"]]:
                entry["status"] = status
    return kept


def _order(digest):
    return hashlib.sha256((SEED + str(digest)).encode("utf-8")).hexdigest()


def select_roles(kept, per_agent):
    """Per agent: every refused or stamped prompt, then the rest by _order, up to per_agent."""
    chosen = []
    for agent in ROLE_AGENTS:
        mine = [(digest, v) for (a, digest), v in kept.items() if a == agent]
        mine.sort(key=lambda dv: (dv[1]["status"] == "valid", _order(dv[0])))
        chosen += [dict(v, agent=agent, prompt_sha256=d) for d, v in mine[:per_agent]]
    return chosen


ROLES_BAR = {
    "schema": "producer-roles-replay-bar-v1",
    "decision": "recorded by the lead in docs/loop/DECISIONS.md before sealing",
    "question": ("On the other producer roles' own saved prompts, does checkpoint 168's adapter (which every "
                 "local_producer role loads in final mode) keep, raise or lower the share of replies that pass "
                 "the role's own contract, against the same base with no adapter?"),
    "paths": ["sdpa"],
    "checkpoints": ["tuned", "base"],
    "rules": {
        "A_determinism": ("The tuned rows reproduce the saved reply byte for byte (reference) on at least 95 percent "
                          "of the tuned rows, every exception listed; below that the comparison is void and no rule "
                          "below is read. A saved call that ran under the envelope constraint with an intervention "
                          "(one ARCHIVIST call of the 180 when this bar was written) is replayed without it and is "
                          "expected to differ; it is listed, not excused from the count."),
        "B_per_role": ("For each role, the discordant pairs are a_only_valid (tuned valid, base not) and "
                       "b_only_valid (base valid, tuned not). With n = their sum, the base is better when "
                       "b_only_valid > a_only_valid and the one-sided sign test P(X >= b_only_valid | n, 1/2) is at "
                       "most LEVEL; the tuned producer is better in the mirror case; otherwise no difference is "
                       "shown. n below 6 cannot reach LEVEL and is reported as too few."),
        "C_cost": ("Per role and checkpoint the replies that ran to their allowance and the output tokens are "
                   "reported beside B; a checkpoint is not called better on a role where it runs to the "
                   "allowance on more prompts and B shows no difference."),
        "D_failures": ("A failure (out of memory, refused kernel, prompt over context) on either side removes that "
                       "pair from B and is reported by kind."),
    },
    "decides": {
        "base_better_on_a_role": ("A decision proposing that role be served by the base with the adapter disabled "
                                  "for its calls, built and measured again through the pipeline's own call path "
                                  "before adoption; nothing changes in the product from this replay alone."),
        "tuned_better_or_no_difference": "No change; 168 keeps serving every producer role.",
        "every_case": ("These prompts are the no-regression set of the PROCESSOR training candidate "
                       "(docs/loop/PRODUCER_TRAINING_PLAN.md): the candidate is not adopted if it is worse than 168 "
                       "on any role by rule B."),
    },
    "not_measured": ("Contract validity only. Whether a valid reply is RIGHT needs gold these saved prompts do not "
                     "have; no content-quality claim is made from this replay. STYLE_GUARDIAN, AMENDMENT_DRAFTER, "
                     "EDITOR_HEAD_OF_UNIT and EDITOR_HEAD_OF_SECTION have no saved local call and are not covered."),
    "level": LEVEL,
}

EDITOR_CLERK_BAR = {
    "schema": "editor-clerk-constraint-replay-bar-v1",
    "decision": "recorded by the lead in docs/loop/DECISIONS.md before sealing",
    "question": ("Does EDITOR_CLERK's envelope constraint (DECODING-B, config/envelope_decoding.json, adopted on "
                 "saved replies only at the S5 close) hold on the model, as ARCHIVIST's did in R2b?"),
    "paths": ["sdpa", "sdpa_constrained"],
    "rules": {
        "A_mechanism": ("Every constrained reply with 0 interventions is byte-identical to its sdpa reply; 0 dead "
                        "ends."),
        "B_valid_set": ("On the `valid` set sdpa reproduces the saved reply byte for byte (exceptions listed), and "
                        "under the constraint every prompt has 0 interventions and passes its validator."),
        "C_no_harm": ("No prompt valid under sdpa is invalid under the constraint; peak GPU memory of the two paths "
                      "equal within 5 percent."),
        "D_failures": ("On the `failed` and `stamped` sets sdpa reproduces the saved reply and the validator refuses "
                       "it (a stamped reply lacks `kind`); under the constraint each gets an intervention; the count "
                       "made valid is the fix rate, reported with the key the model writes in kind's place left "
                       "unknown until read."),
    },
    "decides": {"A_B_C_hold": "The constraint stays adopted for EDITOR_CLERK, now measured on the model.",
                "otherwise": "A decision names the rule that failed; the constraint is withdrawn for EDITOR_CLERK "
                             "only if C fails."},
}


def write_selection(out, chosen):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "call_ids.json").write_text(json.dumps(chosen, indent=2) + "\n", encoding="utf-8")
    return out


def counts(chosen, key):
    found = {}
    for c in chosen:
        found.setdefault(c[key], {}).setdefault(c["status"], 0)
        found[c[key]][c["status"]] += 1
    return found


def roles(records_root, runs, per_agent, out):
    found = folders(records_root, runs)
    kept = distinct_calls(found, set(ROLE_AGENTS))
    chosen = select_roles(kept, int(per_agent))
    out = write_selection(out, chosen)
    used = sorted({c["folder"] for c in chosen})
    value = replay_prompts.extract(used, out / "replay_prompts.json", checkpoints=["tuned", "base"],
                                   call_ids={c["call_id"]: c["agent"].lower() for c in chosen})
    bar = dict(ROLES_BAR, runs=list(runs), per_agent=int(per_agent), seed=SEED,
               distinct_saved={a: sum(1 for (x, _) in kept if x == a) for a in ROLE_AGENTS},
               selected=counts(chosen, "agent"), prompt_count=value["prompt_count"],
               prompts_sha256=hashlib.sha256((out / "replay_prompts.json").read_bytes()).hexdigest())
    (out / "bar.json").write_text(json.dumps(bar, indent=2) + "\n", encoding="utf-8")
    return bar


def editor_clerk(records_root, runs, out):
    found = folders(records_root, runs)
    kept = distinct_calls(found, {"EDITOR_CLERK"})
    chosen = [dict(v, agent=a, prompt_sha256=d) for (a, d), v in sorted(kept.items(), key=lambda kv: _order(kv[0][1]))]
    out = write_selection(out, chosen)
    used = sorted({c["folder"] for c in chosen})
    value = replay_prompts.extract(used, out / "replay_prompts.json", agents={"EDITOR_CLERK"},
                                   call_ids={c["call_id"]: c["status"] for c in chosen})
    bar = dict(EDITOR_CLERK_BAR, runs=list(runs), selected=counts(chosen, "agent"), prompt_count=value["prompt_count"],
               prompts_sha256=hashlib.sha256((out / "replay_prompts.json").read_bytes()).hexdigest())
    (out / "bar.json").write_text(json.dumps(bar, indent=2) + "\n", encoding="utf-8")
    return bar


def main(argv=None):
    parser = argparse.ArgumentParser(prog="producer_replays.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("roles", "editor-clerk"):
        sub = commands.add_parser(name, allow_abbrev=False)
        sub.add_argument("--records-root", required=True)
        sub.add_argument("--runs", required=True)
        sub.add_argument("--out", required=True)
        if name == "roles":
            sub.add_argument("--per-agent", type=int, required=True)
    args = parser.parse_args(argv)
    runs = [r for r in args.runs.split(",") if r]
    try:
        bar = (roles(args.records_root, runs, args.per_agent, args.out) if args.command == "roles"
               else editor_clerk(args.records_root, runs, args.out))
    except (ValueError, OSError) as exc:
        print("producer_replays stopped: %s" % exc, file=sys.stderr)
        return 4
    print(json.dumps({k: bar[k] for k in ("prompt_count", "selected", "prompts_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
