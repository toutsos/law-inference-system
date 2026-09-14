"""Raw text out of a ΦΕΚ PDF, one entry per page, nothing cleaned yet.

Extraction and normalization are separate steps on purpose. What comes out of
here is what the PDF actually contains — page furniture, hyphenated line
breaks, a mathematical ∆ standing in for Greek Δ and all. Step 4 decides what
to do about each of those, and keeping the decisions out of this module means
a normalization change never requires re-reading 260 pages of PDF.

The library is **pypdf**, chosen in step 3 by measurement; see the V2 note.
The short version: a ΦΕΚ is typeset in two columns, and pdfplumber's
``extract_text`` sorts words by position across the whole page, so it returns
line 1 of the left column and line 1 of the right column as a single line —
fluent, well-formed Greek that says something nobody wrote.
"""

import statistics
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from greek_law.ingestion.manifest import CorpusDocument

MEASURED_COLUMN_WIDTH = 51
"""Median characters per line of a single ΦΕΚ column, measured 2026-09-14.

Steady at 51 across both corpus documents and across their contents pages and
their body pages (observed range 35–59). It is documentation, not a threshold:
:func:`pages_with_suspicious_line_width` calibrates against each document.
"""

_SUBSTANTIAL_LINE = 20
"""Lines shorter than this are excluded from the median.

Headings, article numbers and page furniture are short, and a page is mostly
prose. Including them would drag the median below the column width and make
every page look narrow.
"""


class ExtractedPage(BaseModel):
    """One page of a PDF, as text.

    ``number`` is the 1-based index **in the PDF**, which is not the printed
    gazette page number — PDF page 6 of ν. 5110/2024 carries "3188" in its
    header. Citations need the printed one; recovering it means parsing the
    header, which is step 4's problem, not this module's.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int
    text: str


class ExtractedDocument(BaseModel):
    """Every page of one corpus document, in order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    pages: list[ExtractedPage]


def extract_pages(path: Path) -> list[ExtractedPage]:
    """Read every page of a PDF as text, in document order."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [
        ExtractedPage(number=index, text=page.extract_text() or "")
        for index, page in enumerate(reader.pages, start=1)
    ]


def extract_document(
    document: CorpusDocument, root: Path = Path()
) -> ExtractedDocument:
    """Extract a document named by the manifest, keeping its id attached."""
    return ExtractedDocument(
        document_id=document.id, pages=extract_pages(root / document.file)
    )


def median_line_length(text: str) -> float:
    """Median length of the substantial lines on a page. 0.0 if there are none."""
    lengths = [
        len(line)
        for line in text.splitlines()
        if len(line.strip()) >= _SUBSTANTIAL_LINE
    ]
    return statistics.median(lengths) if lengths else 0.0


def pages_with_suspicious_line_width(
    document: ExtractedDocument, factor: float = 1.5
) -> list[int]:
    """Pages whose lines are far wider than the rest of this document's.

    The failure this watches for is column splicing: two columns joined into
    one line each, which roughly doubles line width while producing text that
    reads perfectly and is completely wrong. Nothing raises when it happens, so
    the only defence is noticing the shape.

    Calibrated against the document itself rather than against
    :data:`MEASURED_COLUMN_WIDTH`, so a single-column act does not report every
    page. **The limitation that follows is real and is not worked around here:
    a document spliced on *every* page moves its own baseline and reports
    nothing.** That case is caught by the golden files in step 9 and by reading
    the output in step 10 — not by this function.
    """
    widths = [median_line_length(page.text) for page in document.pages]
    substantial = [width for width in widths if width > 0]
    if not substantial:
        return []

    limit = statistics.median(substantial) * factor
    return [
        page.number
        for page, width in zip(document.pages, widths, strict=True)
        if width > limit
    ]
