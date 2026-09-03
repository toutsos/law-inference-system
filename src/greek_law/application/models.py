from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from greek_law.llm.models import FinishReason

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Question(BaseModel):
    """A user's natural-language question, at the application boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: QuestionText


class AnswerMetadata(BaseModel):
    """Facts about the call that produced an answer — not part of the answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    tokens_in: int
    tokens_out: int
    duration_seconds: float
    finish_reason: FinishReason


class Answer(BaseModel):
    """The application's response to a Question.

    V3 adds ``sources: list[SourceReference]`` beside ``text``; V6 adds
    structured citations. Both are additions, not changes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    metadata: AnswerMetadata
