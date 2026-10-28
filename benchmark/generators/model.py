"""The abstract test model the families build, and its rendering to Markdown.

A family never writes Markdown by hand: it builds a Doc (title, preamble, units of
blocks), a Conventions (rules), and Reference files, and this module renders them in
the one layout the published format describes (section 2 and 3): one title line,
every unit heading at level 2, label lines, tables in their own paragraph, blank lines
between blocks, LF endings, ASCII only.
"""
import copy


class Unit:
    def __init__(self, heading, blocks, tag=None):
        self.heading = heading
        self.blocks = blocks          # list of ("lines", [[label, value], ...]) | ("table", headers, rows) | ("prose", text)
        self.tag = tag                # family bookkeeping (never rendered)

    def clone(self):
        return Unit(self.heading, copy.deepcopy(self.blocks), copy.deepcopy(self.tag))

    def line_value(self, label):
        for b in self.blocks:
            if b[0] == "lines":
                for pair in b[1]:
                    if pair[0] == label:
                        return pair[1]
        return None

    def set_line(self, label, value):
        for b in self.blocks:
            if b[0] == "lines":
                for pair in b[1]:
                    if pair[0] == label:
                        pair[1] = value
                        return
        raise KeyError(label)

    def remove_line(self, label):
        for b in self.blocks:
            if b[0] == "lines":
                for i, pair in enumerate(b[1]):
                    if pair[0] == label:
                        del b[1][i]
                        return
        raise KeyError(label)

    def insert_line(self, label, value, block=0, after=None):
        lines_blocks = [b for b in self.blocks if b[0] == "lines"]
        b = lines_blocks[block]
        if after is None:
            b[1].append([label, value])
            return
        for i, pair in enumerate(b[1]):
            if pair[0] == after:
                b[1].insert(i + 1, [label, value])
                return
        raise KeyError(after)


class Doc:
    def __init__(self, title, preamble, units):
        self.title = title
        self.preamble = preamble
        self.units = units

    def clone(self):
        return Doc(self.title, self.preamble, [u.clone() for u in self.units])


class Rule:
    def __init__(self, rid, name, text, scope=None, requires=None, severity="required",
                 tags=("conformance",)):
        self.rid = rid
        self.name = name
        self.text = text
        self.scope = list(scope or [])
        self.requires = list(requires or [])
        self.severity = severity
        self.tags = list(tags)


class Conventions:
    def __init__(self, title, intro, rules):
        self.title = title
        self.intro = intro
        self.rules = rules


def _render_blocks(blocks):
    parts = []
    for b in blocks:
        if b[0] == "lines":
            if b[1]:
                parts.append("\n".join("%s: %s" % (lab, val) for lab, val in b[1]))
        elif b[0] == "table":
            headers, rows = b[1], b[2]
            lines = ["| " + " | ".join(headers) + " |",
                     "|" + "|".join("---" for _ in headers) + "|"]
            for row in rows:
                lines.append("| " + " | ".join(row) + " |")
            parts.append("\n".join(lines))
        elif b[0] == "prose":
            parts.append(b[1])
        else:
            raise ValueError("unknown block %r" % (b[0],))
    return parts


def render_doc(doc):
    parts = ["# " + doc.title]
    if doc.preamble:
        parts.append(doc.preamble)
    for u in doc.units:
        parts.append("## " + u.heading)
        parts.extend(_render_blocks(u.blocks))
    return "\n\n".join(parts) + "\n"


def render_reference(title, blocks):
    return "\n\n".join(["# " + title] + _render_blocks(blocks)) + "\n"


def render_conventions(conv):
    parts = ["# " + conv.title, conv.intro]
    for r in conv.rules:
        head = "## %s %s [%s]" % (r.rid, r.name, r.severity)
        for t in r.tags:
            head += " [%s]" % t
        if r.scope:
            head += " [scope: %s]" % ", ".join(r.scope)
        if r.requires:
            head += " [requires: %s]" % ", ".join(r.requires)
        parts.append(head)
        parts.append(r.text)
    return "\n\n".join(parts) + "\n"
