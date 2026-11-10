"""The command-line edge of ingestion: ``poe ingest``.

Separate from ``processed.py`` for the reason ``verify.py`` is separate from
``manifest.py``: printing and exit codes are about a terminal, not about what
ingestion means. ``main`` takes ``argv`` so a test can call it.

The corpus is verified against the manifest *before* anything is written.
Every chunk's ``document_id`` claims the manifest entry's SHA-256; writing
chunks from bytes that do not match it would make that claim false.
"""

import argparse
import sys
from pathlib import Path

from greek_law.ingestion.manifest import (
    DEFAULT_MANIFEST_PATH,
    CheckOutcome,
    check_manifest,
    load_manifest,
)
from greek_law.ingestion.processed import DEFAULT_PROCESSED_DIR, IngestReport, rebuild


def _summary(report: IngestReport) -> str:
    """One line per document: the counts a human checks after every run."""
    return (
        f"{report.document_id}: {report.chunks} chunks, "
        f"{len(report.oversized)} oversized, "
        f"{report.refused_paragraph_markers} paragraph markers refused, "
        f"{report.residual_line_hyphens} line-final hyphens left, "
        f"{len(report.untranslated)} instruments untranslated"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="greek-law-ingest",
        description="Rebuild data/processed/ from data/raw/ and the corpus manifest.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument("--out", type=Path, default=DEFAULT_PROCESSED_DIR)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    failures = [
        result
        for result in check_manifest(manifest, args.root)
        if result.outcome is not CheckOutcome.OK
    ]
    if failures:
        for result in failures:
            print(
                f"{result.outcome.value.upper():9} {result.document_id}  {result.detail}"
            )
        print("\nNothing written: the corpus does not match its manifest.")
        return 1

    reports = rebuild(manifest, args.out, args.root)
    for report in reports:
        print(_summary(report))
    print(f"\n{len(reports)} documents written to {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
