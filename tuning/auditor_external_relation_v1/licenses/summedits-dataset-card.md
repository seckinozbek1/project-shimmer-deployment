---
license: cc-by-4.0
task_categories:
- text-classification
- summarization
language:
- en
tags:
- biology
- finance
- legal
- medical
pretty_name: SummEdits
size_categories:
- 1K<n<10K
---

# Factual Consistency in Summarization 

Can you tell which edits of summaries are consistent, and which are inconsistent?

<p align="center">
  <img width="650" src="https://raw.githubusercontent.com/salesforce/factualNLG/master/images/summedits_examples.png">
</p>


## SummEdits Benchmark (Section 6-7)

We release the 6,348 samples of data for the 10 domains in the SummEdits. Each sample has entries for:
- `domain`: out of the 10 domains in SummEdits,
- `id`: a unique ID for the sample,
- `doc`: the input document,
- `summary`: the summary that is either consistent or inconsistent with the facts in the document,
- `label`: 1 if the summary is factually consistent, and 0 otherwise,
- `seed_summary`: the (consistent) seed summary that was used as a starting point for the summary,
- `edit_types`: for summaries that are inconsistent, corresponds to GPT4 classified type of error.

For more detail on the data loading and benchmarking, we recommend you check out the Github repo: [https://github.com/salesforce/factualNLG](https://github.com/salesforce/factualNLG)

## Related Datasets

If you find **SummEdits** useful, you may also be interested in our companion dataset:

- **SummExecEdit**: https://huggingface.co/datasets/Salesforce/summexecedit  
  A dataset designed to study execution-based editing and reasoning in summarization, complementing the factual consistency focus of SummEdits.

These datasets together provide a broader view of summarization evaluation, covering both factual consistency and execution-oriented editing.

## Ethical Considerations
This release is for research purposes only in support of an academic paper. Our models, datasets, and code are not specifically designed or evaluated for all downstream purposes. We strongly recommend users evaluate and address potential concerns related to accuracy, safety, and fairness before deploying this model. We encourage users to consider the common limitations of AI, comply with applicable laws, and leverage best practices when selecting use cases, particularly for high-risk scenarios where errors or misuse could significantly impact people’s lives, rights, or safety. For further guidance on use cases, refer to our AUP and AI AUP. 

