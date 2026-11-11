# What a reader of the draft resolution case should report

**Not shown to any model.** This file is outside `workload/`, so neither the sealer nor a run
receives it.

Real public text, with nothing planted. A demonstration, never benchmark evidence. Nothing here
has been run on a model.

## Source

| Version | Symbol | Date | Sponsors | PDF |
|---|---|---|---|---|
| Draft | A/C.2/74/L.34 | 23 October 2019 | Republic of Korea | https://digitallibrary.un.org/record/3833768/files/A_C.2_74_L.34-EN.pdf |
| Revision | A/C.2/74/L.34/Rev.1 | 20 November 2019 | Bhutan, Mauritius, Mongolia, Republic of Korea, Turkmenistan | https://digitallibrary.un.org/record/3836683/files/A_C.2_74_L.34_Rev.1-EN.pdf |

Both were fetched on 6 November 2026. The SHA-256 of each PDF is in
`build_resolution_case.py`. UN Digital Library records:
https://digitallibrary.un.org/record/3833768 (the draft) and
https://digitallibrary.un.org/record/3836683 (the revision).

**The adopted text is A/RES/74/212**, https://digitallibrary.un.org/record/3848292, recorded there
as adopted without vote at the 52nd plenary meeting. The catalogue gives the revision as its
draft; the adopted text itself was not fetched or compared with it. A run's report cites these
records, the fetch date and A/RES/74/212.

`source/` holds pdftotext's output, with one change: typographic quotation marks are written as
straight ones, because the repository's commit scan refuses them. No word changes. The builder
declares its repairs (three of letter spacing or a lost hyphen, the rest footnote marks) and
`--check` confirms that every word of `source/` is kept. The PDFs were not compared with the
Markdown by eye, line by line.

## The changes between the versions

1. **The name.** International Day for Blue Sky becomes International Day of Clean Air for blue
   skies, in the title and in operative paragraph 1.
2. **The date.** 15 November becomes 7 September. "To be observed starting in 2020" is unchanged.
3. **Operative paragraph 2.** "Urges Member States to devote" becomes "Invites all Member
   States, organizations of the United Nations system ..." "to observe the International Day in
   an appropriate manner". The list of activities goes, and enhancing international cooperation
   towards clean air comes in. The call is softer and the addressees wider.
4. **Operative paragraph 3.** The invitation to the Secretary-General to keep the General
   Assembly informed goes, and a reference to the annex to Economic and Social Council
   resolution 1980/67 comes in.
5. **Operative paragraph 4,** on voluntary contributions, is unchanged.
6. **Operative paragraph 5.** "to ensure the observance" becomes "to promote the observance".
7. **The preamble is cut and rebalanced.** The named Sustainable Development Goal targets go,
   though their substance stays. The cancer classification, the 6.5 million premature deaths and
   the 2050 projection go. A paragraph on ecosystems is added, "the elderly" becomes "older
   persons", the list of named partnerships becomes "various projects, partnerships, mechanisms
   and instruments", and the three statements on climate become one on mitigation. Footnote 3
   goes with the Convention it cited.
8. **The sponsors** grow from one to five.

## Internal contradictions and broken references

None was planted, and I found none on reading both texts. The internal references hold in both
versions (the International Day as named in operative paragraph 1, the annex to resolution
1980/67). A run that reports one needs reading against the text before it is believed. Whether
each external citation is correct was not checked.

## What Python makes of it, computed on this machine with no model

No step of the shipped configuration compares two paragraphs: the passage comparison
(`[compare: passages]`) was measured and not adopted (D-294), so the rule that declared it was
removed. A contradiction between two paragraphs, had there been one, would be seen only by the
unit-by-unit judging, which shows a model one paragraph with only its neighbours.

Python computes no finding and no change record on this case, because neither version has a
figure in a label line: the date and the name are prose. The multi-round review reuses no unit
between the versions, not even an unchanged paragraph: a unit's signature includes the document's
measures, and the `Distr.:` line reads "23 October" and "20 November" as a figure in `October` and
one in `November`, so the two documents' measures differ.

The paragraph numbers of the two versions do not line up, because the preamble was rewritten. A
heading such as "Preambular paragraph 4" means something different in each file, so comparing
units by heading compares unrelated paragraphs.
