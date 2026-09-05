import random

import pytest

from greek_law.llm.errors import (
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from greek_law.llm.models import ChatResponse, Message
from greek_law.llm.retrying_client import RetryingLLMClient
from tests.fakes import FlakyLLMClient, RecordingSleep

_A_RESPONSE = ChatResponse(
    model="test-model",
    content="Καλημέρα",
    finish_reason="stop",
    tokens_in=37,
    tokens_out=11,
    duration_seconds=0.24,
)


def _one_message() -> list[Message]:
    return [Message(role="user", content="Γεια")]


def _retrying(
    inner: FlakyLLMClient,
    sleep: RecordingSleep,
    max_attempts: int = 3,
    budget_seconds: float = 60.0,
) -> RetryingLLMClient:
    """A RetryingLLMClient with a seeded RNG and a sleep that does not wait."""
    return RetryingLLMClient(
        inner,
        max_attempts=max_attempts,
        first_backoff_seconds=0.5,
        budget_seconds=budget_seconds,
        sleep=sleep,
        rng=random.Random(0),
    )


def test_a_successful_call_is_passed_through_without_sleeping() -> None:
    """The happy path costs exactly one call and zero delay.

    The cost of a retry wrapper must be nothing when nothing fails. Catches a
    loop that sleeps before its first attempt rather than between attempts —
    which adds the full backoff to every single call in the system, turning a
    fast path into a slow one with no error anywhere to explain it.
    """
    inner = FlakyLLMClient(_A_RESPONSE, failures=[])
    sleep = RecordingSleep()

    response = _retrying(inner, sleep).chat(_one_message())

    assert response == _A_RESPONSE
    assert inner.calls == 1
    assert sleep.delays == []


def test_a_transient_failure_is_retried_and_the_later_success_is_returned() -> None:
    """Two timeouts then a success returns the success on the third attempt.

    The whole reason the wrapper exists. Catches the loop returning None,
    swallowing the eventual response, or re-raising after a successful retry —
    all of which turn a recovered call into a failed one, which is worse than
    not retrying at all because it also burns the latency.
    """
    inner = FlakyLLMClient(
        _A_RESPONSE,
        failures=[LLMTimeoutError("slow"), LLMUnavailableError("503")],
    )
    sleep = RecordingSleep()

    response = _retrying(inner, sleep).chat(_one_message())

    assert response == _A_RESPONSE
    assert inner.calls == 3
    assert len(sleep.delays) == 2


def test_a_permanent_failure_is_not_retried() -> None:
    """LLMRequestError propagates after exactly one attempt.

    The transient/permanent split earning its keep. A typo in OLLAMA_MODEL
    returns 404 forever; retrying it spends the whole budget to reach the same
    answer, turning an instant, obvious misconfiguration into a slow one. Also
    catches the except clause being widened to LLMError, which would swallow
    the distinction the type tree was built for.
    """
    inner = FlakyLLMClient(_A_RESPONSE, failures=[LLMRequestError("404")])
    sleep = RecordingSleep()

    with pytest.raises(LLMRequestError):
        _retrying(inner, sleep).chat(_one_message())

    assert inner.calls == 1
    assert sleep.delays == []


def test_the_last_error_is_raised_once_the_attempts_are_spent() -> None:
    """After max_attempts transient failures the final error reaches the caller.

    A retry policy must fail loudly, not silently return a degraded answer or
    loop forever. Pins the attempt count too: off-by-one here means either a
    wasted extra call to a dead provider on every failure, or one fewer retry
    than configured — neither visible without counting.
    """
    inner = FlakyLLMClient(
        _A_RESPONSE,
        failures=[LLMTimeoutError(f"attempt {n}") for n in range(5)],
    )
    sleep = RecordingSleep()

    with pytest.raises(LLMTimeoutError, match="attempt 2"):
        _retrying(inner, sleep, max_attempts=3).chat(_one_message())

    assert inner.calls == 3
    assert len(sleep.delays) == 2


def test_max_attempts_of_one_disables_retrying_entirely() -> None:
    """max_attempts=1 makes the wrapper a pass-through that never sleeps.

    The boundary. Someone will set this to disable retries in a test or an eval
    run, and an off-by-one that still retried once would make V4's measurements
    silently include a second call the operator believed was switched off.
    """
    inner = FlakyLLMClient(_A_RESPONSE, failures=[LLMTimeoutError("slow")])
    sleep = RecordingSleep()

    with pytest.raises(LLMTimeoutError):
        _retrying(inner, sleep, max_attempts=1).chat(_one_message())

    assert inner.calls == 1
    assert sleep.delays == []


def test_the_backoff_ceiling_doubles_between_attempts() -> None:
    """Each delay is drawn from [0, b) with b doubling: 0.5, then 1.0.

    Exponential growth is the point of backoff — a fixed delay hammers a
    struggling provider at a constant rate and prevents it recovering. Catches
    the multiplier being dropped (constant delay) or applied to the drawn value
    instead of the ceiling (which would make the growth random, not
    exponential). Only the upper bounds hold for every seed — jitter is
    deliberately random, so a delay may be anywhere in [0, ceiling). The lower
    bound on the second delay is specific to Random(0) and is what actually
    demonstrates the ceiling grew; change the seed and it must be rechecked.
    """
    inner = FlakyLLMClient(
        _A_RESPONSE,
        failures=[LLMTimeoutError("1"), LLMTimeoutError("2")],
    )
    sleep = RecordingSleep()

    _retrying(inner, sleep).chat(_one_message())

    first, second = sleep.delays
    assert 0.0 <= first < 0.5
    assert 0.5 <= second < 1.0


def test_the_wall_clock_budget_stops_retrying_before_it_is_exceeded() -> None:
    """With no budget left, the transient error is raised instead of slept on.

    Attempt count alone cannot bound how long a call takes: a timeout has
    already consumed the full request_timeout before it raises, so three
    attempts at a 30s timeout is a 90-second failure that a caller with a
    deadline experiences as a hang. The budget is what makes the worst case
    predictable, and it must be checked *before* sleeping, not after.
    """
    inner = FlakyLLMClient(_A_RESPONSE, failures=[LLMTimeoutError("slow")])
    sleep = RecordingSleep()

    with pytest.raises(LLMTimeoutError):
        _retrying(inner, sleep, budget_seconds=0.0).chat(_one_message())

    assert inner.calls == 1
    assert sleep.delays == []
