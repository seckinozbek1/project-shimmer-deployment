# SciTab reasoning types (source for the N2 operation list, D-782 point 4)

Written 2026-11-19 14:15 +0300 by the lead (b9916f12), read from the paper before any data read: SciTab (arXiv 2305.13186), section 3.1 "Reasoning Analysis", subsection "Reasoning Types", Table 2 (HTML version, https://arxiv.org/html/2305.13186). Names and descriptions quoted as published; proportion of reasoning steps in percent.

| Function name | Description | Prop. (%) |
|---|---|---|
| Simple lookup | Retrieve the value for a specific cell. | 20.6 |
| Comparison | Compare two numbers. | 19.5 |
| Closed-domain knowledge | Extract information from context sentences in the table caption or article. | 12.1 |
| Open-domain knowledge | Extract additional information required by domain experts. | 5.3 |
| Commonsense knowledge | Extract commonsense knowledge necessary for claim verification. | 5.3 |
| Subtract | Perform subtraction of two numbers. | 5.3 |
| Divide | Perform division of two numbers. | 5.3 |
| Rank | Determine the rank of a set of numbers. | 5.3 |
| Different / Same | Determine if two numbers are different or the same. | 5.3 |
| Add | Calculate the sum of two numbers. | 4.0 |
| Max / Min | Retrieve the maximum or minimum number from a set of numbers. | 3.1 |
| Col / Rowname | Retrieve the column or row name from the table. | 3.1 |
| Trend same/different | Determine the trend for two columns or rows, whether they are the same or different. | 2.9 |
| Set check | Verify if a value belongs to a set of numbers. | 2.9 |

Use: the declared operation list of config/cell_selection.json (form block, lane/n2-table-authority) is taken from the computable rows of this table (the three knowledge rows are not computable from cells and stay with the model). The mapping is committed with the held N2 merge, before any data read.
