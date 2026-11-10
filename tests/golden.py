"""Helpers for golden-file tests: read a page fixture, compare or accept output.

A plain module like ``fakes.py``, imported by the tests that need it. The
comparison is on bytes, because the pipeline promises byte-identical output;
the diff shown on failure is on text, because that is what a human reads.
"""

import difflib
import re
import shutil
from itertools import islice
from pathlib import Path

import pytest

from greek_law.ingestion.extraction import ExtractedDocument, ExtractedPage

_PAGE_MARKER = re.compile(r"^=== page (\d+) ===\n", re.MULTILINE)
"""The line that opens each page of a fixture, naming its real PDF page."""

_DIFF_LINES = 60
"""How much of a diff a failure prints — enough to see the change, no more."""


def read_pages(path: Path, document_id: str) -> ExtractedDocument:
    """Load a page fixture as the raw, un-normalized output of extraction.

    The file is the pages' text, each opened by ``=== page N ===``. A marker
    line rather than a form feed so the fixture reads in any editor; it cannot
    collide with gazette text, which never contains a line of ``=`` signs.
    """
    parts = _PAGE_MARKER.split(path.read_text(encoding="utf-8"))
    return ExtractedDocument(
        document_id=document_id,
        pages=[
            ExtractedPage(number=int(number), text=body.removesuffix("\n"))
            for number, body in zip(parts[1::2], parts[2::2], strict=True)
        ],
    )


def assert_matches_golden(actual: Path, expected: Path, *, update: bool) -> None:
    """Fail unless ``actual`` is byte-identical to the golden file ``expected``.

    With ``update`` the golden file is overwritten instead and the check
    passes — the one way to accept a change on purpose. A missing golden file
    fails rather than being created, so a golden that was never reviewed
    cannot appear silently and then vouch for whatever produced it.
    """
    if update:
        expected.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(actual, expected)
        return
    if not expected.exists():
        pytest.fail(
            f"no golden file at {expected}; review the output, then re-run "
            "this test with --update-golden to accept it (add "
            '-m "slow or not slow" if it is a slow test)'
        )
    if actual.read_bytes() == expected.read_bytes():
        return

    diff = difflib.unified_diff(
        expected.read_text(encoding="utf-8").split("\n"),
        actual.read_text(encoding="utf-8").split("\n"),
        fromfile=f"golden/{expected.name}",
        tofile=f"output/{actual.name}",
        lineterm="",
    )
    pytest.fail(
        f"{actual.name} differs from its golden file. If the change is "
        "intended, re-run with --update-golden.\n"
        + "\n".join(islice(diff, _DIFF_LINES))
    )
