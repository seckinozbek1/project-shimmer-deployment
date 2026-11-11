"""OGE GNN engine (build B3 of 3; ontology/SCHEMA.md + BUILD INVARIANT + the approved STEP 0 trace).

SCOPE HONESTY (read this before reasoning about what the gate proves):
  v1 proves the GNN runs ONE forward pass + ONE backprop over the new-delta nodes WITHOUT ERROR on
  a declared training set's graph, that the weights move, and that state persists incrementally. It
  does NOT prove LEARNING. It has no Tier-2 signal: the self-supervised reconstruction below is all
  it fits, and run outputs are never its signal (D-S112 item 1). So this engine demonstrates that the
  machinery executes a clean fwd/backward cycle and persists -- not that anything was learned. The
  gate-check names say "MACHINERY not learning" for the same reason.

WHAT IT DOES
  - Loads a DECLARED training set's graph (never ontology/stores/, see below) into a node feature
    matrix X built ONLY from
    the approved SAFE allowlist (node-type one-hot incl a stub-Document bucket, degree, stub/incomplete
    flags, and the per-type SAFE categoricals/counts). Categoricals are turned into features by
    DETERMINISTIC feature hashing (hashlib.sha256, NOT Python's salted hash()) into K fixed buckets, so
    the feature width F is CONSTANT across runs even as new category values appear -- this is what lets
    the persisted weight matrix stay valid for incremental updates.
  - Builds a symmetric (undirected) normalized adjacency A_hat = D^-1/2 (A + I) D^-1/2 from the
    edge-list. The self-loop (A + I) means a zero-edge graph degrades to A_hat = I, so the forward pass
    is well-defined even on a near-empty graph.
  - Model: a minimal message-passing graph AUTOENCODER (one graph-conv layer + a linear decoder):
        Z = A_hat . X ; H = relu(Z We) ; X_hat = H Wd ; loss = MSE(X_hat, X)
    Self-supervised: the reconstruction target is the input itself, so there are NO labels and NO
    Tier-2 signal -- honest for an empty-Tier-2 graph.
  - DELTA-ONLY BACKPROP: the forward pass runs over the FULL graph (neighborhood context), but the
    loss/gradient is summed ONLY over the rows of nodes NEW since the last high-water mark; non-delta
    rows contribute zero gradient. First call (no prior state): delta = the whole declared graph. State
    (weights, the trained-node-id high-water mark, the chain of training sets, metadata) persists to the
    state file the caller names.

PAYLOAD-FREE (BUILD INVARIANT)
  Features derive ONLY from SAFE fields. The builder reads a HARDCODED SAFE allowlist and never
  dereferences a RAW field (original_text/proposed_text/comment/title/rule/examples/...). gnn_state
  holds weights + structural metadata (node ids, dims, counts) only -- zero raw content. If a provision
  arrives with masked text ([REDACTED:...]) it simply never enters X or the state, because the builder
  does not read those fields at all.

TRAINED BY ITS OWN TRAINING ONLY (D-S112 item 1, D-417)
  The GNN never learns from runs. No run calls `gnn_update` (gate check 64 holds that). It is
  trained only by its own command, `python scripts/ontology_gnn.py train --training-set <file>
  --state <file>`, on a DECLARED training set: a JSON declaration (`declare_training_set`) naming
  one graph file by path and SHA-256 and stating that the material is domain- and case-agnostic,
  made for training. A declaration whose graph is the run-captured store (ontology/stores/), whose
  digest does not match, or which does not state both properties is refused before any weight moves.
  Training further on one user's own material is a later, opt-in path (D-S112 item 1; a loose end
  until the deployment form is decided), never this command run by itself.

DEPENDENCY / DEVICE
  torch (declared + pinned in requirements.txt). GPU is OPTIONAL and warn-not-fail: device = cuda if
  available else cpu, with a single warning when CUDA is absent; a missing GPU never fails anything.
  Determinism: torch.manual_seed + numpy seed are set, and the gate forces device=cpu so check results
  do not depend on GPU presence. GPU is a runtime accelerator, never a correctness dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent.parent
OGE_STORES_DIR = ROOT / "ontology" / "stores"
# What runs write besides the store: durable/ (learnings, governance, cache). A graph built from a
# source under either is the run store's (D-446).
DURABLE_DIR = ROOT / "durable"
DEFAULT_GRAPH_PATH = OGE_STORES_DIR / "graph.json"
DEFAULT_STATE_PATH = OGE_STORES_DIR / "gnn_state.json"

# ---- SAFE feature allowlist (approved STEP 0 trace). The feature builder reads ONLY these keys. ----
# Node-type one-hot vocabulary (a stub Document gets its own bucket per the trace).
NODE_TYPE_VOCAB = ["Document", "Document_stub", "Provision", "Convention", "CitationForm", "SpeechAct"]
# SAFE categorical fields fed through feature hashing (value text is a category label, not content).
CATEGORICAL_FIELDS = ("date_confidence", "finding_type", "action", "severity", "category")
# The exact set of node-dict keys the builder is permitted to read. Anything else is RAW or unused.
SAFE_FEATURE_FIELDS = frozenset(
    {"type", "stub", "incomplete", "context_refs", "sample_count", "evidence_count"} | set(CATEGORICAL_FIELDS)
)
# RAW fields (Table D + Q5) that must NEVER enter the feature matrix or the persisted state.
RAW_FIELDS = frozenset({
    "original_text", "proposed_text", "comment", "title", "rule", "examples", "note",
    "source_file", "source_location", "pattern", "abs_path", "doc_id",
})

HASH_BUCKETS = 16            # fixed categorical-hash width -> F constant across runs
NUMERIC_FIELDS = ("degree", "stub", "incomplete", "context_refs_count", "sample_count", "evidence_count")
FEATURE_DIM = len(NODE_TYPE_VOCAB) + HASH_BUCKETS + len(NUMERIC_FIELDS)  # F (constant)

TRAINING_SET_KIND = "gnn-training-set-v1"


class TrainingSetRefused(ValueError):
    """A training set that is not declared, not agnostic, not the declared bytes, or the run store."""


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# What the tool can and cannot check (D-432 item 2): it checks the declaration's form, the graph's
# bytes against its digest, and that the graph is not the run store's (by digest, against every
# file of ontology/stores/, and by the build provenance ontology_graph writes). Whether the material
# is domain- and case-agnostic is the declaring person's statement, made by their own arguments and
# recorded with their name; the tool never writes it and cannot verify it.
AGNOSTIC_LIMIT = ("domain- and case-agnostic as stated by the person who declared it; the tool checks "
                  "the form, the digest and that the graph is not the run store's, not the material")


def declare_training_set(path, graph_path, name, material, *, domain_agnostic, case_agnostic, declared_by):
    """Write the declaration of a training set: one graph file, by path relative to the
    declaration and SHA-256, what it is, and the declaring person's own statement that it is
    domain- and case-agnostic (each passed by them, never defaulted). Returns the declaration."""
    if domain_agnostic is not True or case_agnostic is not True:
        raise TrainingSetRefused("the declaring person states both domain- and case-agnostic, or nothing is declared")
    if not (isinstance(declared_by, str) and declared_by.strip()):
        raise TrainingSetRefused("a declaration names who declares it")
    path, graph_path = Path(path), Path(graph_path)
    declaration = {"kind": TRAINING_SET_KIND, "name": name, "material": material,
                   "domain_agnostic": domain_agnostic, "case_agnostic": case_agnostic,
                   "declared_by": declared_by.strip(), "limit": AGNOSTIC_LIMIT,
                   "graph": Path(graph_path.resolve().relative_to(path.resolve().parent)).as_posix()
                   if graph_path.resolve().is_relative_to(path.resolve().parent) else str(graph_path.resolve()),
                   "graph_sha256": _sha(graph_path)}
    path.write_text(json.dumps(declaration, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return declaration


def load_training_set(path):
    """(declaration, graph path) of a declared training set, or TrainingSetRefused."""
    path = Path(path)
    try:
        declaration = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TrainingSetRefused("the training set declaration cannot be read")
    if not isinstance(declaration, dict) or declaration.get("kind") != TRAINING_SET_KIND:
        raise TrainingSetRefused("not a %s declaration" % TRAINING_SET_KIND)
    if declaration.get("domain_agnostic") is not True or declaration.get("case_agnostic") is not True:
        raise TrainingSetRefused("the declaration does not state domain- and case-agnostic material")
    if not declaration.get("name"):
        raise TrainingSetRefused("the declaration names no training set")
    if not declaration.get("material"):
        raise TrainingSetRefused("the declaration names no material")
    if not (isinstance(declaration.get("declared_by"), str) and declaration["declared_by"].strip()):
        raise TrainingSetRefused("the declaration names no one who declared it")
    graph = Path(declaration.get("graph") or "")
    graph = (graph if graph.is_absolute() else path.parent / graph).resolve()
    if graph.is_relative_to(OGE_STORES_DIR.resolve()):
        raise TrainingSetRefused("the run-captured store is never a training set (D-S112 item 1)")
    if not graph.is_file() or _sha(graph) != declaration.get("graph_sha256"):
        raise TrainingSetRefused("the declared graph is missing or is not the declared bytes")
    refused = run_store_content(graph)
    if refused:
        raise TrainingSetRefused(refused)
    return declaration, graph


def run_store_content(graph_path):
    """The reason a graph is the run store's by content, or None: its bytes equal a file of
    ontology/stores/, or ontology_graph's build provenance says a source was the repository's own
    store. A graph copied from the store and then edited, or built by other code from it, is not
    caught: that limit is stated in AGNOSTIC_LIMIT's neighbour, here."""
    digest = _sha(graph_path)
    stores = OGE_STORES_DIR.resolve()
    if stores.is_dir():
        for stored in sorted(stores.rglob("*")):
            if stored.is_file() and _sha(stored) == digest:
                return "the declared graph is byte for byte a file of the run store (%s)" % stored.name
    try:
        graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "the declared graph cannot be read"
    built = graph.get("built_from") if isinstance(graph, dict) else None
    if isinstance(built, dict) and built.get("default_sources"):
        return ("the declared graph was built from the repository's own stores (%s), which runs write"
                % ", ".join(built["default_sources"]))
    run_written = (OGE_STORES_DIR.resolve(), DURABLE_DIR.resolve())
    for name, source in sorted(((built or {}).get("source_paths") or {}).items()) if isinstance(built, dict) else ():
        try:
            resolved = Path(source).resolve()
        except (OSError, ValueError, TypeError):
            return "a source path of the declared graph cannot be read (%s)" % name
        if any(resolved == root or resolved.is_relative_to(root) for root in run_written):
            return ("the declared graph was built from %s under ontology/stores/ or durable/, which runs write"
                    % name)
    return None


