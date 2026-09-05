from greek_law.llm.models import ChatResponse, Message


class FakeLLMClient:
    """A canned LLMClient: no HTTP, no Ollama, fully deterministic.

    Note what is missing: it does not inherit from LLMClient. Satisfying the
    Protocol is structural — having the right method is the whole requirement.
    """

    def __init__(self, response: ChatResponse) -> None:
        self._response = response
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message]) -> ChatResponse:
        self.calls.append(messages)
        return self._response


class FlakyLLMClient:
    """An LLMClient that raises a queued sequence of errors, then succeeds.

    Each chat() call pops the next queued exception and raises it; once the
    queue is empty it returns the canned response. That shape lets one fake
    cover "fails twice then works", "always fails", and "fails permanently".
    """

    def __init__(self, response: ChatResponse, failures: list[Exception]) -> None:
        self._response = response
        self._failures = list(failures)
        self.calls = 0

    def chat(self, messages: list[Message]) -> ChatResponse:
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return self._response


class RecordingSleep:
    """A stand-in for time.sleep that records the delay instead of waiting.

    Makes backoff assertable and keeps the suite instant: a real exponential
    backoff of 0.5s + 1.0s would add 1.5 seconds per test.
    """

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
