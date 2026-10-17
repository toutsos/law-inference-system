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
    ArticleHeading,
    ArticleText,
    container_paths,
    find_article_headings,
    find_article_texts,
    find_instrument_headings,
    find_instrument_texts,
    line_coverage,
    numbering_breaks,
    ordinal_value,
    rejected_heading_candidates,
    split_paragraphs,
    unreadable_container_lines,
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
    """ν. 5110/2024 yields άρθρα 1–82 and π.δ. 62/2025 άρθρα 1–588 plus 141Α.

    The unit tests above check each rule against hand-built pages; this one
    checks all three together against 320 pages of real gazette, where the
    decoys are mixed in with the body rather than isolated. Both counts are
    independently verifiable — each act's last contents entry is «Άρθρο 82
    Έναρξη ισχύος» and «Άρθρο 588 Έναρξη ισχύος» respectively — so this is a
    comparison against the document's own index, not against a number this
    parser produced once. The decree's 589th heading is άρθρο 141Α, an inserted
    article its contents page also lists.

    A contiguous 1..N is a much stronger claim than a count: a decoy admitted
    into the run, or a real article missed, breaks the sequence even when the
    total happens to look right.
    """
    expected = {"fek_a_75_2024": 82, "fek_a_121_2025": 589}

    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        headings = find_article_headings(normalized)

        assert numbering_breaks(headings) == [], entry.id
        assert len(headings) == expected[entry.id], entry.id


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


# ---------------------------------------------------------------------------
# Step 5c — where an article's text ends, and what of it is the title
# ---------------------------------------------------------------------------


def test_an_articles_text_runs_from_its_title_to_the_next_heading() -> None:
    """The slice is heading-exclusive at the start and at the end.

    The baseline behaviour everything else here refines. If the end were off by
    one heading, άρθρο 1 would carry άρθρο 2's provisions under άρθρο 1's
    citation — the phantom-article failure again, this time produced by the
    slicer rather than by a decoy, and equally invisible in the output.
    """
    page = (
        "Άρθρο 1\nΣκοπός\nΣκοπός του παρόντος είναι:\nΆρθρο 2\nΑντικείμενο\nκείμενο.\n"
    )

    first, second = find_article_texts(document(page))

    assert first.title == "Σκοπός"
    assert first.text == "Σκοπός του παρόντος είναι:"
    assert second.title == "Αντικείμενο"


def test_the_text_keeps_the_line_breaks_it_was_extracted_with() -> None:
    """Lines are joined with newlines, not reflowed into prose.

    Step 5d finds numbered paragraphs by a line-initial «1.», so reflowing the
    span into one blob here would destroy the only signal the next step has.
    Joining is 5d's decision to make after it has used the line starts, and a
    change that "tidies" the text into a single line would break 5d silently
    rather than loudly.
    """
    page = (
        "Άρθρο 1\nΣκοπός\n1. πρώτη παράγραφος\n2. δεύτερη παράγραφος\nΆρθρο 2\nΤέλος\n"
    )

    (first, _) = find_article_texts(document(page))

    assert first.text == "1. πρώτη παράγραφος\n2. δεύτερη παράγραφος"


def test_a_container_heading_does_not_end_up_in_the_previous_article() -> None:
    """ΜΕΡΟΣ Γ’ and its title are trimmed off the article before it.

    The gazette prints a container heading between two articles, so the lines
    belong to neither; 59 spans across the corpus end this way. Left in, every
    ΜΕΡΟΣ and ΚΕΦΑΛΑΙΟ title becomes the closing sentence of whatever article
    happened to precede it — text that reads as enacted provision and is a
    section header, which is exactly the kind of wrongness no test downstream
    can see.
    """
    page = (
        "Άρθρο 1\nΣκοπός\nΣκοπός του παρόντος είναι:\n"
        "ΜΕΡΟΣ Γ’\nΕΚΣΥΓΧΡΟΝΙΣΜΟΣ ΘΕΣΜΙΚΟΥ ΠΛΑΙΣΙΟΥ\n"
        "Άρθρο 2\nΑντικείμενο\nκείμενο.\n"
    )

    (first, _) = find_article_texts(document(page))

    assert first.text == "Σκοπός του παρόντος είναι:"


def test_an_annex_announced_by_the_article_stays_inside_it() -> None:
    """π.δ. 62/2025 άρθρο 490: the ΠΑΡΑΡΤΗΜΑ *is* the provision.

    «Προσαρτάται και αποτελεί αναπόσπαστο μέρος του παρόντος Υποκεφαλαίου το
    ακόλουθο παράρτημα:» — 226 lines follow, and an earlier version of the cut
    rule treated `ΠΑΡΑΡΤΗΜΑ` as a block boundary everywhere and dropped every
    one of them, along with the 85-line compensation table of άρθρο 333. That
    is the one error direction with no recovery: under-cutting leaves a long
    span the coverage report shouts about, while over-cutting deletes enacted
    law quietly. Annex markers therefore end an article only in the document's
    final span.
    """
    page = (
        "Άρθρο 1\nΠαράρτημα\nΠροσαρτάται το ακόλουθο παράρτημα:\n"
        "ΠΑΡΑΡΤΗΜΑ\nΔιατάξεις αναφοράς\nΆρθρο 2\nΤέλος\nκείμενο.\n"
    )

    (first, _) = find_article_texts(document(page))

    assert (
        first.text
        == "Προσαρτάται το ακόλουθο παράρτημα:\nΠΑΡΑΡΤΗΜΑ\nΔιατάξεις αναφοράς"
    )


def test_the_enactment_formula_ends_the_last_article() -> None:
    """«Παραγγέλλομε τη δημοσίευση…» is where ν. 5110/2024's body stops.

    The last article's span has no next heading to end it, so it otherwise
    absorbs the rest of the document — for ν. 5110/2024 that is 72 lines of
    signature block: the date, the President, twenty ministers. Those lines
    would be chunked and embedded as the text of «άρθρο 82 Έναρξη ισχύος», so a
    question about when the law takes effect would retrieve a list of
    ministers.
    """
    page = (
        "Άρθρο 1\nΣκοπός\nκείμενο.\n"
        "Άρθρο 2\nΈναρξη ισχύος\nΗ ισχύς του παρόντος αρχίζει.\n"
        "Παραγγέλλομε τη δημοσίευση του παρόντος\nΑθήνα, 24 Μαΐου 2024\n"
    )

    (_, last) = find_article_texts(document(page))

    assert last.text == "Η ισχύς του παρόντος αρχίζει."


