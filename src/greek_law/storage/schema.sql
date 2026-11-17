-- V3's storage: one row per chunk. Applied by `poe schema`; safe to re-run.
-- Decisions: vault/Versions/V3 - First RAG System.md, step 2.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    -- Chunk.key, e.g. 'π.δ.62/2025/άρθρο-84/παρ-3'. Step 4 upserts on it.
    key                text PRIMARY KEY,

    -- The whole Chunk, as Chunk.model_dump(mode="json"). The source of truth:
    -- reading a row back is Chunk.model_validate(row["chunk"]).
    chunk              jsonb NOT NULL,

    -- Filter columns, computed by Postgres from `chunk` so they cannot drift.
    -- NOT NULL where the model requires the field: a renamed field fails the
    -- insert instead of filling the column with NULLs.
    document_id        text NOT NULL GENERATED ALWAYS AS (chunk ->> 'document_id') STORED,
    act_type           text NOT NULL GENERATED ALWAYS AS (chunk -> 'source' -> 'act' ->> 'act_type') STORED,
    act_number         text NOT NULL GENERATED ALWAYS AS (chunk -> 'source' -> 'act' ->> 'number') STORED,
    act_year           int  NOT NULL GENERATED ALWAYS AS ((chunk -> 'source' -> 'act' ->> 'year')::int) STORED,
    instrument_article text          GENERATED ALWAYS AS (chunk -> 'source' -> 'instrument' ->> 'ratifying_article') STORED,
    article            text NOT NULL GENERATED ALWAYS AS (chunk -> 'source' ->> 'article') STORED,
    paragraph          text          GENERATED ALWAYS AS (chunk -> 'source' ->> 'paragraph') STORED,

    -- bge-m3, 1024 dimensions (step 3). Keep in step with EMBEDDING_DIMENSIONS.
    embedding          vector(1024) NOT NULL,
    embedding_model    text NOT NULL,
    -- sha256 of Chunk.embedding_text; step 4 skips chunks whose hash is unchanged.
    embedded_text_hash text NOT NULL
);