"""Throwaway: read what two PDF extractors actually produce, side by side.

Not production code and not a dependency of the package — run it with
``uv run --with pypdf --with pdfplumber``. The point of step 3 is to choose an
extraction library by reading its output against the real ΦΕΚ, and a choice
made before the comparison would make the comparison theatre.

Kept after the choice was made: step 4 re-runs the confusable census against
normalized text, and V5 re-runs it against queries. Run it with ``uv run
--with pypdf --with pdfplumber``; neither is a project dependency.
"""

import argparse
import difflib
import time
import unicodedata
from collections import Counter
from pathlib import Path

GREEK_BLOCKS = ((0x0370, 0x03FF), (0x1F00, 0x1FFF))
ALLOWED_ALONGSIDE_GREEK = set(".,·;:()[]«»\"'’‘-–—/0123456789 \t")


def is_greek(character: str) -> bool:
    return any(low <= ord(character) <= high for low, high in GREEK_BLOCKS)


def extract_pypdf(path: Path, pages: range) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [reader.pages[number].extract_text() or "" for number in pages]


def extract_pdfplumber(path: Path, pages: range) -> list[str]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [pdf.pages[n].extract_text() or "" for n in pages]


def extract_pdfplumber_layout(path: Path, pages: range) -> list[str]:
    """Same library, asked to preserve the printed layout instead of reflowing.

    Without this, ``extract_text`` sorts words by (top, left) across the whole
    page, which on a two-column ΦΕΚ reads line 1 of the left column and line 1
    of the right column as one line.
    """
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [pdf.pages[n].extract_text(layout=True) or "" for n in pages]


def foreign_characters_in_greek_words(text: str) -> Counter[str]:
    """Characters sitting inside a Greek word that are not Greek.

    This is the confusable census. A Latin ``T`` or a mathematical ``∆`` inside
    ΕΦΗΜΕΡΙΔΑ is invisible to the eye and fatal to exact matching, and Unicode
    normalization does not touch it — NFC only unifies *equivalent* encodings
    of the same character, and these are different characters.
    """
    census: Counter[str] = Counter()
    for token in text.split():
        if not any(is_greek(character) for character in token):
            continue
        for character in token:
            if not is_greek(character) and character not in ALLOWED_ALONGSIDE_GREEK:
                census[character] += 1
    return census


def describe(character: str) -> str:
    name = unicodedata.name(character, "<unnamed>")
    return f"{character!r} U+{ord(character):04X} {name}"


def report(label: str, pages: list[str], seconds: float) -> None:
    text = "\n".join(pages)
    print(f"\n### {label}")
    print(f"  {seconds:.2f} s for {len(pages)} pages, {len(text)} characters")
    print(f"  lines: {len(text.splitlines())}")
    print(
        f"  hyphen-at-end-of-line: "
        f"{sum(1 for x in text.splitlines() if x.rstrip().endswith('-'))}"
    )
    census = foreign_characters_in_greek_words(text)
    if not census:
        print("  no foreign characters inside Greek words")
        return
    print("  foreign characters inside Greek words:")
    for character, count in census.most_common():
        print(f"    {count:5d}  {describe(character)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--first", type=int, default=1, help="1-based, inclusive")
    parser.add_argument("--last", type=int, default=12, help="1-based, inclusive")
    parser.add_argument("--out", type=Path, default=Path("data/probe"))
    parser.add_argument("--diff-lines", type=int, default=40)
    args = parser.parse_args()

    pages = range(args.first - 1, args.last)
    print(f"{args.pdf}, pages {args.first}–{args.last}")

    results: dict[str, list[str]] = {}
    extractors = (
        ("pypdf", extract_pypdf),
        ("pdfplumber", extract_pdfplumber),
        ("pdfplumber-layout", extract_pdfplumber_layout),
    )
    for label, extract in extractors:
        started = time.monotonic()
        results[label] = extract(args.pdf, pages)
        report(label, results[label], time.monotonic() - started)

    args.out.mkdir(parents=True, exist_ok=True)
    for label, extracted in results.items():
        destination = args.out / f"{args.pdf.stem}.{label}.txt"
        destination.write_text(
            "\n".join(
                f"\n----- page {number + 1} -----\n{page}"
                for number, page in zip(pages, extracted, strict=True)
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {destination}")

    print(f"\n### first {args.diff_lines} differing lines (pypdf → pdfplumber)")
    diff = difflib.unified_diff(
        "\n".join(results["pypdf"]).splitlines(),
        "\n".join(results["pdfplumber"]).splitlines(),
        fromfile="pypdf",
        tofile="pdfplumber",
        lineterm="",
        n=1,
    )
    for line in list(diff)[: args.diff_lines]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
