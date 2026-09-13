"""Read-only routing projection. Missing evidence never means a zero-call review."""
from __future__ import annotations

import json
from pathlib import Path

import run_completion


def read_activation(run_dir, run_id):
    path = Path(run_dir) / "audit" / "agent_activation.json"
    result = {"run_id": run_id, "recorded": False, "availability": "not_recorded",
              "activation_mode": None, "agent_states": [], "decisions": []}
    completion = run_completion.read(run_dir)
    result["completion"] = (completion if completion and completion.get("run_id") == run_id else None)
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("unsupported schema")
        if data.get("run_id") != run_id:
            result["availability"] = "run_identity_mismatch"
            return result
        if data.get("activation_mode") not in {"dense", "sparse"}:
            raise ValueError("unsupported profile")
        agents, rows, states = data["agents"], data["decisions"], data["agent_states"]
        if (not isinstance(agents, list) or not all(isinstance(a, str) for a in agents)
                or len(set(agents)) != len(agents) or not isinstance(rows, list)
                or not isinstance(states, list)):
            raise ValueError("invalid roster")
        for row in rows:
            if (not isinstance(row, dict) or row.get("agent") not in agents
                    or type(row.get("actual_call")) is not bool
                    or type(row.get("eligible")) is not bool
                    or type(row.get("activated")) is not bool
                    or (row["activated"] and not row["eligible"])
                    or (row["actual_call"] and not row["activated"])
                    or not isinstance(row.get("reason"), str)
                    or not isinstance(row.get("state"), str)):
                raise ValueError("invalid decision")
        if (len(states) != len(agents) or not all(isinstance(s, dict) for s in states)
                or {s.get("agent") for s in states} != set(agents)):
            raise ValueError("invalid states")
        for state in states:
            own = [r for r in rows if r["agent"] == state["agent"]]
            if (type(state.get("actual_calls")) is not int
                    or state["actual_calls"] != sum(r["actual_call"] for r in own)
                    or state.get("state") != (own[-1]["state"] if own else "phase_not_reached")
                    or (own and type(state.get("eligible")) is not bool)
                    or state.get("eligible") != (own[-1]["eligible"] if own else None)
                    or type(state.get("activated")) is not bool
                    or state["activated"] != any(r["activated"] for r in own)):
                raise ValueError("inconsistent aggregate")
    except (OSError, ValueError, KeyError, TypeError):
        result["availability"] = "unreadable_or_invalid"
        return result
    result.update(recorded=True, availability="recorded", activation_mode=data["activation_mode"],
                  agent_states=[{k: s.get(k) for k in ("agent", "state", "eligible", "activated", "actual_calls")}
                                for s in states],
                  decisions=[{k: r.get(k) for k in ("decision_id", "agent", "eligible", "activated",
                             "reason", "state", "actual_call", "call_id", "outcome", "truncated",
                             "recovered", "source_phase", "doc_id", "trigger_source", "decision_kind",
                             "refire_count", "refire_limit", "downstream_consumer", "evidence")}
                             for r in rows])
    return result
