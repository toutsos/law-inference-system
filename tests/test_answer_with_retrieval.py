import pytest

from greek_law.application import (
    GROUNDED_PROMPT_VERSION,
    NOT_FOUND_ANSWER,
    AnswerMetadata,
    Question,
    answer_with_retrieval,
    build_grounded_messages,
)
from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion.chunking import Chunk
from greek_law.llm.models import ChatResponse
from greek_law.retrieval import DEFAULT_K, NoEmbeddingsError, RetrievedChunk
from tests.fakes import FakeLLMClient, FakeRetriever

_N5110 = ActIdentity(act_type="ν.", number="5110", year=2024)

_A_RESPONSE = ChatResponse(
    model="ilsp/llama-krikri-8b-instruct",
    content="Δικαιούχος είναι ο ανάδοχος (ν. 5110/2024, άρθρο 11 παρ. 1).",
    finish_reason="stop",
    tokens_in=1200,
    tokens_out=40,
    duration_seconds=3.5,
    attempts=1,
)


def _hit(article: str, distance: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            document_id="test_doc",
            source=SourceReference(act=_N5110, article=article, paragraph="1"),
            article_title=None,
            text=f"Κείμενο του άρθρου {article}.",
        ),
        distance=distance,
    )


_HITS = [_hit("11", 0.34), _hit("12", 0.41)]


def test_the_llm_receives_the_grounded_prompt_built_from_the_hits() -> None:
    """The model gets build_grounded_messages(question, hit chunks), in order.

    Pins the wiring between the two seams. Catches the service sending the V1
    prompt (build_messages) — fluent, uncited answers that look like a model
    problem — or passing the chunks reordered or only the first one, which
    silently changes what step 9 measures.
    """
    llm = FakeLLMClient(_A_RESPONSE)
    question = Question(text="Ποιος είναι δικαιούχος;")

    answer_with_retrieval(question, FakeRetriever(_HITS), llm)

    expected = build_grounded_messages(question, [hit.chunk for hit in _HITS])
    assert llm.calls == [expected]


def test_the_retriever_is_asked_the_question_text_at_the_default_k() -> None:
    """retrieve() receives the validated question text and DEFAULT_K.

    Catches str(question) being passed — the Pydantic repr "text='…'" would be
    embedded, still returning plausible neighbours — and a k hard-coded in the
    service drifting from the step 6 decision to keep DEFAULT_K.
    """
    retriever = FakeRetriever(_HITS)

    answer_with_retrieval(
        Question(text="  Ποιος;  "), retriever, FakeLLMClient(_A_RESPONSE)
    )

    assert retriever.calls == [("Ποιος;", DEFAULT_K)]


def test_the_answer_is_stamped_with_the_grounded_prompt_version() -> None:
    """A RAG answer carries prompt_version "v2" and the call's usage.

    prompt_version is how step 9 tells V3's answers from V1's in the results
    files. Catches the service reusing PROMPT_VERSION ("v1") — every RAG
    answer would be labelled as a no-retrieval baseline answer.
    """
    answer = answer_with_retrieval(
        Question(text="Ποιος;"), FakeRetriever(_HITS), FakeLLMClient(_A_RESPONSE)
    )

    assert answer.text == _A_RESPONSE.content
    assert answer.metadata == AnswerMetadata(
        model="ilsp/llama-krikri-8b-instruct",
        prompt_version=GROUNDED_PROMPT_VERSION,
        tokens_in=1200,
        tokens_out=40,
        duration_seconds=3.5,
        finish_reason="stop",
        attempts=1,
    )


def test_a_retrieval_failure_stops_before_the_llm_is_called() -> None:
    """NoEmbeddingsError propagates, and the model is never asked.

    Catches a service that swallows the error and asks the model with no
    provisions — which would come back as NOT_FOUND_ANSWER for every question:
    an empty database reported as a legal finding.
    """
    llm = FakeLLMClient(_A_RESPONSE)
    retriever = FakeRetriever(error=NoEmbeddingsError("run `poe load`"))

    with pytest.raises(NoEmbeddingsError):
        answer_with_retrieval(Question(text="Ποιος;"), retriever, llm)

    assert llm.calls == []


def test_sources_are_the_retrieved_provisions_nearest_first() -> None:
    """Answer.sources is the hits' SourceReferences, in retrieval order.

    Sources mean "shown to the model" (step 8 decision A), so they come from
    the retriever, never from the model's text. Catches the list being taken
    from only the first hit, reordered, or rebuilt by parsing the answer —
    which step 7 showed drops the act or the paragraph, and would make step
    10 call a generation failure a retrieval failure.
    """
    answer = answer_with_retrieval(
        Question(text="Ποιος;"), FakeRetriever(_HITS), FakeLLMClient(_A_RESPONSE)
    )

    assert answer.sources == [hit.chunk.source for hit in _HITS]


def test_sources_are_kept_when_the_model_refuses() -> None:
    """A refusal still carries every provision the model was shown.

    Hiding sources on refusal is a display decision made in the CLI, not a
    fact about the answer. Catches the service emptying sources on refusal:
    step 10 could then no longer see "the right provision was retrieved and
    the model still refused" — the clearest generation failure there is.
    """
    refusal = _A_RESPONSE.model_copy(update={"content": NOT_FOUND_ANSWER})

    answer = answer_with_retrieval(
        Question(text="Ποιος;"), FakeRetriever(_HITS), FakeLLMClient(refusal)
    )

    assert answer.sources == [hit.chunk.source for hit in _HITS]
