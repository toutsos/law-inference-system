from typing import Any

import pytest

from experiments.baseline_no_rag.compare import render

_QUESTIONS: dict[str, Any] = {
    "set_version": "n5110-2024-v1",
    "questions": [
        {"id": "q01", "text": "Ερώτηση ένα;", "expected": "Άρθρο 3."},
        {"id": "q02", "text": "Ερώτηση δύο;", "expected": "Άρθρο 5."},
    ],
}


def _run(retrieval: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run": {
            "set_version": "n5110-2024-v1",
            "retrieval": retrieval,
            "started_at": "2026-11-24T18:04:04+00:00",
        },
        "answers": answers,
    }


_V1 = (
    _run(
        "none",
        [
            {"id": "q01", "answer": "Ο ν. 4914/2022."},
            {"id": "q02", "answer": "Δεν γνωρίζω."},
        ],
    ),
    {
        "annotations": {
            "q01": {"verdict": "fabricated"},
            "q02": {"verdict": "refused"},
        }
    },
)

_RAG = (
    _run(
        "pgvector bge-m3 k=5",
        [
            {
                "id": "q01",
                "answer": "Ο ν. 5110/2024 (άρθρο 3).",
                "sources": ["ν. 5110/2024, άρθρο 3 παρ. 1"],
            },
            {
                "id": "q02",
                "answer": "1.500.000 ευρώ.",
                "sources": ["ν. 5110/2024, άρθρο 5 παρ. 1"],
            },
        ],
    ),
    {
        "annotations": {
            "q01": {"verdict": "correct", "note": "Άρθρο 3 στη θέση 1."},
            "q02": {"verdict": "partially_correct", "flags": ["unsupported_detail"]},
        }
    },
)


def test_each_question_gets_one_summary_row_with_both_verdicts() -> None:
    """The summary table pairs V1's and RAG's verdict for the same id.

    The row is the whole point of step 9. Catches the join going wrong — the
    RAG verdict of q02 printed beside V1's q01 — which would turn the
    payoff measurement into a plausible-looking table of the wrong pairs.
    """
    sheet = render(_V1, _RAG, _QUESTIONS, "a-vs-b")

    assert "| q01 | ❌ fabricated citation | ✅ correct |" in sheet
    assert "| q02 | ⚠️ refused | 🟡 partially correct |" in sheet


def test_both_runs_are_tallied_separately() -> None:
    """One count line per run, over the same ids.

    These two lines are what the V3 note will quote. Catches both lines being
    tallied from the same run — the comparison would claim no change at all.
    """
    sheet = render(_V1, _RAG, _QUESTIONS, "a-vs-b")

    assert "**V1:** ❌ fabricated citation 1 · ⚠️ refused 1" in sheet
    assert "**RAG:** ✅ correct 1 · 🟡 partially correct 1" in sheet


def test_the_rag_answer_shows_its_sources_flags_and_note() -> None:
    """Under each question the RAG section carries sources, flags and note.

    Step 10 reads this sheet to sort failures; sources are how it tells a
    retrieval failure from a generation one. Catches any of the three being
    dropped on the way from the files to the sheet.
    """
    sheet = render(_V1, _RAG, _QUESTIONS, "a-vs-b")

    assert "**Sources.** `ν. 5110/2024, άρθρο 3 παρ. 1`" in sheet
    assert "**Flags.** `unsupported_detail`" in sheet
    assert "**Note.** Άρθρο 3 στη θέση 1." in sheet


def test_a_question_missing_from_one_run_is_marked_not_skipped() -> None:
    """A RAG run made with --only still renders; the gap is labelled.

    Catches a KeyError on the first id the partial run lacks — and the
    opposite failure, silently omitting the question, which would make a
    partial run's tally look like a whole set's.
    """
    partial = (_run("pgvector bge-m3 k=5", [_RAG[0]["answers"][0]]), _RAG[1])

    sheet = render(_V1, partial, _QUESTIONS, "a-vs-b")

    assert "### RAG — not asked in this run" in sheet


def test_runs_of_a_different_question_set_are_refused() -> None:
    """A run whose set_version differs from questions.json raises.

    The join is by id, and ids are only meaningful within one set. Catches a
    future set's q03 being compared with V1's q03 — different questions,
    same id, a comparison that looks valid and means nothing.
    """
    other = (
        {**_RAG[0], "run": {**_RAG[0]["run"], "set_version": "other-v2"}},
        _RAG[1],
    )

    with pytest.raises(ValueError, match="other-v2"):
        render(_V1, other, _QUESTIONS, "a-vs-b")


def test_an_unknown_verdict_is_refused() -> None:
    """A verdict outside the vocabulary raises, as it does in review.py.

    compare.py reads the annotations itself rather than through review.py's
    render, so it needs its own check. Catches a typo rendering as a KeyError
    traceback or, if looked up with .get, as a blank cell that the tally skips.
    """
    typo = (_RAG[0], {"annotations": {"q01": {"verdict": "corect"}}})

    with pytest.raises(ValueError, match="unknown verdict"):
        render(_V1, typo, _QUESTIONS, "a-vs-b")