def test_a_trailing_table_ends_the_body_of_a_decree() -> None:
    """π.δ. 62/2025 ends in a ΠΙΝΑΚΑΣ, not in an enactment formula.

    Its άρθρο 588 span is 2 342 lines of which 2 are law; the rest is the
    πίνακας κωδικοποιητικών διατάξεων — the same table rule 2 spends its
    existence refusing as a source of phantom headings, which would arrive here
    a second time as άρθρο 588's text. A π.δ. prints no «Παραγγέλλομε», so the
    formula alone does not close the body and the annex markers are needed in
    the final span.
    """
    page = (
        "Άρθρο 1\nΣκοπός\nκείμενο.\n"
        "Άρθρο 2\nΈναρξη ισχύος\nΗ ισχύς αρχίζει.\n"
        "ΠΙΝΑΚΑΣ ΚΩΔΙΚΟΠΟΙΗΤΙΚΩΝ ΔΙΑΤΑΞΕΩΝ\nΆρθρο 1 Άρθρο 648 ΑΚ\n"
    )

    (_, last) = find_article_texts(document(page))

    assert last.text == "Η ισχύς αρχίζει."


def test_a_wrapped_title_is_joined_back_into_one_phrase() -> None:
    """A title printed over two lines is one title, not a title plus a sentence.

    74% of ν. 5110/2024's titles wrap. Taking only the first line would leave
    «Σύσταση Ελληνικού Κέντρου Αμυντικής» as the title of άρθρο 3 and push
    «Καινοτομίας» into the text, so the title shown beside a retrieved chunk
    would be a fragment and the provision's text would open with a stray word.
    """
    page = (
        "Άρθρο 3\nΣύσταση Ελληνικού Κέντρου Αμυντικής\nΚαινοτομίας\n"
        "1. Συστήνεται ανώνυμη εταιρεία.\nΆρθρο 4\nΤέλος\nκείμενο.\n"
    )

    (first, _) = find_article_texts(document(page))

    assert first.title == "Σύσταση Ελληνικού Κέντρου Αμυντικής Καινοτομίας"
    assert first.text == "1. Συστήνεται ανώνυμη εταιρεία."


def test_a_numbered_paragraph_ends_the_title() -> None:
    """«1.» is proof the title is over, and proof there was none when it is first.

    The strongest of the three signals, and the only one that is not a
    threshold: a line opening a numbered paragraph cannot be part of a heading.
    Without it a one-line title followed by a short «1. …» line would absorb
    the first paragraph of the provision into the title field.
    """
    titled = "Άρθρο 1\nΣκοπός\n1. Σκοπός είναι:\nΆρθρο 2\nΤέλος\nκείμενο.\n"

    (first, _) = find_article_texts(document(titled))

    assert (first.title, first.text) == ("Σκοπός", "1. Σκοπός είναι:")


def test_a_full_width_line_is_text_even_when_it_follows_a_title_line() -> None:
    """A line at the column's full width was wrapped by the typesetter, not centred.

    Titles are centred and therefore break early — measured maximum 47
    characters, median 26–35 — while body lines are justified to roughly 51.
    The threshold sits at 44 because that is where the measured error count is
    lowest, and the test pins the discrimination rather than the number: a
    second title line is short, a first text line is not.
    """
    page = (
        "Άρθρο 209\nΕξαιρέσεις για ορισμένες Κυριακές\n"
        "εμπορικά καταστήματα που λειτουργούν προαιρετικά\n"
        "τις Κυριακές, σύμφωνα με τις διατάξεις.\nΆρθρο 210\nΤέλος\nκείμενο.\n"
    )

    (first, _) = find_article_texts(document(page))

    assert first.title == "Εξαιρέσεις για ορισμένες Κυριακές"
    assert first.text.startswith("εμπορικά καταστήματα")


def test_a_line_ending_in_a_full_stop_is_text_however_short_it_is() -> None:
    """A title never ends in sentence punctuation; a short closing line does.

    Without this, the last wrapped line of a one-sentence article — «μισθός.»,
    seven characters, well under any width threshold — reads as the second line
    of the title, and the article's own concluding word disappears from its
    text. Adding the rule removed every such case across the corpus but one.
    """
    page = (
        "Άρθρο 3\nΈλλειψη συμφωνίας για το μισθό\n"
        "Αν η εργασία παρέχεται μόνο με μισθό, λογίζεται\nμισθός.\n"
        "Άρθρο 4\nΤέλος\nκείμενο.\n"
    )

    (first, _) = find_article_texts(document(page))

    assert first.title == "Έλλειψη συμφωνίας για το μισθό"
    assert first.text.endswith("μισθός.")


def test_a_ratifying_article_does_not_absorb_the_instrument_it_enacts() -> None:
    """άρθρο 13's text is its ratification clause, not the whole καταστατικό.

    The two namespaces interleave by position, so the instrument's headings are
    boundaries for the body article too: without them άρθρο 13's span is 1 188
    lines of ν. 5110/2024 — thirty articles of a company statute filed as the
    text of one article of the law, every provision in it citable only as
    «άρθρο 13» and the instrument's own thirty articles duplicated beside it.
    """
    page = (
        "Άρθρο 12\nΠόροι\nκείμενο.\n"
        "Άρθρο 13\nΚαταστατικό\nΚυρώνεται το καταστατικό, ως εξής:\n«ΚΑΤΑΣΤΑΤΙΚΟ\n"
        "Άρθρο πρώτο\nΝομική μορφή\nΤο ΕΛΚΑΚ λειτουργεί.\n"
        "Άρθρο δεύτερο\nΕπωνυμία\nΗ επωνυμία είναι.\n"
        "Άρθρο 14\nΛοιπά\nκείμενο.\n"
    )

    body = find_article_texts(document(page))
    (instrument,) = find_instrument_texts(document(page))

    ratifying = next(article for article in body if article.heading.number == "13")
    assert ratifying.text == "Κυρώνεται το καταστατικό, ως εξής:\n«ΚΑΤΑΣΤΑΤΙΚΟ"
    assert instrument.label == "ΚΑΤΑΣΤΑΤΙΚΟ"
    assert instrument.ratifying_article == "13"
    assert [(a.heading.number, a.title) for a in instrument.articles] == [
        ("πρώτο", "Νομική μορφή"),
        ("δεύτερο", "Επωνυμία"),
    ]
    assert instrument.articles[-1].text == "Η επωνυμία είναι."


