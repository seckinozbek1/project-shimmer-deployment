# WORDS chain and main list: working TODO

Durable because the session can end without warning. Updated as each item lands.

## Status

- [x] MODEL-A: shipped model serves both dense voters; no new dependency
- [ ] MODEL-A2: four voters have no measured threshold. Solving by expanding the
      reference set (lexical voters fail on isolation, not on principle).
- [ ] TWO-K: redaction intent decided by the ensemble
- [ ] WORDS-B: convert the inventory field by field
- [ ] WORDS-D: full repository sweep for word decisions
- [ ] WORDS-E: convert SEMANTIC list worst first
- [ ] WORDS-F: check that fails when a new literal word list appears
- [ ] FOUR .. TWENTY-ONE: main list

## Decisions made in the operator's place (gathered for the final report)

1. **Expanded the redaction reference set rather than dropping voters.**
   Four of five voters had no measurable threshold on 15 positives. The
   measured cause was lexical isolation, not a flaw in the voters, so the fix
   is more and more varied reference text. Writing reference text is work, not
   a ruling, so I did it rather than asking.
