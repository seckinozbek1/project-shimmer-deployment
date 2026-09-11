"""The GNN as a candidate finder (ontology chain, job 4; decision 9's shape).

WHAT THIS PRODUCES, and the sentence to read before any other: a RANKING OVER
GRAPH STRUCTURE. With no Tier-2 signal the GNN has learned nothing, so the
embedding it ranks in is a function of the SAFE feature row (node type, degree,
stub and incomplete flags, hashed structural categoricals) propagated once over
the adjacency. Node type, degree, edges. That is a real thing and a modest one,
and it must never be presented as learned relevance. Every surface that shows a
candidate carries that qualifier: this module's own output field
(`ranked_on`), the route, the console, the report and the README.

THE SHAPE, per decision 9 and unchanged by this build:

  the graph NARROWS      this module proposes which provisions MAY relate,
  the model DECIDES      a model call decides whether they do (not built here;
                         the pairing this produces is an input to that call),
  the reasoning is TEXT  written by the model, never by a score,
  the score is SHOWN     not hidden, so a reader can see how weak it is.

The GNN never asserts a relation. It proposes a candidate set. Nothing in this
module writes a Relation record, and the deterministic baseline (job 2,
scripts/relation_extract.py) stays beside it, not replaced by it: both are scored
on the long-range corpus later and the operator chooses between them after
measurement. The baseline sets the bar, having already found the long-range
reference on a fixture.

WHY THE EXISTING ENCODER, and not a second model: gnn_update already persists an
encoder trained (in the machinery sense) over the Tier-1 graph, and building a
separate scorer would mean two things that must agree about what a node is. This
reuses the persisted weights through the same GraphAutoencoder the update path
uses, so a candidate set is always ranked in the same space the state file holds.

NOT MEASURED. No candidate set has been scored against anything. The store is
empty, so the only graphs this has run on are fixtures. Nothing here is known to
be useful; it is known to be correct on fixtures.

Deterministic and local. Imports torch (as ontology_gnn does) and loads NO
language model: a forward pass over a few hundred nodes on CPU is seconds, and is
not what the no-model standing rule is about.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

import ontology_gnn
from ontology_gnn import (DEFAULT_GRAPH_PATH, DEFAULT_HIDDEN, DEFAULT_SEED,
                          DEFAULT_STATE_PATH, FEATURE_DIM, GraphAutoencoder,
                          build_adjacency, build_features)

# The one honest description of what the ranking rests on, carried in the output so
# no consumer can render a candidate set without it.
# One definition of the qualifier, in the torch-free state module, imported here
# so the finder and the state reader can never drift apart on what they claim.
from ontology_gnn_state import RANKED_ON_STRUCTURE  # noqa: E402

# Only these node types are proposed as candidates. A candidate pair is a pair of
# PROVISIONS: proposing that a Document relates to a Convention is not the question
# decision 9 asks, and a finder that returns them would bury the pairs that matter.
CANDIDATE_NODE_TYPE = "Provision"


def _load_state(state_path):
    p = Path(state_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def embed_nodes(graph, *, state_path=None, hidden=DEFAULT_HIDDEN, seed=DEFAULT_SEED,
                device=None):
    """Run the persisted encoder over the graph and return (H, node_ids, provenance).

    H is the hidden representation, one row per node. `provenance` says whether the
    weights came from a persisted state or from a deterministic initialisation, which
    a caller must be able to report: a candidate set ranked by freshly initialised
    weights is even less than one ranked by persisted ones, and the difference must
    never be invisible.

    No backward pass, no optimiser, no state written: this READS the state the update
    path owns. A candidate finder that trained would be a second writer of the same
    weights.
    """
    dev = ontology_gnn._resolve_device(device)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    X_np, node_ids, degrees = build_features(graph)
    A_np = build_adjacency(graph, node_ids)
    model = GraphAutoencoder(FEATURE_DIM, hidden).to(dev)

    prior = _load_state(state_path if state_path else DEFAULT_STATE_PATH)
    weights_from = "initialised"
    if prior and prior.get("feature_dim") == FEATURE_DIM and prior.get("hidden") == hidden:
        with torch.no_grad():
            model.encoder.weight.copy_(
                torch.tensor(prior["encoder_weight"], dtype=torch.float32))
            model.decoder.weight.copy_(
                torch.tensor(prior["decoder_weight"], dtype=torch.float32))
        weights_from = "persisted"
    else:
        with torch.no_grad():
            model.encoder.weight.copy_(torch.tensor(
                rng.normal(0, 0.1, size=model.encoder.weight.shape), dtype=torch.float32))
            model.decoder.weight.copy_(torch.tensor(
                rng.normal(0, 0.1, size=model.decoder.weight.shape), dtype=torch.float32))

    if not node_ids:
        return np.zeros((0, hidden)), [], {"weights_from": weights_from,
                                           "device": str(dev), "nodes": 0,
                                           "trained_count": int((prior or {}).get(
                                               "trained_count") or 0),
                                           "n_updates": int((prior or {}).get(
                                               "n_updates") or 0)}
    with torch.no_grad():
        X = torch.tensor(X_np, dtype=torch.float32, device=dev)
        A_hat = torch.tensor(A_np, dtype=torch.float32, device=dev)
        _x_hat, H = model(A_hat, X)
    return (H.cpu().numpy(), node_ids,
            {"weights_from": weights_from, "device": str(dev), "nodes": len(node_ids),
             "trained_count": int((prior or {}).get("trained_count") or 0),
             "n_updates": int((prior or {}).get("n_updates") or 0)})


def _cosine(matrix):
    """Pairwise cosine similarity of the rows. A zero row (a node whose features are
    all zero) yields zeros rather than a division error, and zero is the right answer:
    nothing is known about it, so it is close to nothing."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe = np.where(norms > 0, norms, 1.0)
    unit = matrix / safe
    unit = np.where(norms > 0, unit, 0.0)
    return unit @ unit.T


