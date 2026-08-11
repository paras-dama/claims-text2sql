# Ambiguity Findings Log

Real ambiguities discovered during development, used to build the
taxonomy in app/llm/ambiguity_taxonomy.py and later the eval set.

## 1. Metric definition — "total paid"
- Found: Step 5 testing, question "What is the total paid amount for claim X?"
- Interpretation A: claims.total_paid_amount (cached field)
- Interpretation B: SUM(claim_reserves.amount) WHERE tran_type_code = 'Loss Payment'
- Why ambiguous: the cache can drift from the ledger (~15% of synthetic claims, by design)

## 2. Status filter — "open claims"
- Found: Step 6 testing, question "How many claims are currently open?"
- Interpretation A: claim_status_code = 'open'
- Interpretation B: claim_status_code IN ('open', 'reopened')
- Why ambiguous: "reopened" is arguably still "open" in a business sense,
  but an adjuster's worklist view might treat it as distinct

## 3. Category aggregation — "total expenses"
- Interpretation A: tran_subtype_code = 'Claim Expense' only
- Interpretation B: tran_subtype_code IN ('Claim Expense', 'Legal Expense', 'Mitigation', 'LAE')
- Why ambiguous: "expenses" is a loose business term without a single
  fixed database definition