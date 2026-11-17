from typing import Protocol


class Embedder(Protocol):
    """Turns texts into vectors: one per text, in the order given.

    The seam between the load pipeline (and, in step 5, the question) and
    whatever computes embeddings. Callers never see HTTP, Ollama or batching
    limits — only texts in, vectors out — so tests can pass a fake that
    returns fixed vectors without a model running.
    """

    @property
    def model(self) -> str:
        """The model the vectors come from — stored on every row it embeds."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return ``vectors`` with ``vectors[i]`` the embedding of ``texts[i]``."""
        ...
