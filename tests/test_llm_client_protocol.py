from greek_law.llm.client import LLMClient
from greek_law.llm.models import ChatResponse, Message
from greek_law.llm.ollama_client import OllamaClient
from tests.fakes import FakeLLMClient

_A_RESPONSE = ChatResponse(
    model="test-model",
    content="Καλημέρα",
    finish_reason="stop",
    tokens_in=37,
    tokens_out=11,
    duration_seconds=0.24,
)


def _requires_an_llm_client(client: LLMClient) -> LLMClient:
    """Type-level assertion: mypy rejects anything that isn't an LLMClient."""
    return client


def test_ollama_client_satisfies_the_protocol() -> None:
    """OllamaClient is accepted where an LLMClient is required.

    The assertion that makes step 4 real. `_requires_an_llm_client` is a no-op
    at runtime, so this test passes under pytest no matter what — mypy is what
    actually checks it, and mypy fails if OllamaClient.chat's signature ever
    drifts from the Protocol. Without a type checker this test asserts nothing,
    which is precisely why mypy was added.
    """
    client = OllamaClient(base_url="http://ollama.test", model="m", timeout=1.0)

    assert _requires_an_llm_client(client) is client


def test_fake_satisfies_the_protocol_without_inheriting_from_it() -> None:
    """A class with no link to LLMClient still satisfies it.

    Protocol conformance is structural: FakeLLMClient neither imports nor
    inherits LLMClient, and having the right method is the entire requirement.
    In Java this test could not exist — a fake would have to `implements`. This
    is the concrete payoff of choosing Protocol over ABC.
    """
    fake = FakeLLMClient(_A_RESPONSE)

    assert _requires_an_llm_client(fake) is fake


def test_fake_returns_its_canned_response_and_records_the_call() -> None:
    """The fake returns exactly what it was given and remembers the arguments.

    The fake's own contract, tested because everything from step 9 onward
    depends on it. `.calls` is how later tests assert *which prompt was sent*
    without an LLM: if recording broke, those tests would keep passing while
    checking nothing at all.
    """
    fake = FakeLLMClient(_A_RESPONSE)
    messages = [Message(role="user", content="Γεια")]

    assert fake.chat(messages) is _A_RESPONSE
    assert fake.calls == [messages]
