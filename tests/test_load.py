"""V3 step 4's load pipeline: idempotent, resumable, pruning only what it loaded.

The first four tests need nothing. The rest are marked ``db`` and run against
the compose Postgres, with a fake embedder so no model is needed. ``load``
commits per batch by the step 4 decision, so a rolled-back transaction cannot
isolate these tests as it does step 2's: each test gets a fresh Postgres
*schema* (a namespace inside the database) that is dropped afterwards. The
dev database's own ``chunks`` table is never touched.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from greek_law.config import Settings
from greek_law.domain import ActIdentity, SourceReference, StructuralUnit
from greek_law.embedding import EmbeddingUnavailableError
from greek_law.ingestion.chunking import Chunk
from greek_law.storage.load import (
    check_unique_keys,
    load,
    read_corpus,
    text_hash,
)
from greek_law.storage.schema import EMBEDDING_DIMENSIONS

_PD = ActIdentity(act_type="π.δ.", number="62", year=2025)
_LAW = ActIdentity(act_type="ν.", number="5110", year=2024)


def _chunk(
    article: str,
    text: str = "Κείμενο.",
    act: ActIdentity = _PD,
    title: str | None = None,
) -> Chunk:
    document_id = "fek_a_121_2025" if act is _PD else "fek_a_75_2024"
    return Chunk(
        document_id=document_id,
        source=SourceReference(act=act, article=article),
        article_title=title,
        text=text,
    )


class FakeEmbedder:
    """Returns one fixed-size vector per text and records every call.

    ``fail_on_call`` makes the n-th call (1-based) raise, the way Ollama
    going away mid-load would.
    """

    def __init__(self, model: str = "bge-m3", fail_on_call: int | None = None):
        self.model = model
        self.calls: list[list[str]] = []
        self._fail_on_call = fail_on_call

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if len(self.calls) == self._fail_on_call:
            raise EmbeddingUnavailableError("Ollama went away")
        return [[0.5] * EMBEDDING_DIMENSIONS for _ in texts]

    @property
    def embedded(self) -> int:
        return sum(len(texts) for texts in self.calls)


# --- no database ---------------------------------------------------------------


def test_an_empty_chunk_file_stops_the_load(tmp_path: Path) -> None:
    """A ``.jsonl`` with no chunks raises instead of loading as "no provisions".

    An empty file means ingestion broke. Read as a document with zero chunks,
    a later design that prunes by file instead of by chunk would delete every
    row of that act — so the loader refuses it up front.
    """
    (tmp_path / "fek_a_75_2024.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="no chunks"):
        read_corpus(tmp_path)


def test_a_missing_processed_directory_says_to_ingest(tmp_path: Path) -> None:
    """No chunk files at all points at ``poe ingest``, not at a stack trace."""
    with pytest.raises(FileNotFoundError, match="poe ingest"):
        read_corpus(tmp_path)


def test_duplicate_keys_are_refused() -> None:
    """Two chunks with one key raise, naming it.

    Upserting both would keep whichever came second and drop the other with
    no trace. Chunking guarantees unique keys today (a slow test pins it);
    this guards the loader if that ever breaks.
    """
    with pytest.raises(ValueError, match="άρθρο-7"):
        check_unique_keys([_chunk("7"), _chunk("7", text="Άλλο.")])


def test_the_hash_covers_the_header_not_only_the_text() -> None:
    """Changing an article's title changes the hash, so the chunk is re-embedded.

    The embedder sees ``embedding_text`` — citation and title, then the text.
    Hashing ``text`` alone would keep a vector computed from the old title
    after a title fix, and nothing would say so.
    """
    before = _chunk("7", title="Καταβολή μισθού")
    after = _chunk("7", title="Καταβολή του μισθού")

    assert before.text == after.text
    assert text_hash(before) != text_hash(after)


# --- with the compose Postgres ---------------------------------------------------


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    schema = sql.Identifier(f"test_load_{uuid4().hex[:12]}")
    with psycopg.connect(str(Settings().database_url)) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        connection.execute(sql.SQL("SET search_path TO {}, public").format(schema))
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
            connection.commit()


def _keys(conn: psycopg.Connection[Any]) -> set[str]:
    return {key for (key,) in conn.execute("SELECT key FROM chunks")}


@pytest.mark.db
def test_a_second_load_embeds_nothing_and_changes_nothing(
    conn: psycopg.Connection[Any],
) -> None:
    """Load twice: same rows, and the second run makes no embedding call.

    This is the step's definition of done — "running twice ≠ duplicates" —
    plus the hash skip that makes a re-run take seconds instead of four
    minutes.
    """
    chunks = [_chunk(str(n)) for n in range(1, 6)]
    first, second = FakeEmbedder(), FakeEmbedder()

    load(conn, chunks, first, batch_size=2)
    report = load(conn, chunks, second, batch_size=2)

    assert first.embedded == 5
    assert second.calls == []
    assert report.unchanged == 5
    assert _keys(conn) == {chunk.key for chunk in chunks}


@pytest.mark.db
def test_only_a_changed_chunk_is_re_embedded(conn: psycopg.Connection[Any]) -> None:
    """After one paragraph's text changes, only that paragraph is sent."""
    load(conn, [_chunk("1"), _chunk("2")], FakeEmbedder())
    embedder = FakeEmbedder()

    load(conn, [_chunk("1"), _chunk("2", text="Νέο κείμενο.")], embedder)

    assert embedder.calls == [[_chunk("2", text="Νέο κείμενο.").embedding_text]]


