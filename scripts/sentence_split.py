"""Where a sentence ends, in any script, decided by the text's form (D-668, READING-A).

passage_pairs used to end a sentence only at `.`, `!` or `?` followed by white space and a
capital or a digit, so a line in Chinese or Japanese (no space after `。`), Hindi (`।`), Arabic
(`؟`), Greek (`;`) or Armenian (`։`) was one passage, and its short sentences under the word
floor were dropped. No language and no locale is named here. What is read is the form:

- a sentence TERMINATOR is a character whose Unicode name says it is a full stop, a question
  mark, an exclamation mark or a danda, in any script (`terminators`), an inverted opening mark
  (Spanish `¿`) and a combining or modifier mark left out;
- after a NARROW terminator (and any closing quotes or brackets) a sentence ends where white
  space is followed, past any opening quote or bracket, by a digit or by a letter that is not
  lowercase (a capital, or a letter of a script with no case): "e.g. the" stays one sentence;
- after a WIDE terminator (East Asian width wide or fullwidth, the form of `。` and `！`) a
  sentence ends at once, with or without white space, since those scripts put no space there;
- a word is the one tokeniser's (`pairing_map.words`); a run of wide characters counts as one
  word for every two of its characters, since those scripts write no space between words.

For ASCII text the ends are exactly the ones the old pattern found, and the word count is the
same. A stretch of more than `LONGEST` characters in which no end is found is text Python cannot
split: it is refused on the record (`refusal`), never handed on as one sentence; why is
`no_sentence_end` (no terminator in it: Thai, or a script whose stop has no such name) or
`sentence_end_not_decided` (a terminator Python could not decide on, as before a lowercase
letter in a script whose letters are all lowercase).
"""
from __future__ import annotations

import functools
import sys
import unicodedata

import pairing_map

# Measured on every Markdown file under benchmark/ (1317 files, 16 November 2026): the longest
# passage any of them gives is far below this, so nothing shipped is refused (check 498).
LONGEST = 1200
NO_END, NOT_DECIDED = "no_sentence_end", "sentence_end_not_decided"
_NAMES = ("FULL STOP", "QUESTION MARK", "EXCLAMATION MARK", "DANDA")
_NOT_NAMES = ("INVERTED", "COMBINING", "MODIFIER")
# The old pattern's quote and bracket marks, kept so ASCII text ends where it always did.
_OLD_CLOSING = "\"')]" + chr(0x201D) + chr(0x2019)
_OLD_OPENING = "\"'([" + chr(0x201C) + chr(0x2018)


@functools.lru_cache(maxsize=1)
def terminators() -> frozenset:
    """Every sentence terminator of the Basic and Supplementary Multilingual Planes, by name."""
    found = set()
    for code in range(min(sys.maxunicode, 0x1FFFF) + 1):
        name = unicodedata.name(chr(code), "")
        if any(n in name for n in _NAMES) and not any(n in name for n in _NOT_NAMES):
            found.add(chr(code))
    return frozenset(found)


def _wide(ch) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def _closing(ch) -> bool:
    """A closing quote or bracket: an ASCII one of the old pattern's, or any other character of
    a closing or quote punctuation class (a quote mark closes in one script and opens in another,
    so its place, right after the terminator, decides)."""
    if ch.isascii():
        return ch in _OLD_CLOSING
    return ch in _OLD_CLOSING or unicodedata.category(ch) in ("Pe", "Pf", "Pi")


def _opening(ch) -> bool:
    """An opening quote or bracket, or an inverted opening mark (`¿`, `¡`)."""
    if ch.isascii():
        return ch in _OLD_OPENING
    return (ch in _OLD_OPENING or unicodedata.category(ch) in ("Ps", "Pi", "Pf")
            or (unicodedata.category(ch) == "Po" and "INVERTED" in unicodedata.name(ch, "")))


def _starts(ch) -> bool:
    """A character a sentence may start with after a narrow terminator: a digit, or a letter
    that is not lowercase (the old pattern's capital, widened to every script's)."""
    return ch.isdigit() or (ch.isalpha() and unicodedata.category(ch) != "Ll")


def ends(line: str) -> list:
    """The offsets in `line` where a sentence ends and the next begins, in order."""
    stops = terminators()
    out, i, n = [], 0, len(line)
    while i < n:
        if line[i] not in stops:
            i += 1
            continue
        j = i
        while j < n and line[j] in stops:
            j += 1
        wide = _wide(line[j - 1])
        while j < n and _closing(line[j]):
            j += 1
        k = j
        while k < n and line[k].isspace():
            k += 1
        if wide:
            if k < n:
                out.append(k)
        elif k > j and k < n:
            # one opening mark at most, then a letter; or a digit with no mark before it
            if _opening(line[k]):
                if k + 1 < n and line[k + 1].isalpha() and unicodedata.category(line[k + 1]) != "Ll":
                    out.append(k)
            elif _starts(line[k]):
                out.append(k)
        i = max(j, i + 1)
    return out


def size(text: str) -> int:
    """How many words `text` holds: the one tokeniser's words, a hyphen separating, each run of
    wide characters counting one word per two characters (at least one)."""
    count = 0
    for word in pairing_map.words(text, join_hyphens=False):
        wide = sum(1 for ch in word if _wide(ch))
        count += max(1, wide // 2) if wide else 1
    return count


def refusal(piece: str):
    """None when `piece` is a sentence Python may hand on; else why it cannot be split."""
    if len(piece) <= LONGEST:
        return None
    stops = terminators()
    return NOT_DECIDED if any(ch in stops for ch in piece) else NO_END
