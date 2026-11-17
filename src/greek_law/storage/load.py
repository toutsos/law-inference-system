"""Load ``data/processed/`` into Postgres: embed what changed, upsert, prune.

Idempotent by the step 4 decisions: running it twice leaves the table exactly
as running it once, and the second run makes no embedding call at all.

- **Skip what is unchanged.** A row whose ``embedded_text_hash`` and
  ``embedding_model`` match is not re-embedded. If only the chunk's metadata
  changed (its ``path``, say), the JSON is rewritten and the vector kept.
- **Commit per batch.** Each batch is embedded, upserted and committed on its
  own, so a crash keeps the finished batches and the next run resumes.
- **Prune last, and only inside the loaded documents.** Rows whose key this
  run did not produce are deleted only after every batch has succeeded, and
  only for documents this run actually read.
"""

import argparse
import hashlib
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from greek_law.compositions import build_embedder
from greek_law.config import Settings
from greek_law.embedding import Embedder, EmbeddingError
from greek_law.ingestion.chunking import Chunk
from greek_law.ingestion.processed import DEFAULT_PROCESSED_DIR, read_chunks
from greek_law.storage.schema import apply_schema

BATCH_SIZE = 16
"""Texts per ``/api/embed`` request — and per commit."""

_UPSERT = """
    INSERT INTO chunks (key, chunk, embedding, embedding_model, embedded_text_hash)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (key) DO UPDATE SET
        chunk = EXCLUDED.chunk,
        embedding = EXCLUDED.embedding,
        embedding_model = EXCLUDED.embedding_model,
        embedded_text_hash = EXCLUDED.embedded_text_hash
"""

_UPDATE_CHUNK = "UPDATE chunks SET chunk = %s WHERE key = %s"

_PRUNE = """
    DELETE FROM chunks
    WHERE document_id = ANY(%s) AND key <> ALL(%s)
"""


@dataclass(frozen=True)
class LoadReport:
    """What one load did, counted. ``embedded + rewritten + unchanged == chunks``."""

    documents: list[str]
    chunks: int
    embedded: int
    rewritten: int
    unchanged: int
    deleted: int


def text_hash(chunk: Chunk) -> str:
    """sha256 of exactly the text the embedder sees — header included."""
    return hashlib.sha256(chunk.embedding_text.encode("utf-8")).hexdigest()


def read_corpus(directory: Path) -> list[Chunk]:
    """Every chunk of every ``*.jsonl`` in ``directory``, refusing empty files.

    An empty file is almost certainly a broken ingest, not a law without
    provisions. Loading it would be harmless only by accident; refusing it
    keeps "the database matches ``data/processed/``" from ever meaning
    "the database lost a document".
    """
    paths = sorted(directory.glob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"no *.jsonl in {directory}; run `poe ingest` first")
    chunks: list[Chunk] = []
    for path in paths:
        found = read_chunks(path)
        if not found:
            raise ValueError(f"{path} has no chunks; re-run `poe ingest`")
        chunks.extend(found)
    return chunks


def check_unique_keys(chunks: list[Chunk]) -> None:
    """Raise if two chunks share a key — the second would overwrite the first."""
    duplicates = sorted(
        key for key, n in Counter(c.key for c in chunks).items() if n > 1
    )
    if duplicates:
        raise ValueError(f"duplicate chunk keys: {', '.join(duplicates[:5])}")


def load(
    conn: psycopg.Connection[Any],
    chunks: list[Chunk],
    embedder: Embedder,
    batch_size: int = BATCH_SIZE,
    on_batch: Callable[[int, int], None] | None = None,
) -> LoadReport:
    """Make ``chunks`` the table's content for their documents. See the module doc.

    ``on_batch(done, total)`` is called after each committed batch, for
    progress output; the function itself prints nothing.
    """
    check_unique_keys(chunks)
    apply_schema(conn)
    conn.commit()
    register_vector(conn)

    stored: dict[str, tuple[str, Any]] = {
        key: (digest, chunk_json)
        for key, digest, chunk_json in conn.execute(
            "SELECT key, embedded_text_hash, chunk FROM chunks "
            "WHERE embedding_model = %s",
            (embedder.model,),
        )
    }

    to_embed: list[Chunk] = []
    to_rewrite: list[Chunk] = []
    for chunk in chunks:
        previous = stored.get(chunk.key)
        if previous is None or previous[0] != text_hash(chunk):
            to_embed.append(chunk)
        elif previous[1] != chunk.model_dump(mode="json"):
            to_rewrite.append(chunk)

    with conn.cursor() as cur:
        cur.executemany(
            _UPDATE_CHUNK,
            [(Jsonb(c.model_dump(mode="json")), c.key) for c in to_rewrite],
        )
    conn.commit()

    done = 0
    for batch in batched(to_embed, batch_size):
        vectors = embedder.embed([chunk.embedding_text for chunk in batch])
        with conn.cursor() as cur:
            cur.executemany(
                _UPSERT,
                [
                    (
                        chunk.key,
                        Jsonb(chunk.model_dump(mode="json")),
                        Vector(vector),
                        embedder.model,
                        text_hash(chunk),
                    )
                    for chunk, vector in zip(batch, vectors, strict=True)
                ],
            )
        conn.commit()
        done += len(batch)
        if on_batch is not None:
            on_batch(done, len(to_embed))

    documents = sorted({chunk.document_id for chunk in chunks})
    deleted = conn.execute(
        _PRUNE, (documents, [chunk.key for chunk in chunks])
    ).rowcount
    conn.commit()

    return LoadReport(
        documents=documents,
        chunks=len(chunks),
        embedded=len(to_embed),
        rewritten=len(to_rewrite),
        unchanged=len(chunks) - len(to_embed) - len(to_rewrite),
        deleted=deleted,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="greek-law-load",
        description="Embed data/processed/ and store it in Postgres.",
    )
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    args = parser.parse_args(argv)

    settings = Settings()
    chunks = read_corpus(args.processed_dir)
    embedder = build_embedder(settings)

    def progress(done: int, total: int) -> None:
        print(f"\rembedded {done}/{total}", end="", file=sys.stderr, flush=True)

    started = time.perf_counter()
    try:
        with psycopg.connect(str(settings.database_url)) as conn:
            report = load(conn, chunks, embedder, on_batch=progress)
    except EmbeddingError as error:
        print(f"\nload stopped: {error}", file=sys.stderr)
        print("Finished batches are saved; re-run to resume.", file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started

    print(file=sys.stderr)
    print(
        f"{len(report.documents)} documents, {report.chunks} chunks: "
        f"{report.embedded} embedded, {report.rewritten} metadata rewritten, "
        f"{report.unchanged} unchanged, {report.deleted} deleted "
        f"({elapsed:.1f} s, model {embedder.model})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
