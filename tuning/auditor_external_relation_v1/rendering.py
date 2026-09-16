"""Reversible wrappers; no paraphrase, sentence segmentation, or word reordering."""
import hashlib

PAIRS = [('plain', 'bullet'), ('bullet', 'plain'), ('plain', 'numbered'),
         ('numbered', 'plain'), ('bullet', 'numbered'), ('numbered', 'bullet')]
PREFIX = {'plain': '', 'bullet': '- ', 'numbered': '1. '}

def pair(lineage):
    return PAIRS[int(hashlib.sha256(('render:'+lineage).encode()).hexdigest(), 16) % len(PAIRS)]

def render(text, style):
    return PREFIX[style] + text

def reverse(text, style):
    prefix = PREFIX[style]
    if not text.startswith(prefix):
        raise ValueError('renderer_prefix')
    return text[len(prefix):]
