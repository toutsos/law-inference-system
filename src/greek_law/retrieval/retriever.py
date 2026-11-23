"""The retrieval seam: a question in, the nearest provisions out.

Step 7's service will depend on this protocol, not on Postgres, so its tests
can pass a fake that returns fixed chunks. V5's hybrid retriever will be a
second implementation of the same protocol.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from greek_law.ingestion.chunking import Chunk

DEFAULT_K = 5
"""Chunks per question. Step 3: bge-m3 had all 17 dev questions in its top 5."""


class RetrievedChunk(BaseModel):
    """One hit: the chunk as stored, and its cosine distance from the question.

    0 is the same direction, 1 unrelated, 2 opposite. Smaller is nearer.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: Chunk
    distance: float


class Retriever(Protocol):
    def retrieve(self, question: str, k: int = DEFAULT_K) -> list[RetrievedChunk]:
        """The ``k`` chunks nearest to ``question``, nearest first."""
        ...


class NoEmbeddingsError(Exception):
    """The store has no vectors from the model the question was embedded with."""
