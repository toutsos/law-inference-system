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

Step 5c cuts each located heading down to a title and a text
(:func:`find_article_texts`, :func:`find_instrument_texts`). An article runs to
the next heading of *either* namespace, trimmed at a container opener and — in
the document's final span only — at the enactment formula or an annex marker.
:func:`line_coverage` is the check on all of it: every line of the document
lands in exactly one of four buckets, and the four must sum to the total.

The container path (ΒΙΒΛΙΟ, ΜΕΡΟΣ, ΤΜΗΜΑ, ΚΕΦΑΛΑΙΟ) is step 5e, which is where
the lines trimmed above are claimed; numbered paragraphs are step 5d. A third
numbering form, «Άρθρο μόνο», is still unread and is what
:func:`unreadable_heading_lines` now reports.
"""

import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from greek_law.ingestion.extraction import ExtractedDocument

_ARTICLE_HEADING = re.compile(r"^Άρθρο (\d+(?: ?[Α-Ω])?)$")
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

The optional ``[Α-Ω]`` admits an inserted article — the form amendments use to
place one between two existing ones — **and the space in it is not optional
decoration**: π.δ. 62/2025 prints ``Άρθρο 141 Α``, digits, space, letter, and
without the space here its 204 lines were filed as the tail of άρθρο 141.
Found 2026-10-17 while measuring for step 5d, which is where the symptom
showed: άρθρο 141 appeared to carry two complete paragraph runs, 1–12 and then
1–9 again.

Nothing in this module caught it, and that is the part worth remembering.
:func:`numbering_breaks` passed, because an article that was never found is not
*missing from* a run; :func:`unreadable_heading_lines` skips the line because
the character after «Άρθρο » is a digit. It fell through the parse and both
reports, each for a locally good reason.

The number is stored glued whichever way it is printed, so one spelling reaches
``SourceReference.article`` and the retrieval key. Allowing the space costs
nothing measurable: ``^Άρθρο \\d+ [Α-Ω]$`` matches **exactly one line in the
corpus**, that heading. The πίνακας κωδικοποιητικών διατάξεων's lookalikes —
``Άρθρο 141 Α Άρθρο 15 ν. 5163/2024``, ``Άρθρο 4 Υ Α 19040/1981`` (a Υ.Α., not
an article 4Υ) and ``Άρθρο 71 Α Άρθρο 543`` — all carry trailing text, so the
closing anchor refuses them exactly as before.
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


def numbering_breaks(headings: Sequence[ArticleHeading]) -> list[str]:
    """Article numbers that do not continue the act's sequence — empty is the claim.

    An act's articles run 1 to N in order, exactly once, and an amendment may
    insert a lettered article between two of them: 141, **141Α**, 142 is a
    legitimate sequence, and so is 3, 3Α, 3Β, 4. This returns the numbers
    fitting neither pattern, so an empty list *is* the contiguity proof step 5a
    rests on — stated once here instead of re-derived by every caller.

    It replaces the ``== list(range(1, n + 1))`` comparison the probe and the
    tests used until π.δ. 62/2025's άρθρο 141Α was found, which that comparison
    would have called a broken sequence: the corpus's one real insertion
    failing the check that exists to catch decoys.

    A break does not advance the expected number, so an admitted decoy is
    reported once rather than invalidating every article after it.
    """
    breaks: list[str] = []
    previous: tuple[int, str] | None = None
    for heading in headings:
        current = _order(heading.number)
        expected = (1, "") if previous is None else (previous[0] + 1, "")
        inserted = (
            previous is not None
            and current[0] == previous[0]
            and current[1] > previous[1]
        )
        if current != expected and not inserted:
            breaks.append(heading.number)
            continue
        previous = current
    return breaks


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
                number=match.group(1).replace(" ", ""),
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


_BLOCK_OPENER = re.compile(r"^(?:ΒΙΒΛΙΟ|ΜΕΡΟΣ|ΤΜΗΜΑ|ΚΕΦΑΛΑΙΟ|ΥΠΟΚΕΦΑΛΑΙΟ)\b")
"""A container heading, which belongs to no article and ends the one before it.

The gazette prints these between two articles, so their lines are the tail of
the previous span and are not that article's text. **59 spans across the corpus
end this way** (7 in ν. 5110/2024, 52 in π.δ. 62/2025), 2–8 lines each. Left
in, every ΜΕΡΟΣ and ΚΕΦΑΛΑΙΟ title reads as the closing sentence of whichever
article happened to precede it.