def test_every_line_of_the_document_is_accounted_for() -> None:
    """The four coverage buckets add up to the document's line count.

    The 5c analogue of step 5a's contiguity check: an arithmetic identity no
    silent drop can satisfy. A slicer that lost a page, double-counted a span
    or trimmed into the void would still return plausible articles — but the
    sum would stop matching, which is why the report is a tested invariant
    rather than a debugging aid.
    """
    page = (
        "περιεχόμενα\nΆρθρο 1\nΣκοπός\nκείμενο.\n"
        "ΜΕΡΟΣ Β’\nΤΙΤΛΟΣ\nΆρθρο 2\nΤέλος\nΗ ισχύς αρχίζει.\n"
        "Παραγγέλλομε τη δημοσίευση"  # no trailing newline: it would add an empty line
    )

    coverage = line_coverage(document(page))

    assert coverage.balances
    assert (coverage.front_matter, coverage.between_articles, coverage.trailing) == (
        1,
        2,
        1,
    )


@pytest.mark.slow
def test_the_corpus_slices_at_the_sizes_it_was_measured_at() -> None:
    """94.1% and 87.4% of corpus lines land inside an article, as measured.

    A regression fence on the whole of 5c in one number per document. Every
    boundary rule moves these: dropping the instrument boundaries inflates
    ν. 5110/2024's article lines by 1 183, dropping the final-span rule inflates
    π.δ. 62/2025's by 2 338, and trimming containers too eagerly deflates both.
    The three spans that drove the design are pinned beside them, because a
    share can stay still while two errors cancel.
    """
    sliced = {}
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        sliced[entry.id] = (
            find_article_texts(normalized),
            line_coverage(normalized),
        )

    law, decree = sliced["fek_a_75_2024"], sliced["fek_a_121_2025"]

    assert all(coverage.balances for _, coverage in sliced.values())
    assert (law[1].front_matter, law[1].between_articles, law[1].trailing) == (
        277,
        39,
        72,
    )
    assert (
        decree[1].front_matter,
        decree[1].between_articles,
        decree[1].trailing,
    ) == (744, 183, 2338)

    lines = {article.heading.number: article.text.count("\n") + 1 for article in law[0]}
    assert (lines["13"], lines["82"]) == (3, 3)
    assert (
        next(
            article.text.count("\n") + 1
            for article in decree[0]
            if article.heading.number == "588"
        )
        == 2
    )


@pytest.mark.slow
def test_the_katastatiko_articles_carry_their_own_titles_and_text() -> None:
    """All thirty instrument articles come out with a title and non-empty text.

    The namespace step 5b went to the trouble of separating is only worth
    separating if its provisions are readable, and «Σύνθεση του Διοικητικού
    Συμβουλίου» — άρθρο δέκατο πέμπτο — is the provision the V2 note has used
    since 2026-09-07 to state why one ΦΕΚ carries two numberings. An empty text
    here would mean the second namespace is located and lost.
    """
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        if entry.id != "fek_a_75_2024":
            continue
        normalized = normalize_document(extract_document(entry))
        (instrument,) = find_instrument_texts(normalized)

    assert len(instrument.articles) == 30
    assert all(article.title for article in instrument.articles)
    assert all(article.text for article in instrument.articles)

    fifteenth = instrument.articles[14]
    assert fifteenth.heading.number == "δέκατο πέμπτο"
    assert fifteenth.title == "Σύνθεση του Διοικητικού Συμβουλίου"


@pytest.mark.slow
def test_one_corpus_title_is_known_to_swallow_a_line_of_law() -> None:
    """π.δ. 62/2025 άρθρο 209 is the measured failure of the title rule.

    Recorded as a known defect rather than left to be discovered: its first
    text line is 33 characters and ends in no punctuation, so nothing
    distinguishes it from a wrapped title and «Επιτρέπεται η απασχόληση των
    εργαζομένων σε» is filed as part of the title. The text still begins mid
    sentence, so the provision loses its opening clause in the field a reader
    checks a citation against — one article in 670, against 614 titles the rule
    gets exactly right. If a future change fixes it, this test fails and the
    V2 note's debt entry comes out.
    """
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        if entry.id != "fek_a_121_2025":
            continue
        articles = find_article_texts(normalize_document(extract_document(entry)))

    article = next(a for a in articles if a.heading.number == "209")

    assert article.title is not None
    assert article.title.endswith("Επιτρέπεται η απασχόληση των εργαζομένων σε")
    assert article.text.startswith("εμπορικά καταστήματα")


# ---------------------------------------------------------------------------
# An inserted article's number (5a amendment, 2026-10-17)
# ---------------------------------------------------------------------------


def test_an_inserted_article_number_is_read_with_or_without_a_space() -> None:
    """π.δ. 62/2025 prints «Άρθρο 141 Α», and it is an article of the Code.

    Found by measuring for step 5d: the original pattern accepted `141Α` glued
    but not `141 Α` spaced, so άρθρο 141Α's 204 lines were filed as the tail of
    άρθρο 141 — which is also why that article appeared to carry two complete
    paragraph runs, 1–12 and then 1–9 again.

    Nothing caught it. The sequence check still passed, because an article that
    was never found is not *missing from* a run; and
    `unreadable_heading_lines` skips the line because the character after
    «Άρθρο » is a digit. The number is stored glued whichever way it is
    printed, so one spelling reaches `SourceReference` and the retrieval key.
    """
    spaced = "Άρθρο 141\nΤίτλος\nκείμενο.\nΆρθρο 141 Α\nΤίτλος\nκείμενο.\n"

    headings = find_article_headings(document(spaced))

    assert [heading.number for heading in headings] == ["141", "141Α"]


