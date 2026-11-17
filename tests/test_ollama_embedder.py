"""OllamaEmbedder against a fake transport — no Ollama needed.

What is pinned is what V3 step 3 learned and step 4 relies on: the request
never lets Ollama truncate, and the response is refused unless it holds
exactly one vector of the schema's size per text sent. Failures in any of
these would not crash a load; they would store wrong vectors under right keys.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from greek_law.embedding import (
    EmbeddingProtocolError,
    EmbeddingRequestError,
    EmbeddingUnavailableError,
    OllamaEmbedder,
)

_DIMS = 3


def _embedder(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaEmbedder:
    return OllamaEmbedder(
        base_url="http://ollama.test",
        model="bge-m3",
        num_ctx=8192,
        dimensions=_DIMS,
        timeout=5,
        http_client=httpx.Client(
            base_url="http://ollama.test", transport=httpx.MockTransport(handler)
        ),
    )


def _answering(
    body: dict[str, Any],
    status: int = 200,
    captured: list[httpx.Request] | None = None,
) -> OllamaEmbedder:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(status, json=body)

    return _embedder(handler)


def _raising(error: Exception) -> OllamaEmbedder:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return _embedder(handler)


def test_every_request_forbids_truncation_and_names_the_context() -> None:
    """The body carries ``truncate: false`` and ``num_ctx``, and all texts at once.

    Without both settings Ollama cuts a long chunk to its default context and
    embeds the head only — no error, a vector of the right size, and the
    tail of the paragraph unfindable. Step 3's first run is how this was
    found.
    """
    captured: list[httpx.Request] = []
    embedder = _answering(
        {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}, captured=captured
    )

    embedder.embed(["πρώτο", "δεύτερο"])

    body = json.loads(captured[0].content)
    assert captured[0].url.path == "/api/embed"
    assert body == {
        "model": "bge-m3",
        "input": ["πρώτο", "δεύτερο"],
        "truncate": False,
        "options": {"num_ctx": 8192},
    }


def test_vectors_come_back_in_the_order_of_the_texts() -> None:
    """``result[i]`` is the vector Ollama returned at position i, untouched."""
    embedder = _answering({"embeddings": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]})

    assert embedder.embed(["a", "b"]) == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def test_fewer_vectors_than_texts_is_refused() -> None:
    """A batch of 2 answered with 1 vector raises instead of returning it.

    Zipping a short list with the chunks would silently drop the last chunk
    — or, if a vector went missing from the middle, store every later
    vector under the wrong key. Nothing downstream could notice.
    """
    embedder = _answering({"embeddings": [[0.1, 0.2, 0.3]]})

    with pytest.raises(EmbeddingProtocolError, match="sent 2 texts, got 1"):
        embedder.embed(["a", "b"])


def test_a_vector_of_the_wrong_size_is_refused() -> None:
    """A vector whose length is not ``dimensions`` raises, naming the model.

    The usual cause is a different model than the schema was built for.
    Caught here, the message says so; caught by Postgres, it is «expected
    1024 dimensions, not 768» halfway through a load, with no model named.
    """
    embedder = _answering({"embeddings": [[0.1, 0.2, 0.3], [0.1, 0.2]]})

    with pytest.raises(EmbeddingProtocolError, match="vector 1 has 2 dimensions"):
        embedder.embed(["a", "b"])


def test_an_empty_batch_makes_no_request() -> None:
    """``embed([])`` returns ``[]`` without calling Ollama.

    A load where every chunk is unchanged has nothing to embed; it should
    cost nothing and not depend on Ollama even running.
    """
    captured: list[httpx.Request] = []
    embedder = _answering({"embeddings": []}, captured=captured)

    assert embedder.embed([]) == []
    assert captured == []


def test_a_rejected_request_carries_ollamas_own_message() -> None:
    """HTTP 400 becomes EmbeddingRequestError with Ollama's explanation in it.

    «input length exceeds the context length» and «model "bge-m3" not
    found» both arrive as 4xx; the status alone does not say which, and
    the fix is different (shorter chunk vs ``ollama pull``).
    """
    embedder = _answering(
        {"error": "the input length exceeds the context length"}, status=400
    )

    with pytest.raises(EmbeddingRequestError, match="exceeds the context length"):
        embedder.embed(["a"])


@pytest.mark.parametrize(
    "embedder",
    [
        _answering({"error": "boom"}, status=500),
        _raising(httpx.ConnectError("connection refused")),
        _raising(httpx.ReadTimeout("timed out")),
    ],
    ids=["http-500", "connect-error", "timeout"],
)
def test_transport_failures_surface_as_unavailable(embedder: OllamaEmbedder) -> None:
    """Ollama down, slow or failing raises EmbeddingUnavailableError, not httpx's.

    The seam's rule: a caller never imports httpx to handle a failure. A raw
    ``httpx.ConnectError`` escaping would make the loader's error handling
    depend on which HTTP library this class happens to use.
    """
    with pytest.raises(EmbeddingUnavailableError):
        embedder.embed(["a"])


def test_an_unreadable_body_is_a_protocol_error() -> None:
    """A 200 without an ``embeddings`` field raises EmbeddingProtocolError."""
    embedder = _answering({"something_else": []})

    with pytest.raises(EmbeddingProtocolError, match="unreadable"):
        embedder.embed(["a"])
