"""The cut rule for long documents (preregistration section 5.3), applied before
bundling so every arm receives the same text.

The token counter is injected: section 5.3 counts with the main reading agent's own
tokenizer from the pinned checkpoint, which the standard library cannot load. The
budget (context length minus the B1 prompt with an empty document, minus the output
allowance, minus 32) is computed by the caller from the values VERSIONS.md pins;
`budget()` is that arithmetic.

What is counted is the document file exactly as it is written into the bundle
(title, headings, label lines, part texts and the cut line). Words for the cut line
are whitespace-separated words of the parts' source text before bundling.
"""
from __future__ import annotations

import re

NOTE = "[Document cut: the remaining {removed} of {total} words are not shown.]"


def budget(max_context: int, prompt_tokens_empty_document: int, output_allowance: int) -> int:
    return int(max_context) - int(prompt_tokens_empty_document) - int(output_allowance) - 32


def words(text: str) -> int:
    return len(text.split())


def note(removed: int, total: int) -> str:
    return NOTE.format(removed=removed, total=total)


def not_cut(texts) -> dict:
    return {"cut": False, "applied": False, "words_total": sum(words(t) for t in texts),
            "words_removed": 0, "parts_kept": len(texts), "whole_parts_kept": len(texts),
            "parts_total": len(texts)}


def _with_note(kept, total):
    removed = total - sum(words(t) for t in kept)
    return kept[:-1] + [kept[-1].rstrip() + "\n" + note(removed, total)], removed


def cut_parts(texts, limit: int, count, render):
    """(kept texts, info). `count(text) -> int` is the model's tokenizer; `render(texts)`
    is the document file those part texts make. Whole parts from the start while the
    document fits, the cut line appended to the last kept part; if the first part alone
    does not fit, it is cut at the last whitespace that fits."""
    texts = list(texts)
    total = sum(words(t) for t in texts)
    info = dict(not_cut(texts), applied=True)
    if count(render(texts)) <= limit:
        return texts, info
    best = None
    for k in range(1, len(texts) + 1):
        candidate, removed = _with_note(texts[:k], total)
        if count(render(candidate)) > limit:
            break
        best = (candidate, removed, k)
    if best is None:
        first = texts[0]
        cuts = [m.start() for m in re.finditer(r"\s", first)]
        lo, hi = 0, len(cuts) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate, removed = _with_note([first[:cuts[mid]]], total)
            if count(render(candidate)) <= limit:
                best, lo = (candidate, removed, 0), mid + 1
            else:
                hi = mid - 1
        if best is None:
            raise ValueError("the budget does not hold even the cut line")
    kept, removed, whole = best
    info.update(cut=True, words_removed=removed, parts_kept=len(kept), whole_parts_kept=whole)
    return kept, info