The lines are trimmed here and claimed by nobody yet; :func:`line_coverage`
counts them as ``between_articles`` so step 5e has a number to hit.
"""

_END_OF_BODY = re.compile(r"^(?:ΠΑΡΑΡΤΗΜΑ|ΠΙΝΑΚΑΣ|Παραγγέλλομε)\b")
"""What ends the act's body, applied **only in the document's final span**.

The last article has no next heading to stop it, so it otherwise absorbs the
rest of the file: 72 lines of signature block in ν. 5110/2024 (the date, the
President, twenty ministers), and **2 338** lines in π.δ. 62/2025 — the πίνακας
κωδικοποιητικών διατάξεων, the same table rule 2 spends its existence refusing
as a source of phantom headings, arriving a second time as άρθρο 588's text.
Both markers are needed because a π.δ. prints no «Παραγγέλλομε».

**The restriction to the final span is the load-bearing part, and it was
measured rather than reasoned.** An earlier version matched these anywhere and
silently deleted enacted law: π.δ. 62/2025's άρθρο 333 ends «… βάσει σύμβασης
ή εθίμου, ως εξής:» and the 79-line ``ΠΙΝΑΚΑΣ ΑΠΟΖΗΜΙΩΣΕΩΝ ΕΡΓΑΖΟΜΕΝΩΝ`` that
follows *is* the severance scale, while άρθρο 490 attaches a 231-line
``ΠΑΡΑΡΤΗΜΑ`` it declares an inseparable part of itself. Under-cutting leaves
an oversized span that :func:`line_coverage` shouts about; over-cutting drops a
provision in silence. See the step 5c decisions for the colon-gated
generalisation that was measured and deliberately not built.
"""

_PARAGRAPH_START = re.compile(r"^\d+\.")
"""A line opening a numbered paragraph — proof that the title is over.

The one title signal that is not a threshold: a line beginning «1.» cannot be
part of a heading. As the *first* line after a heading it is also proof the
article has no title at all, which is why it is tested before anything else.
Step 5d is what reads these properly.
"""

_TITLE_MAX_WIDTH = 44
"""Above this width a line was wrapped by the typesetter, not centred.

Titles are centred and break early — measured maximum 47 characters, median
26–35 — while body text is justified to roughly 51 (see
:data:`~greek_law.ingestion.extraction.MEASURED_COLUMN_WIDTH`). 44 is where the
measured error count bottoms out: scored against the 623 titles the contents
pages pin exactly, the rule reads **614 exactly, 8 short and 1 long**. Raising
it to 47 trades 6 of those truncations for 33 over-reads, and over-reading is
the direction that moves a line of law into the title field.
"""

_TITLE_MAX_LINES = 5
"""Hard cap on title lines, the longest measured being exactly 5.

A backstop, not a rule: if the three signals ever all fail on one article, the
damage is bounded to five lines instead of the whole provision.
"""

_SENTENCE_END = (".", ":", ";", "·", "!")
"""A title never ends in sentence punctuation; a short closing line does.

What rescues «μισθός.» — seven characters, the last wrapped line of
π.δ. 62/2025's άρθρο 3 — from being read as a second line of the title. Without
it the article's own concluding word leaves its text. ``·`` is the Greek άνω
τελεία, which the corpus uses where English would use a semicolon.
"""


class ArticleText(BaseModel):
    """One article's title and text, with the heading that located it.

    Composes :class:`ArticleHeading` rather than copying its fields, so
    provenance has exactly one home and cannot drift: ``article.heading.page``
    is the page a citation prints, and it is the same object
    :func:`find_article_headings` returned.

    ``title`` is ``None`` when the article printed none — the first line after
    the heading already opened a numbered paragraph. ``text`` keeps the line
    breaks it was extracted with, because **step 5d finds paragraphs by a
    line-initial «1.»**; reflowing the span into prose here would destroy the
    only signal the next step has. Joining is 5d's decision to make once it has
    used the line starts.

    This is an ingestion type, not :class:`~greek_law.domain.Article`. The
    domain model holds text only inside a :class:`~greek_law.domain.Paragraph`,
    so building one here would mean inventing a single unnumbered paragraph for
    5d to re-split — the domain object assembled twice, once wrongly. Domain
    assembly happens once, at the end of step 5.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    heading: ArticleHeading
    title: str | None
    text: str


