# result_sheet.md: per-agent deliverable

- generated: 2026-09-18T10:52:42.044161+00:00

## PROCESSOR
_(failed: incomplete_extraction)_

## SPEECH_ACT_TAGGER
```json
{
  "agent": "SPEECH_ACT_TAGGER",
  "doc_id": "result_sheet",
  "items": [
    {
      "ref": "REF-0021",
      "kind": "tag",
      "confidence": "CONFIDENT",
      "utterance_id": "REF-0021",
      "speech_act": "STATE",
      "ts": "2026-09-18T10:48:46.474425+00:00",
      "revision": 1,
      "item_id": "SPEECH_ACT_TAGGER:tag:REF-0021:0"
    }
  ]
}
```

## LEGAL_ANALYST
```json
{
  "agent": "LEGAL_ANALYST",
  "doc_id": "result_sheet",
  "items": [
    {
      "claim_id": "CONV-002",
      "confidence": "CONFIDENT",
      "kind": "finding",
      "reasoning": "The result sheet is missing the analysing laboratory for the result RES-ALDER, which violates CONV-002.",
      "ref": "REF-0072",
      "ref_ids": [
        "REF-0072"
      ],
      "verdict": "irregular",
      "ts": "2026-09-18T10:49:03.452118+00:00",
      "revision": 1,
      "item_id": "LEGAL_ANALYST:finding:REF-0072:0"
    }
  ]
}
```
_(failed: contract_violation)_

## VERIFIER
_(failed: contract_violation)_

## FACT_CHECKER
```json
{
  "agent": "FACT_CHECKER",
  "doc_id": "result_sheet.md",
  "items": [
    {
      "ref": "REF-0022",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "claim_id": "RES-CEDAR_Sodium_Value",
      "verdict": "irregular",
      "search_method": "direct_comparison",
      "ref_ids": [
        "REF-0022"
      ],
      "field_label": "Sodium",
      "value_a": 99,
      "unit_a": "mmol/L",
      "value_b": 148,
      "unit_b": "mmol/L",
      "relation": "sum_mismatch",
      "source_refs": [
        "REF-0022"
      ],
      "explanation": "The measured value of Sodium (99 mmol/L) does not match the expected value stated in the document (148 mmol/L).",
      "quote": "Sample identifier: SPEC-CEDAR\nTest: Chloride\nMeasured value: 99 mmol/L\nAnalysing laboratory: Eastfield",
      "ts": "2026-09-18T10:51:23.970094+00:00",
      "revision": 1,
      "item_id": "FACT_CHECKER:finding:REF-0022:0"
    },
    {
      "ref": "REF-0024",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "claim_id": "RES-BIRCH_Potassium_Value",
      "verdict": "ok",
      "search_method": "direct_comparison",
      "ref_ids": [
        "REF-0024"
      ],
      "field_label": "Potassium",
      "value_a": 3.1,
      "unit_a": "mmol/L",
      "value_b": 3.1,
      "unit_b": "mmol/L",
      "relation": "unchanged_from_prior",
      "source_refs": [
        "REF-0024"
      ],
      "explanation": "The measured value of Potassium (3.1 mmol/L) matches the expected value stated in the document (3.1 mmol/L).",
      "ts": "2026-09-18T10:51:23.970099+00:00",
      "revision": 1,
      "item_id": "FACT_CHECKER:finding:REF-0024:1"
    },
    {
      "ref": "REF-0025",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "claim_id": "RES-DAMSON_Calcium_Value",
      "verdict": "irregular",
      "search_method": "direct_comparison",
      "ref_ids": [
        "REF-0025"
      ],
      "field_label": "Total calcium",
      "value_a": 2.3,
      "unit_a": "mmol/L",
      "value_b": null,
      "unit_b": "mmol/L",
      "relation": "sum_mismatch",
      "source_refs": [
        "REF-0025"
      ],
      "explanation": "The measured value of Total calcium (2.3 mmol/L) does not match the expected value stated in the document (null).",
      "ts": "2026-09-18T10:51:23.970103+00:00",
      "revision": 1,
      "item_id": "FACT_CHECKER:finding:REF-0025:2"
    },
    {
      "ref": "REF-0026",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "claim_id": "RES-ELDER_Bilirubin_Value",
      "verdict": "irregular",
      "search_method": "direct_comparison",
      "ref_ids": [
        "REF-0026"
      ],
      "field_label": "Total bilirubin",
      "value_a": 24,
      "unit_a": "umol/L",
      "value_b": null,
      "unit_b": "umol/L",
      "relation": "sum_mismatch",
      "source_refs": [
        "REF-0026"
      ],
      "explanation": "The measured value of Total bilirubin (24 umol/L) does not match the expected value stated in the document (null).",
      "ts": "2026-09-18T10:51:23.970106+00:00",
      "revision": 1,
      "item_id": "FACT_CHECKER:finding:REF-0026:3"
    },
    {
      "ref": "REF-0028",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "claim_id": "RES-FIRTH_Albumin_Value",
      "verdict": "irregular",
      "search_method": "direct_comparison",
      "ref_ids": [
        "REF-0028"
      ],
      "field_label": "Albumin",
      "value_a": 42,
      "unit_a": "g/L",
      "value_b": null,
      "unit_b": "g/L",
      "relation": "sum_mismatch",
      "source_refs": [
        "REF-0028"
      ],
      "explanation": "The measured value of Albumin (42 g/L) does not match the expected value stated in the document (null).",
      "ts": "2026-09-18T10:51:23.970109+00:00",
      "revision": 1,
      "item_id": "FACT_CHECKER:finding:REF-0028:4"
    }
  ]
}
```

