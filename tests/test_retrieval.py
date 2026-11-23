"""V3 step 5's semantic search: the question's nearest chunks, nearest first.

All tests are marked ``db``: they run real SQL (``<=>``, ``ORDER BY``,
``LIMIT``) against the compose Postgres, inside a throwaway schema
(``isolated_conn``). The table is filled through step 4's ``load``, so what
these tests read is exactly what the real write path writes.

No model runs. ``AngleEmbedder`` places every text at a chosen angle in a
plane, so each cosine distance is known in advance: a text at angle *a* is
``1 - cos(a)`` away from a question at angle 0. bge-m3's own vectors are not
tested here — whether its *rankings* are any good is step 6's reading and
V4's metrics, not a unit test.
"""

import math
from collections.abc import Sequence
from typing import Any

import psycopg
import pytest

from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion.chunking import Chunk
from greek_law.retrieval import NoEmbeddingsError, PgVectorRetriever
from greek_law.storage.load import load
from greek_law.storage.schema import EMBEDDING_DIMENSIONS, apply_schema

pytestmark = pytest.mark.db

_PD = ActIdentity(act_type="π.δ.", number="62", year=2025)
_LAW = ActIdentity(act_type="ν.", number="5110", year=2024)

QUESTION = "Ποιος είναι δικαιούχος των δικαιωμάτων πνευματικής ιδιοκτησίας;"


def _chunk(article: str, act: ActIdentity = _PD) -> Chunk:
    document_id = "fek_a_121_2025" if act is _PD else "fek_a_75_2024"
    return Chunk(
        document_id=document_id,
        source=SourceReference(act=act, article=article),
        article_title=f"Τίτλος άρθρου {article}",
        text=f"Κείμενο του άρθρου {article}.",
    )


def _at(degrees: float) -> list[float]:
    """A unit vector at ``degrees`` in the plane of the first two axes."""
    radians = math.radians(degrees)
    return [math.cos(radians), math.sin(radians)] + [0.0] * (EMBEDDING_DIMENSIONS - 2)


class AngleEmbedder:
    """Embeds each known text at a fixed angle; the question sits at 0°.

    An unknown text raises ``KeyError`` — a test that embeds something it did
    not plan for fails loudly instead of getting an arbitrary vector.
    """

    def __init__(self, angles: dict[str, float], model: str = "bge-m3") -> None:
        self.model = model
        self.calls: list[list[str]] = []
        self._angles = {QUESTION: 0.0, **angles}

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [_at(self._angles[text]) for text in texts]


def _load_at(
    conn: psycopg.Connection[Any],
    placed: Sequence[tuple[Chunk, float]],
    model: str = "bge-m3",
) -> None:
    """Store each chunk with the vector for its angle, through the real loader."""
    angles = {chunk.embedding_text: angle for chunk, angle in placed}
    load(conn, [chunk for chunk, _ in placed], AngleEmbedder(angles, model=model))


def test_results_come_nearest_first_with_their_cosine_distances(
    isolated_conn: psycopg.Connection[Any],
) -> None:
    """Chunks at 80°, 10° and 40° come back as 10°, 40°, 80°, with 1 - cos(angle).

    Loaded in a scrambled order so that "came back in insertion order" cannot
    pass by accident. Catches a missing or reversed ``ORDER BY`` (the farthest
    chunk first — retrieval would hand the LLM the *least* relevant law), and
    the wrong operator: ``<#>`` returns the *negative* inner product, and
    ``<->`` Euclidean distance, so either would fail the distance check.
    """
    far, near, middle = _chunk("80"), _chunk("10"), _chunk("40")
    _load_at(isolated_conn, [(far, 80), (near, 10), (middle, 40)])
    retriever = PgVectorRetriever(isolated_conn, AngleEmbedder({}))

    hits = retriever.retrieve(QUESTION, k=3)

    assert [hit.chunk for hit in hits] == [near, middle, far]
    assert [hit.distance for hit in hits] == pytest.approx(
        [1 - math.cos(math.radians(a)) for a in (10, 40, 80)], abs=1e-6
    )


def test_k_returns_only_the_nearest_k(
    isolated_conn: psycopg.Connection[Any],
) -> None:
    """Of four chunks, ``k=2`` returns the two nearest — not any two.

    Catches ``LIMIT`` applied before the sort (a subquery written the wrong
    way round), which returns k rows that are merely the first ones stored.
    """
    chunks = [(_chunk(str(angle)), angle) for angle in (70, 5, 50, 20)]
    _load_at(isolated_conn, chunks)
    retriever = PgVectorRetriever(isolated_conn, AngleEmbedder({}))

    hits = retriever.retrieve(QUESTION, k=2)

    assert [hit.chunk.source.article for hit in hits] == ["5", "20"]