class InstrumentTexts(BaseModel):
    """One ratified instrument's articles, sliced — the 5c half of InstrumentArticles.

    Mirrors :class:`InstrumentArticles` field for field, for the reason that
    type is grouped at all: ``label`` and ``ratifying_article`` are one fact
    about all thirty articles, and repeating them per article would allow half
    of it to be stated.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None
    ratifying_article: str
    articles: list[ArticleText]


class LineCoverage(BaseModel):
    """Where every line of the document ended up. 5c's version of contiguity.

    Step 5a can prove its parse by the act's own numbering running 1..N. There
    is no such proof for a slice, so the check here is an arithmetic identity:
    the four buckets must sum to the document's line count, and
    :attr:`balances` asserts it.

    - ``front_matter`` — before the first heading: the ΦΕΚ masthead, the
      preamble, the whole πίνακας περιεχομένων.
    - ``in_articles`` — heading, title and text lines of every article, in both
      namespaces.
    - ``between_articles`` — trimmed tails, which are the container headings
      step 5e will claim.
    - ``trailing`` — from the final span's cut to the end of the file: the
      signature block, the annexes, the correspondence tables.

    Measured: ν. 5110/2024 ``277 + 6 206 + 39 + 72 = 6 594`` (94.1% in
    articles); π.δ. 62/2025 ``744 + 22 599 + 183 + 2 338 = 25 864`` (87.4%). A
    slicer that lost a page, double-counted a span or trimmed into the void
    would still return plausible articles — it could not keep the sum.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int
    in_articles: int
    front_matter: int
    between_articles: int
    trailing: int

    @property
    def balances(self) -> bool:
        """Whether the four buckets account for every line exactly once."""
        return self.total == (
            self.in_articles + self.front_matter + self.between_articles + self.trailing
        )


class _Span(NamedTuple):
    """One article's extent, as four flat line positions.

    ``start`` is the heading line; the title is ``start + 1 .. title_stop``, the
    text is ``title_stop .. text_stop``, and ``text_stop .. stop`` is the
    trimmed tail that belongs to no article. A ``NamedTuple`` because this is a
    record with no behaviour and never leaves the module — Java would reach for
    a `record` here, and the fields are read by name for the same reason.
    """

    heading: ArticleHeading
    start: int
    title_stop: int
    text_stop: int
    stop: int


def _text_stop(
    lines: Sequence[tuple[int, int | None, int, str]],
    start: int,
    stop: int,
    final: bool,
) -> int:
    """Where the article's text ends: the first block boundary, or the next heading.

    ``final`` is what makes the annex markers safe — see :data:`_END_OF_BODY`.
    Scanning from ``start + 1`` rather than ``start`` because the heading line
    itself is never a boundary for its own article.
    """
    for position in range(start + 1, stop):
        line = lines[position][3]
        if _BLOCK_OPENER.match(line) or (final and _END_OF_BODY.match(line)):
            return position
    return stop


def _title_stop(
    lines: Sequence[tuple[int, int | None, int, str]], start: int, limit: int
) -> int:
    """Where the title ends — three local signals, in order of certainty.

    The first line after the heading is the title unless it opens a numbered
    paragraph, which is proof there is none. Every further line continues the
    title while it stays under :data:`_TITLE_MAX_WIDTH`, opens no paragraph and
    does not end a sentence. Returning ``start + 1`` therefore means "no
    title", which is the same value as "the title is zero lines long" and is
    read that way by :func:`_article_text`.

    An empty line also ends the title. ``normalize_whitespace`` leaves none in
    the corpus, so this costs nothing today and keeps a blank line from being
    absorbed into a heading if a future source emits one.
    """
    if start + 1 >= limit or _PARAGRAPH_START.match(lines[start + 1][3].strip()):
        return start + 1
    stop = start + 2
    while stop < limit and stop - start - 1 < _TITLE_MAX_LINES:
        line = lines[stop][3]
        stripped = line.strip()
        if (
            not stripped
            or _PARAGRAPH_START.match(stripped)
            or len(line) >= _TITLE_MAX_WIDTH
            or stripped.endswith(_SENTENCE_END)
        ):
            break
        stop += 1
    return stop


