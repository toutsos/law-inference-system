import time

import httpx

from greek_law.llm.errors import (
    LLMError,
    LLMProtocolError,
    LLMRateLimitedError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from greek_law.llm.models import ChatResponse, FinishReason, Message

_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
}


def _translate_status(error: httpx.HTTPStatusError) -> LLMError:
    """Map an HTTP status onto the seam's own error hierarchy."""
    status = error.response.status_code
    if status == 429:
        return LLMRateLimitedError(f"Rate limited by the provider (HTTP {status}).")
    if status >= 500:
        return LLMUnavailableError(f"The provider failed (HTTP {status}).")
    return LLMRequestError(f"The provider rejected the request (HTTP {status}).")


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout)

    def chat(self, messages: list[Message]) -> ChatResponse:
        started = time.perf_counter()
        try:
            response = self._http.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "messages": [message.model_dump() for message in messages],
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(
                f"The provider did not respond in time: {error}"
            ) from error
        except httpx.HTTPStatusError as error:
            raise _translate_status(error) from error
        except httpx.RequestError as error:
            raise LLMUnavailableError(
                f"Could not reach the provider: {error}"
            ) from error
        elapsed = time.perf_counter() - started

        try:
            body = response.json()
            return ChatResponse(
                model=body["model"],
                content=body["message"]["content"],
                finish_reason=_FINISH_REASONS.get(body["done_reason"], "other"),
                tokens_in=body["prompt_eval_count"],
                tokens_out=body["eval_count"],
                duration_seconds=elapsed,
            )
        except (ValueError, KeyError, TypeError) as error:
            raise LLMProtocolError(
                f"Unreadable response from the provider: {error!r}"
            ) from error
