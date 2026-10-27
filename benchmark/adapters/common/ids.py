"""Opaque ids (preregistration section 0), the hash split rule (section 1) and the
length band (section 1, holdout sampling)."""
from __future__ import annotations

import hashlib

BENCHMARKS = ("contradoc", "cuad", "scitab", "findver", "contractnli")
OPAQUE_LENGTH = 12
SPLIT_MODULUS = 5
DEVELOPMENT = "development"
HOLDOUT = "holdout"
# Length bands by the document's words (`word_count`, section 5.6): (name, lower bound).
LENGTH_BANDS = (("A", 0), ("B", 1000), ("C", 5000), ("D", 20000))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key_string(value) -> str:
    """The split key as a string (section 1): an integer in decimal with no sign and no
    leading zeros, a string exactly as stored. Anything else is refused."""
    if isinstance(value, bool):
        raise TypeError("a boolean is not an id")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("a negative integer id has no unsigned decimal form")
        return str(value)
    if isinstance(value, str):
        return value
    raise TypeError("an id must be an integer or a string, not " + type(value).__name__)


def _check(benchmark: str) -> str:
    if benchmark not in BENCHMARKS:
        raise ValueError("unknown benchmark " + repr(benchmark))
    return benchmark


def opaque_item_id(benchmark: str, source_item_id) -> str:
    """First 12 hex characters of SHA-256 of `item:<benchmark>:<source item id>`."""
    return sha256_hex("item:%s:%s" % (_check(benchmark), key_string(source_item_id)))[:OPAQUE_LENGTH]


def opaque_document_id(benchmark: str, source_document_id) -> str:
    """First 12 hex characters of SHA-256 of `document:<benchmark>:<source document id>`."""
    return sha256_hex("document:%s:%s" % (_check(benchmark), key_string(source_document_id)))[:OPAQUE_LENGTH]


def text_identity(text: str) -> str:
    """A document "identified by the SHA-256 of its text": the lowercase hex SHA-256 of
    the UTF-8 bytes of the text exactly as distributed, no normalisation."""
    return sha256_hex(text)


def split_value(key) -> int:
    """SHA-256 of the key's UTF-8 bytes, read as an unsigned big-endian integer."""
    return int.from_bytes(hashlib.sha256(key_string(key).encode("utf-8")).digest(), "big")


def split_side(key) -> str:
    """Development when the digest is 0 modulo 5, otherwise the holdout pool. The key is
    always the DOCUMENT's split key, never an item id."""
    return DEVELOPMENT if split_value(key) % SPLIT_MODULUS == 0 else HOLDOUT


_MARKUP_CHARACTERS = frozenset("|-:")


def is_table_word(token: str) -> bool:
    """Inside table text a token made only of `-`, `:` and `|` is markup, not a word
    (preregistration section 5.6, Words)."""
    return not set(token) <= _MARKUP_CHARACTERS


def is_pipe_row(line: str) -> bool:
    """A line whose first non-blank character is `|`: a table row, so table text."""
    return line.lstrip().startswith("|")


def cell_word_count(cell: str) -> int:
    """The words of one table cell (SciTab's column names and cell values): table text."""
    return sum(1 for token in str(cell).split() if is_table_word(token))


def word_count(text: str) -> int:
    """The one word count (section 5.6, Words): Python's str.split() with no argument, on
    each line; on a pipe row (table text) a token made only of `-`, `:` and `|` is not a
    word, on any other line every token is. Bands, the cut line's N and M and every count
    in parts.json use it, so a table's words are its cell words wherever it is counted."""
    total = 0
    for line in text.split("\n"):
        tokens = line.split()
        total += sum(1 for t in tokens if is_table_word(t)) if is_pipe_row(line) else len(tokens)
    return total


def length_band(words: int) -> str:
    band = LENGTH_BANDS[0][0]
    for name, lower in LENGTH_BANDS:
        if words >= lower:
            band = name
    return band