def test_a_correspondence_row_naming_an_inserted_article_is_still_refused() -> None:
    """«Άρθρο 141 Α Άρθρο 15 ν. 5163/2024» is a table row, not a heading.

    The three lookalikes the widened pattern has to keep refusing, all from
    π.δ. 62/2025's πίνακας κωδικοποιητικών διατάξεων — this one, `Άρθρο 4 Υ Α
    19040/1981` (a Υ.Α., not an article 4Υ) and `Άρθρο 71 Α Άρθρο 543`. Rule
    1's closing anchor is what refuses them, which is why the space was allowed
    only between the digits and a single letter: `^Άρθρο \\d+ [Α-Ω]$` matches
    exactly one line in the whole corpus, the real heading on PDF page 60.
    """
    rows = (
        "Άρθρο 141 Α Άρθρο 15 ν. 5163/2024 άρθρα 5 και 6 Οδηγίας (ΕΕ)\n"
        "Άρθρο 4 Υ Α 19040/1981, όπως διαμορφώθηκε με το άρθρο\n"
        "Άρθρο 71 Α Άρθρο 543\n"
    )

    assert find_article_headings(document(rows)) == []


def test_numbering_breaks_accepts_an_insertion_and_reports_a_gap() -> None:
    """141, 141Α, 142 is unbroken; a jump to 144 is not.

    The contiguity claim had been written as `numbers == [str(n) for n in
    range(...)]` in the probe and the corpus test, which άρθρο 141Α breaks — the
    corpus's one legitimate insertion would have been reported as a parse
    failure, and the pressure then is to weaken the check that catches decoys.
    Stating the rule once, as a function, is what lets it be right about both.
    """
    headings = find_article_headings(
        document("Άρθρο 1\nΤ\nκ.\nΆρθρο 1Α\nΤ\nκ.\nΆρθρο 2\nΤ\nκ.\n")
    )
    assert numbering_breaks(headings) == []

    gapped = [
        ArticleHeading(number=number, page=1, gazette_page=3001, line=0)
        for number in ("1", "2", "4")
    ]
    assert numbering_breaks(gapped) == ["4"]


# ---------------------------------------------------------------------------
# Step 5d — numbered paragraphs inside one article
# ---------------------------------------------------------------------------


def article(text: str, number: str = "1") -> ArticleText:
    """An ArticleText carrying `text`, for the paragraph splitter to cut.

    `split_paragraphs` takes the article rather than a bare string because the
    numbering restarts per article, so these tests construct the smallest thing
    that carries that boundary. The title is set to something non-empty so a
    test can never pass because the title was accidentally None.
    """
    return ArticleText(
        heading=ArticleHeading(number=number, page=1, gazette_page=3001, line=0),
        title="Τίτλος",
        text=text,
    )


def test_numbered_paragraphs_split_at_their_markers_and_drop_the_number() -> None:
    """«1. …» and «2. …» become two paragraphs whose text omits the marker.

    The unit a citation names. Without the split, «άρθρο 141 παρ. 2» can only
    be answered with the whole article — up to 263 lines — and step 6 has no
    boundary to chunk on but line count, which is the fixed-size cutting the
    chunking step exists to avoid.

    The marker is dropped from the text because the number is kept in the
    field: two copies of one fact are two things that can disagree, and step 7
    renders «παρ. 2» from the field.
    """
    split = split_paragraphs(
        article("1. Πρώτη παράγραφος.\nσυνέχεια.\n2. Δεύτερη παράγραφος.")
    )

    assert [(p.number, p.text) for p in split.paragraphs] == [
        ("1", "Πρώτη παράγραφος.\nσυνέχεια."),
        ("2", "Δεύτερη παράγραφος."),
    ]


def test_text_before_the_first_marker_is_an_unnumbered_paragraph() -> None:
    """An article's lead-in is kept, with number None.

    23 articles in the corpus open with unnumbered text before «1.» — π.δ.
    62/2025's άρθρο 141Α begins «Ειδικά για τη διεξαγωγή … ισχύουν τα εξής:».
    Dropping it would lose the sentence that governs how every numbered
    paragraph below it is read, and attaching it to παρ. 1 would cite it as
    παρ. 1, which is a different provision.
    """
    split = split_paragraphs(article("Ισχύουν τα εξής:\n1. Πρώτη.\n2. Δεύτερη."))

    assert [(p.number, p.text) for p in split.paragraphs] == [
        (None, "Ισχύουν τα εξής:"),
        ("1", "Πρώτη."),
        ("2", "Δεύτερη."),
    ]


def test_an_article_with_no_markers_is_one_unnumbered_paragraph() -> None:
    """253 corpus articles print no paragraph number at all.

    The V0 domain model already documents `number is None` as citing with no
    παρ. component — «ν. 5110/2024, άρθρο 1» is the complete and correct
    citation for such an article. Returning zero paragraphs instead would make
    the article's text unreachable through the paragraph layer everything
    downstream reads.
    """
    split = split_paragraphs(article("Σκοπός του παρόντος είναι:\nα) η ανάπτυξη."))

    assert [(p.number, p.text) for p in split.paragraphs] == [
        (None, "Σκοπός του παρόντος είναι:\nα) η ανάπτυξη.")
    ]


def test_a_date_opening_a_wrapped_line_is_not_a_paragraph_marker() -> None:
    """«8.4.2023, ήτοι από την έναρξη ισχύος» is a date, not παρ. 8.

    36 such lines in the corpus. The shape rule refuses them on the required
    whitespace after the full stop, before any counting happens — a paragraph
    marker is always followed by a space, a date never is.
    """
    split = split_paragraphs(
        article("1. Η ισχύς αρχίζει από την\n8.4.2023, ήτοι από την έναρξη ισχύος.")
    )

    assert [p.number for p in split.paragraphs] == ["1"]
    assert split.refused_markers == []


def test_a_time_that_reads_as_the_expected_number_is_still_not_a_marker() -> None:
    """π.δ. 62/2025 άρθρο 170: «05.00» arrived exactly where παρ. 5 was due.

    The case that decided the shape rule. `int("05")` is 5, so the sequence
    rule accepted the time as παρ. 5 and then refused the article's real παρ. 5
    — one provision renumbered and one lost, with a contiguous run to show for
    it. A decoy filter that only works when the decoy's number is wrong is
    luck; requiring the space is the rule.
    """
    split = split_paragraphs(
        article(
            "1. Πρώτη.\n2. Δεύτερη.\n3. Τρίτη.\n4. Τέταρτη.\n"
            "05.00, ανεξαρτήτως ώρας έναρξης και λήξης βάρδιας\n"
            "5. Πέμπτη."
        )
    )

    assert [p.number for p in split.paragraphs] == ["1", "2", "3", "4", "5"]
    assert split.paragraphs[-1].text.startswith("Πέμπτη")


