import pytest
from pydantic import ValidationError

from greek_law.application import Answer, AnswerMetadata, Question


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_a_blank_question_is_rejected(blank: str) -> None:
    """Empty, spaces-only and newline-only questions all fail validation.

    A blank question would be sent to the LLM as an empty user message, and the
    model would answer *something* — inventing a topic from the system prompt
    alone. That is a fabricated answer to a question nobody asked, and it would
    look like a model failure rather than an unvalidated input. min_length=1
    alone catches only the first case; the whitespace cases are what
    strip_whitespace=True adds, and dropping it would leave them passing.
    """
    with pytest.raises(ValidationError):
        Question(text=blank)


def test_question_text_is_stripped_before_it_is_stored() -> None:
    """Surrounding whitespace is removed at construction, not at the call site.

    The same question typed with and without a trailing newline must be one
    question, not two. V4 keys eval results by question text and V12 will cache
    on it; untrimmed text would produce two cache entries and two eval rows for
    one question, quietly halving any hit rate.
    """
    question = Question(text="  Τι ισχύει για την καταγγελία;\n")

    assert question.text == "Τι ισχύει για την καταγγελία;"


def test_an_answer_cannot_be_edited_after_it_is_built() -> None:
    """Assigning to a field of a built Answer raises.

    frozen=True stated as a test. Step 10 saves baseline answers and V7 replays
    them; if a formatting or redaction step could mutate an Answer in place, the
    record on disk would stop matching the call that produced it, and the
    baseline would silently drift from what the model actually said.
    """
    answer = Answer(
        text="Η απάντηση.",
        metadata=AnswerMetadata(
            model="test-model",
            tokens_in=37,
            tokens_out=11,
            duration_seconds=0.24,
            finish_reason="stop",
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        answer.text = "Κάτι άλλο"  # type: ignore[misc]

    assert "frozen" in str(exc_info.value)
