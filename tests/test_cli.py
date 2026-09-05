import logging

import pytest

from greek_law.cli import _build_client, _configure_logging, run
from greek_law.config import Settings
from greek_law.llm.errors import LLMTimeoutError, LLMUnavailableError
from greek_law.llm.models import ChatResponse
from greek_law.llm.ollama_client import OllamaClient
from greek_law.llm.retrying_client import RetryingLLMClient
from tests.fakes import FakeLLMClient, FlakyLLMClient

_A_RESPONSE = ChatResponse(
    model="ilsp/llama-krikri-8b-instruct",
    content="Η απάντηση του μοντέλου.",
    finish_reason="stop",
    tokens_in=37,
    tokens_out=11,
    duration_seconds=0.25,
)


def _truncated() -> ChatResponse:
    return _A_RESPONSE.model_copy(update={"finish_reason": "length"})


def test_the_answer_goes_to_stdout_and_nothing_else_does(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """stdout carries the answer text alone, with no diagnostics mixed in.

    stdout is the product; the usage numbers are diagnostics and belong on the
    log (stderr). Catches a debugging print() left behind, or usage printed
    rather than logged — either of which corrupts `greek-law "..." > answer.txt`
    and, more importantly, poisons step 10's saved baseline files with token
    counts that a future reader would mistake for part of the model's answer.
    """
    exit_code = run("Τι ισχύει;", FakeLLMClient(_A_RESPONSE))

    assert exit_code == 0
    assert capsys.readouterr().out == "Η απάντηση του μοντέλου.\n"


def test_the_usage_line_reports_tokens_duration_and_rate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One INFO line carries model, prompt version, both token counts and rate.

    This is the whole of step 8: cost awareness as a habit before V3 multiplies
    prompt size and V9 multiplies call counts. tokens_in is the number that
    matters — it is what explodes when retrieved chunks are prepended — so a
    log that omits it would leave the V3 context-budget question unanswerable
    with no error to signal the gap.
    """
    with caplog.at_level(logging.INFO, logger="greek_law.cli"):
        run("Τι ισχύει;", FakeLLMClient(_A_RESPONSE))

    line = caplog.text
    assert "tokens_in=37" in line
    assert "tokens_out=11" in line
    assert "duration=0.25s" in line
    assert "rate=44.0 tok/s" in line
    assert "prompt=v1" in line


def test_a_truncated_answer_is_reported_as_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """finish_reason "length" produces a WARNING that the answer is incomplete.

    Truncation arrives as a normal, successful response with a complete-looking
    body — nothing raises, and the text ends mid-sentence in fluent Greek. This
    log line is the only signal. Without it, step 10 would record a half answer
    as a whole one and the baseline would understate what the model can do.
    """
    with caplog.at_level(logging.INFO, logger="greek_law.cli"):
        run("Τι ισχύει;", FakeLLMClient(_truncated()))

    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_a_complete_answer_produces_no_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """finish_reason "stop" logs usage only — no warning.

    The other half of the boundary above. A warning on every call is a warning
    on no call: operators stop reading it within a day, and the truncation
    signal is then permanently lost.
    """
    with caplog.at_level(logging.INFO, logger="greek_law.cli"):
        run("Τι ισχύει;", FakeLLMClient(_A_RESPONSE))

    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_a_provider_failure_exits_nonzero_without_a_traceback(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An LLMError becomes exit code 1 and a logged message, not a stack trace.

    Step 7 gave failures a type; this is where the application finally decides
    what to *do* with one. Catches the exception escaping main, which prints a
    traceback that tells a user nothing actionable — and, because an uncaught
    exception exits with code 1 as well, the exit code alone would not reveal
    the difference. Asserting stdout stayed empty is what distinguishes them.
    """
    client = FlakyLLMClient(_A_RESPONSE, failures=[LLMUnavailableError("refused")])

    with caplog.at_level(logging.ERROR, logger="greek_law.cli"):
        exit_code = run("Τι ισχύει;", client)

    assert exit_code == 1
    assert "LLMUnavailableError" in caplog.text
    assert capsys.readouterr().out == ""


def test_a_zero_duration_does_not_divide_by_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A call reported as instantaneous logs rate=0.0 instead of crashing.

    perf_counter can return the same value twice on a coarse clock, and a
    cached or mocked response can legitimately measure zero. ZeroDivisionError
    here would turn a *successful* answer into a crash inside the logging of
    it — the worst possible place, since the work was already done and paid for.
    """
    instant = _A_RESPONSE.model_copy(update={"duration_seconds": 0.0})

    with caplog.at_level(logging.INFO, logger="greek_law.cli"):
        run("Τι ισχύει;", FakeLLMClient(instant))

    assert "rate=0.0 tok/s" in caplog.text


def test_the_client_stack_is_retries_wrapped_around_ollama() -> None:
    """_build_client returns a RetryingLLMClient decorating an OllamaClient.

    The composition root is the one place the concrete stack is chosen, and the
    order is not interchangeable: retries must sit *outside* the provider to see
    its failures at all. Catches the wrapper being dropped during a refactor,
    which loses every retry silently — the system would still answer, just
    fragilely, and no test of behaviour would notice.
    """
    client = _build_client(Settings())

    assert isinstance(client, RetryingLLMClient)
    assert isinstance(client._inner, OllamaClient)


def test_usage_is_logged_for_an_answer_that_needed_a_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A retried call still reports usage once, from the attempt that succeeded.

    Pins the known gap deliberately: RetryingLLMClient logs nothing, so the two
    failed attempts leave no trace and duration reflects only the final one.
    This test documents that the numbers describe the *successful attempt*, not
    the wall-clock the user waited — so a future reader of the V4 measurements
    does not mistake them for end-to-end latency.
    """
    inner = FlakyLLMClient(_A_RESPONSE, failures=[LLMTimeoutError("slow")])
    client = RetryingLLMClient(inner, first_backoff_seconds=0.0, sleep=lambda _: None)

    with caplog.at_level(logging.INFO, logger="greek_law.cli"):
        exit_code = run("Τι ισχύει;", client)

    assert exit_code == 0
    assert inner.calls == 2
    assert caplog.text.count("tokens_in=37") == 1


def test_only_our_own_loggers_are_given_the_configured_level() -> None:
    """greek_law.* gets settings.log_level; everything else stays at WARNING.

    basicConfig configures the *root* logger and every library inherits from
    it, so setting the level there hands httpcore the same verbosity we wanted
    for ourselves — which buried the one usage line we care about under twenty
    lines of TCP handshake on the first real run. Catches a regression to
    basicConfig(level=...), and pins the root at WARNING so a third-party
    DEBUG flood cannot come back.
    """
    root = logging.getLogger()
    ours = logging.getLogger("greek_law")
    saved = (root.level, ours.level)

    try:
        _configure_logging(Settings(log_level="DEBUG"))

        assert ours.level == logging.DEBUG
        assert root.level == logging.WARNING
        assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING
    finally:
        root.setLevel(saved[0])
        ours.setLevel(saved[1])