def test_a_bare_table_row_number_is_not_a_paragraph_marker() -> None:
    """π.δ. 62/2025 άρθρο 503 is a table, and «2.» is its Α/Α column.

    Its 418 lines are a classification table whose row numbers the extraction
    serialises alone on a line, between the rows' prose. Read as paragraphs
    they would cut the table into pieces numbered as provisions; refused, the
    article is one unnumbered paragraph holding the table, which is what it is.
    """
    split = split_paragraphs(
        article("Πίνακας ειδικοτήτων\nΤμήματος Ηλεκτρολογίας\n2.\nΚτηνοτροφία")
    )

    assert [p.number for p in split.paragraphs] == [None]
    assert split.refused_markers == []


def test_a_wrapped_article_reference_is_not_a_marker_and_stays_in_its_sentence() -> (
    None
):
    """«… του άρθρου» / «105.» is a cross-reference whose number wrapped.

    π.δ. 62/2025's άρθρο 95: the sentence of παρ. 1 ends on a line reading just
    `105.`, which has a marker's exact shape. Two things have to hold at once —
    it must not open a paragraph, and it must stay inside παρ. 1, because it is
    the end of that provision's sentence. Nothing follows the full stop, so the
    shape rule refuses it before the sequence rule is consulted, which is why
    it is not in `refused_markers`: the line was never a candidate, and nothing
    was dropped.
    """
    split = split_paragraphs(
        article(
            "1. Εφαρμόζεται σύμφωνα με την περ. γ) του άρθρου\n105.\n2. Δεν εφαρμόζεται:"
        )
    )

    assert [p.number for p in split.paragraphs] == ["1", "2"]
    assert split.refused_markers == []
    assert split.paragraphs[0].text.endswith("105.")


def test_a_wrapped_reference_with_prose_after_it_is_refused_and_reported() -> None:
    """«83. Χρέη εισηγητή και γραμματέα ασκούν υπάλληλοι» is the same decoy, dressed.

    10 of these in the corpus. Here the wrapped article number is followed by
    the next sentence on the same line, so it passes the shape rule and only
    the article's own run can refuse it — άρθρο 91 expects παρ. 2, not παρ. 83.
    It is reported, because a refused marker that is really a paragraph and one
    that is really a reference look identical once dropped, and only one of
    those is acceptable.
    """
    split = split_paragraphs(
        article(
            "1. Στην Κεντρική Υπηρεσία συστήνεται επιτροπή του άρθρου\n"
            "83. Χρέη εισηγητή και γραμματέα ασκούν υπάλληλοι.\n"
            "2. Με απόφαση του Υπουργού."
        )
    )

    assert [p.number for p in split.paragraphs] == ["1", "2"]
    assert split.refused_markers == [
        "83. Χρέη εισηγητή και γραμματέα ασκούν υπάλληλοι."
    ]


def test_an_amended_acts_paragraphs_are_suppressed_and_reported() -> None:
    """ν. 5110/2024 άρθρο 61 reprints ν.δ. 398/1974's paragraphs in guillemets.

    The step 5a problem one level down: the markers inside the quotation are
    **another act's**, and admitting them files ν.δ. 398/1974's provisions
    under «ν. 5110/2024, άρθρο 61 παρ. 2». Measured without the quotation rule,
    the sequence rule took the quoted παρ. 2–8 as this article's own and
    refused its real παρ. 2 — not a near miss, an inversion.

    172 markers across 30 articles of that act are suppressed this way, against
    0 in π.δ. 62/2025, which codifies and amends nothing. They are reported
    because that count is the evidence the rule is doing work.
    """
    split = split_paragraphs(
        article(
            "1. Το άρθρο 17 του ν.δ. 398/1974 αντικαθίσταται ως εξής:\n"
            "«Άρθρο 17\n"
            "1. Για τον προσδιορισμό του ύψους του βοηθήματος\n"
            "2. Με απόφαση του Υπουργού\n"
            "3. Η ως άνω απόφαση.»\n"
            "2. Η ισχύς του παρόντος αρχίζει από 1.1.2023."
        )
    )

    assert [p.number for p in split.paragraphs] == ["1", "2"]
    assert len(split.quoted_markers) == 3
    assert split.paragraphs[1].text.startswith("Η ισχύς")


def test_the_quotation_scope_resets_at_every_article() -> None:
    """A ratification quotation spans articles, and must not silence them.

    ν. 5110/2024's άρθρο 13 opens «ΚΑΤΑΣΤΑΤΙΚΟ and the closing guillemet lands
    1 183 lines later inside the instrument's άρθρο τριακοστό. Carrying
    quotation depth across articles would leave all thirty of the καταστατικό's
    articles permanently inside a quotation — and every one of them with no
    paragraphs at all, which is a worse failure than the one rule 2 prevents.

    Depth starting at 0 per article is also what bounds the failure mode step
    5a rejected document-wide: an unmatched guillemet can cost this article's
    paragraphs, never the rest of the document's.
    """
    opening = split_paragraphs(article("Κυρώνεται το καταστατικό:\n«ΚΑΤΑΣΤΑΤΙΚΟ", "13"))
    inside = split_paragraphs(
        article("1. Εκτός από την πτώχευση.\n2. Η εκκαθάριση.»", "τριακοστό")
    )

    assert [p.number for p in opening.paragraphs] == [None]
    assert [p.number for p in inside.paragraphs] == ["1", "2"]


def test_a_refused_marker_does_not_invalidate_what_follows_it() -> None:
    """After a refusal the expectation still points at the next real number.

    If a refused marker advanced the count, one decoy would push every
    following paragraph out of the run and an article would lose everything
    after its first oddity — the cascade failure `numbering_breaks` avoids at
    article level, avoided here at paragraph level for the same reason.
    """
    split = split_paragraphs(
        article("1. Πρώτη.\n83. Χρέη εισηγητή.\n2. Δεύτερη.\n3. Τρίτη.")
    )

    assert [p.number for p in split.paragraphs] == ["1", "2", "3"]
    assert split.refused_markers == ["83. Χρέη εισηγητή."]


def test_an_article_with_no_text_yields_no_paragraphs() -> None:
    """Empty text produces an empty list, not a paragraph holding nothing.

    No corpus article is empty today — the shortest has two lines — but a
    `Paragraph` with empty text would be a citable provision with no content,
    which is worse than an article that visibly has none. The boundary is
    pinned so a future source cannot introduce one quietly.
    """
    assert split_paragraphs(article("")).paragraphs == []


