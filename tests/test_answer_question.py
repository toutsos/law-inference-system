from greek_law.application import AnswerMetadata, Question, answer_question
from greek_law.llm.models import ChatResponse, Message
from tests.fakes import FakeLLMClient

_A_RESPONSE = ChatResponse(
    model="ilsp/llama-krikri-8b-instruct",
    content="Η απάντηση του μοντέλου.",
    finish_reason="stop",
    tokens_in=37,
    tokens_out=11,
    duration_seconds=0.24,
)


def test_the_question_reaches_the_llm_as_a_single_user_message() -> None:
    """V1 sends exactly one message: the question text, with role "user".

    Pins the prompt actually sent, which is the only thing distinguishing a
    working application from one that answers a *different* question. Catches
    the text being wrapped, truncated, or sent under role "system" — all of
    which produce a plausible answer, so no test that only inspects the returned
    text would notice. This test is written to FAIL at step 6, when a system
    message is added: that failure is the step landing, not a regression.
    """
    fake = FakeLLMClient(_A_RESPONSE)
    text = "Τι ισχύει για την καταγγελία σύμβασης;"

    answer_question(Question(text=text), fake)

    assert fake.calls == [[Message(role="user", content=text)]]


def test_the_model_content_becomes_the_answer_text() -> None:
    """What the LLM said is what the caller reads back, unaltered.

    The application boundary's headline contract. Catches the text being taken
    from the wrong place — a nested field, or a str() of the whole response —
    which would surface to the user as an answer wrapped in JSON debris rather
    than as an exception.
    """
    answer = answer_question(Question(text="Γεια"), FakeLLMClient(_A_RESPONSE))

    assert answer.text == "Η απάντηση του μοντέλου."


def test_every_call_measurement_lands_on_the_matching_metadata_field() -> None:
    """All five ChatResponse measurements arrive under the right Answer names.

    The mapping block in service.py is hand-written field by field, so a
    copy-paste slip that swaps tokens_in with tokens_out, or reuses
    response.tokens_out twice, type-checks and never raises. It would invert
    step 8's usage log and make the V3 context-budget numbers wrong in the
    direction that looks reassuring. Comparing the whole model at once catches
    any permutation, not just the pair a targeted assertion happened to check.
    """
    answer = answer_question(Question(text="Γεια"), FakeLLMClient(_A_RESPONSE))

    assert answer.metadata == AnswerMetadata(
        model="ilsp/llama-krikri-8b-instruct",
        tokens_in=37,
        tokens_out=11,
        duration_seconds=0.24,
        finish_reason="stop",
    )
