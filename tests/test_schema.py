"""V3 step 2's schema against the real Postgres from ``poe up``.

Marked ``db``: these need the compose database running, so ``poe test`` skips
them and ``poe test-all`` runs them. Each test gets its own throwaway Postgres
schema (``isolated_conn`` in ``conftest.py``), so the table is created, used
and dropped without touching the dev database's ``chunks``.

Until 2026-11-18 these tests used a rolled-back transaction on the dev
database's own ``chunks`` table. That isolated their *writes* but not their
*reads*: once step 4's ``poe load`` filled the real table, the first insert
collided with the real ``π.δ.62/2025/άρθρο-1`` and five tests failed.

What is pinned is the schema's contract with :class:`Chunk`: the filter columns
Postgres derives from the JSON, the round trip back to the model, and the
loud failures the step 2 decisions rely on.
"""

from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from greek_law.domain import ActIdentity, RatifiedInstrument, SourceReference
from greek_law.ingestion.chunking import Chunk
from greek_law.storage.schema import EMBEDDING_DIMENSIONS, apply_schema

pytestmark = pytest.mark.db

_INSERT = """
    INSERT INTO chunks (key, chunk, embedding, embedding_model, embedded_text_hash)
    VALUES (%s, %s::jsonb, %s::vector, 'bge-m3', 'not-a-real-hash')
"""

_FILTER_COLUMNS = """
    SELECT document_id, act_type, act_number, act_year,
           instrument_article, article, paragraph
    FROM chunks WHERE key = %s
"""

_INSTRUMENT_CHUNK = Chunk(
    document_id="fek_a_75_2024",
    source=SourceReference(
        act=ActIdentity(
            act_type="ν.", number="5110", year=2024, fek="Α' 75/24.05.2024"
        ),
        instrument=RatifiedInstrument(
            cited_as="του καταστατικού", ratifying_article="13"
        ),
        article="δέκατο πέμπτο",
        paragraph="1",
    ),
    article_title="Σύνθεση του Διοικητικού Συμβουλίου",
    text="Το Διοικητικό Συμβούλιο αποτελείται από επτά μέλη.",
)

_PLAIN_CHUNK = Chunk(
    document_id="fek_a_121_2025",
    source=SourceReference(
        act=ActIdentity(act_type="π.δ.", number="62", year=2025),
        article="1",
    ),
    text="Με τη σύμβαση εργασίας ο εργαζόμενος έχει υποχρέωση…",
)


def _vector(dimensions: int = EMBEDDING_DIMENSIONS) -> str:
    """pgvector's text form, ``[0.1,0.1,…]`` — enough until step 4 picks an adapter."""
    return "[" + ",".join(["0.1"] * dimensions) + "]"


def _insert(conn: psycopg.Connection[Any], chunk: Chunk) -> None:
    conn.execute(_INSERT, (chunk.key, chunk.model_dump_json(), _vector()))


@pytest.fixture
def conn(isolated_conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    """An isolated connection with the schema applied, as step 4 will find it."""
    apply_schema(isolated_conn)
    return isolated_conn


def test_applying_the_schema_twice_is_harmless(conn: psycopg.Connection[Any]) -> None:
    """A second application, on a table that already holds rows, changes nothing.

    Step 4 applies the schema on every load. Without ``IF NOT EXISTS`` the
    second load would fail on «relation already exists»; with a ``DROP`` /
    ``CREATE`` pair instead, it would silently discard every embedding — four
    minutes of work — each time.
    """
    _insert(conn, _PLAIN_CHUNK)

    apply_schema(conn)

    assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (1,)


def test_filter_columns_are_derived_from_the_chunk_json(
    conn: psycopg.Connection[Any],
) -> None:
    """Postgres fills every filter column from ``chunk``; nothing is passed twice.

    A JSON path that does not follow the model's field names (``year`` vs
    ``act_year``, ``ratifying_article`` vs ``instrument``) yields NULL, not an
    error, for a nullable column — and a filter on it matches nothing. This
    test uses a chunk inside a ratified instrument, the one shape where every
    column has a value, so each path is checked against a real one.
    """
    _insert(conn, _INSTRUMENT_CHUNK)

    row = conn.execute(_FILTER_COLUMNS, (_INSTRUMENT_CHUNK.key,)).fetchone()

    assert row == (
        "fek_a_75_2024",
        "ν.",
        "5110",
        2024,
        "13",
        "δέκατο πέμπτο",
        "1",
    )


def test_an_absent_paragraph_is_sql_null_not_the_text_null(
    conn: psycopg.Connection[Any],
) -> None:
    """A chunk with no paragraph and no instrument gets NULL in those columns.

    Pydantic writes ``"paragraph": null``. Extracted with ``->`` instead of
    ``->>``, that is a JSON ``null`` — and as text, the four-letter string
    'null', which ``paragraph IS NULL`` does not match. Every unnumbered
    article would then look like it had a paragraph called «null».
    """
    _insert(conn, _PLAIN_CHUNK)

    row = conn.execute(
        "SELECT instrument_article, paragraph FROM chunks WHERE key = %s",
        (_PLAIN_CHUNK.key,),
    ).fetchone()

    assert row == (None, None)


def test_a_stored_chunk_reads_back_as_an_equal_chunk(
    conn: psycopg.Connection[Any],
) -> None:
    """``Chunk.model_validate(row["chunk"])`` returns what was inserted.

    The step 2 decision makes the JSON the source of truth and Pydantic the
    only definition of its shape. That holds only if the round trip is
    lossless — Greek text, the nested instrument and all — and if nothing in
    ``jsonb`` (which reorders keys) trips ``extra="forbid"``.
    """
    _insert(conn, _INSTRUMENT_CHUNK)

    row = conn.execute(
        "SELECT chunk FROM chunks WHERE key = %s", (_INSTRUMENT_CHUNK.key,)
    ).fetchone()

    assert row is not None
    assert Chunk.model_validate(row[0]) == _INSTRUMENT_CHUNK


def test_the_column_takes_exactly_embedding_dimensions(
    conn: psycopg.Connection[Any],
) -> None:
    """A vector one short of ``EMBEDDING_DIMENSIONS`` is refused by Postgres.

    The constant in Python and ``vector(1024)`` in the SQL are two statements
    of one fact. If someone changes the model and only one of them, this
    fails — rather than step 4 failing on the first insert, or worse, the
    constant validating vectors the table will not take.
    """
    _insert(conn, _PLAIN_CHUNK)  # exactly EMBEDDING_DIMENSIONS: accepted

    with pytest.raises(psycopg.errors.DataException, match="dimensions"):
        conn.execute(
            _INSERT,
            (
                "short",
                _INSTRUMENT_CHUNK.model_dump_json(),
                _vector(EMBEDDING_DIMENSIONS - 1),
            ),
        )


def test_json_missing_a_required_field_fails_the_insert(
    conn: psycopg.Connection[Any],
) -> None:
    """If ``article`` were renamed in the model, inserts would fail loudly.

    The cost the step 2 decision accepted for generated columns: their JSON
    paths name the model's fields. ``NOT NULL`` is what turns a rename into
    an error at the first insert, instead of 2 136 rows whose ``article`` is
    NULL and a filter that quietly returns nothing.
    """
    renamed = _PLAIN_CHUNK.model_dump(mode="json")
    renamed["source"]["article_number"] = renamed["source"].pop("article")

    with pytest.raises(psycopg.errors.NotNullViolation, match="article"):
        conn.execute(_INSERT, ("renamed", Jsonb(renamed), _vector()))
