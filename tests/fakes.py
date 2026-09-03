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
