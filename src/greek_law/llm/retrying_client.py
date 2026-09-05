import random
import time
from collections.abc import Callable

from greek_law.llm.client import LLMClient
from greek_law.llm.errors import TransientLLMError
from greek_law.llm.models import ChatResponse, Message


class RetryingLLMClient:
    """An LLMClient that retries another LLMClient's transient failures.

    It *is* an LLMClient and *has* an LLMClient, so it wraps any implementation
    without inheriting from one. Nothing here knows about Ollama, HTTP or Greek
    law: the only thing it reads is the transient/permanent split in errors.py.
    """

    def __init__(
        self,
        inner: LLMClient,
        max_attempts: int = 3,
        first_backoff_seconds: float = 0.5,
        budget_seconds: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._inner = inner
        self._max_attempts = max_attempts
        self._first_backoff_seconds = first_backoff_seconds
        self._budget_seconds = budget_seconds
        self._sleep = sleep
        self._rng = rng or random.Random()

    def chat(self, messages: list[Message]) -> ChatResponse:
        deadline = time.monotonic() + self._budget_seconds
        backoff = self._first_backoff_seconds
        attempt = 1

        while True:
            try:
                return self._inner.chat(messages)
            except TransientLLMError:
                if attempt >= self._max_attempts:
                    raise
                delay = self._rng.uniform(0.0, backoff)
                if time.monotonic() + delay >= deadline:
                    raise
                self._sleep(delay)
                backoff *= 2
                attempt += 1
