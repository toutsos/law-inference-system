"""The command-line edge of corpus verification: argv in, exit code out.

Separate from ``manifest.py`` for the same reason ``cli.py`` is separate from
``compositions.py``: printing and exit codes are about a terminal, not about
what a manifest means. ``main`` takes ``argv`` so a test can call it.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="greek-law-corpus",
        description="Check data/raw/ against the committed corpus manifest.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--root", type=Path, default=Path())
    args = parser.parse_args(argv)

    results = check_manifest(load_manifest(args.manifest), args.root)
    for result in results:
        print(f"{result.outcome.value.upper():9} {result.document_id}  {result.detail}")

    failures = [r for r in results if r.outcome is not CheckOutcome.OK]
    print(f"\n{len(results) - len(failures)}/{len(results)} documents verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
