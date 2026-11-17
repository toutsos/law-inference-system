from greek_law.embedding.embedder import Embedder
from greek_law.embedding.errors import (
    EmbeddingError,
    EmbeddingProtocolError,
    EmbeddingRequestError,
    EmbeddingUnavailableError,
)
from greek_law.embedding.ollama_embedder import OllamaEmbedder

__all__ = [
    "Embedder",
    "EmbeddingError",
    "EmbeddingProtocolError",
    "EmbeddingRequestError",
    "EmbeddingUnavailableError",
    "OllamaEmbedder",
]
