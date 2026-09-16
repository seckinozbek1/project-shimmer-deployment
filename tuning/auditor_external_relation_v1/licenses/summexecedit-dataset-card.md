---
license: cc-by-4.0
task_categories:
- text-classification
- summarization
language:
- en
tags:
- reasoning
- biology
- finance
- legal
- medical
pretty_name: SummExecEdit
size_categories:
- 1K<n<10K
---

# Factual Consistency in Summarization

Evaluate your model's ability to detect and explain the factual inconsistency in summaries. This repo contains the benchmark from our paper ["SummExecEdit: A Factual Consistency Benchmark in Summarization with Executable Edits"](https://arxiv.org/abs/2412.13378).

## SummExecEdit Benchmark

This benchmark is built over our previous benchmark - [SummEdits](https://huggingface.co/datasets/Salesforce/summedits). Consistent summaries are used from SummEdits. New inconsistent and challenging summaries are generated using executable editing mechanism.

We release the 4,241 samples of data for the 10 domains in the SummExecEdit. Each sample has entries for:
- `sample_id`: unique ID for the sample,
- `doc_id`: unique ID for the document,
- `doc`: input document,
- `original_summary`: the summary that is either consistent or inconsistent with the facts in the document,
- `original_text`: the text in original_summary to be replaced to introduce factual inconsistency,
- `replace_text`: the text with which original_text is replaced that introduces factual inconsistency,
- `edited_summary`: the summary that is either consistent or inconsistent with the facts in the document,
- `explanation`: explanation for factual inconsistency if present,
- `domain`: domain to which document and summary belongs,
- `model`: model which is used for executable editing i.e. generating original_text, replace_text, and explanation,
- `edit_type`: "summedits" if the summary is factually consistent, and summexecedit otherwise,

If you find this useful, please consider citing:

```bibtex
@misc{thorat2024summexeceditfactualconsistencybenchmark,
      title={SummExecEdit: A Factual Consistency Benchmark in Summarization with Executable Edits}, 
      author={Onkar Thorat and Philippe Laban and Chien-Sheng Wu},
      year={2024},
      eprint={2412.13378},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2412.13378}, 
}
```
