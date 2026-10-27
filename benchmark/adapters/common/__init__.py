"""Shared parts of the four benchmark adapters (docs/benchmarks/PREREGISTRATION.md).

Standard library only. Nothing here imports the repository's scripts/, so the folder
benchmark/adapters/ runs on its own wherever it is copied.

  ids      opaque ids (section 0), the hash split rule (section 1), the length band
  bundle   the one bundle writer for docs/INPUT_FORMAT.md (input-format-v1-draft)
  cut      the cut rule for long documents (section 5.3), with an injected counter
  mapping  run output to label (sections 5.1 and 5.2), S-1 and S-2
  metrics  the measures of section 3, ABSTAIN and zero division per section 4
  cli      the build, label, score and split commands every adapter shares
"""
