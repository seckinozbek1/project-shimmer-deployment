"""OGE Tier-1 graph ingest (build B2; ontology/SCHEMA.md sections A, B, C5/C6 + RATIFIED).

Builds an in-memory Tier-1 knowledge graph from the durable sources and serializes it to
ontology/stores/graph.json (a plain node-list + edge-list, stdlib only, no external graph lib).
Deterministic, local, no model calls.

Sources (Q9: OGE data under ontology/; the rest are the existing durable/config stores):
  ontology/stores/provisions.jsonl        provisions captured by B1 (may be empty)
  durable/learnings/document_dates.json    Document/Case nodes (id = filename; NO abs_path, Q7)
  config/convention_registry.json          Convention nodes (id = CONV-*)
  durable/learnings/citation_convention.json  CitationForm nodes (id = name) + CITES patterns
  durable/learnings/speech_acts_taxonomy.json SpeechAct nodes (id = name) + EXHIBITS patterns
  durable/governance/operator_decisions.jsonl OperatorDecision nodes (a verdict joined to its subject)

PAYLOAD-FREE (BUILD INVARIANT): ingest reads provisions AS STORED and never unmasks. If B1
stored a provision field masked (sensitive run), the graph node carries the placeholder. The
derivable CITES/EXHIBITS regexes run against the stored text, so a placeholder simply does not
match (correct; no attempt to recover raw text). graph.json never contains abs_path (Q7) and
never unmasks content the source store had masked.

Edges (SCHEMA B + C5/C6):
  HAS_PROVISION    Document -> Provision   (provision document_id; stub Document if no filename match)
  GOVERNED_BY      Provision -> Convention (provision convention_ref -> CONV id; N:1 per Q4)
  CROSS_REFERENCES Provision -> Provision  (context_refs -> ref_id; missing targets become stubs, Q3)
  CITES            Provision -> CitationForm (re.search(form.pattern, original_text AS STORED))
  EXHIBITS         Provision -> SpeechAct    (re.search(act.pattern, original_text AS STORED))
  DECIDED_ON       OperatorDecision -> Convention (the subject rule an operator ruled on; the
                   first edge whose source is not a Provision, and the first carrying a human
                   judgement rather than an identifier match or a regex)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Reuse the EXISTING OGE masked-write gate (B1) -- not a second masker. INFRA-041 P4 closes the
# cross-run leak gap: under sensitive mode Convention.rule (Q5) and CitationForm.examples (Q6) are
# masked to typed placeholders, real content otherwise. mask_field is None-passthrough + [REDACTED:TYPE].
from ontology_capture import mask_field
# night W7: provisions are read through the scoped storage layer, never from the file.
import ontology_store

ROOT = Path(__file__).resolve().parent.parent
OGE_STORES_DIR = ROOT / "ontology" / "stores"

DEFAULT_SOURCES = {
    "provisions": OGE_STORES_DIR / "provisions.jsonl",
    "document_dates": ROOT / "durable" / "learnings" / "document_dates.json",
    "conventions": ROOT / "config" / "convention_registry.json",
    "citation_forms": ROOT / "durable" / "learnings" / "citation_convention.json",
    "speech_acts": ROOT / "durable" / "learnings" / "speech_acts_taxonomy.json",
    # An operator's verdict, joined to the subject it was about. Until this the
    # builder read five files and no operator decision reached the graph at all,
    # so the one record type carrying both a target and a human verdict was
    # invisible to everything downstream. An absent file yields no nodes, which
    # is the current state and is not an error.
    "operator_decisions": ROOT / "durable" / "governance" / "operator_decisions.jsonl",
}
DEFAULT_GRAPH_PATH = OGE_STORES_DIR / "graph.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _safe_compile(pattern):
    """Compile a stored regex pattern AS STORED. A malformed pattern yields None (skipped),
    never a crash. No extra flags are added: the pattern's own behavior is honored."""
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error:
        return None


def _count_by(items, key):
    out = {}
    for it in items:
        k = it.get(key)
        out[k] = out.get(k, 0) + 1
    return out


