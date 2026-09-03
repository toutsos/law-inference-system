from greek_law.application.models import Answer, AnswerMetadata, Question
from greek_law.llm.client import LLMClient
from greek_law.llm.models import Message


def answer_question(question: Question, client: LLMClient) -> Answer:
    """Answer a legal question with no retrieval — the V1 baseline path."""
    response = client.chat([Message(role="user", content=question.text)])

    return Answer(
        text=response.content,
        metadata=AnswerMetadata(
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            duration_seconds=response.duration_seconds,
            finish_reason=response.finish_reason,
        ),
    )
