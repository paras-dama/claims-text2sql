import psycopg
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db.introspect import introspect_schema

# Loaded once at module import — reused across calls, since loading
# the model repeatedly would be slow.
_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def _embed_text(text: str) -> list[float]:
    return _embedding_model.encode(text).tolist()


def build_and_store_schema_embeddings() -> None:
    """
    Introspects the schema, builds one embedding per table (using its
    full compact prompt-string representation as the text to embed),
    and stores them in schema_embeddings. Clears old entries first so
    this is safe to re-run after schema changes.
    """
    schema = introspect_schema()

    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    cur.execute("DELETE FROM schema_embeddings")

    for table in schema.tables:
        description = table.to_prompt_string()
        embedding = _embed_text(description)
        cur.execute(
            """
            INSERT INTO schema_embeddings (table_name, description, embedding)
            VALUES (%s, %s, %s)
            """,
            (table.table_name, description, embedding),
        )

    conn.commit()
    cur.close()
    conn.close()


def retrieve_relevant_tables(question: str, top_k: int = 2) -> list[str]:
    """
    Given a natural language question, returns the table descriptions
    most semantically relevant to it, using cosine similarity search
    via pgvector's HNSW index.

    NOTE: with only 2 tables in this project, top_k=2 effectively
    returns everything, so this doesn't change behavior yet — it's
    here to demonstrate the retrieval pattern correctly, ready to
    matter once/if the schema grows.
    """
    query_embedding = _embed_text(question)

    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT description
        FROM schema_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding, top_k),
    )
    results = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()
    return results