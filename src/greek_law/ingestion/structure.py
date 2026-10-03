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

One ΦΕΚ can also carry **two article namespaces**. Greek legislation enacts a
complete instrument — a καταστατικό, a code, a convention — by ratifying it
through a single article, and the instrument keeps its own numbering, usually
spelled out: «άρθρο 15» of ν. 5110/2024 is *Εκπαίδευση - Κέντρα Αριστείας*,
while «άρθρο δέκατο πέμπτο» of the καταστατικό its άρθρο 13 enacted is *Σύνθεση
του Διοικητικού Συμβουλίου*. :func:`find_instrument_headings` reads that second
namespace, and it is a separate call precisely because interleaving the two
would destroy the contiguity invariant above.

Locating headings is all this module does. Titles and article text are step 5c;
the container path (ΒΙΒΛΙΟ, ΜΕΡΟΣ, ΤΜΗΜΑ, ΚΕΦΑΛΑΙΟ) is step 5e. A third
numbering form, «Άρθρο μόνο», is still unread and is what
:func:`unreadable_heading_lines` now reports.
"""

import re
from bisect import bisect_right
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

_ORDINAL_HEADING = re.compile(r"^Άρθρο ([^\W\d_]+(?: [^\W\d_]+)?)$")
"""An article numbered in words: ``Άρθρο δέκατο πέμπτο``.

``[^\\W\\d_]`` is "a word character that is not a digit or an underscore" —
i.e. a letter, Unicode-aware, so it spans Greek without naming a range. One or
two words, which is every ordinal from πρώτο to ενενηκοστό ένατο.

Shape alone is not enough and the margin is wide: over ν. 5110/2024 this
pattern matches **39 lines where there are 30 articles**. The nine extras are
contents entries whose title happens to be a single word — ``Άρθρο τρίτο
Έδρα``, ``Άρθρο έκτο Διάρκεια`` — which have a heading's exact shape.
:func:`ordinal_value` is what refuses them, so the word table is the recogniser
and not merely a converter.
"""


_ORDINAL_VALUE = {
    "πρώτο": 1,
    "δεύτερο": 2,
    "τρίτο": 3,
    "τέταρτο": 4,
    "πέμπτο": 5,
    "έκτο": 6,
    "έβδομο": 7,
    "όγδοο": 8,
    "ένατο": 9,
    "δέκατο": 10,
    "ενδέκατο": 11,
    "δωδέκατο": 12,
    "εικοστό": 20,
    "τριακοστό": 30,
    "τεσσαρακοστό": 40,
    "πεντηκοστό": 50,
    "εξηκοστό": 60,
    "εβδομηκοστό": 70,
    "ογδοηκοστό": 80,
    "ενενηκοστό": 90,
}
"""Greek ordinals in the neuter, as an article heading prints them.

**Additive, which is why one table suffices** — ``δέκατο έκτο`` is 10 + 6 and
``εικοστό πέμπτο`` is 20 + 5. The positional reading (``δέκατο`` as a 1 in the
tens column) needs a second table and three special cases: ``εικοστό`` standing
alone is 20 rather than a 2 with an empty units slot, and ``ενδέκατο`` and
``δωδέκατο`` are single words carrying a tens component, because Greek does not
say «δέκατο πρώτο» for 11th.

Twenty entries covering 1–99. The corpus needs fourteen; the tens are included
because a ratified instrument with forty articles is unremarkable and each
costs one line. Hundreds are left out deliberately — **an unmapped word makes
the whole heading unmappable, so it is reported by
:func:`unreadable_heading_lines` rather than mis-numbered.** Under-covering is
loud, so the table grows on evidence.

**Case-sensitive, and that is load-bearing.** Headings print the ordinal in
lower case; titles are capitalised. So a title word like ``Έκτο`` cannot match
the key ``έκτο``, which is a second line of defence behind the closed
vocabulary.
"""


_HEADING_LINE = re.compile(r"^Άρθρο (\S.*)$")
"""Any line that begins like a heading, whatever follows.

The input to :func:`unreadable_heading_lines`, which then subtracts everything
the module *can* read. Written as a wide match plus an exclusion rather than as
a narrow match, because the report has to be defined by what is left over — a
pattern enumerating the unreadable forms could only ever list the ones already
known about.
"""


def ordinal_value(words: str) -> int | None:
    """The number a spelled-out ordinal denotes, or ``None`` if it is not one.

    ``None`` is the whole point and is returned for anything outside the closed
    vocabulary: it is how ``Άρθρο τρίτο Έδρα`` is told from ``Άρθρο δέκατο
    τρίτο``, and how a form the table does not cover reaches the unreadable
    report instead of being guessed at. Every word must map — a partial match
    would let a title word contribute to an article number.

    The sum is also what makes the contiguity check available for an
    instrument: ν. 5110/2024's καταστατικό comes out 1..30 with no gaps, the
    same proof step 5a gives for the act's own 1..82.
    """
    parts = words.split()
    if not parts or not all(part in _ORDINAL_VALUE for part in parts):
        return None
    return sum(_ORDINAL_VALUE[part] for part in parts)


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


class InstrumentArticles(BaseModel):
    """One ratified instrument's own articles, and the act article that enacted it.

    Grouped rather than flagged on each heading. The alternative — two optional
    fields on :class:`ArticleHeading` — would repeat one fact thirty times and
    allow half of it: a heading carrying a label with no ratifying article, or
    the reverse, renders a citation nobody can resolve. That is the same
    argument that chose a nested ``RatifiedInstrument`` over flat fields in step
    5b-i, and it applies identically here.

    ``label`` is the instrument naming itself — the line that opens the
    quotation, ``«ΚΑΤΑΣΤΑΤΙΚΟ``, with the guillemet removed. It is recorded
    **as printed**, in the nominative: turning it into the genitive a citation
    needs («του καταστατικού») is Greek morphology, and by the step 5b-ii
    decision this module does not attempt it. ``None`` means the instrument
    printed no such line.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None
    ratifying_article: str
    headings: list[ArticleHeading]


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


