import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from greek_law.llm.errors import (
    LLMError,
    LLMProtocolError,
    LLMRateLimitedError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
    PermanentLLMError,
    TransientLLMError,
)
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

    return _client_with(handler)


def _client_raising(error: Exception) -> OllamaClient:
    """An OllamaClient whose transport fails instead of answering.

    MockTransport propagates whatever the handler raises, which is how a
    timeout or a refused connection is simulated without a network.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return _client_with(handler)


def _client_with(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaClient:
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


def test_no_httpx_exception_escapes_the_seam() -> None:
    """A provider failure surfaces as LLMError, never as an httpx type.

    This is the whole point of step 7 and replaces the test that deliberately
    pinned the opposite. If httpx leaks, every caller — service.py, the CLI, the
    V9 agent loop — must import httpx to write a try/except, which welds the
    application to one transport and makes the hosted client a breaking change
    rather than a drop-in. Asserting the httpx type is *absent* is the only
    formulation that catches a new failure path added later without translation.
    """
    client = _client_returning({"error": "model not found"}, status=404)

    with pytest.raises(LLMError) as exc_info:
        client.chat(_one_message())

    assert not isinstance(exc_info.value, httpx.HTTPError)


def test_a_read_timeout_becomes_llm_timeout_error() -> None:
    """A request that never completes raises LLMTimeoutError.

    The single most common real failure against a local 8B model: an answer of
    a few hundred tokens legitimately outruns a short read timeout. Untranslated
    it arrives as httpx.ReadTimeout, which a caller catching httpx.HTTPError
    would *miss entirely* — ReadTimeout is a TransportError, not an HTTPError —
    and the process would die mid-question with a stack trace.
    """
    client = _client_raising(httpx.ReadTimeout("timed out"))

    with pytest.raises(LLMTimeoutError):
        client.chat(_one_message())


def test_a_refused_connection_becomes_llm_unavailable_error() -> None:
    """Ollama not running raises LLMUnavailableError, not httpx.ConnectError.

    The first error anyone meets on a fresh machine, and the one the 2026-08-30
    port mix-up produced. It must be distinguishable from "the model rejected
    the request", because the operator action is completely different: start the
    server versus fix the payload.
    """
    client = _client_raising(httpx.ConnectError("connection refused"))

    with pytest.raises(LLMUnavailableError):
        client.chat(_one_message())


def test_http_429_becomes_llm_rate_limited_error() -> None:
    """A 429 is reported as rate limiting, separately from other 4xx.

    Ollama never sends one; a hosted provider sends them constantly, and 429 is
    the one 4xx where retrying the *identical* request is correct. Collapsing it
    into LLMRequestError would make the retry policy skip exactly the case
    retries exist for, and the failure would look like a quota problem nobody
    can reproduce locally.
    """
    client = _client_returning({"error": "slow down"}, status=429)

    with pytest.raises(LLMRateLimitedError):
        client.chat(_one_message())


def test_http_500_becomes_llm_unavailable_error() -> None:
    """A 5xx is the provider's fault, so it is reported as unavailability.

    Catches the boundary being written as `status > 500` or `status >= 400`,
    either of which puts a retryable server fault in the permanent branch. The
    call then fails once and stays failed, and a transient blip during the V4
    eval run scores as a retrieval miss.
    """
    client = _client_returning({"error": "internal"}, status=503)

    with pytest.raises(LLMUnavailableError):
        client.chat(_one_message())


def test_http_404_becomes_a_permanent_request_error() -> None:
    """A 404 (wrong model name) is permanent — retrying cannot fix it.

    The realistic cause is a typo in OLLAMA_MODEL or a model never pulled. If
    this landed in the transient branch, step 7's retry policy would sit there
    re-sending a request guaranteed to fail, turning an instant, obvious
    misconfiguration into a slow one.
    """
    client = _client_returning({"error": "model not found"}, status=404)

    with pytest.raises(LLMRequestError) as exc_info:
        client.chat(_one_message())

    assert isinstance(exc_info.value, PermanentLLMError)


def test_a_body_missing_a_field_becomes_llm_protocol_error() -> None:
    """A 200 response we cannot read raises LLMProtocolError, not KeyError.

    Ollama omits prompt_eval_count when a prompt is served from its cache, so
    this is a real body, not a hypothetical one. Untranslated it escapes as a
    bare KeyError('prompt_eval_count') — an exception type that says "bug in our
    code" to whoever reads the traceback, sending the next hour to the wrong
    layer. It is deliberately *permanent*: re-sending will not grow the field.
    """
    body = {key: value for key, value in _BODY.items() if key != "prompt_eval_count"}
    client = _client_returning(body)

    with pytest.raises(LLMProtocolError) as exc_info:
        client.chat(_one_message())

    assert isinstance(exc_info.value, PermanentLLMError)


def test_the_transient_and_permanent_split_is_what_a_retry_policy_reads() -> None:
    """Timeouts and 5xx are TransientLLMError; a bad request never is.

    The classification is the seam's real contract with the retry policy, and it
    is invisible in any single exception type. Pinning it here means a future
    error added to the wrong branch fails a test rather than silently changing
    retry behaviour — a new permanent error under Transient burns the retry
    budget on a hopeless call; a transient one under Permanent gives up on a
    blip that a second attempt would have survived.
    """
    timeout = _client_raising(httpx.ReadTimeout("timed out"))
    unavailable = _client_returning({"error": "internal"}, status=503)
    bad_request = _client_returning({"error": "bad"}, status=400)

    for client, expected in (
        (timeout, TransientLLMError),
        (unavailable, TransientLLMError),
        (bad_request, PermanentLLMError),
    ):
        with pytest.raises(expected):
            client.chat(_one_message())
