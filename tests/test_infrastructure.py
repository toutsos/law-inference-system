"""Static checks on compose.yaml — no Docker daemon needed.

These read the compose file as text. A YAML parser would be more robust, but
it would be a new dependency bought for three regexes; if the file grows past
what a regex can read honestly, that is the moment to add one.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from greek_law.config import Settings

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "compose.yaml"


def _compose_text() -> str:
    return COMPOSE_FILE.read_text(encoding="utf-8")


def _environment_value(key: str) -> str:
    match = re.search(rf"^\s*{key}:\s*(\S+)\s*$", _compose_text(), re.MULTILINE)
    assert match, f"{key} not found in {COMPOSE_FILE.name}"
    return match.group(1)


def test_the_database_image_is_pinned_to_an_exact_version() -> None:
    """The pgvector image names an exact pgvector release and Postgres major.

    `pgvector/pgvector:latest` or `:pg18` moves whenever upstream publishes, so
    two `poe up` runs a month apart can start different databases, and a
    retrieval result measured in V4 stops being reproducible with nothing in
    the repository having changed. This is the infrastructure twin of
    committing `uv.lock`.
    """
    match = re.search(r"^\s*image:\s*(\S+)\s*$", _compose_text(), re.MULTILINE)

    assert match, "no image: line in compose.yaml"
    assert re.fullmatch(r"pgvector/pgvector:\d+\.\d+\.\d+-pg\d+", match.group(1)), (
        f"image is not pinned to <pgvector version>-pg<major>: {match.group(1)}"
    )


def test_the_database_port_is_published_on_localhost_only() -> None:
    """Postgres is reachable from this machine, not from the network.

    A bare `5432:5432` publishes on every interface, and Docker writes its own
    firewall rules, so on shared Wi-Fi the database — with a password that is
    committed to this repository — is reachable by anyone on the network.
    Binding to 127.0.0.1 makes the committed password harmless.
    """
    ports = re.findall(r"^\s*-\s*\"?([\d.:]+)\"?\s*$", _compose_text(), re.MULTILINE)
    published = [p for p in ports if p.endswith(":5432")]

    assert published, "no port mapping to 5432 in compose.yaml"
    assert all(p.startswith("127.0.0.1:") for p in published), published


def test_the_default_database_url_matches_compose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings' default DATABASE_URL points at the database compose starts.

    The two files state the same facts — user, password, database name, port —
    and nothing else ties them together. Change one, forget the other, and
    `poe up` reports a healthy database while every connection fails with an
    authentication or "database does not exist" error that names neither file.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)

    url = urlsplit(str(Settings(_env_file=None).database_url))
    host_port = re.search(r"127\.0\.0\.1:(\d+):5432", _compose_text())

    assert host_port, "no localhost port mapping to 5432 in compose.yaml"
    assert url.hostname == "localhost"
    assert url.port == int(host_port.group(1))
    assert url.username == _environment_value("POSTGRES_USER")
    assert url.password == _environment_value("POSTGRES_PASSWORD")
    assert url.path.lstrip("/") == _environment_value("POSTGRES_DB")
