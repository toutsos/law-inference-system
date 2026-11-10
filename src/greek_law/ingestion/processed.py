"""Run the whole ingestion pipeline and keep what it produced, on disk.

Everything before this module lives only as long as a process: the 2 136
chunks are rebuilt from the PDFs every time anything wants them. This writes
them to ``data/processed/`` — the build output of ingestion, the way
``target/`` is the build output of a Maven project: git-ignored, never edited
by hand, and rebuildable from ``data/raw/`` and the manifest at any time.

Two files per manifest document, by the step 8 decisions:

- ``<id>.jsonl`` — one :class:`~greek_law.ingestion.chunking.Chunk` per line,
  stored fields only. ``key``, ``header`` and ``embedding_text`` are derived on
  load, so a file can never carry a header that disagrees with its reference.
- ``<id>.report.json`` — what the pipeline could not handle, counted. Saved
  rather than only printed, because a report only helps if a change in it is
  noticed: a parser change that refuses three more paragraph markers shows up
  as a diff here even if nobody reads the terminal.

The output is deterministic — the same corpus gives byte-identical files —
because step 9's golden files and V3's idempotent load both depend on it.
Nothing variable, such as a timestamp, is written.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from greek_law.ingestion.assembly import assemble
from greek_law.ingestion.chunking import Chunk, chunk_act, oversized_chunks
from greek_law.ingestion.extraction import ExtractedDocument, extract_document
from greek_law.ingestion.manifest import CorpusDocument, Manifest
from greek_law.ingestion.normalization import (
    normalize_document,
    residual_confusables,
    residual_line_hyphens,
)
from greek_law.ingestion.structure import (
    LineCoverage,
    find_article_headings,
    find_article_texts,
    find_instrument_texts,
    line_coverage,
    numbering_breaks,
    rejected_heading_candidates,
    split_paragraphs,
    unreadable_container_lines,
    unreadable_heading_lines,
)

DEFAULT_PROCESSED_DIR = Path("data/processed")


class IngestReport(BaseModel):
    """Everything one document's ingestion counted instead of dropping.

    One field per report the pipeline already computes, so this adds no new
    judgement — it gathers the existing ones into a file. Counts where the
    detail lives in ``scripts/probe_structure.py``; lists where the detail is
    short and a diff should name it (an oversized chunk's key, a numbering
    break).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    chunks: int
    oversized: list[str]
    untranslated: list[str]
    numbering_breaks: list[str]
    rejected_heading_candidates: int
    unreadable_heading_lines: int
    unreadable_container_lines: int
    refused_paragraph_markers: int
    quoted_paragraph_markers: int
    residual_line_hyphens: int
    residual_confusables: int
    line_coverage: LineCoverage


