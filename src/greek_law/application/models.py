from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from greek_law.domain import SourceReference
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
    prompt_version: str
    tokens_in: int
    tokens_out: int
    duration_seconds: float
    finish_reason: FinishReason
    attempts: int


class Answer(BaseModel):
    """The application's response to a Question.

    ``sources`` are the provisions the model was shown, nearest first — not
    the ones it chose to cite. Empty on the no-retrieval path. V6 adds
    structured citations beside them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    sources: list[SourceReference] = []
    metadata: AnswerMetadata
