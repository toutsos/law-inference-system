"""V3 step 6's inspection runner: the question set, the sheet, the record.

Fast tests only. Rendering is a pure function of the hits, so the tests build
``RetrievedChunk``s by hand; no Postgres, no Ollama. Whether bge-m3 returns the
*right* chunks is what a human reads on the sheet — not a unit test.
"""

import re
from typing import Any

from experiments.retrieval_inspection.run import (
    FULL_TEXT_TOP,
    QUESTIONS_FILE,
    load_questions,
    render,
    to_record,
)
from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion.chunking import Chunk
from greek_law.retrieval import RetrievedChunk

_PD = ActIdentity(act_type="π.δ.", number="62", year=2025)

_ENTRY: dict[str, Any] = {
    "id": "p04",
    "text": "Τι πρέπει να κάνω αν χτυπήσω την ώρα της δουλειάς;",
    "expected": ["π.δ. 62/2025, άρθρο 554"],
    "note": "No shared keyword with the law.",
}

_RUN: dict[str, Any] = {
    "started_at": "2026-11-23T10:00:00+00:00",
    "set_version": "retrieval-inspection-v1",
    "embedding_model": "bge-m3",
    "k": 10,
}


def _hits(n: int) -> list[RetrievedChunk]:
    """``n`` hits, nearest first: article 501 at 0.101, 502 at 0.102, …"""
    return [
        RetrievedChunk(
            chunk=Chunk(
                document_id="fek_a_121_2025",
                source=SourceReference(act=_PD, article=str(500 + rank)),
                article_title=f"Τίτλος {500 + rank}",
                text=f"Κείμενο του άρθρου {500 + rank}.",
            ),
            distance=0.1 + rank / 1000,
        )
        for rank in range(1, n + 1)
    ]


def _table_rows(sheet: str) -> list[str]:
    """The hit rows of the sheet's tables: lines like ``| 3 | 0.1030 | …``."""
    return [line for line in sheet.splitlines() if re.match(r"\| \d+ \|", line)]


def test_question_set_loads_and_ids_are_unique() -> None:
    """The committed set parses and no two questions share an id.

    The id is how a sheet row is matched to its question in the JSON record
    and, in V5, to the same question in a later run. A duplicated id — easy
    when q01–q10 were copied from V1's file by hand — would make two different
    questions indistinguishable in exactly that comparison.
    """
    book = load_questions(QUESTIONS_FILE)
    ids = [entry["id"] for entry in book["questions"]]

    assert book["set_version"] == "retrieval-inspection-v1"
    assert len(ids) == len(set(ids)) == 16


def test_every_question_has_the_fields_the_run_reads() -> None:
    """Each entry has ``id``, ``text`` and an ``expected`` list of strings.

    The run embeds questions one by one; a missing field would raise a
    ``KeyError`` halfway through, after several questions had already been
    embedded, and no sheet would be written. An ``expected`` given as one
    string instead of a list would render character by character.
    """
    for entry in load_questions(QUESTIONS_FILE)["questions"]:
        assert isinstance(entry["id"], str) and entry["id"], entry
        assert isinstance(entry["text"], str) and entry["text"], entry
        assert isinstance(entry["expected"], list), entry
        assert all(isinstance(item, str) for item in entry["expected"]), entry


def test_only_the_out_of_corpus_questions_expect_nothing() -> None:
    """x1 and x2 have an empty ``expected``; every other question names one.

    An empty ``expected`` tells the reader "every hit here is wrong". On an
    answerable question that would make a correct rank-1 hit look like a
    failure; on x1/x2 a filled one would hide the very thing those questions
    exist to show — that the search returns something no matter what.
    """
    for entry in load_questions(QUESTIONS_FILE)["questions"]:
        if entry["id"].startswith("x"):
            assert entry["expected"] == [], entry["id"]
        else:
            assert entry["expected"], entry["id"]


def test_sheet_lists_every_hit_in_rank_order() -> None:
    """All k hits appear in the table, nearest first, with their distance.

    Ranks 6–10 are on the sheet only to show *where* a provision landed when
    it missed the top 5 — the evidence for or against changing k. If the
    table were cut at 5, or reordered, that evidence would silently vanish.
    """
    sheet = render(_RUN, [(_ENTRY, _hits(10))])
    rows = _table_rows(sheet)

    assert len(rows) == 10
    for rank, row in enumerate(rows, start=1):
        assert row.startswith(f"| {rank} | {0.1 + rank / 1000:.4f} |"), row
        assert f"άρθρο {500 + rank}" in row, row


def test_only_the_top_hits_carry_full_text() -> None:
    """The first ``FULL_TEXT_TOP`` hits get their text; the rest only a row.

    The top 5 are what step 7 will hand the LLM, so they are what has to be
    read word by word. If every hit carried its text, 16 questions × 10 hits
    would bury those 80 that matter under 80 that do not.
    """
    sheet = render(_RUN, [(_ENTRY, _hits(10))])

    for rank in range(1, FULL_TEXT_TOP + 1):
        assert f"Κείμενο του άρθρου {500 + rank}." in sheet
    for rank in range(FULL_TEXT_TOP + 1, 11):
        assert f"Κείμενο του άρθρου {500 + rank}." not in sheet


def test_the_record_keeps_rank_key_and_distance() -> None:
    """The JSON record stores, per hit, its rank, chunk key, citation, distance.

    The JSON is the "before" V5's hybrid search will be compared against. The
    key is what a later run can be joined on (citations are prose and may be
    re-worded); without the distance, a comparison could say *that* a hit
    moved but not by how much.
    """
    record = to_record(_ENTRY, _hits(2))

    assert record["id"] == "p04"
    assert record["question"] == _ENTRY["text"]
    assert record["expected"] == _ENTRY["expected"]
    assert record["hits"][0] == {
        "rank": 1,
        "key": "π.δ.62/2025/άρθρο-501",
        "citation": "π.δ. 62/2025, άρθρο 501",
        "distance": 0.101,
    }
    assert record["hits"][1]["rank"] == 2