DEFAULT_SEED = 1337
DEFAULT_HIDDEN = 16
DEFAULT_LR = 0.01
STATE_SCHEMA = "oge_gnn_state/v1"


def _node_type_key(node):
    """The node-type bucket, with a dedicated stub-Document bucket (trace)."""
    t = node.get("type")
    if t == "Document" and node.get("stub"):
        return "Document_stub"
    return t


def _safe_view(node):
    """Return ONLY the SAFE keys of a node. This is the single chokepoint through which the feature
    builder sees a node: a RAW field is structurally unreachable because it is filtered out here."""
    return {k: v for k, v in node.items() if k in SAFE_FEATURE_FIELDS}


def _hash_bucket(field, value):
    """Deterministic feature hashing (sha256, NOT salted hash()): (field=value) -> a fixed bucket."""
    h = hashlib.sha256(f"{field}={value}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % HASH_BUCKETS


def _node_feature_row(node, degree):
    """Build one SAFE feature row for a node. Reads only _safe_view(node); never a RAW field.
    Layout: [node-type one-hot (6)] + [hashed categoricals (K=16)] + [numeric block (6)] = F."""
    view = _safe_view(node)
    row = np.zeros(FEATURE_DIM, dtype=np.float64)

    # node-type one-hot (uses the unfiltered type via _node_type_key, which reads only 'type'/'stub')
    tkey = _node_type_key(node)
    if tkey in NODE_TYPE_VOCAB:
        row[NODE_TYPE_VOCAB.index(tkey)] = 1.0
    base = len(NODE_TYPE_VOCAB)

    # hashed SAFE categoricals
    for f in CATEGORICAL_FIELDS:
        v = view.get(f)
        if v is not None and v != "":
            row[base + _hash_bucket(f, str(v))] = 1.0
    base += HASH_BUCKETS

    # numeric block (log1p-tamed counts/degree; stub/incomplete are 0/1 flags)
    numeric = {
        "degree": np.log1p(float(degree)),
        "stub": 1.0 if view.get("stub") else 0.0,
        "incomplete": 1.0 if view.get("incomplete") else 0.0,
        "context_refs_count": np.log1p(float(len(view.get("context_refs") or []))),
        "sample_count": np.log1p(float(view.get("sample_count") or 0)),
        "evidence_count": np.log1p(float(view.get("evidence_count") or 0)),
    }
    for i, name in enumerate(NUMERIC_FIELDS):
        row[base + i] = numeric[name]
    return row


def build_features(graph):
    """Build the SAFE node feature matrix X and the node-id list from a graph dict.
    Returns (X: np.ndarray [N, F], node_ids: list[str], degrees: list[int]).
    PAYLOAD-FREE: every row comes from _node_feature_row -> _safe_view; no RAW field is read."""
    nodes = graph.get("nodes") or []
    node_ids = [str(n.get("id")) for n in nodes]
    index = {nid: i for i, nid in enumerate(node_ids)}

    # undirected degree from the edge-list (self-loops added later in the adjacency)
    degrees = [0] * len(nodes)
    for e in (graph.get("edges") or []):
        s, t = str(e.get("source")), str(e.get("target"))
        if s in index:
            degrees[index[s]] += 1
        if t in index and t != s:
            degrees[index[t]] += 1

    if not nodes:
        return np.zeros((0, FEATURE_DIM), dtype=np.float64), [], []
    X = np.stack([_node_feature_row(n, degrees[i]) for i, n in enumerate(nodes)])
    return X, node_ids, degrees


def build_adjacency(graph, node_ids):
    """Symmetric normalized adjacency with self-loops: A_hat = D^-1/2 (A + I) D^-1/2.
    Zero-edge graphs degrade to A_hat = I (self-loops only), so the forward pass is always defined.
    Returns a dense np.ndarray [N, N] (graphs are small; no sparse machinery needed)."""
    n = len(node_ids)
    if n == 0:
        return np.zeros((0, 0), dtype=np.float64)
    index = {nid: i for i, nid in enumerate(node_ids)}
    A = np.eye(n, dtype=np.float64)  # self-loops (A + I)
    for e in (graph.get("edges") or []):
        s, t = str(e.get("source")), str(e.get("target"))
        if s in index and t in index:
            i, j = index[s], index[t]
            A[i, j] = 1.0
            A[j, i] = 1.0  # undirected for message passing
    deg = A.sum(axis=1)
    d_inv_sqrt = np.where(deg > 0, 1.0 / np.sqrt(deg), 0.0)
    return (A * d_inv_sqrt[:, None]) * d_inv_sqrt[None, :]


class GraphAutoencoder(nn.Module):
    """Minimal message-passing graph autoencoder. One graph-conv (the A_hat . X mixing is applied
    outside, in forward) + relu + a linear decoder. Reconstructs X from neighborhood-mixed inputs."""

    def __init__(self, feature_dim, hidden):
        super().__init__()
        self.encoder = nn.Linear(feature_dim, hidden, bias=False)
        self.decoder = nn.Linear(hidden, feature_dim, bias=False)

    def forward(self, a_hat, x):
        z = a_hat @ x                       # message passing (neighborhood mixing)
        h = torch.relu(self.encoder(z))     # embeddings
        x_hat = self.decoder(h)             # reconstruction
        return x_hat, h


def _resolve_device(device):
    """device=cpu|cuda|None. None -> cuda if available else cpu, with a single warn-not-fail notice."""
    if device is not None:
        return torch.device(device)
    if torch.cuda.is_available():
        return torch.device("cuda")
    print("OGE GNN: no CUDA device, running on CPU", flush=True)
    return torch.device("cpu")


def _load_state(state_path):
    p = Path(state_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def gnn_update(training_set, state_path, *, device=None, seed=DEFAULT_SEED,
               hidden=DEFAULT_HIDDEN, lr=DEFAULT_LR, log=True):
    """Run ONE forward pass + ONE delta-only backprop over a DECLARED training set's graph and
    persist state. The GNN's own training only (module header): `training_set` is a declaration
    `load_training_set` accepts, never the run store; `state_path` is where the state is written.

    MACHINERY, NOT LEARNING (see module header). Loads the declared graph, builds the SAFE feature matrix,
    loads any prior state, computes the delta (nodes new since the last high-water mark), runs one
    fwd + one backward whose gradient is summed ONLY over delta rows, takes one SGD step, and persists
    weights + the updated high-water mark. First run: delta = the whole graph.

    Returns a summary dict (counts, delta size, loss, weight-delta norm, device) -- never raw content.
    Empty/thin-graph safe: a 0-node or 0-edge graph still does a clean (possibly zero-gradient) cycle.
    """
    declaration, gpath = load_training_set(training_set)
    if not state_path:
        raise TrainingSetRefused("the state file to write is named by the caller")
    spath = Path(state_path)
    dev = _resolve_device(device)

    # determinism (numpy seed governs the no-prior-state weight init we hand to torch)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    graph = json.loads(gpath.read_text(encoding="utf-8")) if gpath.exists() else {"nodes": [], "edges": []}
    X_np, node_ids, _ = build_features(graph)
    A_np = build_adjacency(graph, node_ids)
    n = len(node_ids)

    model = GraphAutoencoder(FEATURE_DIM, hidden).to(dev)
    prior = _load_state(spath)
    if prior is not None:
        import ontology_gnn_state
        refused = ontology_gnn_state.provenance_refusal(prior)
        if refused:
            raise TrainingSetRefused(refused)
    chain = list((prior or {}).get("training_sets") or [])
    trained_ids = set()
    n_updates_prev = 0
    if prior and prior.get("feature_dim") == FEATURE_DIM and prior.get("hidden") == hidden:
        # restore persisted weights (incremental run); else (re)initialize deterministically
        with torch.no_grad():
            model.encoder.weight.copy_(torch.tensor(prior["encoder_weight"], dtype=torch.float32))
            model.decoder.weight.copy_(torch.tensor(prior["decoder_weight"], dtype=torch.float32))
        trained_ids = set(prior.get("trained_node_ids") or [])
        n_updates_prev = int(prior.get("n_updates") or 0)
    else:
        with torch.no_grad():
            model.encoder.weight.copy_(torch.tensor(
                rng.normal(0, 0.1, size=model.encoder.weight.shape), dtype=torch.float32))
            model.decoder.weight.copy_(torch.tensor(
                rng.normal(0, 0.1, size=model.decoder.weight.shape), dtype=torch.float32))

    # delta = nodes new since the last high-water mark (first run: all)
    delta_ids = [nid for nid in node_ids if nid not in trained_ids]
    delta_size = len(delta_ids)

    # snapshot encoder weights to measure that the backward step actually moved them
    enc_before = model.encoder.weight.detach().clone()

    loss_val = 0.0
    if n > 0:
        X = torch.tensor(X_np, dtype=torch.float32, device=dev)
        A_hat = torch.tensor(A_np, dtype=torch.float32, device=dev)
        delta_set = set(delta_ids)
        mask = torch.tensor([1.0 if nid in delta_set else 0.0 for nid in node_ids],
                            dtype=torch.float32, device=dev)

        optimizer = torch.optim.SGD(model.parameters(), lr=lr)
        optimizer.zero_grad()
        x_hat, _ = model(A_hat, X)
        # MSE summed ONLY over delta rows (non-delta rows contribute zero gradient)
        sq = (x_hat - X) ** 2
        denom = mask.sum() * FEATURE_DIM
        if float(denom) > 0:
            loss = (sq * mask[:, None]).sum() / denom
            loss.backward()
            optimizer.step()
            loss_val = float(loss.detach().cpu())
        # denom == 0 (no new deltas): no backward, weights unchanged -- the honest "nothing new" case

    weight_delta_norm = float(torch.linalg.norm(
        (model.encoder.weight.detach() - enc_before).cpu()))
    n_updates = n_updates_prev + (1 if delta_size > 0 and n > 0 else 0)

    # persist: weights + structural metadata + new high-water mark. ZERO raw content.
    new_trained = sorted(trained_ids | set(node_ids))
    state = {
        "schema": STATE_SCHEMA,
        "tier": 1,
        "claim": "machinery-not-learning (no Tier-2 signal; trained only on declared training sets, never by a run)",
        # The whole chain of declared training sets, in order (D-432 item 1).
        "training_sets": chain + [{"name": declaration["name"], "graph_sha256": declaration["graph_sha256"],
                                   "declared_by": declaration["declared_by"], "limit": declaration["limit"],
                                   "domain_agnostic": declaration["domain_agnostic"],
                                   "case_agnostic": declaration["case_agnostic"]}],
        # night W7 c: the storage scope the graph (and so this state) was built from.
        "scope": graph.get("scope"),
        "feature_dim": FEATURE_DIM,
        "hidden": hidden,
        "seed": seed,
        "node_type_vocab": NODE_TYPE_VOCAB,
        "hash_buckets": HASH_BUCKETS,
        "encoder_weight": model.encoder.weight.detach().cpu().tolist(),
        "decoder_weight": model.decoder.weight.detach().cpu().tolist(),
        "trained_node_ids": new_trained,
        "trained_count": len(new_trained),
        "n_updates": n_updates,
        "last_delta_size": delta_size,
        "last_loss": loss_val,
        "last_device": str(dev),
    }
    spath.parent.mkdir(parents=True, exist_ok=True)
    spath.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "nodes": n,
        "edges": len(graph.get("edges") or []),
        "feature_dim": FEATURE_DIM,
        "delta_size": delta_size,
        "weight_delta_norm": weight_delta_norm,
        "loss": loss_val,
        "n_updates": n_updates,
        "device": str(dev),
        "state_path": str(spath),
    }
    if log:
        # The words a reader sees FIRST decide what they believe, and "loss=",
        # "weight_delta=" and "device=" are exactly the vocabulary of a real
        # training run; "(MACHINERY not learning)" used to sit as a
        # parenthetical AFTER them, in a reader's eye the numbers carry the
        # authority and the caveat reads as a footnote easy to skim past.
        # This computes nothing differently (same reconstruction_loss,
        # same weight_delta_norm, same summary dict, same gate-check
        # behavior); only the words describing it changed, to say what the
        # module's own docstring above already says: this is a self-
        # supervised reconstruction fit over Tier-1 structure with NO Tier-2
        # signal yet, proven to execute without error, not proven or claimed
        # to have learned anything a reader would call learning.
        print(f"[ontology_gnn] self-supervised reconstruction fit, no Tier-2 signal yet "
              f"(not a trained relevance model): {delta_size}/{n} node(s) updated this run, "
              f"reconstruction_loss={loss_val:.6f}, weight_movement={weight_delta_norm:.6f}, "
              f"device={dev} -> {spath.name}", flush=True)
    return summary


def main(argv=None):
    """The GNN's own training command; the only route to `gnn_update` (D-S112 item 1)."""
    parser = argparse.ArgumentParser(prog="ontology_gnn.py", allow_abbrev=False,
                                     description="The GNN's own training, on a declared training set only.")
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train", allow_abbrev=False)
    t.add_argument("--training-set", required=True, help="a gnn-training-set-v1 declaration")
    t.add_argument("--state", required=True, help="the state file to write")
    t.add_argument("--device", default=None)
    t.add_argument("--seed", type=int, default=DEFAULT_SEED)
    dcl = sub.add_parser("declare", allow_abbrev=False,
                         help="write a training-set declaration; the agnostic statement is yours, by these flags")
    dcl.add_argument("--out", required=True)
    dcl.add_argument("--graph", required=True)
    dcl.add_argument("--name", required=True)
    dcl.add_argument("--material", required=True)
    dcl.add_argument("--declared-by", required=True)
    dcl.add_argument("--domain-agnostic", action="store_true")
    dcl.add_argument("--case-agnostic", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "declare":
        try:
            declare_training_set(args.out, args.graph, args.name, args.material,
                                 domain_agnostic=args.domain_agnostic or None,
                                 case_agnostic=args.case_agnostic or None, declared_by=args.declared_by)
        except TrainingSetRefused as exc:
            print("ontology_gnn: refused: %s" % exc, file=sys.stderr)
            return 3
        return 0
    try:
        s = gnn_update(args.training_set, args.state, device=args.device, seed=args.seed)
    except TrainingSetRefused as exc:
        print("ontology_gnn: refused: %s" % exc, file=sys.stderr)
        return 3
    print(f"OGE GNN: {s['nodes']} nodes, delta={s['delta_size']}, "
          f"loss={s['loss']:.6f}, weight_delta={s['weight_delta_norm']:.6f}, device={s['device']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
