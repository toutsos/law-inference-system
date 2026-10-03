"""Locating article headings in a ΦΕΚ, and refusing the three kinds of decoy.

Every heading string in this file is a real line from one of the two corpus
documents, taken from the step 5a census in the V2 note. That matters more here
than anywhere else so far: the decoys are not hypothetical malformed input,
they are what the gazette actually prints — a table of contents that repeats
the whole article sequence, a correspondence table that repeats part of it, and
amendment text that quotes articles belonging to *other* acts.

A phantom article is the ingestion-layer twin of V1's fabricated citation: it
is well-formed Greek, carries a plausible number, and says something nobody
enacted. The tests are grouped by which of the module's three rules they pin —
shape, what follows, and the act's own numbering — because each rule exists to
defeat a decoy the other two cannot.
"""

import pytest

from greek_law.ingestion import DEFAULT_MANIFEST_PATH, load_manifest
from greek_law.ingestion.extraction import (
    ExtractedDocument,
    ExtractedPage,
    extract_document,
)
from greek_law.ingestion.normalization import normalize_document
from greek_law.ingestion.structure import (
    find_article_headings,
    find_instrument_headings,
    ordinal_value,
    rejected_heading_candidates,
    unreadable_heading_lines,
)


def document(*pages: str) -> ExtractedDocument:
    """Build a document from one string per page, gazette numbers 3000 upward.

    The gazette number is set because provenance is half of what a heading
    carries, and a helper that left it `None` would let a test pass while the
    field it should be checking was never populated.
    """
    return ExtractedDocument(
        document_id="test",
        pages=[
            ExtractedPage(number=number, text=text, gazette_page=3000 + number)
            for number, text in enumerate(pages, start=1)
        ],
    )


BODY = "Άρθρο 1\nΣκοπός\nΣκοπός του παρόντος είναι:\nΆρθρο 2\nΑντικείμενο\n"
"""ν. 5110/2024, PDF page 3: how the body prints a heading — number alone."""


# ---------------------------------------------------------------------------
# Rule 1 — shape: the number alone on its line
# ---------------------------------------------------------------------------


def test_an_article_heading_is_the_number_alone_on_its_line() -> None:
    """The body's own form — «Άρθρο 1» on one line, «Σκοπός» on the next.

    This is the shape the whole step rests on, so it is pinned before any
    decoy. If the pattern were loosened to accept a trailing title, every
    contents entry in the corpus would become an article and ν. 5110/2024 would
    report 164 articles instead of 82 — each duplicate carrying a different
    slice of text under the same citation.
    """
    headings = find_article_headings(document(BODY))

    assert [heading.number for heading in headings] == ["1", "2"]


def test_a_heading_carries_the_page_it_was_found_on_and_the_printed_number() -> None:
    """Each heading records its PDF page, its gazette page and its line index.

    Provenance has to be captured at the moment of the match, because nothing
    downstream can recover it: a list of article numbers cannot say which page
    to cite, and the line index is what step 5c slices the article's text at.
    Recovering either by re-scanning later would mean two pieces of code
    agreeing on the same pattern forever.
    """
    (heading,) = find_article_headings(document("πρόλογος\nΆρθρο 7\nΠόροι\n"))

    assert (heading.page, heading.gazette_page, heading.line) == (1, 3001, 1)


def test_a_contents_entry_keeps_its_title_on_the_heading_line() -> None:
    """«Άρθρο 1 Σκοπός» — one line — is a contents entry, not a heading.

    The gazette typesets the πίνακας περιεχομένων with the title on the same
    line as the number and the body with the title beneath it. ν. 5110/2024's
    contents list all 82 articles this way on PDF pages 1–3, so a pattern that
    tolerated the trailing title would find the act's full sequence twice and
    rule 3 could not tell the copies apart.
    """
    contents = "Άρθρο 1 Σκοπός\nΆρθρο 2 Αντικείμενο\n"

    assert find_article_headings(document(contents)) == []


