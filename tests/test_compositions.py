from greek_law.compositions import LLM_NUM_CTX, build_client
from greek_law.config import Settings
from greek_law.llm.ollama_client import OllamaClient
from greek_law.llm.retrying_client import RetryingLLMClient


def test_the_client_stack_is_retries_wrapped_around_ollama() -> None:
    """build_client returns a RetryingLLMClient decorating an OllamaClient.

    The composition root is the one place the concrete stack is chosen, and the
    order is not interchangeable: retries must sit *outside* the provider to see
    its failures at all. Catches the wrapper being dropped during a refactor,
    which loses every retry silently — the system would still answer, just
    fragilely, and no test of behaviour would notice.
    """
    client = build_client(Settings())

    assert isinstance(client, RetryingLLMClient)
    assert isinstance(client._inner, OllamaClient)


def test_the_retry_budget_leaves_room_for_every_attempt() -> None:
    """The wall-clock budget is wide enough for max_attempts full timeouts.

    A timeout burns the whole request_timeout before it raises, so a budget
    shorter than attempts x timeout silently cancels the later retries: with a
    30s timeout and a 60s budget, attempt 3 is never made, and with the 180s
    timeout the baseline run uses, attempt 2 is never made either. Nothing
    fails loudly — the call just gives up early while the code and the version
    note both claim three attempts. This is the only place that can notice,
    because the lost attempts leave no log line and no exception of their own.
    """
    settings = Settings(request_timeout=30.0)

    client = build_client(settings)

    assert isinstance(client, RetryingLLMClient)
    assert client._budget_seconds >= settings.request_timeout * client._max_attempts


def test_the_llm_context_window_is_ours_not_the_modelfiles() -> None:
    """build_client hands OllamaClient the project's LLM_NUM_CTX.

    The client can only send what the composition root gives it. Catches the
    wiring falling back to a test value or being dropped in a refactor of
    build_client — the window would revert to whatever the model's publisher
    put in its Modelfile (131 072 for krikri, 31 GB), and switching models
    would change it with no diff in this repository.
    """
    client = build_client(Settings())

    assert isinstance(client, RetryingLLMClient)
    assert isinstance(client._inner, OllamaClient)
    assert client._inner._num_ctx == LLM_NUM_CTX
