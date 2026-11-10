"""Step 8: the pipeline's output on disk, and the command that writes it.

The fast tests write hand-built chunks into ``tmp_path`` — pytest's per-test
temporary directory, the counterpart of JUnit 5's ``@TempDir`` — so they need
no PDF. The slow tests run ``poe ingest`` over the real corpus into a temporary
directory, never into ``data/processed/`` itself, and pin the report numbers
every earlier step recorded.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from greek_law.domain import ActIdentity, SourceReference, StructuralUnit
from greek_law.ingestion.chunking import Chunk
from greek_law.ingestion.ingest import main
from greek_law.ingestion.processed import (
    Ingested,
    IngestReport,
    chunks_path,
    read_chunks,
    remove_processed,
    report_path,
    write_processed,
)
from greek_law.ingestion.structure import LineCoverage

DECREE = ActIdentity(act_type="π.δ.", number="62", year=2025, fek="Α' 121/11.07.2025")


def _chunk(article: str, paragraph: str | None, text: str) -> Chunk:
    return Chunk(
        document_id="fek_a_121_2025",
        source=SourceReference(act=DECREE, article=article, paragraph=paragraph),
        article_title="Σύμβαση εργασίας",
        path=[StructuralUnit(kind="ΒΙΒΛΙΟ", number="ΠΡΩΤΟ", title="ΑΤΟΜΙΚΟ")],
        text=text,
    )


CHUNKS = [
    _chunk("1", None, "Με τη σύμβαση εργασίας ο εργαζόμενος έχει υποχρέωση"),
    _chunk("2", "1", "Η δοκιμαστική περίοδος\nδεν μπορεί να υπερβαίνει"),
]


def _report(**overrides: object) -> IngestReport:
    fields: dict[str, object] = {
        "document_id": "fek_a_121_2025",
        "chunks": len(CHUNKS),
        "oversized": [],
        "untranslated": [],
        "numbering_breaks": [],
        "rejected_heading_candidates": 0,
        "unreadable_heading_lines": 0,
        "unreadable_container_lines": 0,
        "refused_paragraph_markers": 0,
        "quoted_paragraph_markers": 0,
        "residual_line_hyphens": 0,
        "residual_confusables": 0,
        "line_coverage": LineCoverage(
            total=4, in_articles=4, front_matter=0, between_articles=0, trailing=0
        ),
    }
    fields.update(overrides)
    return IngestReport.model_validate(fields)


def _ingested(chunks: list[Chunk] = CHUNKS) -> Ingested:
    return Ingested(chunks=chunks, report=_report(chunks=len(chunks)))


def test_chunks_read_back_equal_to_what_was_written(tmp_path: Path) -> None:
    """Write, then read: the same chunks, field for field.

    V3 never sees a ``Chunk`` built by the pipeline — only one read from this
    file. A field lost or mangled on the way through JSON would reach the
    vector store with nothing to say it changed.
    """
    write_processed(tmp_path, _ingested())

    assert read_chunks(chunks_path(tmp_path, "fek_a_121_2025")) == CHUNKS


def test_the_chunk_file_is_one_line_per_chunk_named_by_manifest_id(
    tmp_path: Path,
) -> None:
    """``fek_a_121_2025.jsonl`` holds exactly two lines for two chunks.

    The line *is* the record in JSON Lines. A paragraph's own line breaks must
    stay escaped inside its JSON string; written raw, the second chunk here
    would become two broken lines and the file unreadable from that point.
    """
    write_processed(tmp_path, _ingested())

    content = (tmp_path / "fek_a_121_2025.jsonl").read_text(encoding="utf-8")

    assert content.count("\n") == 2
    assert content.endswith("\n")


def test_greek_is_written_as_utf8_not_unicode_escapes(tmp_path: Path) -> None:
    """The file contains «σύμβαση», not ``\\u03c3\\u03cd…``.

    The file is meant to be read by a person and diffed. Escaped Greek makes
    π.δ. 62/2025's file 2.3× larger and every diff unreadable, and it is the
    default of ``json.dumps`` — one switch of serialiser away.
    """
    write_processed(tmp_path, _ingested())

    content = chunks_path(tmp_path, "fek_a_121_2025").read_text(encoding="utf-8")

    assert "σύμβαση εργασίας" in content
    assert "\\u03" not in content


def test_derived_fields_are_not_stored(tmp_path: Path) -> None:
    """No ``key``, ``header`` or ``embedding_text`` in the file.

    They are computed from the stored fields on load. Stored, they could
    disagree with the reference they were derived from — a header naming one
    article above the text of another — and nothing would notice.
    """
    write_processed(tmp_path, _ingested())

    first = json.loads(
        chunks_path(tmp_path, "fek_a_121_2025")
        .read_text(encoding="utf-8")
        .split("\n")[0]
    )

    assert set(first) == {"document_id", "source", "article_title", "path", "text"}


def test_a_unicode_line_separator_inside_text_survives_the_round_trip(
    tmp_path: Path,
) -> None:
    """A chunk whose text holds U+2028 is still one chunk after reading.

    JSON does not escape U+2028 LINE SEPARATOR, and ``str.splitlines()``
    breaks on it. A reader using ``splitlines()`` would cut this chunk in two
    and fail to validate either half — and PDF text is exactly where stray
    Unicode separators turn up.
    """
    chunk = _chunk("3", "1", "πρώτη γραμμή δεύτερη γραμμή")
    write_processed(tmp_path, _ingested([chunk]))

    assert read_chunks(chunks_path(tmp_path, "fek_a_121_2025")) == [chunk]


def test_writing_twice_gives_identical_bytes(tmp_path: Path) -> None:
    """Same input, same bytes — for the chunk file and the report.

    Step 9's golden files compare bytes, and V3's load relies on a re-run
    changing nothing. A timestamp or a set iterated in hash order would make
    every run "different" and every golden comparison fail for no reason.
    """
    write_processed(tmp_path / "a", _ingested())
    write_processed(tmp_path / "b", _ingested())

    for name in ("fek_a_121_2025.jsonl", "fek_a_121_2025.report.json"):
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name
        ).read_bytes()


def test_line_endings_are_newline_only(tmp_path: Path) -> None:
    """The files never contain ``\\r\\n``.

    Without an explicit ``newline``, Python on Windows writes ``\\r\\n``, and
    the same corpus would produce different bytes on different machines —
    a golden-file failure that is about the operating system, not the law.
    """
    write_processed(tmp_path, _ingested())

    assert b"\r" not in chunks_path(tmp_path, "fek_a_121_2025").read_bytes()
    assert b"\r" not in report_path(tmp_path, "fek_a_121_2025").read_bytes()


def test_the_report_is_written_beside_the_chunks_and_reads_back(
    tmp_path: Path,
) -> None:
    """``fek_a_121_2025.report.json`` validates back into the same report.

    The report is the step 8 decision's whole point: what the pipeline could
    not handle, kept where a diff will show it changing. A report that could
    not be read back would be a log nobody can compare.
    """
    report = _report(oversized=["π.δ.62/2025/άρθρο-503/παρ-1"])
    write_processed(tmp_path, Ingested(chunks=CHUNKS, report=report))

    written = report_path(tmp_path, "fek_a_121_2025").read_text(encoding="utf-8")

    assert IngestReport.model_validate_json(written) == report


def test_removing_processed_files_leaves_other_files_alone(tmp_path: Path) -> None:
    """A rebuild clears chunk and report files, and only those.

    A document dropped from the manifest must not leave its chunks behind for
    V3 to load. But the directory is the user's too: a note or a QA export
    left there must survive ``poe ingest``.
    """
    (tmp_path / "old_document.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "old_document.report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "qa-notes.md").write_text("σημειώσεις", encoding="utf-8")

    remove_processed(tmp_path)

    assert [path.name for path in tmp_path.iterdir()] == ["qa-notes.md"]


def test_ingest_writes_nothing_when_the_corpus_does_not_match_its_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing PDF means exit code 1 and an empty output directory.

    Every chunk's ``document_id`` vouches for the manifest's SHA-256. Writing
    chunks from bytes that are absent or different would make that claim false
    for every chunk in the file.
    """
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "documents": [
                    {
                        "id": "fek_a_121_2025",
                        "act": DECREE.model_dump(),
                        "title": "Κώδικας Εργατικού Δικαίου.",
                        "file": "data/raw/missing.pdf",
                        "sha256": "0" * 64,
                        "size_bytes": 1,
                        "source_url": "https://example.org/fek.pdf",
                        "retrieved_on": date(2026, 9, 14).isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "processed"

    exit_code = main(
        ["--manifest", str(manifest_path), "--root", str(tmp_path), "--out", str(out)]
    )

    assert exit_code == 1
    assert "Nothing written" in capsys.readouterr().out
    assert not out.exists()


@pytest.mark.slow
def test_ingest_rebuilds_the_corpus_with_the_reports_every_step_measured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``poe ingest`` over the real corpus: two documents, every count pinned.

    One test for the whole pipeline's output. Each number was measured and
    recorded by an earlier step — 259 + 1 877 chunks, 18 + 7 oversized, 2 + 23
    refused markers, 172 quoted, 33 + 60 hyphens, 9 rejected and 4 unreadable
    headings — so any change anywhere upstream shows up here as a named field.
    """
    exit_code = main(["--out", str(tmp_path)])

    assert exit_code == 0
    assert "2 documents written" in capsys.readouterr().out
    reports = {
        path.name: IngestReport.model_validate_json(path.read_text(encoding="utf-8"))
        for path in tmp_path.glob("*.report.json")
    }
    law = reports["fek_a_75_2024.report.json"]
    decree = reports["fek_a_121_2025.report.json"]

    assert (law.chunks, decree.chunks) == (259, 1877)
    assert (len(law.oversized), len(decree.oversized)) == (18, 7)
    assert (law.refused_paragraph_markers, decree.refused_paragraph_markers) == (2, 23)
    assert (law.quoted_paragraph_markers, decree.quoted_paragraph_markers) == (172, 0)
    assert (law.residual_line_hyphens, decree.residual_line_hyphens) == (33, 60)
    assert (law.rejected_heading_candidates, decree.rejected_heading_candidates) == (
        0,
        9,
    )
    assert (law.unreadable_heading_lines, decree.unreadable_heading_lines) == (0, 4)
    for report in (law, decree):
        assert report.untranslated == []
        assert report.numbering_breaks == []
        assert report.unreadable_container_lines == 0
        assert report.line_coverage.balances
    assert len(read_chunks(tmp_path / "fek_a_121_2025.jsonl")) == 1877


@pytest.mark.slow
def test_ingesting_the_corpus_twice_gives_byte_identical_output(
    tmp_path: Path,
) -> None:
    """Two full runs, four files, the same bytes.

    The Definition of Done says *deterministically*. The fast test proves the
    writer adds nothing variable; this proves the whole pipeline — pypdf
    included — does not either, on the documents it will actually run on.
    """
    main(["--out", str(tmp_path / "a")])
    main(["--out", str(tmp_path / "b")])

    names = sorted(path.name for path in (tmp_path / "a").iterdir())
    assert len(names) == 4
    for name in names:
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name
        ).read_bytes()