def test_a_quoted_amendment_heading_is_not_an_article_of_this_act() -> None:
    """«Άρθρο 65Α» with the guillemet glued on is not a heading.

    ν. 5110/2024, PDF page 52: «Στον ν. 4442/1929 (Α’ 339) προστίθεται άρθρο
    65Α ως εξής:» followed by `«Άρθρο 65Α`. The article being printed belongs
    to ν. 4442/1929, not to ν. 5110/2024 — 34 such headings appear in that one
    document. Accepting them would file another act's provisions under this
    act's citation, which is worse than losing them: a retrieval hit on
    «ν. 5110/2024, άρθρο 65Α» would send a reader to a law that has no such
    article.

    The anchor at the start of the line is what refuses them, and this test is
    the record that it is doing so **by coincidence**: the gazette's habit of
    gluing the opening guillemet to the line start is what makes `^Άρθρο`
    sufficient, and nothing guarantees the next ΦΕΚ indents its quotations
    instead. If this test ever fails on a new document, the fix is not to patch
    the pattern — it is that the coincidence ran out.
    """
    quoted = (
        "Στον ν. 4442/1929 προστίθεται άρθρο 65Α ως εξής:\n«Άρθρο 65Α\nΑπαλλοτρίωση\n"
    )

    assert find_article_headings(document(BODY + quoted)) == find_article_headings(
        document(BODY)
    )


# ---------------------------------------------------------------------------
# Rule 2 — what follows: never another article reference
# ---------------------------------------------------------------------------


def test_a_heading_followed_by_another_article_reference_is_a_table_row() -> None:
    """«Άρθρο 18» followed by «Άρθρο 3 ν. 4443/2016…» is a correspondence row.

    π.δ. 62/2025's πίνακας κωδικοποιητικών διατάξεων (PDF pages 217–260) has
    two columns — this Code's article against the provision it replaced — so
    when the right-hand cell wraps, the left cell is left alone on a line and
    has a heading's exact shape. 88 rows do this.

    What refuses them is that the *next* line is another article reference,
    which a real heading's never is: a real heading is followed by its title or
    by its text. This single condition refuses 82 of the 88 and **refuses none
    of the 670 real articles in either document** — measured, not assumed. Rule
    1 alone would admit all 88 as articles of the Κώδικας.
    """
    table = "Άρθρο 18\nΆρθρο 3 ν. 4443/2016, όπως διαμορφώθηκε με την παρ. 1\n"

    assert find_article_headings(document(table)) == []
    assert rejected_heading_candidates(document(table)) == []


def test_the_plural_form_also_disqualifies_a_heading() -> None:
    """«Άρθρα 1 της Οδηγίας 2000/43/ΕΚ» counts as an article reference too.

    The same table cites EU directives in the plural, on PDF page 218. Matching
    only the singular would leave those rows looking like real articles, and
    they would then have to be caught by rule 3 — which works, but spends the
    non-local rule on a case a two-character pattern change handles.
    """
    table = "Άρθρο 16\nΆρθρα 1 της Οδηγίας 2000/43/ΕΚ\n"

    assert find_article_headings(document(table)) == []


def test_the_following_line_is_read_across_a_page_boundary() -> None:
    """A heading on a page's last line is judged by the next page's first line.

    Three headings in π.δ. 62/2025 are the final line of their page. Walking
    page by page would find no following line for them and accept them with
    rule 2 never applied — right by accident in those three cases, wrong by
    construction, and the kind of gap that surfaces as an inexplicable extra
    article on the first document that breaks the accident. Same reasoning as
    `dehyphenate` walking the document's lines as one sequence in step 4c.
    """
    assert find_article_headings(document("Άρθρο 18", "Άρθρο 3 ν. 4443/2016")) == []


def test_a_heading_on_the_documents_very_last_line_is_kept() -> None:
    """With no following line at all, there is nothing to disqualify a heading.

    Reached in practice because `strip_colophon` leaves the final page empty,
    so the real last line of text can be anything. Absent evidence is not
    evidence of a decoy, and the alternative — rejecting it — would silently
    drop a real final article. The run rule still has to agree with it.
    """
    headings = find_article_headings(document("Άρθρο 1\nΣκοπός\nΆρθρο 2"))

    assert [(heading.number, heading.line) for heading in headings] == [
        ("1", 0),
        ("2", 2),
    ]


