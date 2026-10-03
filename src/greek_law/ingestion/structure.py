"""Find where each article begins, before deciding what it contains.

Legal text advertises its own structure, which is why structure-aware parsing
is possible at all — but a ΦΕΚ advertises it more than once. Three things in
the corpus print a line that reads exactly like an article heading and is not
one: the **πίνακας περιεχομένων** lists the whole article sequence a second
time, the **πίνακας κωδικοποιητικών διατάξεων** lists part of it a third time,
and **amendment text** quotes articles belonging to other acts entirely.

Nothing raises when a decoy is admitted. It becomes a *phantom article* —
fluent Greek, a plausible number, text nobody enacted — which retrieves and
cites as cleanly as the real thing. That is the same failure class as step 3's
column splice and V1's resolvable fabricated citations, and it is the reason
this module is three rules rather than one regex.

The three rules, each answering a different decoy:

1. **Shape.** ``Άρθρο N`` alone on its line. The body prints the title on the
   next line; the contents prints it on the same one. Anchoring at the line
   start also excludes quoted amendment text for free.
2. **What follows.** The line after a real heading is never another article
   reference. A correspondence table's second column *is* one.
3. **The act's own numbering.** Articles run 1 to N, in order, exactly once, so
   the longest strictly increasing run of what survives rules 1 and 2 is the
   body.

Measured over the corpus: 82 of 82 candidates for ν. 5110/2024, and 588 of 679
for π.δ. 62/2025, contiguous 1..N in both. See the step 5a decisions in the V2
note for the alternatives that were measured and rejected.

This slice locates headings and nothing else. Titles and article text are step
5c; the ΚΑΤΑΣΤΑΤΙΚΟ's spelled-out numbering is step 5b, and until then
:func:`unreadable_heading_lines` is what keeps its absence loud.
"""

import re
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from greek_law.ingestion.extraction import ExtractedDocument

_ARTICLE_HEADING = re.compile(r"^Άρθρο (\d+[Α-Ω]?)$")
"""Rule 1 — a heading is the word, a number, and nothing else on the line.

Anchored at both ends, and both anchors are load-bearing. The end refuses
contents entries, which the gazette typesets as ``Άρθρο 1 Σκοπός`` while the
body puts the title on the following line. The start refuses quoted amendment
text: ν. 5110/2024 prints inserted provisions in guillemets, so PDF page 52
carries ``«Άρθρο 65Α`` — an article of ν. 4442/1929, and 34 such headings sit
in that one document. Admitting those would file another act's provisions under
this act's citation, so a hit on «ν. 5110/2024, άρθρο 65Α» would send a reader
to a law with no such article.

**That the guillemet is glued to the line start is luck, not design** — the
typographic convention and the legal distinction happen to coincide, and
nothing guarantees the next ΦΕΚ indents its quotations instead. Recorded as
technical debt rather than relied on silently; the obvious alternative,
tracking «» nesting depth, was measured and is worse (ν. 5110/2024 holds 202
openers against 201 closers, so one slip reclassifies the rest of the
document).

The optional ``[Α-Ω]`` admits ``Άρθρο 3Α``, the form amendments use to insert
an article between two existing ones. Neither corpus act has one in its body,
so this rests on legislative practice rather than measurement — but the cost is
one-sided: matching a number that does not exist is impossible, while missing a
real one would drop a provision silently.
"""

_ARTICLE_REFERENCE = re.compile(r"^Άρθρ[οα]\b")
"""Rule 2 — what a real heading is never followed by.

The learner's observation, and it does more work than the shape rule it
supplements. π.δ. 62/2025's πίνακας κωδικοποιητικών διατάξεων has two columns —
this Code's article against the provision it replaced — so the line after a
table row is *another article reference*::

    Άρθρο 18
    Άρθρο 3 ν. 4443/2016, όπως διαμορφώθηκε με την παρ. 1

Measured: this refuses 82 of that table's 88 rows, and **refuses none of the
670 real articles** in either document. A real heading is followed by its title
or by its text, never by another ``Άρθρο`` line.

Both nominative forms, singular and plural, because a table cell names a
provision in the nominative — ``Άρθρα 1 της Οδηγίας 2000/43/ΕΚ`` occurs
alongside the singular. The genitive ``Άρθρου`` is deliberately not matched:
``\\b`` stops it, it does not occur in this position in the corpus, and the
asymmetry runs the usual way — refusing too much would drop real provisions.
"""

_UNREADABLE_HEADING = re.compile(r"^Άρθρο (?!\d)(\S.*)$")
"""A heading line whose numbering none of the three rules can read.

``(?!\\d)`` is a negative lookahead — "not followed by a digit" — and it is
what keeps the report meaningful. A numbered line is read perfectly well and
either kept or deliberately rejected; a line numbered in *words* is a scheme
with no rule behind it at all. Without the lookahead this would also count the
corpus's 1 746 contents entries and bury the 64 lines that matter.
"""

_SUFFIX_LETTERS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
"""The letters an inserted article's number can end in, for ordering only."""


