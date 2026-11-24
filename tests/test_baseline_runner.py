import json
from pathlib import Path

from experiments.baseline_no_rag.run import QUESTIONS_FILE, ask, load_questions
from greek_law.domain import ActIdentity, SourceReference
from greek_law.embedding import EmbeddingUnavailableError
from greek_law.ingestion.chunking import Chunk
from greek_law.llm.errors import LLMTimeoutError
from greek_law.llm.models import ChatResponse
from greek_law.retrieval import DEFAULT_K, NoEmbeddingsError, RetrievedChunk
from tests.fakes import FakeLLMClient, FakeRetriever, FlakyLLMClient

_AN_ENTRY = {
    "id": "q01",
    "text": "Ποια αποζημίωση δικαιούται υπάλληλος με 10 έτη υπηρεσίας;",
    "probes": "Invented month counts on ν. 2112/1920.",
}

_A_RESPONSE = ChatResponse(
    model="ilsp/llama-krikri-8b-instruct:latest",
    content="Σύμφωνα με τον ν. 2112/1920 ...",
    finish_reason="stop",
    tokens_in=312,
    tokens_out=418,
    duration_seconds=17.418,
)


def test_a_record_carries_the_question_it_answered_and_why_it_was_asked() -> None:
    """id, question text and probe travel into the record beside the answer.

    The results file is read months later, in V3, next to a RAG run of the same
    set. Without the question text and the probe stored *with* the answer, the
    file is a list of Greek paragraphs whose meaning lives only in a separate
    questions.json that may have been edited since. That is exactly how a
    baseline stops being evidence: the answer and the thing it answers drift
    apart and nobody can tell.
    """
    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE))

    assert record["id"] == "q01"
    assert record["question"] == _AN_ENTRY["text"]
    assert record["probes"] == _AN_ENTRY["probes"]


def test_the_full_provenance_block_lands_in_the_record() -> None:
    """Model, prompt version and the usage numbers are saved with every answer.

    An answer without the model and prompt_version that produced it cannot be
    compared to anything: V3's whole argument is "same questions, same prompt,
    now with retrieval", and V7 re-runs the set after prompt edits. Dropping
    one of these fields breaks nothing at runtime and is invisible until the
    comparison is attempted, by which time the run costs minutes to repeat.
    """
    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE))

    assert record["answer"] == "Σύμφωνα με τον ν. 2112/1920 ..."
    assert record["model"] == "ilsp/llama-krikri-8b-instruct:latest"
    assert record["prompt_version"] == "v1"
    assert record["tokens_in"] == 312
    assert record["tokens_out"] == 418
    assert record["duration_seconds"] == 17.42
    assert record["finish_reason"] == "stop"


def test_a_failing_question_becomes_a_record_instead_of_an_exception() -> None:
    """An LLM failure is written down as a result, not raised out of ask().

    The run is eight sequential calls at ~20s each. If question five times out
    and the exception escapes, the four answers already produced are lost with
    it and the whole set has to be re-asked. Recording the failure keeps the
    run's other evidence and leaves a visible hole to re-ask with --only.
    """
    always_fails = FlakyLLMClient(_A_RESPONSE, [LLMTimeoutError("no response")])

    record = ask(_AN_ENTRY, always_fails)

    assert record["error"] == "LLMTimeoutError: no response"
    assert "answer" not in record


def test_the_record_of_a_failure_still_says_which_question_failed() -> None:
    """A failed record keeps its id, question and probe like a successful one.

    Without them the results file has a hole with no label, and the learner
    cannot tell which of the eight probes went unmeasured — the file would
    quietly look like a seven-question set.
    """
    always_fails = FlakyLLMClient(_A_RESPONSE, [LLMTimeoutError("no response")])

    record = ask(_AN_ENTRY, always_fails)

    assert record["id"] == "q01"
    assert record["probes"] == _AN_ENTRY["probes"]


def test_the_question_set_is_well_formed() -> None:
    """questions.json has a set version and 5-10 uniquely-identified questions.

    The ids are how a run record points back at a question and how --only
    re-asks one, so a duplicated id silently overwrites evidence. The count is
    the step's own bound: fewer than five is not a sample, more than ten makes
    the run long enough that the learner stops re-running it. Catches a
    hand-edit that breaks the file for a run that takes minutes to reach it.
    """
    book = load_questions(QUESTIONS_FILE)
    ids = [question["id"] for question in book["questions"]]

    assert book["set_version"]
    assert 5 <= len(ids) <= 10
    assert len(set(ids)) == len(ids)