def test_a_paragraph_whose_case_is_glued_to_the_marker_is_still_read() -> None:
    """«1.α) Κάθε εργοδότης …» — no space, and still παρ. 1.

    Two lines in the corpus print the marker this way, and each cost more than
    itself: missing άρθρο 578's «1.α)» meant παρ. 1 was never accepted, so
    παρ. 2 and παρ. 3 did not continue any run and were refused too — one
    unparsed marker taking a whole article's structure with it. The same
    happened to άρθρο 571's «3.α)», which cost παραγράφους 4, 5 and 6.

    The case letter stays in the paragraph's text, since περιπτώσεις are not
    parsed yet and dropping it would lose the only mark of where περ. α΄ begins.
    """
    split = split_paragraphs(
        article("1.α) Κάθε εργοδότης αναρτά τους όρους.\n2. Για κάθε μεταβολή.")
    )

    assert [(p.number, p.text) for p in split.paragraphs] == [
        ("1", "α) Κάθε εργοδότης αναρτά τους όρους."),
        ("2", "Για κάθε μεταβολή."),
    ]


def test_a_run_that_does_not_start_at_one_is_refused_and_reported() -> None:
    """ν. 5110/2024's άρθρο τέταρτο prints an unnumbered lead, then «2.», «3.».

    The honest cost of requiring the run to start at 1, pinned so it stays a
    recorded choice. Both markers are refused, the article becomes one
    unnumbered paragraph, and nothing is lost — the text is all there and the
    two refusals are reported.

    The alternative was measured: accepting whatever number the first marker
    carries parses π.δ. 62/2025's άρθρο 503 — a classification table — as
    παραγράφους 4 to 8, inventing five provisions that cite cleanly. Under-
    reading one article is recoverable; inventing five is not.
    """
    split = split_paragraphs(
        article("Σκοπός του Κέντρου είναι:\nα) Η παρακολούθηση.\n2. Για την επιδίωξη.")
    )

    assert [p.number for p in split.paragraphs] == [None]
    assert split.refused_markers == ["2. Για την επιδίωξη."]


@pytest.mark.slow
def test_the_corpus_splits_into_the_paragraph_counts_it_was_measured_at() -> None:
    """2 136 paragraphs, 25 refused markers, 172 suppressed as another act's.

    One regression fence over all three rules at corpus scale. Each number
    moves for a different reason: loosening the shape rule inflates the
    paragraph count with dates and table rows, dropping the quotation rule
    moves 172 markers from `quoted` into the paragraph count *and* inverts
    ν. 5110/2024's άρθρο 61, and weakening the sequence rule empties
    `refused_markers`.

    The split between documents is itself the evidence: an amending law quotes
    other acts constantly (172 suppressed markers in 30 articles) and a
    codification quotes none (0).
    """
    totals = {}
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        articles = [
            *find_article_texts(normalized),
            *(a for g in find_instrument_texts(normalized) for a in g.articles),
        ]
        splits = [split_paragraphs(a) for a in articles]
        totals[entry.id] = (
            sum(len(s.paragraphs) for s in splits),
            sum(len(s.refused_markers) for s in splits),
            sum(len(s.quoted_markers) for s in splits),
        )

    assert totals["fek_a_75_2024"] == (259, 2, 172)
    assert totals["fek_a_121_2025"] == (1877, 23, 0)


# ---------------------------------------------------------------------------
# Step 5e — the container path
# ---------------------------------------------------------------------------


def path_of(document: ExtractedDocument, number: str) -> list[str]:
    """The container path of one article, as «KIND NUMBER» strings.

    Comparing rendered strings rather than StructuralUnit objects keeps each
    assertion readable as the chain it is describing; the titles are checked
    separately, where that is what the test is about.
    """
    paths = container_paths(document)
    heading = next(key for key in paths if key.number == number)
    return [f"{unit.kind} {unit.number}" for unit in paths[heading]]


CONTAINED = (
    "ΜΕΡΟΣ Α’\nΣΚΟΠΟΣ\nΆρθρο 1\nΣκοπός\nκείμενο.\n"
    "ΜΕΡΟΣ Β’\nΡΥΘΜΙΣΕΙΣ\nΚΕΦΑΛΑΙΟ Α’\nΓΕΝΙΚΑ\nΆρθρο 2\nΤίτλος\nκείμενο.\n"
    "ΚΕΦΑΛΑΙΟ Β’\nΕΙΔΙΚΑ\nΆρθρο 3\nΤίτλος\nκείμενο.\n"
)
"""Two ΜΕΡΟΣ, two ΚΕΦΑΛΑΙΟ, three articles — the shape both acts print."""


def test_a_container_heading_is_its_number_alone_on_its_line() -> None:
    """«ΜΕΡΟΣ Α’» then its title beneath, exactly as the body prints it.

    The containers are the only place the document says what an article is
    *about*: an article's own text often never names its subject. Without them
    `Article.path` stays empty, a chunk reaches V3 with no subject context, and
    [[V5 - Hybrid Retrieval]] has nothing to filter «what does the Code say
    about leave» against.
    """
    assert path_of(document(CONTAINED), "1") == ["ΜΕΡΟΣ Α’"]
    assert path_of(document(CONTAINED), "2") == ["ΜΕΡΟΣ Β’", "ΚΕΦΑΛΑΙΟ Α’"]


def test_a_contents_entry_keeps_its_title_on_the_container_line() -> None:
    """«ΜΕΡΟΣ ΣΤ’ ΤΕΛΙΚΕΣ, ΜΕΤΑΒΑΤΙΚΕΣ…» is the πίνακας περιεχομένων.

    The same shape rule that separates an article heading from its contents
    entry, and it has to hold here for the same reason: the contents lists
    every container in reverse-chronological nonsense order relative to the
    body, so admitting those entries would push the whole act under whichever
    container the contents happened to list last. 16 such lines in
    ν. 5110/2024 and 83 in π.δ. 62/2025.
    """
    contents = (
        "ΜΕΡΟΣ ΣΤ’ ΤΕΛΙΚΕΣ, ΜΕΤΑΒΑΤΙΚΕΣ, ΕΞΟΥΣΙΟΔΟΤΙΚΕΣ\n"
        "Άρθρο 78 Εξουσιοδοτικές διατάξεις\n"
        "ΜΕΡΟΣ Α’\nΣΚΟΠΟΣ\nΆρθρο 1\nΣκοπός\nκείμενο.\nΆρθρο 2\nΤίτλος\nκείμενο.\n"
    )

    assert path_of(document(contents), "1") == ["ΜΕΡΟΣ Α’"]


