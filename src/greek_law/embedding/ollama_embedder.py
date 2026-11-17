"""An :class:`Embedder` backed by Ollama's ``/api/embed``.

Carries the rules V3 step 3 found the hard way, so no caller has to repeat
them: ``truncate: false`` and an explicit ``num_ctx`` on every request,
because Ollama otherwise cuts a long input silently.
"""

from typing import Any

import httpx

from greek_law.embedding.errors import (
    EmbeddingProtocolError,
    EmbeddingRequestError,
    EmbeddingUnavailableError,
)


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        num_ctx: int,
        dimensions: int,
        timeout: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._num_ctx = num_ctx
        self._dimensions = dimensions
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout)

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._http.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": texts,
                    "truncate": False,
                    "options": {"num_ctx": self._num_ctx},
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise EmbeddingUnavailableError(
                f"{self._model}: no response in time: {error}"
            ) from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            message = f"{self._model}: HTTP {status}: {error.response.text}"
            if status >= 500:
                raise EmbeddingUnavailableError(message) from error
            raise EmbeddingRequestError(message) from error
        except httpx.RequestError as error:
            raise EmbeddingUnavailableError(
                f"{self._model}: could not reach Ollama: {error}"
            ) from error

        try:
            vectors: Any = response.json()["embeddings"]
        except (ValueError, KeyError, TypeError) as error:
            raise EmbeddingProtocolError(
                f"{self._model}: unreadable response: {error!r}"
            ) from error
        self._check(texts, vectors)
        checked: list[list[float]] = vectors
        return checked

    def _check(self, texts: list[str], vectors: Any) -> None:
        """Exactly one vector per text, each ``dimensions`` long — or raise.

        A count mismatch would shift every later vector onto the wrong chunk;
        a wrong length means a different model than the schema was built for.
        Both are caught here, before anything reaches the database.
        """
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            got = len(vectors) if isinstance(vectors, list) else type(vectors).__name__
            raise EmbeddingProtocolError(
                f"{self._model}: sent {len(texts)} texts, got {got} vectors"
            )
        for index, vector in enumerate(vectors):
            if not isinstance(vector, list) or len(vector) != self._dimensions:
                got = len(vector) if isinstance(vector, list) else type(vector).__name__
                raise EmbeddingProtocolError(
                    f"{self._model}: vector {index} has {got} dimensions, "
                    f"expected {self._dimensions}"
                )
