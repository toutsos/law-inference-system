"""Make the same text look the same to a machine, once, at ingestion.

Two things in a ΦΕΚ are invisible to a reader and fatal to exact matching.
Greek encodes every accented vowel twice — precomposed, or a bare vowel plus a
combining mark — and NFC settles that. The second is worse, because NFC cannot
help: the typesetters reached for *homoglyphs*. ν. 5110/2024's running header
reads ``ΕΦΗΜΕΡΙ∆Α``, where ``∆`` is U+2206 INCREMENT, a mathematical operator.
NFC leaves it untouched, and correctly so — NFC unifies different encodings of
the same character, and these are simply different characters.

This module is the character-level half of step 4. Lines and pages — running
headers, de-hyphenation, the trailing colophon page — are a second pass, added
to :func:`normalize_document` next, because they reason about lines rather than
about characters.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from itertools import groupby

from greek_law.ingestion.extraction import ExtractedDocument

_GREEK_BLOCKS = ((0x0370, 0x03FF), (0x1F00, 0x1FFF))
"""Greek and Coptic, plus Greek Extended for polytonic forms."""

_LATIN_TO_GREEK = {
    "A": "Α",
    "B": "Β",
    "E": "Ε",
    "H": "Η",
    "I": "Ι",
    "K": "Κ",
    "M": "Μ",
    "N": "Ν",
    "O": "Ο",
    "P": "Ρ",
    "T": "Τ",
    "X": "Χ",
    "Y": "Υ",
    "Z": "Ζ",
    "o": "ο",
    "∆": "Δ",
}
"""The confusables observed in the corpus, plus the uncontroversial uppercase set.

Deliberately excludes ``n``/``η``, ``u``/``υ`` and ``y``/``γ``: they look like
pairs and are not. The asymmetry is the whole justification — a wrong fold
corrupts text silently, a missing fold only leaves one token unmatched.
"""

_GREEK_TO_LATIN = {
    greek: latin for latin, greek in _LATIN_TO_GREEK.items() if latin.isalpha()
}
"""The same table read backwards, for English words typeset with a Greek letter.

The ``isalpha`` filter is what drops U+2206: it is damage to undo in one
direction, never a character to produce in the other.
"""


def _is_greek(character: str) -> bool:
    return any(low <= ord(character) <= high for low, high in _GREEK_BLOCKS)


def _is_latin(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def _is_letter_like(character: str) -> bool:
    """Whether a character belongs inside a word.

    ``isalpha`` alone is not enough: ``"∆".isalpha()`` is ``False``, because
    U+2206 is category Sm. The character that most needs folding is the one a
    letter test walks straight past.
    """
    return character.isalpha() or character in _LATIN_TO_GREEK


def _runs(text: str) -> Iterator[tuple[bool, str]]:
    """Split text into maximal word-ish and non-word-ish runs, in order."""
    for letter_like, characters in groupby(text, key=_is_letter_like):
        yield letter_like, "".join(characters)


def _fold(run: str) -> str:
    """Resolve one word to a single script by majority, ties going to Greek."""
    greek = sum(1 for character in run if _is_greek(character))
    latin = sum(1 for character in run if _is_latin(character))
    table = _LATIN_TO_GREEK if greek >= latin else _GREEK_TO_LATIN
    return "".join(table.get(character, character) for character in run)


def normalize_characters(text: str) -> str:
    """Compose to NFC, then fold confusables one word at a time.

    NFC runs first and never after: a combining mark is not letter-like, so it
    would cut a word in two, and the majority count would then decide that
    word's script from half of it.
    """
    composed = unicodedata.normalize("NFC", text)
    return "".join(
        _fold(run) if letter_like else run for letter_like, run in _runs(composed)
    )


def residual_confusables(text: str) -> Counter[str]:
    """Count non-Greek letters still sitting in tokens that contain Greek.

    Two misses are accepted by design — ``e-Ε.Φ.Κ.Α.`` must keep its ``e``, and
    the same rule lets ``Α.Σ.Ε.I.`` keep its ``I`` — so the pipeline reports
    what it left rather than implying there was nothing to leave. Silence would
    read as "clean" instead of "not attempted".

    The unit is the whitespace token, not the letter run that :func:`_fold`
    decides on, and that difference is the point: both accepted misses are
    single-script *runs* inside a mixed-script *token*, so counting runs would
    report zero for exactly the cases this exists to surface.
    """
    counts: Counter[str] = Counter()
    for token in text.split():
        if not any(_is_greek(character) for character in token):
            continue
        counts.update(
            character
            for character in token
            if _is_latin(character) or character in _LATIN_TO_GREEK
        )
    return counts


_HEADER_SEARCH_LINES = 3
"""How far down a page the running header is allowed to start.

