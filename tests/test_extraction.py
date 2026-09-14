from pathlib import Path

import pytest

from greek_law.ingestion import DEFAULT_MANIFEST_PATH, load_manifest
from greek_law.ingestion.extraction import (
    ExtractedDocument,
    ExtractedPage,
    extract_document,
    median_line_length,
    pages_with_suspicious_line_width,
)

_COLUMN_WIDTH = 51


def _page(number: int, width: int, lines: int = 20) -> ExtractedPage:
    """A page of `lines` prose lines, each `width` characters of Greek."""
    return ExtractedPage(
        number=number, text="\n".join("α" * width for _ in range(lines))
    )


def _document(*widths: int) -> ExtractedDocument:
    return ExtractedDocument(
        document_id="synthetic",
        pages=[_page(number, width) for number, width in enumerate(widths, start=1)],
    )


def test_median_line_length_ignores_headings_and_page_furniture() -> None:
    """Short lines are excluded from a page's median line length.

    A ΦΕΚ page is mostly prose interrupted by «Άρθρο 87», a gazette page number
    and a running header — all far shorter than a column. Counting them would
    drag every page's median below the real column width, and the splice
    detector calibrated on that median would then never fire.
    """
    text = "\n".join(["Άρθρο 87", "3188", "α" * 50, "α" * 52])

    assert median_line_length(text) == 51.0


def test_a_page_with_no_prose_has_a_median_of_zero() -> None:
    """A page of only short lines reports 0.0 rather than raising.

    Blank pages and pure-heading pages exist in every ΦΕΚ. `statistics.median`
    raises on an empty sequence, so without the guard one blank page would
    abort extraction of a 260-page document.
    """
    assert median_line_length("Άρθρο 87\n\n3188\n") == 0.0


def test_a_page_of_spliced_columns_is_flagged() -> None:
    """One page whose lines are ~twice the document's width is reported.

    This is the failure the whole check exists for: pdfplumber joined line 1 of
    the left column to line 1 of the right column, producing fluent Greek that
    says something nobody wrote. Nothing raises when it happens — the doubled
    line width is the only visible trace.
    """
    document = _document(*([_COLUMN_WIDTH] * 9), _COLUMN_WIDTH * 2)

    assert pages_with_suspicious_line_width(document) == [10]


def test_an_ordinary_two_column_document_flags_nothing() -> None:
    """Normal variation between pages does not trip the check.

    Page widths genuinely wobble (48–52 was measured across the corpus). A
    check that fired on ordinary variation would be muted within a day, which
    is the usual way a warning stops working.
    """
    document = _document(48, 51, 52, 50, 51, 49, 52, 51)

    assert pages_with_suspicious_line_width(document) == []


def test_a_single_column_act_flags_nothing_despite_wide_lines() -> None:
    """Width is judged against this document, not against a ΦΕΚ column.

    Not every act is typeset in two columns. Calibrating on the constant 51
    would report every page of a single-column document as spliced — noise
    that would bury the one real finding in a 260-page run.
    """
    document = _document(*([95] * 8))

    assert pages_with_suspicious_line_width(document) == []


def test_a_document_spliced_on_every_page_is_not_flagged() -> None:
    """The known blind spot, pinned so it is a decision rather than a surprise.

    Self-calibration cannot see a failure that moved the baseline: if every
    page is spliced, every page looks normal relative to the others. This test
    exists so that anyone who later reads `pages_with_suspicious_line_width`
    and assumes it guarantees correct columns is contradicted by the suite.
    The real defence against this case is the golden files in step 9 and
    reading the output in step 10.
    """
    document = _document(*([_COLUMN_WIDTH * 2] * 8))

    assert pages_with_suspicious_line_width(document) == []


def test_a_document_with_no_readable_pages_is_handled() -> None:
    """An all-blank document returns no flags instead of raising.

    A scanned ΦΕΚ with no text layer extracts to empty strings on every page.
    That is a real possibility for older issues, and it should surface as "no
    text" downstream — not as a `StatisticsError` from the quality check.
    """
    document = ExtractedDocument(
        document_id="scanned",
        pages=[ExtractedPage(number=n, text="") for n in (1, 2, 3)],
    )

    assert pages_with_suspicious_line_width(document) == []


@pytest.mark.slow
@pytest.mark.skipif(
    not Path("data/raw").is_dir(), reason="corpus is git-ignored; run `poe corpus`"
)
def test_the_real_corpus_extracts_one_entry_per_page_in_order() -> None:
    """Every PDF page becomes exactly one ExtractedPage, numbered from 1.

    The only test here that opens a real PDF, so it is the only one that would
    notice pypdf changing its API or its page ordering. Catches an off-by-one
    in the `enumerate(start=1)` — which would misalign every page number a
    citation is eventually built from — and a dropped final page, which is
    invisible in a 260-page document until someone asks about its last article.

    Skipped when `data/` is empty, because the corpus is git-ignored by design.
    """
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        if not entry.file.is_file():
            pytest.skip(f"{entry.file} not downloaded")
        document = extract_document(entry)

        numbers = [page.number for page in document.pages]
        assert numbers == list(range(1, len(numbers) + 1))
        assert document.document_id == entry.id
        assert any(page.text.strip() for page in document.pages)