def test_the_default_k_is_five(isolated_conn: psycopg.Connection[Any]) -> None:
    """Without ``k``, seven stored chunks give five hits.

    The default is the step 5 decision, backed by step 3's Recall@5. It is
    also what step 7's prompt will be sized for: a default that silently
    became 50 would multiply every answer's token cost by ten.
    """
    _load_at(isolated_conn, [(_chunk(str(n)), n) for n in range(1, 8)])
    retriever = PgVectorRetriever(isolated_conn, AngleEmbedder({}))

    assert len(retriever.retrieve(QUESTION)) == 5


def test_the_question_is_embedded_once_exactly_as_asked(
    isolated_conn: psycopg.Connection[Any],
) -> None:
    """The embedder receives ``[question]`` — one call, no prefix, no header.

    Step 3 measured bge-m3 *without* a query prefix, so adding one (as
    Qwen's instruction or e5's ``query:`` would) changes the model under test
    from the one that won the comparison. Also catches a header like the
    chunks' ``embedding_text`` being glued onto the question.
    """
    _load_at(isolated_conn, [(_chunk("1"), 10)])
    embedder = AngleEmbedder({})

    PgVectorRetriever(isolated_conn, embedder).retrieve(QUESTION)

    assert embedder.calls == [[QUESTION]]


def test_rows_from_another_model_are_never_returned(
    isolated_conn: psycopg.Connection[Any],
) -> None:
    """A row embedded by another model is skipped, even when it is "nearest".

    Vectors of two models live in unrelated spaces; a distance between them
    is a number with no meaning. The other model's chunk sits at 0° — a
    perfect match, if the ``embedding_model`` filter were missing — so the
    bug this catches would rank it first, plausibly and without any error.
    """
    stranger = _chunk("1", act=_LAW)
    _load_at(isolated_conn, [(stranger, 0)], model="other-model")
    ours = _chunk("2")
    _load_at(isolated_conn, [(ours, 60)])
    retriever = PgVectorRetriever(isolated_conn, AngleEmbedder({}))

    hits = retriever.retrieve(QUESTION)

    assert [hit.chunk for hit in hits] == [ours]


def test_an_empty_store_raises_and_says_to_run_load(
    isolated_conn: psycopg.Connection[Any],
) -> None:
    """No rows for the model raises ``NoEmbeddingsError`` naming ``poe load``.

    An empty list would be read by step 7 as "the corpus has nothing on this"
    and turned into a confident "not found" — for *every* question, after a
    forgotten ``poe load`` or a model change. An empty table is a setup
    failure, not an answer.
    """
    apply_schema(isolated_conn)

    with pytest.raises(NoEmbeddingsError, match="poe load"):
        PgVectorRetriever(isolated_conn, AngleEmbedder({})).retrieve(QUESTION)


@pytest.mark.parametrize("k", [0, -1])
def test_k_below_one_is_refused_before_embedding(
    isolated_conn: psycopg.Connection[Any], k: int
) -> None:
    """``k`` of 0 or less raises ``ValueError``, and nothing is embedded.

    Postgres reads ``LIMIT 0`` as "no rows" — which the empty-store check
    would then report as a missing ``poe load``, sending whoever sees it to
    fix the wrong thing. ``LIMIT -1`` is a SQL error with a worse message.
    """
    apply_schema(isolated_conn)
    embedder = AngleEmbedder({})

    with pytest.raises(ValueError, match="k"):
        PgVectorRetriever(isolated_conn, embedder).retrieve(QUESTION, k=k)
    assert embedder.calls == []


@pytest.mark.parametrize("question", ["", "   \n"])
def test_a_blank_question_is_refused_before_embedding(
    isolated_conn: psycopg.Connection[Any], question: str
) -> None:
    """An empty or whitespace question raises ``ValueError`` without a model call.

    Embedding "" still yields a vector, and the search would return five
    confident-looking hits for a question nobody asked.
    """
    apply_schema(isolated_conn)
    embedder = AngleEmbedder({})

    with pytest.raises(ValueError, match="empty"):
        PgVectorRetriever(isolated_conn, embedder).retrieve(question)
    assert embedder.calls == []
