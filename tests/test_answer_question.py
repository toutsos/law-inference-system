from greek_law.application import (
    PROMPT_VERSION,
    AnswerMetadata,
    Question,
    answer_question,
    build_messages,
)
from greek_law.llm.models import ChatResponse
from tests.fakes import FakeLLMClient

_A_RESPONSE = ChatResponse(
    model="ilsp/llama-krikri-8b-instruct",
    content="Η απάντηση του μοντέλου.",
    finish_reason="stop",
    tokens_in=37,
    tokens_out=11,
    duration_seconds=0.24,
)


def test_the_service_sends_exactly_what_the_prompt_module_built() -> None:
    """answer_question hands the LLM build_messages() output, nothing else.

    Pins the prompt actually sent, which is the only thing distinguishing a
    working application from one that answers a *different* question. Catches
    the service constructing its own message list again — the bug the step 6
    refactor exists to prevent — which would ship the legal system prompt in
    tests while production silently sent a bare question, or vice versa.
    Comparing against build_messages rather than a literal keeps this test
    about the wiring; the prompt's own content is pinned in test_prompts.py.
    """
    fake = FakeLLMClient(_A_RESPONSE)
    question = Question(text="Τι ισχύει για την καταγγελία σύμβασης;")

    answer_question(question, fake)

    assert fake.calls == [build_messages(question)]


def test_the_system_prompt_is_actually_sent() -> None:
    """A system message reaches the model on every call.

    Redundant with the test above by construction, and deliberately so: that
    one would still pass if build_messages were gutted to return only the
    question, since both sides would change together. This one fails. The whole
    of step 6 — pushing the model from vagueness toward citing provisions —
    lives in that message, and its absence costs nothing visible except worse
    answers.
    """
    fake = FakeLLMClient(_A_RESPONSE)

    answer_question(Question(text="Γεια"), fake)

    assert fake.calls[0][0].role == "system"


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
        prompt_version=PROMPT_VERSION,
        tokens_in=37,
        tokens_out=11,
        duration_seconds=0.24,
        finish_reason="stop",
    )
