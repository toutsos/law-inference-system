"""Where concrete implementations are chosen — the composition root.

Every entry point (the CLI, the baseline experiment, FastAPI in V8) builds its
client stack here rather than each assembling its own. That is what makes a
baseline evidence about *this* application: the wiring that produced the
measurement is the wiring that serves a user.

Nothing below this module constructs a collaborator; everything receives one as
a parameter, which is why the whole system is testable without a network.
"""

from typing import Any

import psycopg

from greek_law.config import Settings
from greek_law.embedding import Embedder, OllamaEmbedder
from greek_law.llm.client import LLMClient
from greek_law.llm.ollama_client import OllamaClient
from greek_law.llm.retrying_client import RetryingLLMClient
from greek_law.retrieval import PgVectorRetriever, Retriever
from greek_law.storage.schema import EMBEDDING_DIMENSIONS

MAX_ATTEMPTS = 3

EMBEDDING_MODEL = "bge-m3"
"""Chosen in V3 step 3. A constant, not a setting: changing it also means
changing ``vector(n)`` in schema.sql and re-embedding the corpus."""

LLM_NUM_CTX = 8192
"""The chat model's context window, in tokens. Chosen in V3 step 7: prompts need
at most ~7 500 (top-5 provisions + rules + question + answer). Without it,
krikri's Modelfile loads 131 072 — 31 GB measured with ``ollama ps``."""

EMBEDDING_NUM_CTX = 8192
"""bge-m3's full context. Sent explicitly so Ollama never truncates a chunk."""


def build_client(settings: Settings) -> LLMClient:
    """Assemble the client stack: retries wrapped around a provider."""
    return RetryingLLMClient(
        OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=LLM_NUM_CTX,
            timeout=settings.request_timeout,
        ),
        max_attempts=MAX_ATTEMPTS,
        budget_seconds=settings.request_timeout * MAX_ATTEMPTS + 5.0,
    )


def build_embedder(settings: Settings) -> Embedder:
    """bge-m3 through Ollama, sized to the schema's vector column."""
    return OllamaEmbedder(
        base_url=settings.ollama_base_url,
        model=EMBEDDING_MODEL,
        num_ctx=EMBEDDING_NUM_CTX,
        dimensions=EMBEDDING_DIMENSIONS,
        timeout=settings.request_timeout,
    )


def build_retriever(settings: Settings, conn: psycopg.Connection[Any]) -> Retriever:
    """Exact cosine search in pgvector, the question embedded like the chunks."""
    return PgVectorRetriever(conn, build_embedder(settings))