def test_every_question_records_what_failure_mode_it_probes() -> None:
    """Each question carries non-empty text and a probes rationale.

    A baseline question with no stated probe is untriageable: when the answer
    comes back, nothing says what was supposed to be wrong with it, so the
    annotation degenerates into "sounds plausible". The probe field is what
    turns eight paragraphs of Greek into eight testable claims.
    """
    book = load_questions(QUESTIONS_FILE)

    for question in book["questions"]:
        assert question["text"].strip(), question["id"]
        assert question["probes"].strip(), question["id"]


def test_the_questions_file_is_utf8_greek_not_escaped_ascii() -> None:
    """questions.json is stored as readable Greek, not \\uXXXX escapes.

    json.dumps defaults to ensure_ascii=True, so a future script that rewrites
    this file would turn every question into escape sequences. It still parses
    and every other test still passes — but the file stops being reviewable in
    a diff, which is the only reason to keep the question set in git at all.
    """
    raw = Path(QUESTIONS_FILE).read_text(encoding="utf-8")

    assert "\\u" not in raw
    assert json.loads(raw)["questions"]


def _hit(article: str, distance: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            document_id="test_doc",
            source=SourceReference(
                act=ActIdentity(act_type="ν.", number="5110", year=2024),
                article=article,
                paragraph="1",
            ),
            text=f"Κείμενο του άρθρου {article}.",
        ),
        distance=distance,
    )


def test_a_rag_record_carries_the_citations_shown_to_the_model() -> None:
    """With a retriever, the record stores each source's citation, nearest first.

    Step 10 sorts every wrong answer into "retrieval failure" or "generation
    failure" by asking one thing: was the right provision among the sources?
    Catches a RAG run that saves only the answer text — the sources would be
    gone, and the only record of what the model saw would be its own claims.
    """
    retriever = FakeRetriever([_hit("11", 0.34), _hit("12", 0.41)])

    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE), retriever)

    assert record["sources"] == [
        "ν. 5110/2024, άρθρο 11 παρ. 1",
        "ν. 5110/2024, άρθρο 12 παρ. 1",
    ]
    assert retriever.calls == [(_AN_ENTRY["text"], DEFAULT_K)]


def test_a_rag_record_is_stamped_with_the_grounded_prompt_version() -> None:
    """A RAG record says prompt_version "v2"; a baseline record says "v1".

    prompt_version is how the comparison tells the two runs' answers apart
    inside the files. Catches the --rag path still calling answer_question:
    the run would be labelled RAG, look plausible, and measure V1 again.
    """
    retriever = FakeRetriever([_hit("11", 0.34)])

    rag = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE), retriever)
    baseline = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE))

    assert rag["prompt_version"] == "v2"
    assert baseline["prompt_version"] == "v1"


def test_a_baseline_record_has_an_empty_source_list() -> None:
    """Without a retriever, sources is [] — present, and empty.

    One record shape for both modes, so compare.py can read either run
    without branching. Catches the field missing from baseline records (a
    KeyError in the comparison) or filled with something the model never saw.
    """
    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE))

    assert record["sources"] == []


def test_an_embedding_failure_becomes_a_record_instead_of_an_exception() -> None:
    """Ollama's embedder going away mid-run is recorded, like an LLM failure.

    The RAG run calls two models per question, so it has a second way to
    fail. Catches ask() catching only LLMError: an EmbeddingError would
    escape, abort the run, and throw away the answers already produced.
    """
    retriever = FakeRetriever(error=EmbeddingUnavailableError("Ollama went away"))

    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE), retriever)

    assert record["error"] == "EmbeddingUnavailableError: Ollama went away"
    assert record["id"] == "q01"


def test_an_empty_store_becomes_a_record_instead_of_an_exception() -> None:
    """NoEmbeddingsError (nothing loaded) is recorded, not raised.

    Catches the same escape as above for the store being empty. Every record
    would then carry the same error, which says plainly "run poe load" —
    better than a traceback after the first question.
    """
    retriever = FakeRetriever(error=NoEmbeddingsError("run `poe load`"))

    record = ask(_AN_ENTRY, FakeLLMClient(_A_RESPONSE), retriever)

    assert record["error"] == "NoEmbeddingsError: run `poe load`"