def _provision_nodes(graph):
    """{node_id: node} for the provision nodes only, and the ids in graph order."""
    out = {}
    for n in graph.get("nodes") or []:
        if (n.get("type") or n.get("node")) == CANDIDATE_NODE_TYPE:
            nid = str(n.get("id"))
            if nid:
                out[nid] = n
    return out


def _same_document(a, b):
    """Both nodes' document_id, when both carry one and they match. Used to mark a pair
    as within one document, which is where the long-range case lives; a cross-document
    pair is not excluded, only labelled, because the operator has not said it is
    uninteresting."""
    da, db = a.get("document_id"), b.get("document_id")
    return bool(da and db and da == db)


def find_candidates(graph, *, state_path=None, top_k=5, min_score=0.0,
                    hidden=DEFAULT_HIDDEN, seed=DEFAULT_SEED, device=None,
                    exclude_pairs=None):
    """Propose which provisions MAY relate, ranked by proximity in the encoder's space.

    Returns a dict carrying the candidates and, inseparably, what the ranking rests on.

    `top_k` caps candidates per provision; `min_score` drops weak pairs. `exclude_pairs`
    is an iterable of (source, target) the caller already knows about, which is how the
    deterministic baseline's own relations are kept out of the candidate set: proposing
    what a pattern already found is noise, and the two mechanisms are compared by what
    each finds that the other does not.

    A pair is recorded ONCE (the ranking is symmetric), never twice, and a node is never
    its own candidate. Fewer than two provisions yields an empty candidate set, which is
    the honest answer and the state of every graph in this repository today.
    """
    H, node_ids, prov = embed_nodes(graph, state_path=state_path, hidden=hidden,
                                    seed=seed, device=device)
    provisions = _provision_nodes(graph)
    index = {nid: i for i, nid in enumerate(node_ids)}
    ids = [nid for nid in node_ids if nid in provisions]

    excluded = set()
    for a, b in (exclude_pairs or []):
        excluded.add(tuple(sorted((str(a), str(b)))))

    candidates = []
    if len(ids) >= 2:
        sim = _cosine(H)
        for nid in ids:
            i = index[nid]
            scored = []
            for other in ids:
                if other == nid:
                    continue
                pair = tuple(sorted((nid, other)))
                if pair in excluded:
                    continue
                scored.append((other, float(sim[i, index[other]])))
            scored.sort(key=lambda x: (-x[1], x[0]))
            for other, score in scored[:top_k]:
                if score < min_score:
                    continue
                pair = tuple(sorted((nid, other)))
                candidates.append({
                    "source": pair[0],
                    "target": pair[1],
                    "score": round(score, 6),
                    "same_document": _same_document(provisions[pair[0]],
                                                    provisions[pair[1]]),
                })
        # one row per unordered pair, keeping the highest score seen for it
        best = {}
        for c in candidates:
            key = (c["source"], c["target"])
            if key not in best or c["score"] > best[key]["score"]:
                best[key] = c
        candidates = sorted(best.values(), key=lambda c: (-c["score"], c["source"],
                                                          c["target"]))
    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
        "provisions_considered": len(ids),
        "excluded_known_pairs": len(excluded),
        # The qualifier travels WITH the data, so no consumer can render a candidate
        # set without it. This is the same discipline the override rate uses.
        "ranked_on": RANKED_ON_STRUCTURE,
        "learned_relevance": False,
        "tier2_signal": "empty",
        "weights_from": prov["weights_from"],
        "device": prov["device"],
        "trained_count": prov["trained_count"],
        "n_updates": prov["n_updates"],
    }


