"""The tool registry (D-681 item 7): every tool a model may ask Python to run, declared in one
standard form in `config/table_tools.json`, so no table operation is hard-coded in a prompt or
in the pipeline. Only the operator adds a tool, and each is vetted first
(`tools/vet_table_tool.py`).

    load(path)                         the registry
    entry(registry, name)              one tool's declaration
    vetted_sha256(entry, root)         the digest its vetting must carry
    entry_refusals(entry, registry)    every reason a declaration cannot run, [] when it can
    resolve(entry)                     the tool's function
    relevant(registry, names, ...)     the declared tools shown to one question
    request_ratified(root)             the amendment that switches the request on, or None
    startup_refusals(task, names)      boot's reasons to refuse a declared request

A declaration names the tool (`name`), says what it does in one sentence (`does`), types its
inputs (`inputs`: a cell, a claim figure, a column, or a cell or figure; only the last may
repeat), its output (`outputs`), its `license` (on the operator's `license_allowlist`), its
`source` (`shimmer`, or a package pinned by its wheel's SHA-256), its `entry`
(module:function), the `tasks` it serves, `applies_when` (structural facts only, WORDS-A), its
`examples` (a context, ids, the expected output), `approved_by` (a decision id on the registry's
`approving_decisions`, the operator's declared list) and `vetting` (the digest of the declaration
and of its source module, with the result).

The product rule (D-694 item 3 a). When Shimmer runs as a product, no tool sends anything to the
internet: no web search, no lookup, not even a masked or anonymised query. A tool computes only on
what is already inside Shimmer's own run (the context Python hands it). Vetting refuses a tool that
opens a socket.

The switch. A judge contract declaring `request_tools` for a task changes governed inter-agent
structure (it reverses two points of INFRA-049: the judge writes one grammar-bound request and
chooses among the shown tools), so it is honoured ONLY when `config/constitution.json` holds an
amendment with `operator_approved` true whose `change` names both `cell_claim_request` and
`request_tools` (no amendment id is written here; docs/TABLE_TOOL_REQUEST_DELTA_DRAFT.md is the
draft). Without it boot refuses with one line and the run does not start: the declaration is never
ignored silently. With nothing declared the registry is not read at all.
"""
import hashlib
import importlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "table_tools.json"
REQUEST_TASK_NAME = "cell_claim_request"
REQUEST_KEY = "request_tools"
FIELDS = ("name", "does", "inputs", "outputs", "license", "source", "entry", "tasks", "applies_when", "examples",
          "approved_by", "vetting")
FACTS = ("shown_numbers", "claim_figures", "cells_left_out")
PASSED = "passed"
_DECISION_ID = re.compile(r"D-[0-9]+")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ENTRY = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*")
UNRATIFIED = ("[table-tool-request] STOP: a judge contract declares request_tools for %s, which lets the judge "
              "write one tool request, a change to governed inter-agent structure, and config/constitution.json "
              "holds no operator-approved amendment whose change names cell_claim_request and request_tools; "
              "the lead applies the DELTA in docs/TABLE_TOOL_REQUEST_DELTA_DRAFT.md (approved in advance, D-694), or remove request_tools.")


def load(path=None):
    return json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))


def entry(registry, name):
    found = [e for e in (registry or {}).get("tools") or [] if isinstance(e, dict) and e.get("name") == name]
    return found[0] if len(found) == 1 else None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def declaration(entry_):
    """The declaration as vetted: every field but `vetting` itself."""
    return {k: v for k, v in entry_.items() if k != "vetting"}


def module_file(entry_, root=None, search=None):
    """The source file of a `shimmer` tool's module: scripts/<module>.py, or under `search` (a
    folder a vetting fixture names)."""
    module = str(entry_.get("entry") or "").split(":", 1)[0]
    for folder in ([Path(search)] if search else []) + [Path(root or ROOT) / "scripts"]:
        path = folder / (module.replace(".", "/") + ".py")
        if path.is_file():
            return path
    return None


def vetted_sha256(entry_, root=None, search=None):
    """SHA-256 of the canonical declaration and, for a `shimmer` tool, of its module's source with
    CRLF read as LF, so a changed tool is vetted again before it runs."""
    digest = hashlib.sha256(canonical(declaration(entry_)).encode("utf-8"))
    if entry_.get("source") == "shimmer":
        path = module_file(entry_, root, search)
        digest.update(b"\n" + (path.read_bytes().replace(b"\r\n", b"\n") if path else b""))
    return digest.hexdigest()


def license_allowed(entry_, registry):
    """True when the entry's license is on the operator's `license_allowlist`."""
    return (entry_ or {}).get("license") in ((registry or {}).get("license_allowlist") or [])


def approved(entry_, registry):
    """True when the entry names a decision id on the registry's `approving_decisions`, the
    operator's declared list of decisions that approve tools (a well-formed id alone is not enough)."""
    decision = str((entry_ or {}).get("approved_by") or "")
    return bool(_DECISION_ID.fullmatch(decision)) and decision in ((registry or {}).get("approving_decisions") or [])


