"""The GNN's persisted state, readable without importing torch.

WHY THIS MODULE EXISTS. `state_summary` reads a JSON file and counts what is in
it. It needs no tensor library, and it lived in `ontology_candidates`, which
imports torch at module scope for the candidate finder. Any reader of the state
therefore paid for torch, and a caller that cannot import torch could not read
the state at all: the console's own preview harness stubs `subprocess.Popen`,
torch's import path calls it, and `GET /ontology/gnn` returned a 500, which the
console dutifully rendered as an empty section. The one section whose whole
purpose is to stay visible when the state is absent was the section that
disappeared.

Found by looking at the rendered page rather than at the source, which is the
only way this class of failure shows itself.

The three honesty fields travel from here, so every reader of the state gets
them whether or not it can load a model: with no Tier-2 signal the engine has
learned nothing, and anything ranked from this state rests on graph structure
alone.

Deterministic, local, stdlib only, no model, no tensor library.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "ontology" / "stores" / "gnn_state.json"

RANKED_ON_STRUCTURE = ("graph structure only (node type, degree, edges); the Tier-2 "
                       "signal is empty, so nothing here is learned relevance")


def load_state(state_path=None):
    """The persisted state as a dict, or None when it has never been written."""
    p = Path(state_path) if state_path else DEFAULT_STATE_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def state_summary(state_path=None):
    """What the GNN's persisted state holds, for the read path.

    Structural metadata only: the state file holds weights and counts and no raw
    content by construction, and this surfaces the counts, never the weights.
    Reports the absence of a Tier-2 signal as a first-class field rather than a
    caveat in prose, because that absence is the single most important thing
    about this state.
    """
    prior = load_state(state_path)
    if not prior:
        return {
            "exists": False,
            "tier2_signal": "empty",
            "learned_relevance": False,
            "ranked_on": RANKED_ON_STRUCTURE,
            "note": ("no GNN state has been written; the state is created at the end of "
                     "a run, and no run has been made since the store was scoped"),
        }
    return {
        "exists": True,
        "schema": prior.get("schema"),
        "tier": prior.get("tier"),
        "scope": prior.get("scope"),
        "feature_dim": prior.get("feature_dim"),
        "hidden": prior.get("hidden"),
        "trained_count": prior.get("trained_count"),
        "n_updates": prior.get("n_updates"),
        "last_delta_size": prior.get("last_delta_size"),
        "last_loss": prior.get("last_loss"),
        "last_device": prior.get("last_device"),
        "weights_persisted": bool(prior.get("encoder_weight")),
        "tier2_signal": "empty",
        "learned_relevance": False,
        "ranked_on": RANKED_ON_STRUCTURE,
        "claim": prior.get("claim"),
    }