def test_the_containers_before_the_first_article_belong_to_the_body() -> None:
    """The act's opening containers are printed *above* άρθρο 1, not after it.

    ΜΕΡΟΣ Α’ sits two lines before άρθρο 1 in ν. 5110/2024; ΒΙΒΛΙΟ ΠΡΩΤΟ and
    ΜΕΡΟΣ Α’ five and three lines before it in π.δ. 62/2025. An early version of
    this scan started at the first article heading and left **15 articles with
    an empty path** for that reason alone — the act's whole first part
    unlabelled, with nothing failing.
    """
    assert path_of(document(CONTAINED), "1") == ["ΜΕΡΟΣ Α’"]


def test_a_container_title_is_every_line_until_the_next_heading() -> None:
    """A wrapped container title is one title, joined.

    Measured 1–4 lines across the corpus — ΜΕΡΟΣ Γ’ of ν. 5110/2024 takes four.
    Nothing but the title can appear between a container heading and the next
    heading, which is why this needs none of the width and punctuation signals
    an article title needs.
    """
    wrapped = (
        "ΜΕΡΟΣ Γ’\nΕΚΣΥΓΧΡΟΝΙΣΜΟΣ ΘΕΣΜΙΚΟΥ ΠΛΑΙΣΙΟΥ\n"
        "ΑΝΩΤΑΤΩΝ ΣΤΡΑΤΙΩΤΙΚΩΝ ΕΚΠΑΙΔΕΥΤΙΚΩΝ\nΙΔΡΥΜΑΤΩΝ\n"
        "Άρθρο 1\nΤίτλος\nκείμενο.\nΆρθρο 2\nΤίτλος\nκείμενο.\n"
    )

    paths = container_paths(document(wrapped))
    (unit,) = next(path for path in paths.values())

    assert unit.title == (
        "ΕΚΣΥΓΧΡΟΝΙΣΜΟΣ ΘΕΣΜΙΚΟΥ ΠΛΑΙΣΙΟΥ ΑΝΩΤΑΤΩΝ ΣΤΡΑΤΙΩΤΙΚΩΝ ΕΚΠΑΙΔΕΥΤΙΚΩΝ ΙΔΡΥΜΑΤΩΝ"
    )


def test_an_outer_container_closes_the_ones_inside_it() -> None:
    """ΜΕΡΟΣ Β’ ends ΚΕΦΑΛΑΙΟ Α’; it does not nest under it.

    The rank is what makes a flat sequence of headings into a tree. Without the
    pop, every container ever opened would stay in the path and άρθρο 3 would
    claim to be inside ΚΕΦΑΛΑΙΟ Α’ of a ΜΕΡΟΣ that ended pages earlier — a path
    that is wrong in a way no count or sum can detect, because it is the right
    length and full of real containers.
    """
    sequence = (
        "ΜΕΡΟΣ Α’\nΠΡΩΤΟ\nΚΕΦΑΛΑΙΟ Α’\nΓΕΝΙΚΑ\nΆρθρο 1\nΤ\nκ.\n"
        "ΜΕΡΟΣ Β’\nΔΕΥΤΕΡΟ\nΆρθρο 2\nΤ\nκ.\nΆρθρο 3\nΤ\nκ.\n"
    )

    assert path_of(document(sequence), "1") == ["ΜΕΡΟΣ Α’", "ΚΕΦΑΛΑΙΟ Α’"]
    assert path_of(document(sequence), "2") == ["ΜΕΡΟΣ Β’"]


def test_a_container_of_the_same_level_replaces_its_predecessor() -> None:
    """ΚΕΦΑΛΑΙΟ Β’ succeeds ΚΕΦΑΛΑΙΟ Α’ rather than nesting inside it."""
    assert path_of(document(CONTAINED), "3") == ["ΜΕΡΟΣ Β’", "ΚΕΦΑΛΑΙΟ Β’"]


def test_a_number_with_a_space_before_its_ordinal_mark_is_read() -> None:
    """π.δ. 62/2025 prints «ΜΕΡΟΣ Γ ’», and dropping it would move 80 articles.

    Found by probe while measuring for this step, like «Άρθρο 141 Α» before it.
    A pattern requiring the mark to touch the letter misses this heading, and
    then every article from ΔΙΟΙΚΗΤΙΚΗ ΕΠΟΠΤΕΙΑ ΤΗΣ ΕΡΓΑΣΙΑΣ onwards inherits
    the previous ΜΕΡΟΣ and is filed under ΕΡΓΑΤΙΚΟ ΑΤΥΧΗΜΑ — a plausible path,
    which is why nothing else could catch it.

    The number is stored with the space removed, so one spelling reaches every
    filter and every golden file.
    """
    spaced = "ΜΕΡΟΣ Γ ’\nΔΙΟΙΚΗΤΙΚΗ ΕΠΟΠΤΕΙΑ\nΆρθρο 1\nΤ\nκ.\nΆρθρο 2\nΤ\nκ.\n"

    assert path_of(document(spaced), "1") == ["ΜΕΡΟΣ Γ’"]


def test_roman_latin_and_spelled_out_container_numbers_are_read() -> None:
    """ΤΜΗΜΑ Ι, ΤΜΗΜΑ IV, ΜΕΡΟΣ E’, ΒΙΒΛΙΟ ΠΡΩΤΟ — all four notations.

    The corpus mixes scripts *inside one numbering*: π.δ. 62/2025 writes ΤΜΗΜΑ
    Ι, ΙΙ, ΙΙΙ with the Greek iota and ΤΜΗΜΑ IV, V with Latin letters, and
    ν. 5110/2024 prints ΜΕΡΟΣ E’ with a Latin E. Step 4's `residual_confusables`
    reported none of them, because it skips tokens with no Greek letter at all —
    its recorded debt. Refusing them here would drop three real containers to
    make a point about encoding, so the numbers are read as printed and the
    fold stays step 4's problem.
    """
    mixed = (
        "ΒΙΒΛΙΟ ΠΡΩΤΟ\nΑΤΟΜΙΚΟ ΔΙΚΑΙΟ\nΜΕΡΟΣ E’\nΛΟΙΠΕΣ\n"
        "ΤΜΗΜΑ IV\nΑΠΟΣΠΑΣΗ\nΆρθρο 1\nΤ\nκ.\nΆρθρο 2\nΤ\nκ.\n"
    )

    assert path_of(document(mixed), "1") == [
        "ΒΙΒΛΙΟ ΠΡΩΤΟ",
        "ΜΕΡΟΣ E’",
        "ΤΜΗΜΑ IV",
    ]


