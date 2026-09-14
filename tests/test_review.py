import pytest

from experiments.baseline_no_rag.review import latest_run, render

_A_RUN = {
    "run": {
        "started_at": "2026-09-07T16:53:31+00:00",
        "finished_at": "2026-09-07T16:54:24+00:00",
        "set_version": "n5110-2024-v1",
        "retrieval": "none",
        "model_requested": "ilsp/llama-krikri-8b-instruct",
        "base_url": "http://localhost:11435",
        "timeout_seconds": 180.0,
    },
    "answers": [
        {
            "id": "q01",
            "question": "Με ποιον νόμο συστάθηκε το ΕΛΚΑΚ;",
            "probes": "The anchor question.",
            "answer": "Συστάθηκε με τον ν. 4914/2022.\n\nΝομική μορφή: Ν.Π.Ι.Δ.",
            "model": "ilsp/llama-krikri-8b-instruct",
            "prompt_version": "v1",
            "tokens_in": 264,
            "tokens_out": 186,
            "duration_seconds": 10.51,
            "finish_reason": "stop",
        }
    ],
}

_THE_QUESTIONS = {
    "set_version": "n5110-2024-v1",
    "source": {
        "law": "ν. 5110/2024",
        "fek": "Α' 75/24.05.2024",
        "corpus_document_id": "fek_a_75_2024",
    },
    "questions": [
        {
            "id": "q01",
            "text": "Με ποιον νόμο συστάθηκε το ΕΛΚΑΚ;",
            "probes": "The anchor question.",
            "expected": "Άρθρο 3 ν. 5110/2024: ανώνυμη εταιρεία «ΕΛΚΑΚ ΑΕ».",
        }
    ],
}

_AN_ANNOTATION = {
    "annotations": {
        "q01": {
            "verdict": "fabricated",
            "cited": ["ν. 4914/2022 άρθρο 44"],
            "flags": ["denies_law_exists"],
            "note": "Resolves to a real law about something else.",
        }
    }
}


def test_the_model_answer_survives_into_the_sheet_verbatim() -> None:
    """Every line the model produced appears in the review sheet unaltered.

    The sheet is what the baseline is read from, in V3, next to a RAG run. If
    the renderer truncated a long answer, collapsed its blank lines, or dropped
    the tail after the disclaimer, the reader would be annotating an edited
    quotation while believing it was the transcript — and the results file that
    could prove otherwise is never opened once a readable sheet exists.
    """
    sheet = render(_A_RUN, _THE_QUESTIONS, _AN_ANNOTATION, "a-run")

    assert "> Συστάθηκε με τον ν. 4914/2022." in sheet
    assert "> Νομική μορφή: Ν.Π.Ι.Δ." in sheet


def test_the_expected_provision_is_shown_beside_the_answer() -> None:
    """The ΦΕΚ text from questions.json is rendered with each answer.

    The whole reason the sheet exists is to remove the 60-page re-read from
    annotation. Joining on the wrong key, or silently dropping 'expected' for a
    question whose id is missing from the set, would produce a sheet that looks
    complete and quietly asks the reader to score from memory.
    """
    sheet = render(_A_RUN, _THE_QUESTIONS, _AN_ANNOTATION, "a-run")

    assert "Άρθρο 3 ν. 5110/2024: ανώνυμη εταιρεία «ΕΛΚΑΚ ΑΕ»." in sheet


def test_an_unannotated_question_is_rendered_as_unscored_not_skipped() -> None:
    """A question with no annotation still gets a section, marked unscored.

    Skipping it would shrink a ten-question run to the subset already judged,
    and the summary would then agree with itself — nine of nine scored — while
    a question silently went missing. Annotation happens over several sittings,
    so a half-annotated run is the normal case, not the edge case.
    """
    sheet = render(_A_RUN, _THE_QUESTIONS, {}, "a-run")

    assert "q01 — — not scored" in sheet
    assert "Συστάθηκε με τον ν. 4914/2022" in sheet


def test_an_unknown_verdict_is_refused_rather_than_rendered_blank() -> None:
    """A verdict outside the vocabulary raises instead of passing through.

    Annotations are hand-typed JSON with no schema behind them. 'fabricted' or
    'hallucinated' would otherwise render as an empty cell, and the summary
    tally would undercount the failure the whole run was built to measure — the
    one number a reader of this project will quote.
    """
    typo = {"annotations": {"q01": {"verdict": "hallucinated"}}}

    with pytest.raises(ValueError, match="unknown verdict"):
        render(_A_RUN, _THE_QUESTIONS, typo, "a-run")


def test_an_unknown_flag_is_refused_too() -> None:
    """A flag outside the vocabulary raises instead of being counted silently.

    Flags exist to be aggregated across runs — 'denies_law_exists' appearing
    four times is a finding. A near-miss spelling would split one count into
    two and make a trend across V1 and V3 look like two unrelated rarities.
    """
    typo = {"annotations": {"q01": {"verdict": "fabricated", "flags": ["role-dodge"]}}}

    with pytest.raises(ValueError, match="unknown flag"):
        render(_A_RUN, _THE_QUESTIONS, typo, "a-run")


def test_a_failed_question_renders_its_error_instead_of_crashing() -> None:
    """A record with 'error' and no 'answer' still produces a section.

    run.py deliberately records LLM failures as results, so a run containing
    one is expected, not exceptional. A KeyError here would make the sheet
    un-renderable for exactly the runs that most need reading — and would push
    the reader back to the raw JSON to find out what broke.
    """
    failed = {
        "run": _A_RUN["run"],
        "answers": [
            {
                "id": "q01",
                "question": "Με ποιον νόμο συστάθηκε το ΕΛΚΑΚ;",
                "probes": "The anchor question.",
                "error": "LLMTimeoutError: no response",
            }
        ],
    }

    sheet = render(failed, _THE_QUESTIONS, {}, "a-run")

    assert "LLMTimeoutError: no response" in sheet


def test_the_latest_run_is_the_newest_timestamp_not_the_first_listed(tmp_path) -> None:
    """latest_run picks the most recent file, whatever order the FS returns.

    Path.glob yields in directory order, which on some filesystems is creation
    order and on others is arbitrary. Taking the first would silently re-render
    an old run over the new one's sheet, and the two are indistinguishable at a
    glance because both are full, plausible ten-question reviews.
    """
    for stem in [
        "2026-09-07T16-53-31Z",
        "2026-09-05T09-00-00Z",
        "2026-09-06T12-00-00Z",
    ]:
        (tmp_path / f"{stem}.json").write_text("{}", encoding="utf-8")

    assert latest_run(tmp_path).stem == "2026-09-07T16-53-31Z"