def _source_refusal(source):
    if source == "shimmer":
        return None
    if isinstance(source, dict) and source.get("package") and source.get("version") \
            and _HEX64.fullmatch(str(source.get("wheel_sha256") or "")):
        return None
    return "its source is neither shimmer nor a package pinned by its wheel's SHA-256"


def _inputs_refusal(inputs):
    import table_tools
    if not isinstance(inputs, list) or not inputs:
        return "it declares no inputs"
    for at, slot in enumerate(inputs):
        if not isinstance(slot, dict) or slot.get("type") not in table_tools.SLOT_TYPES or not slot.get("name"):
            return "an input is not a typed slot"
        least, most = slot.get("min", 1), slot.get("max", 1)
        if type(least) is not int or type(most) is not int or not 1 <= least <= most:
            return "an input's count is not 1 <= min <= max"
        if most > 1 and at != len(inputs) - 1:
            return "only the last input may repeat"
    return None


def entry_refusals(entry_, registry, root=None, search=None):
    """Every reason `entry_` cannot run, [] when it can: a missing field, no operator decision, a
    license off the allowlist, an unpinned source, an untyped input, an unknown fact, or a vetting
    digest that does not match the declaration and source as they are now."""
    name = (entry_ or {}).get("name") or "?"
    missing = [f for f in FIELDS if f not in (entry_ or {})]
    if missing:
        return ["the tool %s lacks %s" % (name, ", ".join(missing))]
    out = []
    if not approved(entry_, registry):
        out.append("the tool %s is approved by no operator decision" % name)
    if not license_allowed(entry_, registry):
        out.append("the tool %s has a license off the operator's allowlist" % name)
    for reason in (_source_refusal(entry_.get("source")), _inputs_refusal(entry_.get("inputs"))):
        if reason:
            out.append("the tool %s: %s" % (name, reason))
    if not _ENTRY.fullmatch(str(entry_.get("entry") or "")):
        out.append("the tool %s names no module:function" % name)
    unknown = [k for k in entry_.get("applies_when") or {} if not (k.startswith("min_") and k[4:] in FACTS)]
    if unknown or not isinstance(entry_.get("applies_when"), dict):
        out.append("the tool %s applies on a fact Python does not read" % name)
    vetting = entry_.get("vetting") if isinstance(entry_.get("vetting"), dict) else {}
    if vetting.get("result") != PASSED or vetting.get("sha256") != vetted_sha256(entry_, root, search):
        out.append("the tool %s is not vetted as declared (run tools/vet_table_tool.py)" % name)
    return out


def resolve(entry_):
    module, function = str(entry_["entry"]).split(":", 1)
    return getattr(importlib.import_module(module), function)


def applies(entry_, facts):
    """True when every declared floor holds on these structural facts."""
    return all(int(facts.get(key[4:], 0)) >= int(least) for key, least in (entry_.get("applies_when") or {}).items())


def relevant(registry, names, task, facts, max_shown):
    """The declared tools (`names`, in the contract's order) that serve `task` and apply here, at
    most `max_shown`, so a small model's list stays short."""
    out = []
    for name in names or []:
        found = entry(registry, name)
        if found and task in (found.get("tasks") or []) and applies(found, facts):
            out.append(found)
    return out[:max_shown]


def request_ratified(root=None):
    """The id of the operator-approved amendment whose change names cell_claim_request and
    request_tools, or None. Self-contained (json, re, Path), as the INST_FINDER switch is."""
    try:
        amendments = json.loads((Path(root or ROOT) / "config" / "constitution.json").read_text(
            encoding="utf-8")).get("amendments") or []
    except (OSError, ValueError, AttributeError):
        return None
    for amendment in amendments:
        if not isinstance(amendment, dict) or amendment.get("operator_approved") is not True:
            continue
        change = amendment.get("change")
        text = change if isinstance(change, str) else json.dumps(change, ensure_ascii=False)
        if re.search(r"(?<![A-Za-z0-9_])cell_claim_request(?![A-Za-z0-9_])", text) \
                and re.search(r"(?<![A-Za-z0-9_])request_tools(?![A-Za-z0-9_])", text):
            return str(amendment.get("id") or "")
    return None


def startup_refusals(task, names, root=None, registry_path=None):
    """Boot's reasons to refuse `task` declaring `names` as its request tools, [] when it may run
    (or when nothing is declared): no ratified amendment, a registry that cannot be read, a name it
    does not hold or holds twice, or an entry `entry_refusals` names."""
    if not names:
        return []
    if request_ratified(root) is None:
        return [UNRATIFIED % task]
    try:
        registry = load(registry_path or Path(root or ROOT) / "config" / "table_tools.json")
    except (OSError, ValueError) as exc:
        return ["the tool registry cannot be read: %s" % type(exc).__name__]
    out = []
    if len(set(names)) != len(names):
        out.append("the task %s names a request tool twice" % task)
    for name in names:
        found = entry(registry, name)
        if found is None:
            out.append("the task %s declares a request tool the registry does not hold once: %s" % (task, name))
            continue
        if task not in (found.get("tasks") or []):
            out.append("the tool %s does not serve the task %s" % (name, task))
        out.extend(entry_refusals(found, registry, root))
    return out
