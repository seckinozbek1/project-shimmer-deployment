"""B3's reading of a long document in segments (D-S13 item 7; docs/benchmarks/FINDVER_B1_REVISION.md
section 3): the same text every arm receives, after the cut rule of section 5.3, split for
B3 alone into consecutive segments of whole parts, so that no B3 model call exceeds its
model's context.

A segmented document gets a second bundle, `<build>/b3_segments/<document id>/`, which B3
runs in place of the document's own bundle: one run, its targets the segment documents
`<document id>-sNN.md`, each a document of its own to the pipeline. A segment document
keeps the parts' own headings (`## P-00034` stays `## P-00034`), so the unit id the
pipeline gives a segment's j-th part, `u<j>-p-<k>`, names the document's part k, whose
unit id is `u<k>-p-<k>` (`unit_map`). The rules are the document's, every one in
every segment. The labels of a segmented document read every segment's records from that
one run, unit ids translated back (common/mapping.py, `read_segmented_run`).

`ranges` is the one segmentation rule: parts in order, a segment closed before the part
that would take its document file, as written, over `limit` tokens of the main reading
agent's tokenizer. A part that alone exceeds the limit is a segment of its own and is
listed `over_limit`; it is never split, so a unit is never cut in two.
"""
from __future__ import annotations

from . import bundle

SEGMENTS_DIR = "b3_segments"
SEGMENT_SUFFIX = "-s%02d"


def segment_id(document_id: str, position: int) -> str:
    return document_id + SEGMENT_SUFFIX % position


def render_segment(segment_document_id: str, texts, first: int) -> str:
    """A segment document: its title, then the parts `first`, `first + 1`, ... under
    their own document's headings, written exactly as the document writes them."""
    blocks = [bundle.TITLE_PREFIX + segment_document_id]
    for k, text in enumerate(texts, start=first):
        body = bundle.part_lines(text)
        block = bundle.PART_HEADING % k + "\n\n" + bundle.PART_LABEL_LINE
        if body:
            block += "\n\n" + "\n".join(body)
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def segment_unit(position: int, k: int) -> str:
    """The unit id the pipeline gives the `position`-th part of a segment document whose
    heading is the document's part k."""
    return "u%02d-%s" % (position, bundle.slug(bundle.heading_text(k)))


def ranges(document_id: str, texts, limit: int, count) -> list:
    """[{segment_id, first, last, tokens, over_limit}] over `texts` (the kept parts), in
    order; `count(text) -> int` is the main reading agent's tokenizer."""
    out, first = [], 1
    total = len(texts)
    while first <= total:
        last = first
        sid = segment_id(document_id, len(out) + 1)
        tokens = count(render_segment(sid, texts[first - 1:last], first))
        while last < total:
            wider = count(render_segment(sid, texts[first - 1:last + 1], first))
            if wider > limit:
                break
            last, tokens = last + 1, wider
        out.append({"segment_id": sid, "first": first, "last": last, "tokens": tokens,
                    "over_limit": tokens > limit})
        first = last + 1
    return out


def plan(count, limit: int):
    """The bundle writer's segment hook (bundle.write_bundles `segment`): for each document,
    its segments by `ranges`; a document of one segment keeps its own bundle for B3
    (`b3_bundle` is its id, `b3_segments` empty); a longer one gets its segment bundle,
    and its parts record lists the segments (no gold; the answer key stays the scorer's)."""
    limit = int(limit)
    if limit <= 0:
        raise ValueError("the B3 segment limit is a positive number of tokens")

    def write(out, doc, kept, record, answers):
        doc_id = doc["document_id"]
        found = ranges(doc_id, kept, limit, count)
        record["b3_segment_limit"] = limit
        if len(found) == 1:
            record["b3_bundle"], record["b3_segments"] = doc_id, []
            return
        folder = out / SEGMENTS_DIR / doc_id
        names = []
        for seg in found:
            name = seg["segment_id"] + ".md"
            names.append(name)
            bundle.write_text(folder / bundle.CONTEXT_DIR / name, render_segment(
                seg["segment_id"], kept[seg["first"] - 1:seg["last"]], seg["first"]))
        bundle.write_json(folder / bundle.CONTEXT_DIR / bundle.MANIFEST_NAME,
                          dict(bundle.manifest(names[0]), targets=names))
        bundle.write_text(folder / bundle.CONVENTIONS_DIR / bundle.RULES_NAME,
                          bundle.render_rules(doc["rules"]))
        bundle.write_json(folder / bundle.ANSWER_NAME, {
            "document": doc_id + ".md", "b3_segments": names,
            "task_given_to_the_pipeline": bundle.TASK_LINE, "twin_of": "", "planted": [],
            "clean": [], "benchmark": doc.get("benchmark"), "input_format": bundle.INPUT_FORMAT_VERSION,
            "unit_ids": "the document's, as in its own bundle", "items": answers})
        record["b3_bundle"] = SEGMENTS_DIR + "/" + doc_id
        record["b3_segments"] = found
    return write


def unit_map(record) -> dict:
    """{segment unit id: document unit id} for one segment record of parts.json."""
    return {segment_unit(j, k): bundle.unit_id(k)
            for j, k in enumerate(range(int(record["first"]), int(record["last"]) + 1), start=1)}
