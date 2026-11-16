"""A JSON schema as a DECODING-B logits constraint (D-672, D-663 (b), #279).

A reply that must be one JSON object of a declared shape (the negotiation advisor's advice and the
validator's mapping) is decoded under a constraint built per request from that request's own schema: object
keys in their declared order, every required key present, enumerated values (ids and labels read from the
item) written as one of their declared strings, free strings within their declared length, integers or
null where declared. The constraint is a grammar for scripts/contract_decoding.py's ContractProcessor, so the
token mask, the stop-token rule and the intervention counts are that processor's own; nothing here chooses a
token. Whitespace is admitted where JSON admits it (up to WS_MAX characters in a run), no fence and no text
around the object.

Schema nodes (plain dicts, built by the caller):
    {"type": "object", "keys": [[name, node, required], ...]}
    {"type": "array", "items": node}
    {"type": "enum", "values": [str, ...]}
    {"type": "string", "max_chars": int}
    {"type": "integer_or_null"}
"""
from __future__ import annotations

import hashlib
import json

import contract_decoding

NAME = "json-schema-contract"
VERSION = 1
WS = " \n\t\r"
WS_MAX = 16
DONE = contract_decoding.DONE
ALPHABET = tuple(chr(c) for c in range(32, 127)) + ("\n", "\t", "\r")
HEX = "0123456789abcdefABCDEF"
ESCAPES = '"\\/bfnrt'


def _check(node, path="$"):
    kind = node.get("type") if isinstance(node, dict) else None
    contract_decoding.require(kind in ("object", "array", "enum", "string", "integer_or_null"),
                              "A schema node needs a known type: " + path)
    if kind == "object":
        names = [k[0] for k in node["keys"]]
        contract_decoding.require(names and len(set(names)) == len(names), "An object declares distinct keys: " + path)
        for name, child, _required in node["keys"]:
            contract_decoding.require(all(c not in name for c in '"\\') and name, "A key is plain text: " + path)
            _check(child, path + "." + name)
    elif kind == "array":
        _check(node["items"], path + "[]")
    elif kind == "enum":
        values = node["values"]
        contract_decoding.require(values and all(isinstance(v, str) and v and all(c not in v for c in '"\\')
                                                 for v in values), "An enum declares plain strings: " + path)
    elif kind == "string":
        contract_decoding.require(type(node["max_chars"]) is int and node["max_chars"] > 0,
                                  "A string declares its length: " + path)


