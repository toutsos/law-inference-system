"""The scoring half of V3 step 3's embedding comparison — no Ollama needed.

Every test here feeds a fake embedder, so what is pinned is the arithmetic and
the bookkeeping: ranking, Recall@k, MRR, and which text gets which prefix. A
bug in any of them would not crash; it would quietly pick the wrong model.
"""

import pytest

from experiments.embedding_comparison.run import (
    MODELS,
    NUM_CTX,
    QUESTIONS_FILE,
    DevQuestion,
    Embedding,
    check_expected_keys,
    evaluate_model,
    first_hit_rank,
    load_corpus,
    load_dev_set,
    mean_reciprocal_rank,
    normalize,
    rank_keys,
    recall_at,
)
from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion.chunking import Chunk
from greek_law.ingestion.processed import DEFAULT_PROCESSED_DIR

_ACT = ActIdentity(act_type="π.δ.", number="62", year=2025)


def _chunk(article: str, text: str) -> Chunk:
    return Chunk(
        document_id="fek_a_121_2025",
        source=SourceReference(act=_ACT, article=article),
        text=text,
    )


def test_the_rank_is_that_of_the_earliest_expected_key() -> None:
    """With two acceptable chunks, the question scores by whichever ranks first.

    d04 and d13 accept either of two chunks. Scoring by the first-listed key
    instead would penalise a model for finding the other right answer — d13's
    άρθρο 221 at rank 1 would count as a miss if άρθρο 175 sat at rank 9.
    """
    ranked = ["x", "b", "y", "a"]

    assert first_hit_rank(["a", "b"], ranked) == 2


def test_recall_at_k_counts_rank_k_as_a_hit_and_k_plus_one_as_a_miss() -> None:
    """Rank 5 is inside the top 5; rank 6 is not.

    An off-by-one here (`<` for `<=`, or a 0-based rank) shifts every model's
    Recall@5 by the questions that land exactly on the boundary — enough, on
    17 questions, to swap which model wins.
    """
    assert recall_at([5, 6], 5) == 0.5


def test_an_unfound_question_counts_as_zero_in_mrr_not_as_absent() -> None:
    """A miss pulls MRR down; it is not dropped from the average.

    Averaging only over found questions would make a model that answers 2 of
    17, both at rank 1, score a perfect 1.0 — better than one that finds all
    17 at rank 2.
    """
    assert mean_reciprocal_rank([1, None]) == 0.5


def test_ranking_is_by_cosine_so_a_longer_vector_does_not_win() -> None:
    """After normalisation the closer direction ranks first, whatever the length.

    Raw dot product rewards magnitude: [10, 10] beats [1, 0.1] against the
    query [1, 0] although it points 45° away. Models do not promise unit-length
    output, so forgetting to normalise would rank by vector length — usually
    by text length — rather than by meaning.
    """
    query = normalize([1.0, 0.0])
    vectors = [normalize([10.0, 10.0]), normalize([1.0, 0.1])]

    assert rank_keys(query, ["long", "close"], vectors) == ["close", "long"]


def test_an_expected_key_missing_from_the_corpus_is_an_error() -> None:
    """A typo in questions.json stops the run instead of scoring as a miss.

    A key that does not exist can never be retrieved, so that question would
    be a permanent miss for every model — dragging all scores down equally,
    with nothing in the output saying the set, not the model, is wrong.
    """
    question = DevQuestion(id="d99", text="…", expected_keys=["π.δ.62/2025/άρθρο-9999"])

    with pytest.raises(ValueError, match="d99"):
        check_expected_keys([question], {"π.δ.62/2025/άρθρο-1"})


def test_the_query_template_wraps_questions_and_never_documents() -> None:
    """Questions are embedded through the template; chunks as their embedding_text.

    Qwen3-Embedding is trained with the instruction on the query side only.
    Applying it to the 2 136 chunks too, or forgetting it on the questions,
    is the classic asymmetric-embedding mistake: nothing errors, the model
    just scores worse than it is, and the comparison picks the other one.
    """
    seen: list[str] = []

    def fake_embed(text: str) -> Embedding:
        seen.append(text)
        return Embedding(vector=[1.0, 0.0], tokens=len(text))

    chunk = _chunk("1", "Κείμενο.")
    question = DevQuestion(id="d01", text="Ερώτηση;", expected_keys=[chunk.key])

    evaluate_model([chunk], [question], {"instructed": "Q:{question}"}, fake_embed)

    assert seen == [chunk.embedding_text, "Q:Ερώτηση;"]


def test_every_model_has_its_own_context_length() -> None:
    """Each model in MODELS names the context window it is run with.

    The context is per model because the tokenizers differ by ~3x on Greek:
    the longest chunk is 5 142 bge-m3 tokens but 13 814 qwen3-embedding
    tokens. A model added to MODELS without an entry would fail with a
    KeyError only when its turn comes — after the earlier models have spent
    minutes embedding, and with their results lost.
    """
    assert set(NUM_CTX) == set(MODELS)


@pytest.mark.slow
def test_every_expected_key_of_the_dev_set_exists_in_the_corpus() -> None:
    """embedding-dev-v1 points only at chunks `poe ingest` actually produces.

    The keys were checked by hand when the set was written. A later change to
    chunking or to key derivation would silently orphan them; this is the
    test that notices before a comparison run does.
    """
    _, questions = load_dev_set(QUESTIONS_FILE)
    chunks = load_corpus(DEFAULT_PROCESSED_DIR)

    check_expected_keys(questions, {chunk.key for chunk in chunks})