Both observed shapes fit in three lines. The bound is the only thing standing
between this rule and a provision that cites a gazette issue: legislation
quotes «Τεύχος A’ 75/24.05.2024» constantly, and an unbounded search would
delete the citing provision along with everything above it.
"""


_ISSUE_STAMP = re.compile(r"Τεύχος\s+\S+\s*\d+/\d{2}\.\d{2}\.\d{4}")
"""The issue stamp that ends the running header, in both documents.

``\\S+`` rather than ``[ΑΒ]’`` for the τεύχος letter because the ``A`` printed
there is U+0041 LATIN A — it sits alone in its own letter run, so the fold
reads it as Latin and leaves it, correctly by its own rule.
"""


_DIGITS = re.compile(r"\d+")


def strip_running_header(text: str) -> tuple[int | None, str]:
    """Remove the gazette's running header, returning the page number it held.

    The header has a different *shape* per document — one glued line in
    ν. 5110/2024, three separate lines in π.δ. 62/2025 — so the rule cannot be
    positional. It anchors on the issue stamp instead and removes everything
    from the top of the page down to it, which handles both without either
    document being a special case.

    The printed gazette page number is the one thing in there worth keeping:
    PDF page 6 of ν. 5110/2024 prints «3188», and citations need the printed
    number. It is read from the text *before* the stamp, because the stamp
    itself is full of digits — issue 75 and a date — and taking the last number
    on the whole line would re-label every page with the year. Which side of
    the number the typesetter glued is not fixed either; it alternates with the
    page layout, 30 pages one way and 28 the other in ν. 5110/2024.

    The printed number is *also* derivable as ``number`` plus a per-document
    constant, which is how the suite checks this function rather than how this
    function works: 317 independent reads that must agree on one offset catch a
    misread page, where an offset taken once from page 1 would be consistent
    with itself and wrong everywhere.

    Returns ``(None, text)`` unchanged when there is no header, which is a page
    that never had a printed number — a cover or a blank — not a failure.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines[:_HEADER_SEARCH_LINES]):
        stamp = _ISSUE_STAMP.search(line)
        if stamp is None:
            continue
        digits = _DIGITS.findall("\n".join([*lines[:index], line[: stamp.start()]]))
        tail = line[stamp.end() :].strip()
        kept = ([tail] if tail else []) + lines[index + 1 :]
        return (int(digits[-1]) if digits else None), "\n".join(kept)
    return None, text


def normalize_document(document: ExtractedDocument) -> ExtractedDocument:
    """Normalize every page, returning a new document and keeping provenance.

    Same type in, same type out, by the step 4 decision: two types describing
    one payload would be two schemas to keep in agreement and a standing
    question about which is the truth. The accepted cost is that nothing in the
    type system says whether a document has been normalized — pipeline order
    carries that guarantee instead, and this function is the only thing that
    ever follows ``extract_document``.
    """
    pages = []
    for page in document.pages:
        gazette_page, text = strip_running_header(normalize_characters(page.text))
        pages.append(
            page.model_copy(update={"text": text, "gazette_page": gazette_page})
        )
    return document.model_copy(update={"pages": pages})
