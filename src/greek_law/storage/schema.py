"""Create V3's Postgres schema: the pgvector extension and one ``chunks`` table.

The SQL lives in ``schema.sql`` beside this module, so it can be read, and run
by hand through ``poe psql``, as SQL. Every statement is ``IF NOT EXISTS``:
applying it to a database that already has the table changes nothing, which is
why the load pipeline can apply it on every run instead of relying on someone
having remembered to. See the step 2 decisions in the V3 note.
"""

import sys
from importlib import resources
from typing import Any

import psycopg

from greek_law.config import Settings

EMBEDDING_DIMENSIONS = 1024
"""bge-m3's vector length — must equal the ``vector(n)`` in ``schema.sql``.

Postgres enforces the column; this constant is for Python, so step 4 can
reject a wrong-sized vector with a message naming the model rather than a
pgvector error halfway through a load. A test inserts a vector of exactly this
length, so the two cannot disagree unnoticed.
"""

SCHEMA_SQL = (
    resources.files("greek_law.storage")
    .joinpath("schema.sql")
    .read_text(encoding="utf-8")
)


def apply_schema(conn: psycopg.Connection[Any]) -> None:
    """Create whatever of the schema is missing; leave existing objects alone.

    Runs inside the caller's transaction and does not commit: the caller
    decides, as with any other statement on ``conn``.
    """
    conn.execute(SCHEMA_SQL)


def main() -> int:
    settings = Settings()
    with psycopg.connect(str(settings.database_url)) as conn:
        apply_schema(conn)
    print("Schema applied: extension vector, table chunks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