class ArticleHeading(BaseModel):
    """Where one article starts, and where in the gazette that is.

    ``page`` is the PDF index and ``gazette_page`` the number the page prints —
    the pair normalization already established on ``ExtractedPage``. ``line`` is
    the heading's index within that page's lines, which is what step 5c slices
    the article's text at.

    Provenance is captured here rather than recovered later because nothing
    downstream can recover it: a list of article numbers cannot say which page
    to cite, and re-finding the position would mean two pieces of code agreeing
    on the same pattern forever.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str
    page: int
    gazette_page: int | None
    line: int


def _order(number: str) -> tuple[int, str]:
    """Sort key for an article number: 3, then 3Α, then 4.

    Plain string comparison would put ``"10"`` before ``"9"``, and a plain
    ``int`` cannot hold ``"3Α"`` at all — hence the pair. ``str.rstrip`` takes a
    *set of characters* to strip, not a suffix to remove, which is the Python
    reading of it rather than the Java ``String.strip`` one.
    """
    digits = number.rstrip(_SUFFIX_LETTERS)
    return int(digits), number[len(digits) :]


def _lines(document: ExtractedDocument) -> list[tuple[int, int | None, int, str]]:
    """Every line of the document in order, each carrying where it came from.

    Flattened across pages rather than walked page by page, for the reason
    ``dehyphenate`` is: three headings in π.δ. 62/2025 are the last line of
    their page, so the line that follows them is on the *next* page. A per-page
    loop would see no following line and accept them without applying rule 2 —
    right by accident in those three cases, and wrong by construction.
    """
    return [
        (page.number, page.gazette_page, index, line)
        for page in document.pages
        for index, line in enumerate(page.text.split("\n"))
    ]


def _candidates(document: ExtractedDocument) -> list[ArticleHeading]:
    """Lines passing rules 1 and 2 — heading-shaped, not followed by a reference.

    Rule 3's decoys are still in here, deliberately: separating those needs the
    whole sequence in document order, which is :func:`_body_span`'s job.
    """
    lines = _lines(document)
    found = []
    for position, (page, gazette_page, index, line) in enumerate(lines):
        match = _ARTICLE_HEADING.match(line)
        if match is None:
            continue
        following = lines[position + 1][3] if position + 1 < len(lines) else ""
        if _ARTICLE_REFERENCE.match(following):
            continue
        found.append(
            ArticleHeading(
                number=match.group(1),
                page=page,
                gazette_page=gazette_page,
                line=index,
            )
        )
    return found


def _body_span(candidates: Sequence[ArticleHeading]) -> tuple[int, int]:
    """Rule 3 — the half-open range of the longest strictly increasing run.

    The act's numbering is the one thing no decoy can fake: a legislative body
    is articles 1 to N in order, exactly once. The contents repeats the whole
    sequence and therefore resets it; the correspondence table restarts low and
    resets it again. Each reset ends a run, and the longest run left is the
    body — 82 of 82 candidates for ν. 5110/2024, 588 of 597 for π.δ. 62/2025.

    **A tie goes to the later run**, which is less a tie-break than the rule
    that handles the contents at all: the contents and the body print the same
    numbers the same number of times, so their runs are the same length
    whenever a wrapped title leaks one through rule 1. A table of contents
    precedes what it indexes by definition, so the later run is the act.
    Resolved the other way, both corpus documents would parse their contents
    page as the act: right numbers, right titles, and not one word of law.

    This is the only non-local rule here, and that is its known cost — you
    cannot look at one line and say why it survived. It earns its place on the
    nine candidates rules 1 and 2 cannot reach, three of which are *provably*
    beyond them: a wrapped contents entry is byte-for-byte a heading followed
    by its title, because that is exactly what it is.
    """
    best = (0, 0)
    start = 0
    for index in range(1, len(candidates) + 1):
        if index < len(candidates) and _order(candidates[index].number) > _order(
            candidates[index - 1].number
        ):
            continue
        if index - start >= best[1] - best[0]:
            best = (start, index)
        start = index
    return best


def find_article_headings(document: ExtractedDocument) -> list[ArticleHeading]:
    """Where each article of this act begins, in document order."""
    candidates = _candidates(document)
    start, stop = _body_span(candidates)
    return candidates[start:stop]


def rejected_heading_candidates(document: ExtractedDocument) -> list[ArticleHeading]:
    """Candidates that passed rules 1 and 2 but fell outside the body run.

    Nine over the corpus: three wrapped contents entries and six correspondence
    table rows whose second column does not begin with ``Άρθρο``. Reported for
    the reason
    :func:`~greek_law.ingestion.normalization.residual_confusables` is — once
    dropped, a contents entry and a real article the rules missed look
    identical, and only one of those is acceptable.
    """
    candidates = _candidates(document)
    start, stop = _body_span(candidates)
    return [*candidates[:start], *candidates[stop:]]


def unreadable_heading_lines(document: ExtractedDocument) -> Counter[str]:
    """Heading lines numbered in a scheme none of the three rules can read.

    64 over the corpus, and they are two separate gaps. 60 are the thirty
    articles of the ΚΑΤΑΣΤΑΤΙΚΟ that άρθρο 13 of ν. 5110/2024 ratifies, counted
    once in the contents and once in the body: «Άρθρο πρώτο» … «Άρθρο
    τριακοστό», a numbering namespace parallel to the act's own, so «άρθρο 15»
    and «άρθρο δέκατο πέμπτο» are different provisions of the same ΦΕΚ. Step 5b
    owns them and the ``SourceReference`` change they force.

    The other four are «Άρθρο μόνο» — the sole-article form — in π.δ. 62/2025's
    correspondence table. Nobody was looking for a third numbering scheme; this
    report is how it was found, which is the argument for having it.
    """
    counts: Counter[str] = Counter()
    for page in document.pages:
        counts.update(
            line for line in page.text.split("\n") if _UNREADABLE_HEADING.match(line)
        )
    return counts
