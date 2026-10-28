# Provenance of the converted data in this folder

The JSONL files in this folder hold documents converted from two public releases published by Salesforce: SummEdits (https://huggingface.co/datasets/Salesforce/summedits) and SummExecEdit. Their licence is CC BY 4.0, for research purposes only; the full text and both dataset cards are kept in `licenses/`, and `docs/fix/AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md` gives the attribution and the changes made.

These files predate the 27 October 2026 loop. They stay in the repository as an attributed record of a quarantined experiment, by the operator's decision of 27 October 2026 (loop decision D-S7). They are never used to train a model, and SummEdits is not used as a benchmark (loop decision D-019).

This note was added after the folder was frozen; it is not one of the files `freeze.json` lists.
