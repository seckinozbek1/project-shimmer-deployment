"""The B1 prompt of preregistration section 5.4, rendered in one place.

`benchmark/baselines/bare_model.py` sends it and the adapters' cut rule (section 5.3)
counts it, so both read the same template (`benchmark/baselines/b1_prompt.json`) through
these functions. Standard library only.

  conventions_from_bundle  every convention of a bundle as written in it: the heading
                           without its leading `#`s, and its text on one line
  reference_from_bundle    the bundle's grounding files (the earlier version included),
                           each as its file name and its text; empty when there are none
  render_user              the user turn, each slot filled once
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_PROMPT = Path(__file__).resolve().parents[2] / "baselines" / "b1_prompt.json"
NO_REFERENCE = "None."
_SLOT = re.compile(r"\{(document|conventions|reference_material|item_id|rule_id|question|"
                   r"label_lines|undecided_label)\}")
_HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*$")
_RULE_ID = re.compile(r"CONV-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", re.IGNORECASE)


def load_prompt(path=None) -> dict:
    spec = json.loads(Path(path or DEFAULT_PROMPT).read_text(encoding="utf-8"))
    for key in ("system", "user_template", "convention_line", "benchmarks"):
        if key not in spec:
            raise ValueError("b1_prompt.json lacks " + key)
    return spec


def conventions_from_text(text: str) -> list:
    """[(heading, text)] for every heading from the first one carrying an operator id
    (`CONV-...`) on, its text being the non-blank lines under it joined by single spaces.
    Paragraphs before the first rule heading are not rules (input format section 3)."""
    rules, current, started = [], None, False
    for line in text.replace("\r\n", "\n").split("\n"):
        m = _HEADING.match(line)
        if m:
            started = started or bool(_RULE_ID.search(m.group(2)))
            current = [m.group(2), []] if started else None
            if current is not None:
                rules.append(current)
        elif current is not None and line.strip():
            current[1].append(line.strip())
    return [(heading, " ".join(" ".join(lines).split())) for heading, lines in rules]


def conventions_from_bundle(bundle) -> list:
    folder = Path(bundle) / "conventions"
    out = []
    for path in sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []:
        out += conventions_from_text(path.read_text(encoding="utf-8"))
    return out


def rule_id_of(heading: str) -> str:
    m = _RULE_ID.search(heading)
    return m.group(0) if m else ""


def reference_from_bundle(bundle) -> str:
    """The grounding files named by the manifest (`grounding` and `prior`), in file-name
    order, each as `<file name>` on one line and its text below; empty when none."""
    context = Path(bundle) / "context"
    manifest = json.loads((context / "_review_targets.json").read_text(encoding="utf-8"))
    names = sorted(set(manifest.get("grounding") or []) | set(manifest.get("prior") or []))
    names = [n for n in names if n not in (manifest.get("targets") or [])]
    blocks = []
    for name in names:
        text = (context / name).read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n")
        blocks.append(name + "\n" + text)
    return "\n\n".join(blocks)


def conventions_block(spec, conventions) -> str:
    return "\n".join(spec["convention_line"].replace("{heading}", heading).replace("{rule_text}", text)
                     for heading, text in conventions)


def render_user(spec, bench_key, *, document, conventions, item, reference="") -> str:
    bench = spec["benchmarks"][bench_key]
    values = {
        "document": document,
        "conventions": conventions_block(spec, conventions),
        "reference_material": reference or NO_REFERENCE,
        "item_id": item["item_id"],
        "rule_id": item["rule_id"],
        "question": bench["question"],
        "label_lines": "\n".join(bench["labels"]),
        "undecided_label": bench["undecided"],
    }
    # One pass: a filled slot is never read again, so braces in the document stay text.
    return _SLOT.sub(lambda m: values[m.group(1)], spec["user_template"])


def overhead(spec, items, conventions, count_prompt, reference="") -> int:
    """The token count of the prompt with an empty document, the largest over `items`;
    count_prompt(system, user) counts the whole prompt as the model sees it."""
    return max(count_prompt(spec["system"], render_user(
        spec, str(i["benchmark"]).lower(), document="", conventions=conventions, item=i,
        reference=reference)) for i in items)