def test_a_ratified_instruments_containers_stay_out_of_the_acts_path() -> None:
    """The καταστατικό's ΚΕΦΑΛΑΙΟ is the statute's, not the law's.

    Two stacks, one per numbering namespace — the third time this document's two
    namespaces force the same answer. Under a single stack the instrument's
    articles come out as [ΜΕΡΟΣ Β’ (the law's), ΚΕΦΑΛΑΙΟ Α’ (the statute's)],
    two documents' structure in one chain, and the act's own next article keeps
    the statute's chapter unless a container of equal or outer rank happens to
    follow immediately. In ν. 5110/2024 one does — ΜΕΡΟΣ Γ’ — so a single stack
    is right there **by luck**, which is exactly what this test removes.

    A path is containment within one namespace; what ties the instrument to the
    act is `RatifiedInstrument.ratifying_article`, recorded in step 5b-i.
    """
    both = (
        "ΜΕΡΟΣ Β’\nΤΟ ΚΕΝΤΡΟ\n"
        "Άρθρο 1\nΣκοπός\nκείμενο.\n"
        "Άρθρο 2\nΚαταστατικό\nΚυρώνεται ως εξής:\n«ΚΑΤΑΣΤΑΤΙΚΟ\n"
        "ΚΕΦΑΛΑΙΟ Α’\nΝΟΜΙΚΗ ΜΟΡΦΗ\nΆρθρο πρώτο\nΝομική μορφή\nκείμενο.\n"
        "ΚΕΦΑΛΑΙΟ Β’\nΟΡΓ ΑΝΑ\nΆρθρο δεύτερο\nΔιοίκηση\nκείμενο.»\n"
        "ΚΕΦΑΛΑΙΟ Α’\nΑΛΛΑ\nΆρθρο 3\nΛοιπά\nκείμενο.\n"
    )

    assert path_of(document(both), "2") == ["ΜΕΡΟΣ Β’"]
    assert path_of(document(both), "πρώτο") == ["ΚΕΦΑΛΑΙΟ Α’"]
    assert path_of(document(both), "δεύτερο") == ["ΚΕΦΑΛΑΙΟ Β’"]
    assert path_of(document(both), "3") == ["ΜΕΡΟΣ Β’", "ΚΕΦΑΛΑΙΟ Α’"]


def test_a_container_number_with_no_rule_is_reported() -> None:
    """A notation the pattern cannot read is named, not skipped.

    The report the corpus proved it needs twice over: «Άρθρο 141 Α» passed
    `numbering_breaks` and `unreadable_heading_lines` alike, and «ΜΕΡΟΣ Γ ’»
    would have moved 80 articles under the wrong ΜΕΡΟΣ. A missing container
    leaves a path that is *plausible* — right length, real containers, wrong
    subject — so nothing downstream can notice it. A digit-numbered ΜΕΡΟΣ and a
    book number outside the five-word table are both unread today.
    """
    odd = "ΜΕΡΟΣ 7\nΑΓΝΩΣΤΟ\nΒΙΒΛΙΟ ΕΒΔΟΜΟ\nΑΓΝΩΣΤΟ\nΆρθρο 1\nΤ\nκ.\nΆρθρο 2\nΤ\nκ.\n"

    assert unreadable_container_lines(document(odd)) == {
        "ΜΕΡΟΣ 7": 1,
        "ΒΙΒΛΙΟ ΕΒΔΟΜΟ": 1,
    }


def test_a_contents_entry_with_a_one_word_title_is_not_reported() -> None:
    """«ΚΕΦΑΛΑΙΟ Α’ ΑΠΕΡΓΙΑ» is a contents entry, and it nearly polluted the report.

    The real near-miss: with the report's bound set on word count rather than
    length, π.δ. 62/2025's shortest contents entry was listed as an unreadable
    heading. One false entry in a report of two is enough to make the report
    worthless, which is why the bound is «short enough to be a number and
    nothing else» — nine characters here against ΜΕΡΟΣ Γ ’'s two.
    """
    assert unreadable_container_lines(document("ΚΕΦΑΛΑΙΟ Α’ ΑΠΕΡΓΙΑ\n")) == {}


@pytest.mark.slow
def test_every_corpus_article_gets_the_container_path_it_was_measured_with() -> None:
    """All 701 articles carry a non-empty path, and nothing is unreadable.

    The end-to-end claim for 5e, and the counts are the fence: 112 paths for
    ν. 5110/2024 at depth 1–2, 589 for π.δ. 62/2025 at depth 2–5. An article
    with an empty path means a container was missed before it; an unreadable
    line means one was missed outright. One full path is spelled out because a
    depth is not a check — ΤΜΗΜΑ ΙΙ and ΚΕΦΑΛΑΙΟ Ε’ are what make άρθρο 219
    about Sunday work rather than about something else four levels up.
    """
    found = {}
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        found[entry.id] = (
            container_paths(normalized),
            unreadable_container_lines(normalized),
        )

    for paths, unreadable in found.values():
        assert unreadable == {}
        assert all(paths.values())

    law, decree = found["fek_a_75_2024"][0], found["fek_a_121_2025"][0]
    assert (len(law), len(decree)) == (112, 589)
    assert {len(path) for path in law.values()} == {1, 2}
    assert {len(path) for path in decree.values()} == {2, 3, 4, 5}

    heading = next(key for key in decree if key.number == "219")
    assert [f"{unit.kind} {unit.number}" for unit in decree[heading]] == [
        "ΒΙΒΛΙΟ ΠΡΩΤΟ",
        "ΜΕΡΟΣ Δ’",
        "ΤΜΗΜΑ ΙΙ",
        "ΚΕΦΑΛΑΙΟ Ε’",
    ]
