"""
Claims-domain ambiguity taxonomy, grounded in real findings from testing
(see evals/notes.md for the full discovery log).

Each entry pairs an ambiguous question with how it SHOULD be handled —
these are used as few-shot examples in the ambiguity-detection prompt.
"""

AMBIGUITY_EXAMPLES = [
    {
        "question": "What is the total paid amount for claim CLM-2024-00001?",
        "ambiguity_type": "metric_definition",
        "explanation": (
            "'Total paid' could mean the cached claims.total_paid_amount "
            "field, or the sum of claim_reserves rows where "
            "tran_type_code = 'Loss Payment'. These can disagree because "
            "the cached field is updated separately from the ledger and "
            "can drift out of sync."
        ),
        "interpretation_a": "claims.total_paid_amount (cached field)",
        "interpretation_b": (
            "SUM(claim_reserves.amount) WHERE tran_type_code = 'Loss Payment'"
        ),
    },
    {
        "question": "How many claims are currently open?",
        "ambiguity_type": "status_filter",
        "explanation": (
            "'Open' could mean claim_status_code = 'open' exactly, or "
            "claim_status_code IN ('open', 'reopened') since a reopened "
            "claim is arguably still active/not closed."
        ),
        "interpretation_a": "claim_status_code = 'open'",
        "interpretation_b": "claim_status_code IN ('open', 'reopened')",
    },
    {
        "question": "What are the total expenses on claim CLM-2024-00050?",
        "ambiguity_type": "category_aggregation",
        "explanation": (
            "'Expenses' could mean only tran_subtype_code = 'Claim Expense', "
            "or a broader set including 'Legal Expense', 'Mitigation', "
            "and 'LAE', which are all arguably expense categories."
        ),
        "interpretation_a": "tran_subtype_code = 'Claim Expense' only",
        "interpretation_b": (
            "tran_subtype_code IN ('Claim Expense', 'Legal Expense', "
            "'Mitigation', 'LAE')"
        ),
    },
]


def build_few_shot_block() -> str:
    """Renders the ambiguity examples as a text block for the prompt."""
    blocks = []
    for ex in AMBIGUITY_EXAMPLES:
        blocks.append(
            f"Question: \"{ex['question']}\"\n"
            f"Ambiguity type: {ex['ambiguity_type']}\n"
            f"Why ambiguous: {ex['explanation']}\n"
            f"Interpretation A: {ex['interpretation_a']}\n"
            f"Interpretation B: {ex['interpretation_b']}"
        )
    return "\n\n".join(blocks)