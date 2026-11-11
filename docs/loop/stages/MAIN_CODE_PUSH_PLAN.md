# Bringing GitHub's main up to the current code (D-487 item 3, D-488)

Seckin approved the push at 19:21 (D-488). This file is the short record of how it is done; the
measurements behind it were made on 11 November between 19:30 and 20:00 and give counts only.

## Why it was not pushed before

D-S5 rule 3 sent the loop branch to `main` only after S14. D-190 gave the public `main` the rewrite of
what GitHub held on 2 November. D-192 (S13 step 11): the local repository keeps the unrewritten history,
so its pre-push hook refuses every push from it; later stages were to reach GitHub only through S14 item
8. Standing order 33 let the local repository push only the progress page (widened by D-482 for the
README and its linked files). The loop tip's tree, as the local repository holds it, still carries the
personal path forms in 181 files (15,433 matches of the verify expression); the project's name and the
collaborator's name have 0 hits in the tree and are in the old history only.

## The route

A fresh clone of the public repository; one new commit on its `main` holding the loop branch's tree,
made by `tools/loop/export_public_tree.py`, never from the old history. The tool leaves out the
excluded classes, applies the S13 rewrite expressions (`expressions.txt`, read at run time) to every
blob and path, takes from the published `loop-v1` every file unchanged since the S13 cut-off (so step 6's
edits stay), keeps the Pages files and the commit map that only the public side holds, and writes the
commit with git plumbing so no filter alters a byte. It reports any changed file whose source digest
another file pins. The local repository's hook and lock are not touched. An independent scanner agent
checks the commit before the lead pushes it.

The alternative, a fresh `git filter-repo` pass over the whole loop branch (S14 item 8 as written),
would force-push `loop/2026-10-27` again (its published tip exists only in the S13 mirror) and publish
every intermediate text of 833 commits; it stays S14 item 8, for Seckin to keep or drop.

## Measured on a throwaway copy

- `git filter-repo` on a one-commit copy of the tree: 79 s; 181 files changed, no path renamed; 179 of
  the 181 come out byte-equal to the copies already public in `loop-v1`.
- S13's `verify_all.py` on that copy, 115 s: 0 for the name expression, the private patterns, the wider
  verify expression, each path form in any case and its UTF-16 form, in objects, messages and paths; 0
  paths under a refused folder; key patterns 0; 5 credential-name matches, all placeholders already
  public.
- The 8 `.docx` files new since `loop-v1`: 156 members, 0 hits.
- Files over 50 MB: 0. Model-weight files: 11, each under 0.1 MB, all already public.
- Citations of commit ids made after the cut-off: 555 in 34 files; they refer to the private history.
