CREATE TABLE schema_embeddings (
    id            SERIAL PRIMARY KEY,
    table_name    VARCHAR(100) NOT NULL,
    description   TEXT NOT NULL,
    embedding     vector(384) NOT NULL
);

CREATE INDEX ON schema_embeddings USING hnsw (embedding vector_cosine_ops);