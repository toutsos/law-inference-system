import json
from pathlib import Path

from experiments.baseline_no_rag.run import QUESTIONS_FILE, ask, load_questions
from greek_law.llm.errors import LLMTimeoutError
from greek_law.llm.models import ChatResponse
from tests.fakes import FakeLLMClient, FlakyLLMClient

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
