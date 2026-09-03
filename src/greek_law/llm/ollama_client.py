import time

import httpx

from greek_law.llm.models import ChatResponse, FinishReason, Message

_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
}


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
        response = self._http.post(
            "/api/chat",
            json={
                "model": self._model,
                "stream": False,
                "messages": [message.model_dump() for message in messages],
            },
        )
        response.raise_for_status()
        elapsed = time.perf_counter() - started
        body = response.json()
        return ChatResponse(
            model=body["model"],
            content=body["message"]["content"],
            finish_reason=_FINISH_REASONS.get(body["done_reason"], "other"),
            tokens_in=body["prompt_eval_count"],
            tokens_out=body["eval_count"],
            duration_seconds=elapsed,
        )
