"""Suite-wide pytest configuration: the ``--update-golden`` switch.

``conftest.py`` is pytest's hook file — loaded automatically for every test
under this directory, no import needed. Its nearest Java relative is a JUnit 5
extension registered for the whole suite.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from greek_law.config import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden files from the current output instead of comparing.",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Whether this run accepts the current output as the new golden files.

    Off by default, and deliberately a command-line flag rather than an
    environment variable: accepting a change to what the pipeline produces
    should be something typed on purpose, once, and visible in the shell
    history — never a setting left on.
    """
    return bool(request.config.getoption("--update-golden"))


@pytest.fixture
def isolated_conn() -> Iterator[psycopg.Connection[Any]]:
    """A connection whose ``search_path`` is a fresh, throwaway Postgres schema.

    For tests of code that commits (``load``), where a rolled-back transaction
    cannot isolate anything. Every table created through this connection lands
    in a schema named ``test_…`` that is dropped afterwards, so the dev
    database's own ``chunks`` table is never read or written. ``public`` stays
    on the path only so the ``vector`` type resolves.
    """
    schema = sql.Identifier(f"test_{uuid4().hex[:12]}")
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
