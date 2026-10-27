"""The cut rule for long documents (preregistration section 5.3): the only implementation.

Applied by the adapter before bundling, so every arm receives the same text. The budget
is computed per document (`budget`): the main reading agent's context length, minus the
B1 prompt with an empty document (the largest over the document's items, rendered from
the bundle's own conventions by common/prompt.py), minus the output allowance, minus 32.
Tokens are counted by an injected counter, the main reading agent's own tokenizer, which
the standard library cannot load.

What the token count covers is the document file exactly as written into the bundle
(title, headings, label lines, part texts and the cut line). The words N and M in the
cut line are words of the source parts: whitespace-separated words of a text part, and
for a table the words of its cells (and caption), so M equals the document's source
word count.
"""
from __future__ import annotations

import re

NOTE = "[Document cut. The remaining {removed} of {total} words are not shown.]"
_TABLE_RULE = re.compile(r"^[|:\-]*\|[|:\-]*$")


def budget(max_context: int, prompt_tokens_empty_document: int, output_allowance: int) -> int:
    return int(max_context) - int(prompt_tokens_empty_document) - int(output_allowance) - 32


def words(text: str) -> int:
    """Whitespace-separated words, a token made only of table pipes and rules not counted
    (so a rendered table counts its cell words)."""
    return sum(1 for token in text.split() if not _TABLE_RULE.match(token))


def note(removed: int, total: int) -> str:
    return NOTE.format(removed=removed, total=total)


def not_cut(texts, part_words=None) -> dict:
    counts = list(part_words) if part_words is not None else [words(t) for t in texts]
    return {"cut": False, "applied": False, "words_total": sum(counts), "words_removed": 0,
            "parts_kept": len(texts), "whole_parts_kept": len(texts), "parts_total": len(texts)}


def cut_parts(texts, limit: int, count, render, part_words=None):
    """(kept texts, info). `count(text) -> int` is the model's tokenizer; `render(texts)`
    is the document file those part texts make; `part_words` the source words of each
    part. Whole parts from the start while the document fits, the cut line appended to
    the last kept part; if the first part alone does not fit, it is cut at the last
    whitespace that fits."""
    texts = list(texts)
    counts = list(part_words) if part_words is not None else [words(t) for t in texts]
    total = sum(counts)
    info = dict(not_cut(texts, counts), applied=True, budget=int(limit))
    if count(render(texts)) <= limit:
        return texts, info

    def with_note(kept, kept_words):
        removed = total - kept_words
        return kept[:-1] + [kept[-1].rstrip() + "\n" + note(removed, total)], removed

    best = None
    for k in range(1, len(texts) + 1):
        candidate, removed = with_note(texts[:k], sum(counts[:k]))
        if count(render(candidate)) > limit:
            break
        best = (candidate, removed, k)
    if best is None:
        first = texts[0]
        cuts = [m.start() for m in re.finditer(r"\s", first)]
        lo, hi = 0, len(cuts) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            prefix = first[:cuts[mid]]
            candidate, removed = with_note([prefix], words(prefix))
            if count(render(candidate)) <= limit:
                best, lo = (candidate, removed, 0), mid + 1
            else:
                hi = mid - 1
        if best is None:
            raise ValueError("the budget does not hold even the cut line")
    kept, removed, whole = best
    info.update(cut=True, words_removed=removed, parts_kept=len(kept), whole_parts_kept=whole)
    return kept, info