# ---------------------------------------------------------------------------
# Rule 3 — the act's own numbering: one increasing run
# ---------------------------------------------------------------------------


def test_the_contents_sequence_loses_to_the_body_sequence() -> None:
    """When the same run appears twice, the later one is the body.

    π.δ. 62/2025 prints articles 1–588 in its contents and again in its body;
    ν. 5110/2024 prints 1–82 twice. Whenever a contents entry's title wraps to
    the next line it leaves a bare number behind that rules 1 and 2 both
    accept, so something has to choose between two runs of the same numbers.

    A tie goes to the later run because a table of contents always precedes
    what it indexes. Were the tie resolved the other way, both corpus documents
    would parse their contents page as the act and every article's text would
    be the few words of the next contents entry.
    """
    contents = "Άρθρο 1\nΣκοπός\nΆρθρο 2\nΑντικείμενο\n"
    headings = find_article_headings(document(contents, BODY))

    assert [heading.page for heading in headings] == [2, 2]


def test_a_wrapped_contents_entry_is_reported_as_rejected() -> None:
    """The three bare numbers π.δ. 62/2025's contents leaves behind are counted.

    PDF page 6 prints «Άρθρο 191» alone because the title «Κατ’ εξαίρεση
    απασχόληση την έκτη ημέρα…» was too long for the line, and page 75 prints
    the real άρθρο 191 the same way. **These two are byte-for-byte identical in
    the extracted text** — a number alone, then its title — so no rule that
    reads only those lines can separate them. They differ on the printed page
    (the body heading has 1.5× the page's median vertical gap above it and is
    centred in its column) and that information does not survive pypdf.

    This is why rule 3 exists and why these three are the cases that justify
    it. Three per document, dropped silently, are indistinguishable from three
    real articles the rules failed to match.
    """
    wrapped = "Άρθρο 191\nΚατ’ εξαίρεση απασχόληση την έκτη ημέρα\n"
    rejected = rejected_heading_candidates(document(wrapped, BODY))

    assert [(heading.number, heading.page) for heading in rejected] == [("191", 1)]


def test_a_correspondence_row_rule_two_misses_is_caught_by_the_numbering() -> None:
    """A table row whose second cell is not an article reference still falls out.

    Six of the 88 rows have a second column that rule 2 does not recognise —
    «Μέτρο εφαρμογής του», «ν. 4485/2017 (Α΄ 114)», «Π.Υ.Σ. 6/2012 (Α΄ 38)».
    Each would need its own pattern, which is how a parser turns into a pile of
    patches justified by one document. Rule 3 takes all six at once, because
    the table restarts its numbering below the body's last article.

    What separates the runs is that restart — the body ends at 588 and the next
    row is «Άρθρο 15» — so the fixture restarts too. A table whose first row
    happened to exceed the body's last article would *extend* the body's run
    instead of starting its own. The table being a re-listing of articles the
    act already contains is what makes that impossible here, not anything in
    the parser.

    The proportion is faithful as well: four body articles against two table
    rows, where the corpus has 588 against 88. A table listing every article of
    the act would tie with the body and win on recency — a real limitation, and
    one a correspondence table cannot exhibit, since it maps only the provisions
    that were codified from somewhere.
    """
    body = BODY + "Άρθρο 3\nΈδρα\nΆρθρο 4\nΠόροι\n"
    table = "Άρθρο 2\nΜέτρο εφαρμογής του\nΆρθρο 3\nΠ.Υ.Σ. 6/2012 (Α΄ 38)\n"
    headings = find_article_headings(document(body, table))

    assert [heading.number for heading in headings] == ["1", "2", "3", "4"]