def digest(schema):
    return hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class SchemaGrammar:
    """The schema's canonical-enough JSON as states over characters. A state is a tuple of frames (a stack,
    innermost last), or DONE once the top value is closed; `walk` returns None for text the schema refuses."""

    def __init__(self, schema):
        _check(schema)
        self.nodes = []
        self.root = self._index(schema)
        self.signature = NAME + ":" + digest(schema)

    def _index(self, node):
        n = len(self.nodes)
        self.nodes.append(None)
        kind = node["type"]
        if kind == "object":
            compiled = {"type": "object", "keys": [(name, self._index(child), bool(req)) for name, child, req in node["keys"]]}
        elif kind == "array":
            compiled = {"type": "array", "items": self._index(node["items"])}
        else:
            compiled = dict(node)
        self.nodes[n] = compiled
        return n

    # frames: ("V", n, ws) a value of node n is due; ("E", n, prefix) inside an enum string;
    # ("S", n, length, esc) inside a free string (esc 0 none, 1 after a backslash, 2..5 hex digits left);
    # ("I", n, digits) an integer; ("L", n, done) the literal null; ("O", n, at, phase, ws) an object:
    # `at` the index of the next key that may come, phase "open" | "key" | "colon" | "after";
    # ("K", n, at, prefix) inside a key string of object n; ("A", n, count, phase, ws) an array: phase
    # "open" | "after" | "next".

    def start(self):
        return (("V", self.root, 0),)

    def _complete(self, stack):
        """The parent of a value that has just been closed."""
        if not stack:
            return DONE
        top = stack[-1]
        if top[0] == "O":
            return stack[:-1] + (("O", top[1], top[2], "after", 0),)
        if top[0] == "A":
            return stack[:-1] + (("A", top[1], top[2] + 1, "after", 0),)
        raise AssertionError("a value closed under %r" % (top,))

    def _open_value(self, stack, n, ch):
        node = self.nodes[n]
        kind = node["type"]
        if kind == "object" and ch == "{":
            return stack + (("O", n, 0, "open", 0),)
        if kind == "array" and ch == "[":
            return stack + (("A", n, 0, "open", 0),)
        if kind == "enum" and ch == '"':
            return stack + (("E", n, ""),)
        if kind == "string" and ch == '"':
            return stack + (("S", n, 0, 0),)
        if kind == "integer_or_null":
            if ch.isdigit():
                return stack + (("I", n, ch),)
            if ch == "-":
                return stack + (("I", n, "-"),)
            if ch == "n":
                return stack + (("L", n, 1),)
        return None

    def _keys_left(self, n, at):
        return self.nodes[n]["keys"][at:]

    def _may_close(self, n, at):
        return not any(req for _name, _child, req in self._keys_left(n, at))

    def step(self, state, ch):
        if state is None or state == DONE:
            return None
        stack = state[:-1]
        top = state[-1]
        kind = top[0]
        if kind == "V":
            _, n, ws = top
            if ch in WS:
                return stack + (("V", n, ws + 1),) if ws < WS_MAX else None
            return self._open_value(stack, n, ch)
        if kind == "E":
            _, n, prefix = top
            values = self.nodes[n]["values"]
            if ch == '"':
                return self._complete(stack) if prefix in values else None
            grown = prefix + ch
            return stack + (("E", n, grown),) if any(v.startswith(grown) for v in values) else None
        if kind == "S":
            _, n, length, esc = top
            if esc == 1:
                if ch == "u":
                    return stack + (("S", n, length, 5),)
                return stack + (("S", n, length + 1, 0),) if ch in ESCAPES else None
            if esc >= 2:
                if ch not in HEX:
                    return None
                return stack + (("S", n, length + (1 if esc == 2 else 0), 0 if esc == 2 else esc - 1),)
            if ch == '"':
                return self._complete(stack)
            if ch < " ":
                return None
            if length >= self.nodes[n]["max_chars"]:
                return None
            if ch == "\\":
                return stack + (("S", n, length, 1),)
            return stack + (("S", n, length + 1, 0),)
        if kind == "I":
            _, n, digits = top
            if ch.isdigit():
                if digits in ("0", "-0"):
                    return None
                return stack + (("I", n, digits + ch),) if len(digits) < 12 else None
            if digits in ("", "-"):
                return None
            return self.step(self._complete(stack), ch)
        if kind == "L":
            _, n, done = top
            if ch == "null"[done]:
                return self._complete(stack) if done == 3 else stack + (("L", n, done + 1),)
            return None
        if kind == "O":
            _, n, at, phase, ws = top
            if ch in WS and phase in ("open", "after", "next", "colon"):
                return stack + (("O", n, at, phase, ws + 1),) if ws < WS_MAX else None
            if phase in ("open", "next"):
                if ch == '"' and self._keys_left(n, at):
                    return stack + (("K", n, at, ""),)
                if ch == "}" and phase == "open" and self._may_close(n, at):
                    return self._complete(stack)
                return None
            if phase == "after":
                if ch == "," and self._keys_left(n, at):
                    return stack + (("O", n, at, "next", 0),)
                if ch == "}" and self._may_close(n, at):
                    return self._complete(stack)
                return None
            if phase == "colon":
                if ch == ":":
                    child = self.nodes[n]["keys"][at - 1][1]
                    return stack + (("O", n, at, "value", 0), ("V", child, 0))
                return None
            return None
        if kind == "K":
            _, n, at, prefix = top
            keys = self.nodes[n]["keys"]
            if ch == '"':
                for j in range(at, len(keys)):
                    name, _child, required = keys[j]
                    if name == prefix:
                        return stack + (("O", n, j + 1, "colon", 0),)
                    if required:
                        break
                return None
            grown = prefix + ch
            for j in range(at, len(keys)):
                name, _child, required = keys[j]
                if name.startswith(grown):
                    return stack + (("K", n, at, grown),)
                if required:
                    break
            return None
        if kind == "A":
            _, n, count, phase, ws = top
            if ch in WS:
                return stack + (("A", n, count, phase, ws + 1),) if ws < WS_MAX else None
            if phase == "open" and ch == "]":
                return self._complete(stack)
            if phase in ("open", "next"):
                child = self.nodes[n]["items"]
                opened = self._open_value(stack + (("A", n, count, "value", 0),), child, ch)
                return opened
            if phase == "after":
                if ch == ",":
                    return stack + (("A", n, count, "next", 0),)
                if ch == "]":
                    return self._complete(stack)
            return None
        return None

    def walk(self, state, text):
        for ch in text:
            state = self.step(state, ch)
            if state is None:
                return None
        return state

    def free(self, state):
        return state not in (None, DONE) and state[-1][0] == "S" and state[-1][3] == 0

    def bound(self, state):
        if self.free(state):
            _, n, length, _esc = state[-1]
            return self.nodes[n]["max_chars"] - length
        return None

    def next_chars(self, state):
        return [ch for ch in ALPHABET if self.step(state, ch) is not None]

    def accepting(self, state):
        if state == DONE:
            return True
        # an integer at the top level closes only on a following character; none of the shapes here does
        return False

    def unrestricted(self, state):
        return False


def accepts(schema, text):
    """Whether `text` is a reply of `schema` (the walk ends on the closed top value)."""
    grammar = SchemaGrammar(schema)
    return grammar.walk(grammar.start(), text) == DONE


class SchemaContract:
    def __init__(self, name, schema):
        self.agent, self.schema = name, schema

    def digest(self):
        return digest(self.schema)


def constraint(name, schema, tok, prompt_tokens, eos_ids, source):
    """The Constraint of one call: its processor under this schema, the generate() keyword that carries it,
    and the record (name, version, schema digest, request source, counts) for the reply record."""
    spec = {"name": NAME, "version": VERSION}
    return contract_decoding.Constraint(SchemaContract(name, schema), spec, digest(schema), tok, prompt_tokens,
                                        eos_ids, source, grammar=SchemaGrammar(schema))