def _spans(
    document: ExtractedDocument,
) -> tuple[
    list[tuple[int, int | None, int, str]],
    list[_Span],
    list[tuple[InstrumentArticles, list[_Span]]],
]:
    """Every article's extent, from one boundary list over *both* namespaces.

    **The two namespaces are separate but their positions interleave**, and
    that is the whole of this function. ν. 5110/2024's άρθρο 13 is followed in
    the document by thirty ordinal headings before άρθρο 14 arrives, so a span
    ended only by the next *body* heading is 1 188 lines long against a median
    of 41 — the entire καταστατικό filed as the text of one article of the law,
    citable only as «άρθρο 13» and duplicated beside the instrument's own
    thirty articles. Merging both heading lists into one sorted boundary list
    fixes it in both directions at once, and άρθρο 13 comes out as what it says:
    three lines ratifying a document printed elsewhere.

    Returns the flattened lines alongside the spans because
    :func:`_article_text` needs them, and re-flattening would walk 25 000 lines
    a second time per call.
    """
    lines = _lines(document)
    position = {(page, index): place for place, (page, _, index, _) in enumerate(lines)}
    body = find_article_headings(document)
    instruments = find_instrument_headings(document)

    located = sorted(
        position[(heading.page, heading.line)]
        for heading in [*body, *(h for group in instruments for h in group.headings)]
    )
    at = {place: index for index, place in enumerate(located)}

    def span(heading: ArticleHeading) -> _Span:
        start = position[(heading.page, heading.line)]
        index = at[start]
        stop = located[index + 1] if index + 1 < len(located) else len(lines)
        text_stop = _text_stop(lines, start, stop, final=index + 1 == len(located))
        return _Span(
            heading, start, _title_stop(lines, start, text_stop), text_stop, stop
        )

    return (
        lines,
        [span(heading) for heading in body],
        [(group, [span(h) for h in group.headings]) for group in instruments],
    )


def _article_text(
    lines: Sequence[tuple[int, int | None, int, str]], span: _Span
) -> ArticleText:
    """Cut one span into a title and a text.

    The title's lines are stripped and joined with a space, because a wrapped
    title is one phrase broken by the column; the text's lines are joined with
    newlines and kept as they were, because 5d reads their starts. ``title or
    None`` turns an empty join into an explicit "no title" rather than an empty
    string that renders as a title nobody notices is missing.
    """
    title = " ".join(
        lines[place][3].strip() for place in range(span.start + 1, span.title_stop)
    )
    text = "\n".join(
        lines[place][3] for place in range(span.title_stop, span.text_stop)
    ).strip()
    return ArticleText(heading=span.heading, title=title or None, text=text)


def find_article_texts(document: ExtractedDocument) -> list[ArticleText]:
    """Each article of this act with its title and text, in document order.

    The 5c counterpart of :func:`find_article_headings`, and one call per
    namespace for the same reason that function has: these are the act's own
    άρθρα 1..N, not the articles of anything it ratified.
    """
    lines, body, _ = _spans(document)
    return [_article_text(lines, span) for span in body]


def find_instrument_texts(document: ExtractedDocument) -> list[InstrumentTexts]:
    """Each ratified instrument's articles with their titles and texts.

    The 5c counterpart of :func:`find_instrument_headings`. ν. 5110/2024's
    καταστατικό comes out as thirty titled provisions — «άρθρο δέκατο πέμπτο
    Σύνθεση του Διοικητικού Συμβουλίου» — which is what makes the namespace
    step 5b separated worth having separated.
    """
    lines, _, instruments = _spans(document)
    return [
        InstrumentTexts(
            label=group.label,
            ratifying_article=group.ratifying_article,
            articles=[_article_text(lines, span) for span in spans],
        )
        for group, spans in instruments
    ]


def line_coverage(document: ExtractedDocument) -> LineCoverage:
    """How many of the document's lines each bucket holds — see :class:`LineCoverage`.

    Same house rule as `residual_confusables` and
    :func:`rejected_heading_candidates`: silence must never read as "clean". A
    span that swallowed an appendix and a span that lost one both look like an
    article from the outside, and this is the number that tells them apart.
    """
    lines, body, instruments = _spans(document)
    spans = sorted(
        [*body, *(span for _, spans in instruments for span in spans)],
        key=lambda span: span.start,
    )
    if not spans:
        return LineCoverage(
            total=len(lines),
            in_articles=0,
            front_matter=len(lines),
            between_articles=0,
            trailing=0,
        )
    return LineCoverage(
        total=len(lines),
        in_articles=sum(span.text_stop - span.start for span in spans),
        front_matter=spans[0].start,
        between_articles=sum(span.stop - span.text_stop for span in spans[:-1]),
        trailing=spans[-1].stop - spans[-1].text_stop,
    )
