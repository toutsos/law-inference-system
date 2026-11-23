"""A :class:`Retriever` over the ``chunks`` table: exact cosine search in pgvector.

Exact, not approximate: Postgres measures the question against every row and
sorts. At 2 136 rows that is ~12 ms (EXPLAIN ANALYZE, step 5 kickoff). An HNSW
index is for when the corpus is big enough for that number to matter.
"""

from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from greek_law.embedding import Embedder
from greek_law.ingestion.chunking import Chunk
from greek_law.retrieval.retriever import (
    DEFAULT_K,
    NoEmbeddingsError,
    RetrievedChunk,
)

_SEARCH = """
    SELECT chunk, embedding <=> %(query)s AS distance
    FROM chunks
    WHERE embedding_model = %(model)s
    ORDER BY embedding <=> %(query)s
    LIMIT %(k)s
"""


class PgVectorRetriever:
    """Embeds the question with ``embedder``; searches only that model's rows.

    The connection belongs to the caller, as with ``apply_schema`` and
    ``load``: opened, committed and closed outside. This class only reads.
    """

    def __init__(self, conn: psycopg.Connection[Any], embedder: Embedder) -> None:
        register_vector(conn)
        self._conn = conn
        self._embedder = embedder

    def retrieve(self, question: str, k: int = DEFAULT_K) -> list[RetrievedChunk]:
        if k < 1:
            raise ValueError(f"k must be at least 1, got {k}")
        if not question.strip():
            raise ValueError("the question is empty")

        [vector] = self._embedder.embed([question])
        rows = self._conn.execute(
            _SEARCH,
            {"query": Vector(vector), "model": self._embedder.model, "k": k},
        ).fetchall()
        if not rows:
            raise NoEmbeddingsError(
                f"no chunks embedded with {self._embedder.model}; run `poe load`"
            )
        return [
            RetrievedChunk(chunk=Chunk.model_validate(chunk), distance=distance)
            for chunk, distance in rows
        ]