def test_a_letter_suffixed_article_stays_inside_the_run() -> None:
    """3, 3Α, 4 is one increasing run, not two.

    Amendments insert articles between existing ones — this is why
    `Article.number` is a string rather than an int (V0). Neither corpus
    document has such an article in its own body, so the only evidence for this
    behaviour is legislative practice, and the cost of being wrong is
    asymmetric: ordering «3Α» before «3» would split the body run in two and
    the longer half would be reported as the whole act.
    """
    pages = "Άρθρο 3\nΤρίτο\nΆρθρο 3Α\nΤρίτο Α\nΆρθρο 4\nΤέταρτο\n"

    assert [heading.number for heading in find_article_headings(document(pages))] == [
        "3",
        "3Α",
        "4",
    ]


def test_a_document_with_no_headings_yields_nothing_rather_than_raising() -> None:
    """An empty document parses to no articles and no rejections.

    The colophon page that `strip_colophon` empties, and ν. 5110/2024's blank
    PDF page 59, both reach this function as pages with no text at all. The
    longest-run search over an empty candidate list is the one place an
    off-by-one would raise `IndexError` on perfectly ordinary input.
    """
    empty = document("", "ΕΦΗΜΕΡΙΔΑ ΤΗΣ ΚΥΒΕΡΝΗΣΕΩΣ\n")

    assert find_article_headings(empty) == []
    assert rejected_heading_candidates(empty) == []


# ---------------------------------------------------------------------------
# What none of the three rules can read
# ---------------------------------------------------------------------------


# Removed 2026-10-03 (step 5b-ii): `test_a_spelled_out_ordinal_heading_is_
# reported_as_unreadable` pinned step 5a's known gap — that «Άρθρο πρώτο» was
# counted and not captured. The gap is closed, so the assertion inverted. Both
# of its claims are now made elsewhere: the ordinals staying out of the act's
# own sequence by `test_the_acts_own_article_sequence_is_unaffected_by_an_
# instrument`, and the report's new contents by
# `test_a_mapped_ordinal_is_no_longer_reported_as_unreadable`.


def test_a_numbered_contents_entry_is_not_reported_as_unreadable() -> None:
    """«Άρθρο 1 Σκοπός» is a rejected decoy, not an unread numbering scheme.

    The two reports answer different questions and must not be merged.
    `unreadable_heading_lines` means "this document numbers articles in a way
    no rule here can read"; a contents entry is read perfectly well and
    deliberately discarded. Counting the corpus's 1 746 contents entries as
    unreadable would bury the 64 lines that actually are.
    """
    assert unreadable_heading_lines(document("Άρθρο 1 Σκοπός\n")) == {}


# ---------------------------------------------------------------------------
# Against the real corpus
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_each_corpus_act_parses_to_one_unbroken_article_sequence() -> None:
    """ν. 5110/2024 yields άρθρα 1–82 and π.δ. 62/2025 άρθρα 1–588.

    The unit tests above check each rule against hand-built pages; this one
    checks all three together against 320 pages of real gazette, where the
    decoys are mixed in with the body rather than isolated. Both counts are
    independently verifiable — each act's last contents entry is «Άρθρο 82
    Έναρξη ισχύος» and «Άρθρο 588 Έναρξη ισχύος» respectively — so this is a
    comparison against the document's own index, not against a number this
    parser produced once.

    A contiguous 1..N is a much stronger claim than a count: a decoy admitted
    into the run, or a real article missed, breaks the sequence even when the
    total happens to look right.
    """
    expected = {"fek_a_75_2024": 82, "fek_a_121_2025": 588}

    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        numbers = [heading.number for heading in find_article_headings(normalized)]

        assert numbers == [
            str(number) for number in range(1, expected[entry.id] + 1)
        ], entry.id


# ---------------------------------------------------------------------------
# A ratified instrument's own numbering (step 5b-ii)
# ---------------------------------------------------------------------------