def build_graph(sources=None, out_path=None, *, sensitive=False,
                scope=ontology_store.DEFAULT_SCOPE):
    """Build the Tier-1 graph from the durable sources and write graph.json. `sources` overrides
    individual source paths (the verify gate passes tempdir fixtures); `out_path` overrides the
    output (the gate writes to a tempdir, never the real ontology/stores/graph.json). Returns the
    graph dict. Safe on empty inputs (produces a valid graph with whatever nodes exist).

    night W7 c: provisions are read through ontology_store.ProvisionStore under `scope`, so
    the graph holds one scope's CURRENT provisions only (superseded revisions and other
    scopes' records are excluded by the storage layer, not here). The graph records the
    scope it was built from.

    sensitive (INFRA-041 P4): masks the cross-run leak fields -- Convention.rule (Q5) and
    CitationForm.examples (Q6) -- to typed placeholders, real content otherwise. Reuses the B1
    mask_field gate (no second masker). Provision text is already masked AT THE SOURCE store by B1,
    so build_graph never unmasks it; this closes the two fields build_graph itself reads raw."""
    src = dict(DEFAULT_SOURCES)
    if sources:
        src.update(sources)

    nodes = {}   # (type, id) -> node dict
    edges = []

    def add_node(ntype, nid, **attrs):
        key = (ntype, nid)
        if key not in nodes:
            nodes[key] = {"type": ntype, "id": nid, **attrs}
        return nodes[key]

    def has(ntype, nid):
        return (ntype, nid) in nodes

    # ----- PHASE 1: materialize all nodes (so edges never dangle) -----

    # Document nodes (id = filename; abs_path deliberately excluded, Q7)
    for d in (_load_json(src["document_dates"], {}).get("documents") or []):
        fn = d.get("filename")
        if not fn:
            continue
        add_node("Document", fn, date=d.get("date"), date_source=d.get("date_source"),
                 date_confidence=d.get("date_confidence"), title=d.get("title"), stub=False)

    # Convention nodes (id = CONV-*)
    for c in (_load_json(src["conventions"], {}).get("conventions") or []):
        cid = c.get("id")
        if not cid:
            continue
        add_node("Convention", cid, category=c.get("category"),
                 rule=mask_field(c.get("rule"), "CONVENTION_RULE", sensitive=sensitive),  # Q5 (P4)
                 source_file=c.get("source_file"), source_location=c.get("source_location"),
                 severity=c.get("severity"), action=c.get("action"))

    # CitationForm nodes (id = name) + compiled CITES patterns
    citation_patterns = []
    for r in (_load_json(src["citation_forms"], {}).get("rules") or []):
        nm = r.get("name")
        if not nm:
            continue
        _ex = r.get("examples", []) or []
        if sensitive and _ex:  # Q6 (P4): mask corpus-derived citation examples under sensitive mode
            _ex = [mask_field("examples", "CITATION_EXAMPLES", sensitive=True)]
        add_node("CitationForm", nm, pattern=r.get("pattern"),
                 sample_count=r.get("sample_count"), examples=_ex)
        citation_patterns.append((nm, _safe_compile(r.get("pattern"))))

    # SpeechAct nodes (id = name) + compiled EXHIBITS patterns
    speechact_patterns = []
    for a in (_load_json(src["speech_acts"], {}).get("speech_acts") or []):
        nm = a.get("name")
        if not nm:
            continue
        add_node("SpeechAct", nm, pattern=a.get("pattern"),
                 evidence_count=a.get("evidence_count"), examples=a.get("examples", []) or [])
        speechact_patterns.append((nm, _safe_compile(a.get("pattern"))))

    # OperatorDecision nodes: a human verdict, joined to its subject. Read from
    # durable/governance/operator_decisions.jsonl, one record per line, each
    # standing alone. SAFE fields only: the decision, the topic, whether a
    # subject was identified, and the subject's id-shaped keys. The record
    # carries no document text by construction (the writer reads an allowlist of
    # id keys off the escalation payload and never the payload itself), so there
    # is nothing here to mask.
    operator_decisions = []
    for line in _load_jsonl(src.get("operator_decisions")):
        did = line.get("decided_at")
        subject = line.get("subject") if isinstance(line.get("subject"), dict) else {}
        node_id = "decision::%s::%s" % (line.get("run_id") or "", did or "")
        add_node("OperatorDecision", node_id,
                 topic=line.get("topic"), decision=line.get("decision"),
                 subject_known=bool(line.get("subject_known")),
                 run_id=line.get("run_id"), decided_at=did)
        operator_decisions.append((node_id, subject))

    # Provision nodes: the scope's CURRENT records, AS STORED (one per id; the storage layer
    # already excluded superseded revisions and every other scope). Provenance and revision
    # are SAFE metadata (no content) and travel onto the node.
    store = ontology_store.ProvisionStore(live_path=src["provisions"], scope=scope)
    for rec in store.current():
        pid = rec.get("id")
        if rec.get("stub"):
            add_node("Provision", pid, document_id=rec.get("document_id"),
                     ref_id=rec.get("ref_id"), stub=True, incomplete=True,
                     provenance=rec.get("provenance"), revision=rec.get("revision"))
        else:
            add_node("Provision", pid, document_id=rec.get("document_id"), ref_id=rec.get("ref_id"),
                     finding_type=rec.get("finding_type"), action=rec.get("action"),
                     severity=rec.get("severity"), convention_ref=rec.get("convention_ref"),
                     context_refs=rec.get("context_refs", []) or [],
                     # text AS STORED (masked or real; ingest never unmasks):
                     original_text=rec.get("original_text"), proposed_text=rec.get("proposed_text"),
                     comment=rec.get("comment"), stub=False,
                     provenance=rec.get("provenance"), revision=rec.get("revision"))

    # Stub Provisions for referenced-only REFs (Q3): any context_ref target not materialized
    for n in [v for (t, _), v in nodes.items() if t == "Provision" and not v.get("stub")]:
        did = n.get("document_id")
        for ref in (n.get("context_refs") or []):
            tgt = f"{did}::{ref}"
            if not has("Provision", tgt):
                add_node("Provision", tgt, document_id=did, ref_id=ref, stub=True, incomplete=True)

    # Stub Documents for provision document_ids with no document_dates filename match
    for n in [v for (t, _), v in nodes.items() if t == "Provision"]:
        did = n.get("document_id")
        if did and not has("Document", did):
            add_node("Document", did, stub=True, incomplete=True,
                     note="materialized from provision document_id (no document_dates filename match)")

    # ----- PHASE 2: build edges over the complete node set -----
    provisions = [v for (t, _), v in nodes.items() if t == "Provision"]

    for n in provisions:
        did = n.get("document_id")
        if did and has("Document", did):
            edges.append({"type": "HAS_PROVISION", "source_type": "Document", "source": did,
                          "target_type": "Provision", "target": n["id"]})

    # DECIDED_ON: an operator's verdict, pointed at what it was about. The first
    # edge type in this graph whose source is not a Provision, and the first that
    # carries a human judgement rather than an identifier match or a regex. A
    # decision whose subject names a rule this registry holds points at that
    # Convention; one whose subject names nothing the graph knows is left
    # unlinked rather than attached to a guess, and subject_known on the node
    # says which it was.
    #
    # NOT added to the GNN feature vocabulary, deliberately. An OperatorDecision
    # node is not in ontology_gnn.NODE_TYPE_VOCAB, so its type one-hot is all
    # zeros: the node is in the graph and reachable, and contributes no learned
    # type signal. Adding it would change the feature width and invalidate the
    # persisted weights (feature_dim 28) in exchange for a signal that is still
    # empty. The vocabulary changes when there is a real corpus of decisions and
    # a model that can read a label, not before.
    for node_id, subject in operator_decisions:
        rule_ref = subject.get("rule_id") or subject.get("source_rule_id")
        if rule_ref and has("Convention", rule_ref):
            edges.append({"type": "DECIDED_ON", "source_type": "OperatorDecision",
                          "source": node_id, "target_type": "Convention",
                          "target": rule_ref})

    stats = {"unmatched_convention_refs": 0}
    for n in provisions:
        if n.get("stub"):
            continue
        cref = n.get("convention_ref")
        if not cref:
            continue
        if has("Convention", cref):
            edges.append({"type": "GOVERNED_BY", "source_type": "Provision", "source": n["id"],
                          "target_type": "Convention", "target": cref})
        else:
            stats["unmatched_convention_refs"] += 1

    for n in provisions:
        if n.get("stub"):
            continue
        did = n.get("document_id")
        for ref in (n.get("context_refs") or []):
            tgt = f"{did}::{ref}"
            edges.append({"type": "CROSS_REFERENCES", "source_type": "Provision", "source": n["id"],
                          "target_type": "Provision", "target": tgt})

    # Derivable CITES (C5) + EXHIBITS (C6): regex over original_text AS STORED.
    for n in provisions:
        if n.get("stub"):
            continue
        text = n.get("original_text") or ""
        if not text:
            continue
        for form_name, rx in citation_patterns:
            if rx is not None and rx.search(text):
                edges.append({"type": "CITES", "source_type": "Provision", "source": n["id"],
                              "target_type": "CitationForm", "target": form_name})
        for act_name, rx in speechact_patterns:
            if rx is not None and rx.search(text):
                edges.append({"type": "EXHIBITS", "source_type": "Provision", "source": n["id"],
                              "target_type": "SpeechAct", "target": act_name})

    node_list = list(nodes.values())
    graph = {
        "schema": "oge_graph/v1",
        "tier": 1,
        "scope": scope,                # night W7 c: the one scope this graph was built from
        "sensitive": bool(sensitive),  # P4: rule + citation examples masked when true
        "generated_at": _now(),
        "nodes": node_list,
        "edges": edges,
        "stats": {
            "nodes_total": len(node_list),
            "nodes_by_type": _count_by(node_list, "type"),
            "edges_total": len(edges),
            "edges_by_type": _count_by(edges, "type"),
            "stub_provisions": sum(1 for n in node_list if n["type"] == "Provision" and n.get("stub")),
            "stub_documents": sum(1 for n in node_list if n["type"] == "Document" and n.get("stub")),
            **stats,
        },
    }

    target = Path(out_path) if out_path else DEFAULT_GRAPH_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph


if __name__ == "__main__":
    g = build_graph()
    s = g["stats"]
    print(f"OGE Tier-1 graph: {s['nodes_total']} nodes {s['nodes_by_type']}, "
          f"{s['edges_total']} edges {s['edges_by_type']} -> {DEFAULT_GRAPH_PATH}")