class Ingested(BaseModel):
    """One document's chunks and the report that goes with them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunks: list[Chunk]
    report: IngestReport


def ingest_document(document: CorpusDocument, root: Path = Path()) -> Ingested:
    """Extract, normalize, assemble and chunk one manifest document.

    The only function that runs the pipeline end to end from a PDF; ``root``
    is where ``data/raw/`` lives, as for
    :func:`~greek_law.ingestion.extraction.extract_document`.
    """
    return ingest_extracted(document, extract_document(document, root))


def ingest_extracted(
    document: CorpusDocument, extracted: ExtractedDocument
) -> Ingested:
    """Everything after extraction: normalize, assemble, chunk and report.

    The seam step 9's golden-file test needs. A committed fixture cannot be a
    PDF — a downloaded ΦΕΚ never enters git, by [[Corpus Sourcing and
    Licensing]] — so the fixture is page *text*, and the pipeline must be able
    to start from text. ``extracted`` is pypdf's raw output, not yet
    normalized: normalization is part of what the golden file pins.
    """
    normalized = normalize_document(extracted)
    assembly = assemble(document, normalized)
    chunks = chunk_act(assembly.act, document)
    return Ingested(
        chunks=chunks,
        report=_report(document, normalized, assembly.untranslated, chunks),
    )


def _report(
    document: CorpusDocument,
    normalized: ExtractedDocument,
    untranslated: list[str],
    chunks: list[Chunk],
) -> IngestReport:
    """Gather every stage's report for one document.

    The structure parsers run again here rather than being threaded through
    from assembly: measured at step 5's review as 2% of the pipeline's time,
    and recorded there as the fix to reach for only when it matters.
    """
    text = "\n".join(page.text for page in normalized.pages)
    articles = [
        *find_article_texts(normalized),
        *(
            article
            for instrument in find_instrument_texts(normalized)
            for article in instrument.articles
        ),
    ]
    splits = [split_paragraphs(article) for article in articles]
    return IngestReport(
        document_id=document.id,
        chunks=len(chunks),
        oversized=[chunk.key for chunk in oversized_chunks(chunks)],
        untranslated=untranslated,
        numbering_breaks=numbering_breaks(find_article_headings(normalized)),
        rejected_heading_candidates=len(rejected_heading_candidates(normalized)),
        unreadable_heading_lines=sum(unreadable_heading_lines(normalized).values()),
        unreadable_container_lines=sum(unreadable_container_lines(normalized).values()),
        refused_paragraph_markers=sum(len(split.refused_markers) for split in splits),
        quoted_paragraph_markers=sum(len(split.quoted_markers) for split in splits),
        residual_line_hyphens=residual_line_hyphens(text),
        residual_confusables=sum(residual_confusables(text).values()),
        line_coverage=line_coverage(normalized),
    )


def chunks_path(directory: Path, document_id: str) -> Path:
    """Where a document's chunks are written: ``<directory>/<id>.jsonl``."""
    return directory / f"{document_id}.jsonl"


def report_path(directory: Path, document_id: str) -> Path:
    """Where a document's report is written: ``<directory>/<id>.report.json``."""
    return directory / f"{document_id}.report.json"


def write_processed(directory: Path, ingested: Ingested) -> None:
    """Write one document's chunk file and report file into ``directory``.

    ``newline="\\n"`` is explicit so the bytes are the same on every operating
    system — Windows would otherwise write ``\\r\\n`` and every golden file
    would differ by line endings alone.
    """
    directory.mkdir(parents=True, exist_ok=True)
    document_id = ingested.report.document_id
    chunks_path(directory, document_id).write_text(
        "".join(chunk.model_dump_json() + "\n" for chunk in ingested.chunks),
        encoding="utf-8",
        newline="\n",
    )
    report_path(directory, document_id).write_text(
        ingested.report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_chunks(path: Path) -> list[Chunk]:
    """Load a chunk file back into validated :class:`Chunk` objects.

    Split on ``"\\n"`` and never with ``str.splitlines()``: that also breaks
    on U+2028, U+0085 and other Unicode line separators, which JSON does not
    escape and which can sit inside a chunk's text — one such character would
    cut a chunk in half and fail validation on both pieces.
    """
    return [
        Chunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").split("\n")
        if line
    ]


def remove_processed(directory: Path) -> None:
    """Delete every chunk and report file in ``directory``, and nothing else.

    A rebuild starts clean so the directory holds exactly the manifest's
    documents: a document dropped from the manifest would otherwise leave its
    old chunks behind for V3 to load. Only the two patterns this module
    writes are touched, so a stray note in the directory survives.
    """
    for pattern in ("*.jsonl", "*.report.json"):
        for path in directory.glob(pattern):
            path.unlink()


def rebuild(
    manifest: Manifest, directory: Path = DEFAULT_PROCESSED_DIR, root: Path = Path()
) -> list[IngestReport]:
    """Rebuild ``directory`` from scratch for every document in ``manifest``."""
    remove_processed(directory)
    reports = []
    for document in manifest.documents:
        ingested = ingest_document(document, root)
        write_processed(directory, ingested)
        reports.append(ingested.report)
    return reports
