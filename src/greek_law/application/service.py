from greek_law.application.models import Answer, AnswerMetadata, Question
from greek_law.application.prompts import PROMPT_VERSION, build_messages
from greek_law.llm.client import LLMClient


def answer_question(question: Question, client: LLMClient) -> Answer:
    """Answer a legal question with no retrieval — the V1 baseline path."""
    response = client.chat(build_messages(question))

    return Answer(
        text=response.content,
        metadata=AnswerMetadata(
            model=response.model,
            prompt_version=PROMPT_VERSION,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            duration_seconds=response.duration_seconds,
            finish_reason=response.finish_reason,
        ),
    )
