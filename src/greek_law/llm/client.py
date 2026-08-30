from typing import Protocol

from greek_law.models import ChatResponse, Message


class LLMClient(Protocol):
    def chat(self, messages: list[Message]) -> ChatResponse:
        """Send a chat request to the LLM and return the response."""
        ...