def _quoted_label(
    lines: Sequence[tuple[int, int | None, int, str]], start: int, stop: int
) -> str | None:
    """The first line between two positions that opens a quotation.

    The gazette marks an enacted instrument by quoting it, so the line naming
    it is the one carrying the opening guillemet. Bounded to the span between
    the ratifying article and the instrument's first article, which is the only
    place such a line can belong to this instrument — measured over
    ν. 5110/2024, that span contains exactly one.
    """
    for _, _, _, line in lines[start:stop]:
        if line.startswith("«"):
            return line[1:].strip() or None
    return None


def find_instrument_headings(document: ExtractedDocument) -> list[InstrumentArticles]:
    """The articles of every instrument this act ratified, grouped by instrument.

    A separate function from :func:`find_article_headings` because these are a
    separate namespace: «άρθρο 15» of ν. 5110/2024 and «άρθρο δέκατο πέμπτο» of
    the καταστατικό its άρθρο 13 enacted are different provisions. Returning
    both from one call would interleave two sequences and destroy the
    contiguity invariant that is step 5a's strongest check.

    **Attribution is positional, and it has to be.** A spelled-out ordinal does
    *not* imply a ratified instrument — Greek ratification laws number their own
    articles πρώτο, δεύτερο, τρίτο, so «άρθρο πρώτο του ν. 3850/2010» is a
    top-level article. What identifies the instrument is where its articles sit:
    an ordinal heading inside the span of body article N belongs to the
    instrument N enacted. Measured: all thirty of ν. 5110/2024's fall between
    άρθρο 13 and άρθρο 14, which is also where the ``13`` a citation must print
    comes from.

    An ordinal heading before the act's first article is skipped rather than
    attributed: there is no article that could have ratified it. Not reachable
    in this corpus — the contents' ordinal entries are all refused by
    :func:`ordinal_value` — and skipping is the conservative half of a choice
    whose other half would invent a ratifying article.
    """
    lines = _lines(document)
    position = {(page, index): place for place, (page, _, index, _) in enumerate(lines)}
    body = [
        (position[(heading.page, heading.line)], heading.number)
        for heading in find_article_headings(document)
    ]
    starts = [start for start, _ in body]

    grouped: dict[int, list[tuple[int, ArticleHeading]]] = {}
    for place, (page, gazette_page, index, line) in enumerate(lines):
        match = _ORDINAL_HEADING.match(line)
        if match is None or ordinal_value(match.group(1)) is None:
            continue
        owner = bisect_right(starts, place) - 1
        if owner < 0:
            continue
        grouped.setdefault(owner, []).append(
            (
                place,
                ArticleHeading(
                    number=match.group(1),
                    page=page,
                    gazette_page=gazette_page,
                    line=index,
                ),
            )
        )

    return [
        InstrumentArticles(
            label=_quoted_label(lines, starts[owner], items[0][0]),
            ratifying_article=body[owner][1],
            headings=[heading for _, heading in items],
        )
        for owner, items in sorted(grouped.items())
    ]


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
    """Heading lines whose numbering notation this module has no rule for.

    Defined by subtraction: every line beginning «Άρθρο » whose first token is
    neither a digit form nor a word :func:`ordinal_value` can read. Four over
    the corpus after step 5b-ii, down from 64 before it, and all four are
    «Άρθρο μόνο» — the sole-article form, used by a one-article instrument.
    Each sits in π.δ. 62/2025's correspondence table naming *another*
    instrument's only article, so none is a provision this corpus loses.

    A digit form is excluded on its **first character**, not on the whole
    token, and the distinction is not cosmetic: the correspondence table prints
    ``Άρθρο 3, όπως διαμορφώθηκε και`` and ``Άρθρο 5α π.δ. 1/1990``, whose
    first tokens are ``3,`` and ``5α``. Requiring a clean number took the
    corpus count from 4 to 167 — every table row that continues into prose.

    Only the first word is examined for an ordinal, which is what keeps
    contents entries out of the count. ``Άρθρο πρώτο Νομική μορφή`` is read
    exactly as well as ``Άρθρο 1 Σκοπός`` is — read, and deliberately discarded
    as a contents entry — so reporting it would conflate "could not be read"
    with "read and rejected" and bury the lines that matter. The two are
    separate reports for that reason; see :func:`rejected_heading_candidates`.
    """
    counts: Counter[str] = Counter()
    for page in document.pages:
        for line in page.text.split("\n"):
            match = _HEADING_LINE.match(line)
            if match is None:
                continue
            remainder = match.group(1)
            if remainder[0].isdigit():
                continue
            if ordinal_value(remainder.split()[0]) is not None:
                continue
            counts[line] += 1
    return counts