## PRACTICE_AUDITOR
```json
{
  "agent": "PRACTICE_AUDITOR",
  "doc_id": "result_sheet",
  "items": [
    {
      "ref": "REF-0007",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "rule_id": "CONV-001",
      "unit_id": "u01-result-res-alder",
      "relation": "above_band",
      "record_verdict": "irregular",
      "value_a": 148.0,
      "unit_a": "mmol/L",
      "source_refs": [
        "REF-0007"
      ],
      "explanation": "measured value against the range against Sodium in the reference corpus gives 148.0 mmol/L against a stated range of 135.0 to 145.0.",
      "value_b": 145.0,
      "unit_b": "mmol/L",
      "source_rule_id": "CONV-L01",
      "field_label": "measured value",
      "ts": "2026-09-18T10:52:41.745113+00:00",
      "revision": 1,
      "item_id": "PRACTICE_AUDITOR:finding:REF-0007:0"
    },
    {
      "ref": "REF-0007",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "rule_id": "CONV-001",
      "unit_id": "u02-result-res-birch",
      "relation": "below_band",
      "record_verdict": "irregular",
      "value_a": 3.1,
      "unit_a": "mmol/L",
      "source_refs": [
        "REF-0007"
      ],
      "explanation": "measured value against the range against Potassium in the reference corpus gives 3.1 mmol/L against a stated range of 3.5 to 5.0.",
      "value_b": 3.5,
      "unit_b": "mmol/L",
      "source_rule_id": "CONV-L01",
      "field_label": "measured value",
      "ts": "2026-09-18T10:52:41.745118+00:00",
      "revision": 1,
      "item_id": "PRACTICE_AUDITOR:finding:REF-0007:1"
    },
    {
      "ref": "REF-0007",
      "kind": "finding",
      "confidence": "CONFIDENT",
      "rule_id": "CONV-001",
      "unit_id": "u05-result-res-elder",
      "relation": "above_band",
      "record_verdict": "irregular",
      "value_a": 24.0,
      "unit_a": "umol/L",
      "source_refs": [
        "REF-0007"
      ],
      "explanation": "measured value against the range against Total bilirubin in the reference corpus gives 24.0 umol/L against a stated range of 1.7 to 17.0.",
      "value_b": 17.0,
      "unit_b": "umol/L",
      "source_rule_id": "CONV-L01",
      "field_label": "measured value",
      "ts": "2026-09-18T10:52:41.745121+00:00",
      "revision": 1,
      "item_id": "PRACTICE_AUDITOR:finding:REF-0007:2"
    }
  ]
}
```

## STYLE_GUARDIAN
_(agent did not run)_