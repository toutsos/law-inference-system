from greek_law.application.models import Answer, AnswerMetadata, Question
from greek_law.application.prompts import (
    GROUNDED_PROMPT_VERSION,
    PROMPT_VERSION,
    build_grounded_messages,
    build_messages,
)
from greek_law.domain import SourceReference
from greek_law.llm.client import LLMClient
from greek_law.llm.models import ChatResponse
from greek_law.retrieval import Retriever


def answer_question(question: Question, client: LLMClient) -> Answer:
    """Answer a legal question with no retrieval — the V1 baseline path."""
    response = client.chat(build_messages(question))
    return _to_answer(response, PROMPT_VERSION, sources=[])


def answer_with_retrieval(
    question: Question, retriever: Retriever, client: LLMClient
) -> Answer:
    """Answer from the provisions nearest to the question — the V3 RAG path.

    Retrieval failures propagate before the model is called: asked with no
    provisions, it would report a setup failure as "not found".
    """
    hits = retriever.retrieve(question.text)
    chunks = [hit.chunk for hit in hits]
    response = client.chat(build_grounded_messages(question, chunks))
    sources = [chunk.source for chunk in chunks]
    return _to_answer(response, GROUNDED_PROMPT_VERSION, sources)


def _to_answer(
    response: ChatResponse,
    prompt_version: str,
    sources: list[SourceReference],
) -> Answer:
    """Wrap the model's reply, its sources and the call's usage into an Answer."""
    return Answer(
        text=response.content,
        sources=sources,
        metadata=AnswerMetadata(
            model=response.model,
            prompt_version=prompt_version,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            duration_seconds=response.duration_seconds,
            finish_reason=response.finish_reason,
            attempts=response.attempts,
        ),
    )