# state_summary lives in ontology_gnn_state, which imports no tensor library: a
# reader of the persisted state must not have to import torch to count what is in
# a JSON file. Re-exported here so every existing caller keeps working, and so
# there is ONE definition rather than two that must agree.
from ontology_gnn_state import load_state as _load_state_shared, state_summary  # noqa: E402,F401


def main(argv=None):
    """Standalone inspection, no pipeline run and no language model:

        py -3.9 -X utf8 scripts/ontology_candidates.py --state
        py -3.9 -X utf8 scripts/ontology_candidates.py --graph <graph.json> [--top-k 3]
    """
    import argparse

    ap = argparse.ArgumentParser(
        description="Propose candidate provision pairs from the ontology graph "
                    "(ranked on graph structure only; not learned relevance).")
    ap.add_argument("--graph", default=None, help="graph.json to read (default: the store's)")
    ap.add_argument("--state", action="store_true", help="print the GNN state summary and exit")
    ap.add_argument("--state-path", default=None, help="gnn_state.json to read")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.state:
        summary = state_summary(args.state_path)
        print(json.dumps(summary, indent=2, ensure_ascii=False) if args.json
              else _render_state(summary))
        return 0

    gpath = Path(args.graph) if args.graph else DEFAULT_GRAPH_PATH
    graph = json.loads(gpath.read_text(encoding="utf-8")) if gpath.exists() else {
        "nodes": [], "edges": []}
    out = find_candidates(graph, state_path=args.state_path, top_k=args.top_k,
                          min_score=args.min_score)
    print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else _render(out))
    return 0


def _render_state(summary):
    lines = ["GNN state"]
    if not summary.get("exists"):
        lines.append("")
        lines.append("  NOT WRITTEN. " + summary["note"])
        lines.append("  Tier-2 signal: empty. Nothing is learned relevance.")
        return "\n".join(lines)
    lines.append("")
    lines.append("  scope %s, tier %s, schema %s"
                 % (summary.get("scope"), summary.get("tier"), summary.get("schema")))
    lines.append("  nodes trained on: %s over %s update(s)"
                 % (summary.get("trained_count"), summary.get("n_updates")))
    lines.append("  last delta %s, last loss %s, device %s"
                 % (summary.get("last_delta_size"), summary.get("last_loss"),
                    summary.get("last_device")))
    lines.append("  weights persisted: %s" % summary.get("weights_persisted"))
    lines.append("")
    lines.append("  Tier-2 signal: EMPTY. Nothing here is learned relevance;")
    lines.append("  a ranking from this state rests on %s." % RANKED_ON_STRUCTURE)
    return "\n".join(lines)


def _render(out):
    lines = ["Candidate provision pairs (%d)" % out["candidate_count"]]
    lines.append("")
    lines.append("  RANKED ON: %s" % out["ranked_on"])
    lines.append("  weights %s, %d provision(s) considered, %d known pair(s) excluded"
                 % (out["weights_from"], out["provisions_considered"],
                    out["excluded_known_pairs"]))
    if not out["candidates"]:
        lines.append("")
        lines.append("  none proposed (fewer than two provisions, or every pair excluded)")
        return "\n".join(lines)
    lines.append("")
    for c in out["candidates"]:
        lines.append("  %.4f  %s  %s  %s" % (c["score"], c["source"], c["target"],
                                             "same document" if c["same_document"]
                                             else "across documents"))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
