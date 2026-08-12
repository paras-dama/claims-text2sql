# Claims Text-to-SQL with Clarification Engine

A text-to-SQL system for insurance claims and reserve/payment accounting
that recognizes genuine ambiguity in natural language questions and asks
targeted clarifying questions — instead of silently picking an
interpretation and returning a plausible-looking but potentially wrong
answer.

## Why this exists

Generic text-to-SQL demos work well on toy schemas because toy schemas
don't have real ambiguity. Claims/reserve accounting does: "total paid"
can mean a cached summary field or a sum over a transaction ledger, and
these can genuinely disagree. "Open claims" is unclear whether it should
include reopened claims. "Total expenses" depends on which expense
categories you count. A system that silently guesses on questions like
these gives confident, wrong answers. This project detects that ambiguity
and asks instead.

## What it does

1. Takes a natural language question about claims/reserve data
2. Generates SQL against the real schema, OR recognizes the question is
   ambiguous and asks a targeted, multiple-choice clarifying question
3. If clarification was needed, merges the user's answer and produces
   final SQL reflecting their chosen interpretation
4. Validates all generated SQL (SELECT-only, table allowlisting via
   dynamic discovery, timeout, row limits) before execution
5. Executes safely against a read-only database role
6. Explains the result in plain English, restating any assumptions made
   and flagging data-quality caveats (e.g. a `NULL` sum meaning "no
   matching transactions," not "zero")

## Architecture

```
Question
  → Schema introspection (dynamic, discovers all DB tables live)
  → LLM: SQL generation + ambiguity detection (structured Pydantic output)
  → [if ambiguous] → clarifying question → user answers → re-generate
  → SQL validation (sqlglot: SELECT-only, table allowlist, timeout, row limit)
  → Execution (read-only DB role)
  → Result explanation (separate LLM call, plain English + caveats)
```

A Streamlit frontend sits on top of the FastAPI backend, rendering
clarifying questions as actual clickable option buttons rather than raw
JSON.

## Key design decisions

- **Dynamic table discovery over a maintained allowlist**: new tables
  added to the database are automatically introspected, validated, and
  queryable with zero code changes — the app queries
  `information_schema` live and excludes a small denylist of its own
  infrastructure tables (e.g. `schema_embeddings`). Chosen deliberately
  for a single-user local project; a multi-tenant production version
  would likely use an explicit allowlist or row-level security instead.
- **pgvector schema retrieval, built but not wired into the live
  pipeline**: at the current schema size (2 tables), the full schema
  fits comfortably in every prompt — retrieval doesn't change correctness
  today. Built ahead of a planned schema expansion (policy, coverages,
  policyholder/person info) where it will matter; swapping it in later is
  a one-line change in the orchestrator.
- **Two-step LLM pipeline** (SQL generation, then a separate result
  explanation call) rather than one large prompt trying to do both —
  smaller, focused prompts are more reliable than one prompt doing
  everything at once.
- **Multiple-choice clarification, not free-text**: the ambiguity space
  in this domain is well-defined — a known, finite set of interpretations
  per ambiguity type — so presenting concrete options is both better UX
  and easier to parse programmatically than open-ended follow-up text.
- **In-memory session state for the clarification loop**: simple and
  correct for a single-process local demo. A production version would use
  Redis with a TTL instead of a Python dict.

## Real bugs found and fixed during development

This project was built iteratively and tested at every step, which
surfaced real bugs rather than a clean, unrealistic build. That process is
arguably the most useful part of the project:

1. **Case-sensitivity mismatch in status filtering.** The LLM generated
   `WHERE claim_status_code != 'CLOSED'` (uppercase) against data actually
   stored as lowercase (`'closed'`), which silently matched every row
   instead of filtering correctly — a "how many claims are open" query
   returned the total row count, not the open count. Root cause: schema
   introspection only exposed column names and types, not real stored
   values, so the LLM guessed a plausible-but-wrong casing. Fixed
   structurally by extending introspection to sample real distinct values
   per categorical column and include them in the schema prompt (e.g.
   `claim_status_code varchar (examples: 'open', 'closed', 'reopened')`),
   rather than patching the one query with a one-off prompt instruction.

2. **"Open claims" status ambiguity.** Testing the fix above raised a
   real follow-up question: should a `reopened` claim count as "open"?
   This became a permanent entry in the ambiguity taxonomy and eval set
   rather than a silently-chosen default — the system now asks instead of
   assuming.

3. **`NULL` vs zero on aggregate sums.** `SUM(amount) WHERE
   tran_type_code = 'Loss Payment'` correctly returns SQL `NULL` (not
   `0`) when a claim has reserve-set transactions but no actual payments
   yet. Left as a raw `null` in early testing, this looked like a bug but
   wasn't — it's accurate SQL behavior that's still bad UX for an end
   user. Handled in the result-explanation layer, which now surfaces a
   caveat (e.g. "no payment transactions recorded yet") instead of
   showing a bare `null`.

4. **Pydantic validation failure on `needs_clarification` responses.**
   `Assumption.chosen_interpretation` was originally a required `str`
   field, but when the LLM correctly returns `status: "needs_clarification"`,
   there isn't a final chosen interpretation yet — the LLM returned `null`
   for that field, and Pydantic rejected the whole response. Fixed by
   making the field `str | None`, since "no decision made yet" is a valid,
   expected state partway through the clarification flow, not malformed
   data.

## Ambiguity taxonomy

| Type | Example question | Interpretations |
|---|---|---|
| Metric definition | "What is the total paid amount for claim X?" | cached `claims.total_paid_amount` field vs. `SUM(claim_reserves.amount)` where `tran_type_code = 'Loss Payment'` — these can disagree due to cache drift |
| Status filter | "How many claims are currently open?" | `claim_status_code = 'open'` exactly vs. `IN ('open', 'reopened')` |
| Category aggregation | "What are the total expenses on claim X?" | `tran_subtype_code = 'Claim Expense'` only vs. combined with `'Legal Expense'`, `'Mitigation'`, `'LAE'` |

Full discovery log, including how each was found, is in `evals/notes.md`.

## Eval results

Tested against 6 questions (3 known-ambiguous, 3 known-clear) on Groq
(`llama-3.3-70b-versatile`):

| Metric | Result |
|---|---|
| Overall accuracy | 100% (6/6) |
| Ambiguity detection recall | 100% (3/3 known-ambiguous questions correctly triggered clarification) |
| Clear question precision | 100% (3/3 known-clear questions correctly proceeded without asking) |
| Avg response time | 1.78s |

**Honest limitation**: this is a small eval set (6 questions). A perfect
score here is a promising early signal, not proof of robustness — it
should be read as "the system correctly handles the specific ambiguity
patterns it was designed around," not "the system handles ambiguity in
general." Expanding to 20-30+ questions, including harder/combined
ambiguity cases and adversarial phrasing, is a natural next step (see
below). Only Groq has been evaluated so far; comparing against
Gemini/OpenAI on the same question set is planned but not yet done.

## Stack

- Python, FastAPI, Pydantic
- PostgreSQL, pgvector
- litellm (provider-agnostic LLM calls; currently tested with Groq)
- sqlglot (SQL parsing and validation)
- Streamlit (frontend)
- sentence-transformers (local embeddings, no external API dependency)

## Local setup

See `SETUP.md` for full environment setup instructions (Windows, no
Docker).

```powershell
git clone https://github.com/paras-dama/claims-text2sql.git
cd claims-text2sql
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with your database password and API keys, create the
database and run the schema:

```powershell
psql -U postgres -c "CREATE DATABASE claims_db;"
psql -U postgres -d claims_db -f data/schema.sql
python -m data.seed.generate_synthetic_data
```

Run the API:
```powershell
uvicorn app.main:app --reload
```

In a second terminal, run the frontend:
```powershell
streamlit run frontend/streamlit_app.py
```

Visit `http://localhost:8501` for the chat UI, or `http://127.0.0.1:8000/docs`
for the raw API.

## Running the eval suite

```powershell
python -m evals.run_eval --provider groq
```

Results are printed to console and saved to `evals/last_run_results.json`.

## Project structure

```
claims-text2sql/
├── .env.example
├── .gitignore
├── README.md
├── SETUP.md
├── requirements.txt
├── app/
│   ├── main.py                    # FastAPI app: /health, /schema, /query, /clarify
│   ├── config.py                  # Pydantic settings from .env
│   ├── domain_tables.py           # Dynamic table discovery (denylist-based)
│   ├── schemas/
│   │   ├── db_schema.py           # ColumnInfo, TableInfo, SchemaInfo
│   │   ├── sql_result.py          # SQLGenerationResult, Assumption, ClarifyingQuestion
│   │   └── explanation.py         # ResultExplanation
│   ├── llm/
│   │   ├── router.py              # Provider-agnostic completion calls via litellm
│   │   ├── prompts.py             # System prompts for SQL gen + explanation
│   │   └── ambiguity_taxonomy.py  # Few-shot ambiguity examples
│   ├── db/
│   │   ├── introspect.py          # Live schema introspection
│   │   ├── executor.py            # Safe, validated query execution
│   │   └── retriever.py           # pgvector retrieval (built, not yet wired in)
│   ├── orchestrator/
│   │   ├── pipeline.py            # Main question -> SQL -> execution flow
│   │   ├── session_state.py       # In-memory clarification session tracking
│   │   └── explainer.py           # Post-execution plain-English explanation
│   └── validation/
│       └── sql_guard.py           # sqlglot-based SQL safety validation
├── data/
│   ├── schema.sql
│   ├── schema_embeddings.sql
│   └── seed/
│       ├── generate_synthetic_data.py
│       └── build_embeddings.py
├── evals/
│   ├── test_questions.json
│   ├── run_eval.py
│   ├── notes.md                   # Real ambiguity/bug discovery log
│   └── last_run_results.json
└── frontend/
    └── streamlit_app.py
```

## What I'd build next

- Wire pgvector retrieval into the live pipeline once the schema grows
  (policy, coverages, person_info)
- Column-level PII masking once `person_info`/policyholder tables are added
- Multi-round clarification (currently capped at one round — if the LLM
  is still unsure after the user's answer, it reports `still_ambiguous`
  rather than asking again)
- Redis-backed session state instead of in-memory, for multi-process
  deployment
- Expand the eval set to 20-30+ questions and run the Groq/Gemini/OpenAI
  comparison