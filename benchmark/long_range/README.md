# Long-range corpus

Tests from generator family 5 (regulation-style provisions) in its long-range layout,
generated from the fixed seeds in `SEEDS.json`, for scoring a candidate finder on one
question: is the related unit in the candidate set? (S3 item 12, used by S6c.)

In every test the four definition provisions open the document and every planted flaw
sits at least twelve units from the definition it needs. Each planted entry of the key
names that unit in `related_unit`:

| Planted kind | `related_unit` |
|---|---|
| a filing-to-notice gap over its window | the provision defining the notice window |
| a receipt-to-answer gap over its window | the provision defining the answer window |
| a filing fee above or below its band | the provision defining the fee class |
| an appeal provision without its appeal body | the provision defining the appeal body |
| a definition without its source | the farthest provision that uses that definition |

Every provision that uses a defined term also carries a text cross reference to the
definition. The key has a top-level `long_range` field describing this; the scorer
ignores it. Each test also has its clean twin and four probes, like every generated
test; the reordered-sections probe remaps `related_unit`.

**Exposed by construction**, like the development suite: for development and
regression only.

## Regenerate

```
py -3.12 benchmark/generators/generate.py suite long_range
py -3.12 benchmark/generators/generate.py check benchmark/long_range/generated
```

`generated/` is ignored by git and by the container build, keys included.
