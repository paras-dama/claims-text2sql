# Claims Text-to-SQL with Clarification Engine

A domain-grounded text-to-SQL system for insurance claims and
reserve/payment accounting, with an ambiguity-detection and clarification
layer on top of plain text-to-SQL.

## Status
Work in progress - early scaffold stage.

## Stack
- Python, FastAPI, Pydantic
- PostgreSQL
- litellm (Groq / Gemini / OpenAI)
- sqlglot for SQL validation

## Local setup
See `SETUP.md` for full environment setup instructions.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with your DB password and API keys, then run:

```powershell
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000/health