STATUTE = (
    "Άρθρο 1\nΣκοπός\n"
    "Άρθρο 2\nΚαταστατικό\n"
    "Κυρώνεται το καταστατικό, το οποίο έχει ως εξής:\n"
    "«ΚΑΤΑΣΤΑΤΙΚΟ\n"
    "ΚΕΦΑΛΑΙΟ Α\u2019\n"
    "Άρθρο πρώτο\nΝομική μορφή\n"
    "Άρθρο δεύτερο\nΕπωνυμία\n"
    "Άρθρο 3\nΈδρα\n"
)
"""ν. 5110/2024's shape in miniature: άρθρο 2 ratifies a καταστατικό of its own.

The real document does this at άρθρο 13 — «Κυρώνεται το αρχικό καταστατικό του
Ελληνικού Κέντρου Αμυντικής Καινοτομίας, το οποίο έχει ως εξής:» then
`«ΚΑΤΑΣΤΑΤΙΚΟ`, a ΚΕΦΑΛΑΙΟ heading, and thirty articles numbered in words. The
intervening ΚΕΦΑΛΑΙΟ line is kept because it stands between the quotation's
opening line and the first ordinal, which is exactly the span the label search
has to cross.
"""


def test_a_compound_ordinal_adds_its_parts() -> None:
    """«δέκατο έκτο» is 16, and «εικοστό πέμπτο» 25.

    Additive composition is what lets one word table cover 1–99. The rejected
    alternative read the words positionally — «δέκατο» as a 1 in the tens
    column — which needs a second table and gets «εικοστό» standing alone
    wrong, since positionally that is a 2 with an empty units slot rather than
    20. Getting a composed ordinal wrong does not fail loudly: it produces a
    real-looking article number for a provision that is somewhere else.
    """
    assert ordinal_value("δέκατο έκτο") == 16
    assert ordinal_value("εικοστό πέμπτο") == 25
    assert ordinal_value("εικοστό") == 20


def test_eleven_and_twelve_are_single_words_not_compounds() -> None:
    """«ενδέκατο» is 11 and «δωδέκατο» is 12, from the table rather than a sum.

    Greek does not say «δέκατο πρώτο» for 11th, so these two carry a tens
    component inside one word and have to be literals. Both are in the corpus:
    ν. 5110/2024's καταστατικό prints them between δέκατο and δέκατο τρίτο. A
    table holding only 1–10 and the tens would return `None` for both and lose
    two provisions — visibly, via the unreadable report, but lose them.
    """
    assert ordinal_value("ενδέκατο") == 11
    assert ordinal_value("δωδέκατο") == 12


def test_an_ordinal_outside_the_table_returns_none_rather_than_a_number() -> None:
    """A word the table does not hold yields `None`, never a partial sum.

    The table stops at ενενηκοστό (90), so «εκατοστό» is unmapped by design —
    hundreds are left out until a document needs them. `None` is what makes
    that safe: the heading becomes unreadable and is *reported*, instead of
    being numbered from the half of it that happens to map.
    """
    assert ordinal_value("εκατοστό") is None
    assert ordinal_value("εκατοστό πρώτο") is None


def test_every_word_must_map_or_the_whole_heading_is_refused() -> None:
    """«τρίτο Έδρα» is not an ordinal, even though «τρίτο» is.

    The nine false positives the word table exists to kill. ν. 5110/2024's
    contents prints `Άρθρο τρίτο Έδρα`, `Άρθρο έκτο Διάρκεια`, `Άρθρο ένατο
    Έσοδα` — a heading's exact shape, because the title happens to be one word.
    Summing only the words that map would make `Άρθρο τρίτο Έδρα` the third
    article of an instrument and duplicate a provision under two addresses.
    """
    assert ordinal_value("τρίτο") == 3
    assert ordinal_value("τρίτο Έδρα") is None
    assert ordinal_value("έκτο Διάρκεια") is None


def test_the_word_table_is_case_sensitive() -> None:
    """A capitalised «Έκτο» does not map, because titles are capitalised.

    The second line of defence behind the closed vocabulary. Headings print the
    ordinal in lower case and titles start with a capital, so case-sensitivity
    refuses a title word that happens to be an ordinal — `Άρθρο δέκατο Έκτο`
    would otherwise read as 16 rather than as article 10 titled «Έκτο». Folding
    case for convenience would remove that for nothing.
    """
    assert ordinal_value("έκτο") == 6
    assert ordinal_value("Έκτο") is None


