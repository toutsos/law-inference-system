import json
from typing import Any

import httpx
import pytest

from greek_law.llm.models import Message
from greek_law.llm.ollama_client import OllamaClient

# A realistic Ollama /api/chat body, taken from the step 3 probe.
_BODY: dict[str, Any] = {
    "model": "test-model",
    "message": {"role": "assistant", "content": "Καλημέρα"},
    "done": True,
    "done_reason": "stop",
    "prompt_eval_count": 37,
    "eval_count": 11,
    "eval_duration": 241992915,
}


def _client_returning(
    body: dict[str, Any],
    status: int = 200,
    captured: list[httpx.Request] | None = None,
) -> OllamaClient:
    """An OllamaClient wired to a fake transport instead of a real server."""

    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(status, json=body)

    return OllamaClient(
        base_url="http://ollama.test",
        model="test-model",
        timeout=1.0,
        http_client=httpx.Client(
            base_url="http://ollama.test",
            transport=httpx.MockTransport(handler),
        ),
    )


def _one_message() -> list[Message]:
    return [Message(role="user", content="Γεια")]


def test_ollama_field_names_are_translated_to_ours() -> None:
    """Ollama's field names arrive under our names, with values intact.

    The seam's core job: prompt_eval_count -> tokens_in, eval_count ->
    tokens_out. Catches the two being swapped, which is plausible because they
    are adjacent ints of similar size — and a swap never crashes. It would
    silently invert every number in step 8's usage log, and the error would
    only show up as an inexplicable cost model much later.
    """
    response = _client_returning(_BODY).chat(_one_message())

    assert response.content == "Καλημέρα"
    assert response.tokens_in == 37
    assert response.tokens_out == 11


def test_done_reason_stop_becomes_finish_reason_stop() -> None:
    """A normally-completed generation maps to finish_reason "stop".

    The happy path through the translation table. Cheap, and it is what makes
    the two failure-path tests below meaningful by contrast.
    """
    response = _client_returning(_BODY).chat(_one_message())

    assert response.finish_reason == "stop"


def test_truncated_response_is_reported_as_length() -> None:
    """A response cut off at the token limit is reported as "length".

    The most important test in this file. Truncation arrives as HTTP 200 with
    a complete-looking body, so nothing raises. If "length" ever fell through
    to "other", step 7 could not detect truncation and the application would
    present half an answer as a whole one — a silent correctness bug in the
    exact place where a legal answer must not be trusted.
    """
    response = _client_returning({**_BODY, "done_reason": "length"}).chat(
        _one_message()
    )

    assert response.finish_reason == "length"


def test_unrecognised_done_reason_degrades_to_other() -> None:
    """An unknown done_reason maps to "other" rather than raising.

    Ollama may add reasons in a future release. This pins the `.get(..., "other")`
    fallback so an upgrade degrades one field instead of failing the whole call
    with a KeyError — a crash that would only ever appear against a live server.
    """
    response = _client_returning({**_BODY, "done_reason": "unload"}).chat(
        _one_message()
    )

    assert response.finish_reason == "other"


def test_duration_is_measured_locally_not_read_from_the_body() -> None:
    """duration_seconds is wall-clock we measured, not Ollama's eval_duration.

    A very plausible regression: the body already contains a duration, so
    reading it looks like a simplification. But hosted providers report no such
    field, so doing that would bake an Ollama-only value into ChatResponse and
    leave AnthropicClient with nothing honest to return — the exact leak this
    type was designed to prevent.
    """
    response = _client_returning(_BODY).chat(_one_message())

    # The body claims 0.242s. The fake transport answers instantly, so anything
    # near that number means eval_duration leaked into the response.
    assert response.duration_seconds < 0.1


def test_request_carries_roles_and_disables_streaming() -> None:
    """The outbound body: right URL, role-tagged messages, streaming off.

    Everything else here checks the response; this checks what we send. Catches
    a regression to /api/generate's flat-prompt shape (which would destroy the
    system/user split step 6 depends on), and catches `stream` flipping to True
    — which returns newline-delimited JSON objects and makes .json() fail in a
    way that looks like a parsing bug rather than a request bug.
    """
    captured: list[httpx.Request] = []
    client = _client_returning(_BODY, captured=captured)

    client.chat(
        [
            Message(role="system", content="You are terse."),
            Message(role="user", content="Γεια"),
        ]
    )

    sent = json.loads(captured[0].content)
    assert str(captured[0].url) == "http://ollama.test/api/chat"
    assert sent["stream"] is False
    assert sent["model"] == "test-model"
    assert sent["messages"] == [
        {"role": "system", "content": "You are terse."},
        {"role": "user", "content": "Γεια"},
    ]


def test_http_error_reaches_the_caller_as_an_httpx_exception() -> None:
    """A non-2xx response currently raises httpx.HTTPStatusError at the caller.

    Documents behaviour that is deliberately wrong: httpx leaks straight
    through the seam, so callers must import httpx to handle a failure. Step 7
    replaces this with our own exception type, and this test will fail then —
    on purpose. That failure is the reminder that the change was the goal.
    """
    client = _client_returning({"error": "model not found"}, status=404)

    with pytest.raises(httpx.HTTPStatusError):
        client.chat(_one_message())
