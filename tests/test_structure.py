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


def test_a_spelled_out_ordinal_heading_is_reported_as_unreadable() -> None:
    """«Άρθρο πρώτο» is counted, not captured — the known gap of this slice.

    Άρθρο 13 of ν. 5110/2024 ratifies a ΚΑΤΑΣΤΑΤΙΚΟ whose own thirty articles
    are numbered in words, so «άρθρο 15» and «άρθρο δέκατο πέμπτο» are
    different provisions of the same ΦΕΚ. This slice reads only digits, and
    that limit has to be loud: thirty provisions absent from the parse with
    nothing reporting their absence is exactly the silent corpus loss this
    version exists to prevent.
    """
    statute = "«ΚΑΤΑΣΤΑΤΙΚΟ\nΆρθρο πρώτο\nΝομική μορφή\n"
    unreadable = unreadable_heading_lines(document(BODY + statute))

    assert find_article_headings(document(BODY + statute)) == find_article_headings(
        document(BODY)
    )
    assert unreadable == {"Άρθρο πρώτο": 1}


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


@pytest.mark.slow
def test_what_the_corpus_leaves_behind_is_the_size_it_was_measured_at() -> None:
    """9 rejected candidates and 64 unreadable heading lines, as measured.

    A regression fence around the two reports rather than around the parse. The
    numbers themselves carry no meaning; what they pin is that a future change
    cannot quietly move provisions between "parsed", "rejected" and "unread". A
    rule 1 loosened to admit contents entries, for instance, keeps the article
    sequence intact — rule 3 still finds the body — while inflating the rejected
    list from 9 to 91, and nothing else in the suite would notice.

    The 9 are three wrapped contents entries and six correspondence rows whose
    second cell rule 2 does not recognise. The 64 unreadable lines are the
    thirty ΚΑΤΑΣΤΑΤΙΚΟ articles of ν. 5110/2024 counted twice — contents and
    body — plus four «Άρθρο μόνο» rows in π.δ. 62/2025's correspondence table,
    the sole-article form and a third numbering scheme this slice cannot read.
    """
    rejected = 0
    unreadable = 0
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        rejected += len(rejected_heading_candidates(normalized))
        unreadable += sum(unreadable_heading_lines(normalized).values())

    assert (rejected, unreadable) == (9, 64)