@pytest.mark.db
def test_a_metadata_change_rewrites_the_json_without_re_embedding(
    conn: psycopg.Connection[Any],
) -> None:
    """A changed ``path`` reaches the stored chunk; the vector is kept.

    ``path`` is not in ``embedding_text``, so the hash does not change. A
    loader that skipped on the hash alone would leave the old JSON — say, a
    ΜΕΡΟΣ title with V2's kerning split still in it — in the table forever.
    """
    original = _chunk("1")
    load(conn, [original], FakeEmbedder())
    moved = original.model_copy(
        update={"path": [StructuralUnit(kind="ΜΕΡΟΣ", number="Α’", title="ΕΡΓΑΣΙΑ")]}
    )
    embedder = FakeEmbedder()

    report = load(conn, [moved], embedder)

    stored = conn.execute("SELECT chunk FROM chunks").fetchone()
    assert stored is not None
    assert Chunk.model_validate(stored[0]) == moved
    assert embedder.calls == []
    assert report.rewritten == 1


@pytest.mark.db
def test_pruning_deletes_only_inside_the_loaded_documents(
    conn: psycopg.Connection[Any],
) -> None:
    """A key gone from one act is deleted; the other act's rows are untouched.

    The scoped DELETE agreed in step 4. Simplified to ``key <> ALL(…)``
    without the ``document_id`` condition, it would delete all of ν. 5110/2024
    the first time only π.δ. 62/2025 is loaded — this test fails if so.
    """
    law = [_chunk("1", act=_LAW), _chunk("2", act=_LAW)]
    decree = [_chunk("1"), _chunk("2"), _chunk("3")]
    load(conn, law + decree, FakeEmbedder())

    report = load(conn, decree[:2], FakeEmbedder())

    assert report.deleted == 1
    assert _keys(conn) == {chunk.key for chunk in law + decree[:2]}


@pytest.mark.db
def test_a_failed_load_keeps_finished_batches_and_deletes_nothing(
    conn: psycopg.Connection[Any],
) -> None:
    """Embedding fails on batch 2: batch 1 stays, nothing is pruned, re-run resumes.

    The step 4 transaction decision (commit per batch, prune last). A stale
    row from an earlier load must survive the failed run — pruning before
    all batches succeed could delete on the evidence of half a corpus.
    """
    stale = _chunk("99")
    load(conn, [stale], FakeEmbedder())
    chunks = [_chunk(str(n)) for n in range(1, 5)]

    with pytest.raises(EmbeddingUnavailableError):
        load(conn, chunks, FakeEmbedder(fail_on_call=2), batch_size=2)
    conn.rollback()

    assert _keys(conn) == {stale.key, chunks[0].key, chunks[1].key}

    resumed = FakeEmbedder()
    load(conn, chunks, resumed, batch_size=2)

    assert resumed.calls == [[chunks[2].embedding_text, chunks[3].embedding_text]]
    assert _keys(conn) == {chunk.key for chunk in chunks}


@pytest.mark.db
def test_a_different_model_re_embeds_everything(
    conn: psycopg.Connection[Any],
) -> None:
    """Rows embedded by another model are not "unchanged", whatever their hash.

    Vectors from two models live in unrelated spaces. Skipping on the hash
    alone would keep bge-m3 vectors under a new model's name, and similarity
    search would compare the question against them — meaningless, no error.
    """
    chunks = [_chunk("1"), _chunk("2")]
    load(conn, chunks, FakeEmbedder(model="bge-m3"))
    other = FakeEmbedder(model="other-model")

    load(conn, chunks, other)

    assert other.embedded == 2
    models = {model for (model,) in conn.execute("SELECT embedding_model FROM chunks")}
    assert models == {"other-model"}


@pytest.mark.db
def test_the_stored_vector_is_the_one_the_embedder_returned(
    conn: psycopg.Connection[Any],
) -> None:
    """A vector round-trips through pgvector unchanged, and next to its own key.

    Checks the ``register_vector`` wiring and the batch zip together: each
    chunk gets a distinct vector, and each row must hold exactly its own.
    """

    class Distinct(FakeEmbedder):
        def embed(self, texts: list[str]) -> list[list[float]]:
            super().embed(texts)
            return [[float(len(t))] * EMBEDDING_DIMENSIONS for t in texts]

    chunks = [_chunk("1", text="α"), _chunk("2", text="ββββ")]
    load(conn, chunks, Distinct(), batch_size=2)

    for chunk in chunks:
        row = conn.execute(
            "SELECT embedding FROM chunks WHERE key = %s", (chunk.key,)
        ).fetchone()
        assert row is not None
        expected = float(len(chunk.embedding_text))
        assert row[0].to_list() == pytest.approx([expected] * EMBEDDING_DIMENSIONS)
