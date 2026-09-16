---
license: unknown
language:
- en
task_categories:
- text-classification
---

# WikiAtomicSample Task from the PEER Benchmark (Performance Evaluation of Edit Representations)

Description from the [benchmark paper](https://arxiv.org/abs/2004.09143):
> We randomly sampled approximately 150K insertion and deletion examples from the English portion of the WikiAtomicEdits (Faruqui et al. 2018). After cleaning, we keep 104K samples.

This dataset was originally published at https://doi.org/10.5281/zenodo.4478266.

## Citations

PEER Benchmark:
```bibtex
@article{marrese-taylor-et-al-2021,
    title = {Variational Inference for Learning Representations of Natural Language Edits},
    volume = {35},
    url = {https://ojs.aaai.org/index.php/AAAI/article/view/17598}, DOI = {10.1609/aaai.v35i15.17598},
    number = {15},
    journal = {Proceedings of the AAAI Conference on Artificial Intelligence},
    author = {Marrese-Taylor, Edison and Reid, Machel and Matsuo, Yutaka},
    year = {2021},
    month = {May},
    pages = {13552-13560},
}
```

Original data source:
```bibtex
@inproceedings{faruqui-etal-2018-wikiatomicedits,
    title = "{W}iki{A}tomic{E}dits: A Multilingual Corpus of {W}ikipedia Edits for Modeling Language and Discourse",
    author = "Faruqui, Manaal  and
      Pavlick, Ellie  and
      Tenney, Ian  and
      Das, Dipanjan",
    editor = "Riloff, Ellen  and
      Chiang, David  and
      Hockenmaier, Julia  and
      Tsujii, Jun{'}ichi",
    booktitle = "Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing",
    month = oct # "-" # nov,
    year = "2018",
    address = "Brussels, Belgium",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/D18-1028/",
    doi = "10.18653/v1/D18-1028",
    pages = "305--315",
    abstract = "We release a corpus of 43 million atomic edits across 8 languages. These edits are mined from Wikipedia edit history and consist of instances in which a human editor has inserted a single contiguous phrase into, or deleted a single contiguous phrase from, an existing sentence. We use the collected data to show that the language generated during editing differs from the language that we observe in standard corpora, and that models trained on edits encode different aspects of semantics and discourse than models trained on raw text. We release the full corpus as a resource to aid ongoing research in semantics, discourse, and representation learning."
}
```