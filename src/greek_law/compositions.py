"""Where concrete implementations are chosen — the composition root.

Every entry point (the CLI, the baseline experiment, FastAPI in V8) builds its
client stack here rather than each assembling its own. That is what makes a
baseline evidence about *this* application: the wiring that produced the
measurement is the wiring that serves a user.

Nothing below this module constructs a collaborator; everything receives one as
a parameter, which is why the whole system is testable without a network.
"""

from greek_law.config import Settings
from greek_law.llm.client import LLMClient
from greek_law.llm.ollama_client import OllamaClient
from greek_law.llm.retrying_client import RetryingLLMClient

MAX_ATTEMPTS = 3


def build_client(settings: Settings) -> LLMClient:
    """Assemble the client stack: retries wrapped around a provider."""
    return RetryingLLMClient(
        OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.request_timeout,
        ),
        max_attempts=MAX_ATTEMPTS,
        budget_seconds=settings.request_timeout * MAX_ATTEMPTS + 5.0,
    )