def test_a_ratified_instruments_articles_are_found_and_grouped() -> None:
    """The ordinals come back as one instrument, in document order.

    The step's headline behaviour. Grouped rather than flagged per heading: the
    instrument is one fact about thirty articles, and repeating it thirty times
    would allow thirty copies to disagree.
    """
    (instrument,) = find_instrument_headings(document(STATUTE))

    assert [heading.number for heading in instrument.headings] == [
        "πρώτο",
        "δεύτερο",
    ]


def test_the_instrument_is_attributed_to_the_article_that_ratified_it() -> None:
    """The ordinals under άρθρο 2 are recorded as ratified by άρθρο 2.

    Attribution is positional and has to be: a spelled-out ordinal does **not**
    imply a ratified instrument, because Greek ratification laws number their
    own articles πρώτο, δεύτερο, τρίτο — π.δ. 62/2025 cites «ΚΝΥ ΑΕ που
    κυρώθηκε με το άρθρο πρώτο του ν. 3850/2010», a top-level article. So
    notation cannot carry the distinction and position must.

    This number is also what the citation prints. Without it, «άρθρο δέκατο
    πέμπτο» has no resolvable address — see the step 5b-i domain tests.
    """
    (instrument,) = find_instrument_headings(document(STATUTE))

    assert instrument.ratifying_article == "2"


def test_the_label_is_the_line_that_opens_the_quotation() -> None:
    """«ΚΑΤΑΣΤΑΤΙΚΟ becomes the label ΚΑΤΑΣΤΑΤΙΚΟ, guillemet removed.

    The gazette marks an enacted instrument by quoting it, so the line naming
    it is the one carrying the opening guillemet — and the search is bounded to
    the span between the ratifying article and the instrument's first article,
    which over ν. 5110/2024 contains exactly one such line. An unbounded search
    would find the first of the 202 guillemets in that document.

    Recorded **as printed**, in the nominative. Turning it into the genitive a
    citation needs («του καταστατικού») is Greek morphology, which by the step
    5b-ii decision this module does not attempt — the corpus cites instruments
    of three genders and a hard-coded «του» would emit «του Σύμβασης».
    """
    (instrument,) = find_instrument_headings(document(STATUTE))

    assert instrument.label == "ΚΑΤΑΣΤΑΤΙΚΟ"


def test_the_acts_own_article_sequence_is_unaffected_by_an_instrument() -> None:
    """άρθρα 1–3 still come back contiguous with the ordinals interleaved.

    Why these are two functions rather than one list. In the real document the
    thirty ordinals sit between άρθρο 13 and άρθρο 14, so a single ordered list
    would read 1–13, πρώτο–τριακοστό, 14–82 and the contiguity invariant — step
    5a's strongest check — could no longer be stated. Keeping the namespaces
    apart keeps both provable.
    """
    assert [heading.number for heading in find_article_headings(document(STATUTE))] == [
        "1",
        "2",
        "3",
    ]


def test_an_ordinal_before_the_acts_first_article_is_skipped() -> None:
    """With no preceding article, there is nothing that could have ratified it.

    Skipping is the conservative half of the choice; the other half would
    invent a ratifying article and emit a citation pointing at an article that
    does not exist — the exact bug step 5b removes. Not reachable in this
    corpus, since the contents' ordinal entries are all refused by the word
    table, so this pins the behaviour rather than a known case.
    """
    assert find_instrument_headings(document("Άρθρο πρώτο\nΝομική μορφή\n")) == []


def test_a_document_with_no_instrument_yields_no_instruments() -> None:
    """π.δ. 62/2025's case: 588 articles and nothing ratified.

    The common case, and the one a grouping function can get wrong by returning
    a single empty instrument instead of no instruments at all — which would
    give step 7 a `ratifying_article` to attach to provisions that have none.
    """
    assert find_instrument_headings(document(BODY)) == []


def test_a_mapped_ordinal_is_no_longer_reported_as_unreadable() -> None:
    """«Άρθρο πρώτο» is read now, so it leaves the unreadable report.

    Step 5a reported all 60 of ν. 5110/2024's ordinal heading lines as
    unreadable, correctly at the time. Leaving them there once they parse would
    make the report claim the pipeline cannot read lines it reads — and a report
    that overstates what is missing gets ignored as fast as one that understates
    it. The corpus count drops 64 → 4, and the four that remain are «Άρθρο
    μόνο», the sole-article form, which is still unread.
    """
    assert unreadable_heading_lines(document(STATUTE)) == {}
    assert unreadable_heading_lines(document("Άρθρο μόνο ν. 690/1945\n")) == {
        "Άρθρο μόνο ν. 690/1945": 1
    }


def test_a_digit_heading_that_runs_on_into_prose_is_not_reported() -> None:
    """`Άρθρο 3, όπως διαμορφώθηκε` is a digit form, comma and all.

    A regression caught by measurement while writing this step. The digit
    exclusion tests the **first character**, not the whole first token; a version
    requiring a clean number took the corpus's unreadable count from 4 to 167,
    pulling in every correspondence-table row whose number is followed by a
    comma or a lower-case letter — `Άρθρο 3, όπως διαμορφώθηκε και`, `Άρθρο 5α
    π.δ. 1/1990`. 163 lines of noise would have buried the four that matter.
    """
    noisy = "Άρθρο 3, όπως διαμορφώθηκε και\nΆρθρο 5α π.δ. 1/1990\n"

    assert unreadable_heading_lines(document(noisy)) == {}


@pytest.mark.slow
def test_the_katastatiko_parses_to_thirty_contiguous_articles() -> None:
    """ν. 5110/2024 yields one instrument, ratified by άρθρο 13, άρθρα 1–30.

    The same proof the act's own sequence gets, applied to the second
    namespace: «πρώτο» … «τριακοστό» mapping to exactly 1..30 with no gap and
    no repeat, independently checkable against the contents page, which lists
    thirty. It also pins that π.δ. 62/2025 has no instrument — a rule that
    found one there would be reading its correspondence table as enacted text.
    """
    found = {}
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        found[entry.id] = find_instrument_headings(normalized)

    assert found["fek_a_121_2025"] == []

    (instrument,) = found["fek_a_75_2024"]
    assert instrument.label == "ΚΑΤΑΣΤΑΤΙΚΟ"
    assert instrument.ratifying_article == "13"
    assert [ordinal_value(h.number) for h in instrument.headings] == list(range(1, 31))


@pytest.mark.slow
def test_what_the_corpus_leaves_behind_is_the_size_it_was_measured_at() -> None:
    """9 rejected candidates and 4 unreadable heading lines, as measured.

    A regression fence around the two reports rather than around the parse. The
    numbers themselves carry no meaning; what they pin is that a future change
    cannot quietly move provisions between "parsed", "rejected" and "unread". A
    rule 1 loosened to admit contents entries, for instance, keeps the article
    sequence intact — rule 3 still finds the body — while inflating the rejected
    list from 9 to 91, and nothing else in the suite would notice.

    The 9 are three wrapped contents entries and six correspondence rows whose
    second cell rule 2 does not recognise. The 4 unreadable lines are all
    «Άρθρο μόνο» rows in π.δ. 62/2025's correspondence table — the sole-article
    form, a numbering scheme neither 5a nor 5b-ii reads. It was 64 before
    5b-ii; the 60 that left were ν. 5110/2024's ΚΑΤΑΣΤΑΤΙΚΟ headings, counted
    once in the contents and once in the body, which now parse.
    """
    rejected = 0
    unreadable = 0
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        rejected += len(rejected_heading_candidates(normalized))
        unreadable += sum(unreadable_heading_lines(normalized).values())

    assert (rejected, unreadable) == (9, 4)
