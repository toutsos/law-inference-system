"""Character-level normalization: NFC plus script-aware confusable folding.

Almost every string in this file is a real token from the corpus, taken from
the confusable census in the V2 note (step 4). Synthetic examples would prove
the function does what it was written to do; these prove it does what the two
ΦΕΚ in `data/raw/` actually require. The one constructed token says so in its
own docstring.
"""

import unicodedata

import pytest

from greek_law.ingestion import DEFAULT_MANIFEST_PATH, load_manifest
from greek_law.ingestion.extraction import (
    ExtractedDocument,
    ExtractedPage,
    extract_document,
)
from greek_law.ingestion.normalization import (
    dehyphenate,
    normalize_characters,
    normalize_document,
    normalize_whitespace,
    residual_confusables,
    residual_line_hyphens,
    strip_colophon,
    strip_running_header,
)

INCREMENT = "∆"
"""MATHEMATICAL INCREMENT — what stands in for Δ in ν. 5110/2024's header."""


def test_a_decomposed_vowel_is_composed() -> None:
    """«Μαΐου» written as iota + combining acute comes back precomposed.

    Greek has two encodings for every accented vowel. Both render identically,
    so a corpus holding one and a query holding the other look equal to a human
    and unequal to `==`, to a BM25 index and to a database. V5's lexical
    retrieval would miss the provision and report no match rather than an
    error — the failure nobody debugs because nothing looks broken.
    """
    decomposed = unicodedata.normalize("NFD", "Μαΐου")

    assert decomposed != "Μαΐου", "fixture is not actually decomposed"
    assert normalize_characters(decomposed) == "Μαΐου"


def test_composition_happens_before_the_fold_not_after() -> None:
    """A combining mark does not split the word it sits in.

    A combining mark is not alphabetic, so it ends a letter-like run: on
    decomposed input the fold would see «AΒι» and «ΓΔΕΖ» as two words, count
    two Latin letters against one Greek in the first, and resolve it *to Latin*
    — rewriting the Greek ι as `i`. One Greek letter in, one Latin letter out,
    from a word that is plainly Greek when read whole. The token is constructed
    rather than quoted: the mechanism is what matters, and the consequence is
    that the fold decides a word's script on the strength of half its letters.
    """
    decomposed = unicodedata.normalize("NFD", "ABΐΓΔΕΖ")

    assert normalize_characters(decomposed) == unicodedata.normalize("NFC", "ΑΒΐΓΔΕΖ")


def test_the_increment_sign_folds_to_greek_delta() -> None:
    """«ΕΦΗΜΕΡΙ∆Α» with a maths operator comes back as Greek «ΕΦΗΜΕΡΙΔΑ».

    This is the most common confusable in the corpus (60 occurrences) and the
    one a rule built on character classes walks straight past: U+2206 is
    category Sm, so `"∆".isalpha()` is False. Left in place it poisons the
    running header on every page of ν. 5110/2024, and any later rule that
    strips the header by matching on «ΕΦΗΜΕΡΙΔΑ» fails on that document only.
    """
    assert normalize_characters("ΕΦΗΜΕΡΙ" + INCREMENT + "Α") == "ΕΦΗΜΕΡΙΔΑ"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ΚΕΦAΛΑΙΟ", "ΚΕΦΑΛΑΙΟ"),
        ("Tμήματος", "Τμήματος"),
        ("στoν", "στον"),
        ("ΔΙΑΚΡIΣΕΩΝ", "ΔΙΑΚΡΙΣΕΩΝ"),
        ("IΙΙ", "ΙΙΙ"),
    ],
)
def test_a_latin_letter_inside_a_greek_word_folds_to_greek(
    raw: str, expected: str
) -> None:
    """Greek words typeset with a stray Latin homoglyph come back all Greek.

    Each of these is a real token from the corpus. `ΚΕΦAΛΑΙΟ` is the dangerous
    one: step 5 finds structural headings by matching «ΚΕΦΑΛΑΙΟ», so a Latin
    `A` in one heading drops a whole chapter of the Κώδικας Εργατικού Δικαίου
    out of the parsed hierarchy — not with an error, with a smaller tree.
    """
    assert normalize_characters(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("(ΑCCRUED", "(ACCRUED"), ("(Βig", "(Big")],
)
def test_a_greek_letter_inside_an_english_word_folds_the_other_way(
    raw: str, expected: str
) -> None:
    """English words whose first letter is Greek are repaired towards Latin.

    These two tokens are why the fold is not a Latin-to-Greek character map.
    Such a map would produce «ΑΓΓΡΥΕΔ»-shaped garbage: a token in no language,
    matching neither a Greek query nor an English one, and unrecognisable to
    the human reading the output during step 10's manual QA.
    """
    assert normalize_characters(raw) == expected


def test_a_latin_word_hyphenated_onto_a_greek_acronym_is_left_alone() -> None:
    """«e-Ε.Φ.Κ.Α.» keeps its Latin `e`.

    The `e` is a genuine Latin letter in the official name of the service, and
    it is surrounded by Greek. The hyphen is the only thing separating it from
    `ΚΕΦAΛΑΙΟ`, which must be folded. Fold this one and the corpus no longer
    contains the string a user types to find it.
    """
    assert normalize_characters("e-Ε.Φ.Κ.Α.") == "e-Ε.Φ.Κ.Α."


def test_an_even_split_goes_to_greek() -> None:
    """«ΣT’» — one Greek letter, one Latin — comes back Greek.

    The corpus is Greek legislation, so an unresolvable tie is far more likely
    to be a mis-typeset Greek word than an English one. Deciding ties towards
    Latin would corrupt the enumerator «ΣΤ’», which labels paragraph lists
    throughout both documents.
    """
    assert normalize_characters("ΣT’") == "ΣΤ’"


def test_a_latin_letter_greek_does_not_have_is_kept() -> None:
    """«ΙV» stays mixed, because Greek has no V.

    The run resolves to Greek, and a fold that forced every character to the
    winning script would have to invent a mapping for `V`. Roman numerals
    appear in the corpus; silently rewriting one to a Greek lookalike would
    change a cross-reference's meaning.
    """
    assert normalize_characters("ΙV") == "ΙV"


def test_an_acronym_cut_into_single_letters_is_not_folded() -> None:
    """«Α.Σ.Ε.I.» keeps its Latin `I` — an accepted miss, pinned on purpose.

    The full stops cut the acronym into one-character runs, and a lone Latin
    letter is read as Latin. This is a false negative, not a corruption, and
    the exact same mechanism is what protects `e-Ε.Φ.Κ.Α.` above. The test
    exists so that anyone who later "fixes" it is told, by a failing test,
    which protection they are trading away.
    """
    assert normalize_characters("Α.Σ.Ε.I.") == "Α.Σ.Ε.I."


def test_digits_punctuation_and_whitespace_survive_unchanged() -> None:
    """Everything that is not letter-like passes through byte for byte.

    Normalization runs before parsing, so it sees «Άρθρο 13» and «παρ. 2»
    before anything has read them. A fold that touched digits, braces or
    newlines would corrupt article numbers and page geometry at the one point
    in the pipeline where there is no way left to check them against the PDF.
    """
    raw = "Άρθρο 13\n{εγγυημένο}  παροχή},\t«ΦΕΚ» Α’ 75/24.05.2024\n"

    assert normalize_characters(raw) == raw


def test_residual_confusables_reports_what_the_fold_deliberately_left() -> None:
    """The Latin letters still sitting in Greek words are counted, not hidden.

    Two misses are accepted by design (above), so the pipeline must say so out
    loud. Silence here would read as "nothing left to fix" rather than "not
    attempted", and the next person would trust exact matching on tokens that
    are still mixed-script.
    """
    folded = normalize_characters("ΙV και ΙΙΙ")

    assert residual_confusables(folded) == {"V": 1}


def test_fully_folded_text_has_no_residue() -> None:
    """Text the fold could repair completely reports an empty counter.

    If the counter reported leftovers for text that is already clean, it would
    cry wolf on every run and stop being read — which is the same outcome as
    not having it.
    """
    assert residual_confusables(normalize_characters("ΚΕΦAΛΑΙΟ Β")) == {}


def test_residual_confusables_counts_tokens_not_just_mixed_words() -> None:
    """«e-Ε.Φ.Κ.Α.» reports its `e`, even though the fold was right to keep it.

    Both accepted misses are single-script *runs* inside a mixed-script
    *token* — which is precisely why the fold left them alone. A counter that
    looked at runs rather than whitespace tokens would therefore report zero
    residue for exactly the cases it exists to surface, and V5 would index a
    token no Greek query matches while the pipeline said nothing was left.
    """
    assert residual_confusables(normalize_characters("e-Ε.Φ.Κ.Α.")) == {"e": 1}


def _document(*texts: str) -> ExtractedDocument:
    return ExtractedDocument(
        document_id="synthetic",
        pages=[
            ExtractedPage(number=number, text=text)
            for number, text in enumerate(texts, start=1)
        ],
    )


def test_every_page_is_normalized_and_page_numbers_are_preserved() -> None:
    """Each page's text is folded; `number` and `document_id` are untouched.

    Page numbers are the spine of provenance: step 4's line pass recovers the
    printed gazette number per page, and V6 cites it. A copy that renumbered
    pages, or dropped one, would produce citations that are well-formed and
    point at the wrong page — V1's fabricated-citation failure, one layer down.
    """
    document = _document("ΚΕΦAΛΑΙΟ", "ΕΦΗΜΕΡΙ" + INCREMENT + "Α")

    normalized = normalize_document(document)

    assert normalized.document_id == "synthetic"
    assert [page.number for page in normalized.pages] == [1, 2]
    assert [page.text for page in normalized.pages] == ["ΚΕΦΑΛΑΙΟ", "ΕΦΗΜΕΡΙΔΑ"]


def test_the_original_document_is_not_modified() -> None:
    """Normalization returns a new document and leaves its input intact.

    The V2 decision is that normalization returns the same *type* rather than a
    `NormalizedDocument`, so nothing in the type system distinguishes raw text
    from normalized text — pipeline order carries that guarantee. The copy is
    what keeps that honest: if normalization mutated in place, a caller holding
    what it believes is raw text would be holding folded text instead, and no
    test downstream could tell.
    """
    document = _document("ΚΕΦAΛΑΙΟ")

    normalize_document(document)

    assert document.pages[0].text == "ΚΕΦAΛΑΙΟ"


@pytest.mark.slow
def test_the_real_corpus_folds_down_to_three_known_safe_characters() -> None:
    """Over both ΦΕΚ, the only residue is `e`, `I` and `V`.

    The unit tests above check the rule against hand-picked tokens; this one
    checks that no *other* confusable is hiding in 1.48 M characters of real
    gazette text. A new document whose typesetter reached for a different
    homoglyph — or a fold table edited without re-measuring — shows up here as
    an unexpected character rather than as mis-matched queries in V5.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    residue: dict[str, int] = {}
    for document in manifest.documents:
        normalized = normalize_document(extract_document(document))
        for page in normalized.pages:
            for character, count in residual_confusables(page.text).items():
                residue[character] = residue.get(character, 0) + count

    assert set(residue) <= {"e", "I", "V"}, residue


ONE_LINE_HEADER = "ΕΦΗΜΕΡΙΔΑ  T ΗΣ ΚΥΒΕΡΝΗΣΕΩΣ3188 Τεύχος A’ 75/24.05.2024"
"""ν. 5110/2024, PDF page 6: the whole header on one line, number glued on."""

THREE_LINE_HEADER = "ΕΦΗΜΕΡΙΔΑ ΤΗΣ ΚΥΒΕΡΝΗΣΕΩΣ\n2924\nΤεύχος A’ 121/11.07.2025"
"""π.δ. 62/2025, PDF page 60: the same furniture, extracted as three lines."""


def test_a_one_line_header_is_removed_and_its_page_number_recovered() -> None:
    """ν. 5110/2024's header goes, and «3188» comes back as data.

    The gazette page number is inside the furniture being deleted, and V6 has to
    cite it — PDF page 6 prints «3188». Delete the line without reading it and
    the only remaining page number is the PDF index, which would produce
    citations that are well-formed, confident and off by 3182.
    """
    page = f"{ONE_LINE_HEADER}\n4. Το συνδυασμένο ποσοστό της συμμετοχής"

    assert strip_running_header(page) == (
        3188,
        "4. Το συνδυασμένο ποσοστό της συμμετοχής",
    )


def test_the_page_number_glued_to_the_following_word_is_recovered_too() -> None:
    """«ΚΥΒΕΡΝΗΣΕΩΣ 3189Τεύχος» yields 3189, not 75 and not nothing.

    The number fuses to whichever neighbour the typesetter left it next to, and
    which side that is alternates with the left/right page layout — 30 of
    ν. 5110/2024's pages glue it backwards, 28 forwards. A rule that found the
    number by splitting on whitespace would work on half the document.
    """
    page = "ΕΦΗΜΕΡΙΔΑ  T ΗΣ ΚΥΒΕΡΝΗΣΕΩΣ 3189Τεύχος A’ 75/24.05.2024\nΆμυνας"

    assert strip_running_header(page) == (3189, "Άμυνας")


def test_a_three_line_header_is_removed_as_one_unit() -> None:
    """π.δ. 62/2025's header spans three lines and all three go.

    Two documents, two shapes, same furniture: this is the proof that the rule
    cannot be "drop line 1". Anchoring on the issue stamp and deleting
    everything above it handles both without either document being a special
    case — and a positional rule would leave «2924» at the top of 259 pages,
    where step 5 would read it as the start of a provision.
    """
    page = f"{THREE_LINE_HEADER}\nκαι Οικονομικών εισηγούνται"

    assert strip_running_header(page) == (2924, "και Οικονομικών εισηγούνται")


def test_the_fek_number_inside_the_stamp_is_not_read_as_the_page_number() -> None:
    """«Τεύχος A’ 75/24.05.2024» contributes no digits to the page number.

    The stamp is full of numbers — issue 75, and the date — and all of them sit
    on the same line as the page number. Searching the whole line would return
    2024, silently re-labelling every page of the document with the year.
    """
    number, _ = strip_running_header(f"{ONE_LINE_HEADER}\nκείμενο")

    assert number == 3188


def test_a_page_with_no_running_header_is_returned_untouched() -> None:
    """The cover page keeps all of its text and reports no gazette number.

    Page 1 of both documents carries the act's title — «ΝΟΜΟΣ ΥΠ’ ΑΡΙΘΜ. 5110»
    — and no running header. A rule that assumed every page has one would eat
    the title line, which is where step 5 reads the act's number from.
    """
    cover = "ΝΟΜΟΣ ΥΠ’ ΑΡΙΘΜ. 5110 \nΊδρυση Ελληνικού Κέντρου"

    assert strip_running_header(cover) == (None, cover)


def test_an_empty_page_is_handled() -> None:
    """A blank page returns no number and no text, rather than raising.

    PDF page 59 of ν. 5110/2024 is blank. Ingestion walks 320 pages
    unattended, so one `IndexError` on an empty line list would abort the run
    at page 59 of 60.
    """
    assert strip_running_header("") == (None, "")


def test_an_issue_stamp_deep_in_the_body_is_not_treated_as_furniture() -> None:
    """A stamp on the sixth line is body text and is kept.

    Legislation quotes gazette references constantly. Without a bound on how
    far down the page the header can be, a provision citing an issue would have
    itself and every line above it deleted — the worst possible failure here,
    because the deletion is invisible in the output.
    """
    body = "\n".join(
        ["γραμμή " + str(n) for n in range(5)]
        + ["όπως δημοσιεύθηκε σε Τεύχος A’ 75/24.05.2024"]
    )

    assert strip_running_header(body) == (None, body)


def test_text_following_the_stamp_on_its_own_line_is_kept() -> None:
    """Anything after the stamp survives, even though the corpus never has any.

    Measured over all 317 header pages: nothing ever follows the stamp. The
    branch exists because the two failure modes are not comparable — a leftover
    header fragment is visible noise that step 10's read-through catches, while
    a provision deleted because it shared a line with the header is gone with
    no trace anywhere.
    """
    page = f"{ONE_LINE_HEADER} Άρθρο 1\nκείμενο"

    assert strip_running_header(page) == (3188, "Άρθρο 1\nκείμενο")


def test_normalize_document_records_the_gazette_page_on_each_page() -> None:
    """Every page carries both numbers: the PDF index and the printed one.

    They differ by a per-document offset that nothing in the file states, so
    keeping only one of them makes the other unrecoverable. `gazette_page` is
    `None` where there is no header, which is a page with no printed number
    rather than a parse failure — the cover.
    """
    document = _document("ΝΟΜΟΣ ΥΠ’ ΑΡΙΘΜ. 5110", f"{ONE_LINE_HEADER}\nκείμενο")

    pages = normalize_document(document).pages

    assert [(page.number, page.gazette_page) for page in pages] == [
        (1, None),
        (2, 3188),
    ]


@pytest.mark.slow
def test_the_printed_page_number_is_the_pdf_index_plus_a_fixed_offset() -> None:
    """Across each ΦΕΚ, `gazette_page - number` is one constant.

    The strongest check available without a human reading 320 pages. A header
    parsed slightly wrongly — the issue number taken instead of the page
    number, a glued digit dropped, a page's furniture missed — moves one page's
    offset and nothing else, so it shows up here as two offsets where there
    should be one.

    Stated as an offset rather than as a consecutive run on purpose: PDF page 59
    of ν. 5110/2024 is blank and therefore prints no number, so the recovered
    numbers jump 3240 → 3242. A consecutiveness test would read that hole as a
    parse error; the offset is indifferent to missing pages and still catches a
    misread one. It also means the printed number of a blank page is derivable
    if anything ever needs it.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    for document in manifest.documents:
        offsets = {
            page.gazette_page - page.number
            for page in normalize_document(extract_document(document)).pages
            if page.gazette_page is not None
        }

        assert len(offsets) == 1, (document.id, sorted(offsets))


@pytest.mark.slow
def test_header_removal_never_deletes_a_provision() -> None:
    """No text removed as a running header contains «Άρθρο».

    The sequence test above proves the *number* was read correctly; it says
    nothing about how much text went with it. This pins the other half: if the
    span ever grew to swallow body text the loss would be silent, and an
    article heading is the cheapest marker that body text was in there.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    for document in manifest.documents:
        for page in extract_document(document).pages:
            folded = normalize_characters(page.text)
            _, body = strip_running_header(folded)
            removed = folded[: len(folded) - len(body)]

            assert "Άρθρο" not in removed, (document.id, page.number)


def test_a_no_break_space_becomes_an_ordinary_space() -> None:
    """U+00A0 is folded to U+0020.

    The corpus holds 2540 of them — «ΕΔΡΑ - ΣΚΟΠΟΣ», «(Β’ 3805)» — and
    they are invisible in every editor. Two tokens separated by one would never
    match a query typed with a normal space, which is the same silent
    retrieval miss as a mis-encoded Δ, arriving through whitespace instead.
    """
    assert normalize_whitespace("ΕΔΡΑ - ΣΚΟΠΟΣ") == "ΕΔΡΑ - ΣΚΟΠΟΣ"


def test_runs_of_spaces_collapse_but_line_breaks_survive() -> None:
    """Horizontal whitespace collapses to one space; newlines are untouched.

    Justified ΦΕΚ columns leave double spaces mid-line. Newlines must survive
    the same pass, because de-hyphenation and step 5's structure detection both
    read lines — collapsing `\\s+` wholesale would weld the document into one
    line and destroy both.
    """
    assert normalize_whitespace("ΕΦΗΜΕΡΙΔΑ  T ΗΣ\nΆρθρο   13") == (
        "ΕΦΗΜΕΡΙΔΑ T ΗΣ\nΆρθρο 13"
    )


def test_leading_and_trailing_space_is_stripped_per_line() -> None:
    """Each line loses its edge whitespace.

    Nearly every extracted body line ends with a space, so without this the
    de-hyphenation check below would have to reason about trailing whitespace
    on every comparison, and «γραμμή » and «γραμμή» would be different chunk
    text for no reason a reader could see.
    """
    assert normalize_whitespace("  4. Το ποσοστό \n κείμενο  ") == (
        "4. Το ποσοστό\nκείμενο"
    )


def _paged(*texts: str) -> list[ExtractedPage]:
    return [
        ExtractedPage(number=number, text=text)
        for number, text in enumerate(texts, start=1)
    ]


def _texts(pages: list[ExtractedPage]) -> list[str]:
    return [page.text for page in pages]


def test_a_word_split_across_a_line_break_is_rejoined() -> None:
    """«Καινοτομί-» + «ας,» becomes «Καινοτομίας,» on one line.

    5065 words in the corpus are broken this way. Left split, each half is a
    token that exists in no dictionary and matches no query: V5's lexical
    search would never find «Καινοτομίας», and V3's embeddings would place the
    two fragments nowhere near the concept.
    """
    page = "Ελληνικού Κέντρου Αμυντικής Καινοτομί-\nας, εκσυγχρονισμός"

    assert _texts(dehyphenate(_paged(page))) == [
        "Ελληνικού Κέντρου Αμυντικής Καινοτομίας,\nεκσυγχρονισμός"
    ]


def test_only_the_continuing_word_moves_not_the_whole_line() -> None:
    """The remainder of the continuation line stays a line of its own.

    Joining whole lines would be the conventional de-hyphenation, and across a
    page boundary it would migrate a whole line of the next page's text onto
    this one — a provision whose text is printed on gazette page 3189 cited as
    3188. Moving only the token that finishes the word keeps provenance exact.
    """
    page = "τον διακριτι-\nκό τίτλο «ΕΛΚΑΚ ΑΕ», που εποπτεύεται"

    assert _texts(dehyphenate(_paged(page))) == [
        "τον διακριτικό\nτίτλο «ΕΛΚΑΚ ΑΕ», που εποπτεύεται"
    ]


def test_a_word_split_across_a_page_break_is_rejoined() -> None:
    """«διακριτι-» ending page 3 joins «κό» starting page 4.

    49 pages of the corpus end mid-word. A de-hyphenation pass that worked one
    page at a time would leave every one of those 49 words broken while fixing
    the 5065 inside pages — and the gap would look like a mysterious parser
    failure rather than a boundary the design never addressed.
    """
    pages = _paged("τον διακριτι-", "κό τίτλο «ΕΛΚΑΚ ΑΕ»")

    assert _texts(dehyphenate(pages)) == ["τον διακριτικό", "τίτλο «ΕΛΚΑΚ ΑΕ»"]


def test_the_rejoined_word_stays_on_the_page_it_started_on() -> None:
    """The completed word belongs to the earlier page, not the later one.

    A citation names where a provision's text begins. The word «διακριτικό»
    starts on the earlier gazette page, so that is the page a reader is sent to
    — and the alternative, pushing the fragment forward, would make the earlier
    page end on a hyphen that points nowhere.
    """
    pages = _paged("τον διακριτι-", "κό τίτλο")

    rejoined = dehyphenate(pages)

    assert rejoined[0].number == 1
    assert "διακριτικό" in rejoined[0].text
    assert "διακριτικό" not in rejoined[1].text


def test_a_hyphen_with_a_space_before_it_is_not_joined() -> None:
    """«εκτυπωτικών -» keeps its hyphen and its line break.

    1546 line-final hyphens in the corpus have a space before them, and they
    are genuinely ambiguous: «κε -» + «ντρικής» is a split word, but
    «εκτυπωτικών -» + «εκδοτικών» is a dash between two complete words, and
    joining that one yields «εκτυπωτικώνεκδοτικών» — a token in no language,
    with two real words destroyed. Not joining leaves a word unmatched; joining
    wrongly corrupts text. The asymmetry decides it.
    """
    page = "την κάλυψη των εκτυπωτικών -\nεκδοτικών αναγκών"

    assert _texts(dehyphenate(_paged(page))) == [page]


def test_a_hyphen_between_digits_is_not_joined() -> None:
    """«2018-» + «957» is left alone.

    Three line-final hyphens in the corpus sit next to digits rather than
    letters. Joining them would silently fuse two numbers into a third that
    appears nowhere in the law — and a wrong article or year number is the one
    kind of error a reader cannot catch by reading fluent Greek.
    """
    page = "της Οδηγίας (ΕΕ) 2018-\n957 του Συμβουλίου"

    assert _texts(dehyphenate(_paged(page))) == [page]


def test_a_word_split_twice_in_a_row_is_fully_rejoined() -> None:
    """A continuation that is itself hyphenated keeps being joined.

    «ελεγκτών - λο-» / «γιστών» occurs in ν. 5110/2024: the joined fragment can
    end in a hyphen of its own. Checking the line as it now stands rather than
    as it arrived makes this fall out for free; a single-pass rule would leave
    the second half broken.
    """
    pages = _paged("ορκωτών ελεγκτών - λο-\nγι-", "στών που είναι")

    assert _texts(dehyphenate(pages)) == ["ορκωτών ελεγκτών - λογιστών", "που είναι"]


def test_an_empty_page_survives_dehyphenation() -> None:
    """A blank page stays blank and does not swallow the next page's text.

    PDF page 59 of ν. 5110/2024 is blank. It sits between two pages of law, so
    a pass that treated an empty page as a line to be joined would splice the
    text across it.
    """
    pages = _paged("κείμενο", "", "άλλο κείμενο")

    assert _texts(dehyphenate(pages)) == ["κείμενο", "", "άλλο κείμενο"]


def test_residual_line_hyphens_counts_what_was_left() -> None:
    """The hyphens de-hyphenation declined to resolve are counted.

    The ambiguous cases are a known 1546-strong gap, not an absence of them.
    Reporting zero when the truth is "not attempted" is how the next person
    comes to believe the text is fully repaired and trusts exact matching on
    tokens that are still in halves.
    """
    assert residual_line_hyphens("εκτυπωτικών -\nεκδοτικών\nκείμενο") == 1
    assert residual_line_hyphens("Καινοτομίας,\nεκσυγχρονισμός") == 0


@pytest.mark.slow
def test_the_corpus_keeps_every_character_except_hyphens_and_spaces() -> None:
    """Normalization removes no Greek letter from the corpus.

    The passes delete things — furniture, hyphens, whitespace — and the whole
    risk of that is deleting one character too many on 320 pages, which no
    assertion about a sample would notice. Comparing the full letter census
    before and after bounds the damage: letters may only be *lost* to the
    header and colophon furniture, never changed in count elsewhere, so a rule
    that ate a line shows up as a deficit far beyond the furniture's size.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    for document in manifest.documents:
        extracted = extract_document(document)
        normalized = normalize_document(extracted)

        def letters(pages: list[ExtractedPage]) -> int:
            return sum(
                1 for page in pages for character in page.text if character.isalpha()
            )

        before = letters(
            [
                page.model_copy(update={"text": normalize_characters(page.text)})
                for page in extracted.pages
            ]
        )
        after = letters(normalized.pages)

        assert 0 <= before - after < 0.02 * before, (document.id, before, after)


SIGNATURES = (
    "Αθήνα, 4 Ιουλίου 2025\nΟ Πρόεδρος της Δημοκρατίας\nΚΩΝΣΤΑΝΤΙΝΟΣ ΑΝ. ΤΑΣΟΥΛΑΣ"
)
COLOPHON = (
    "Καποδιστρίου 34, 104 32 Αθήνα\n"
    "Τηλ. Κέντρο 210 5279000\n"
    "στην ηλεκτρονική διεύθυνση https://eservices.et.gr\n"
    "*01001211107250260*"
)


def test_a_colophon_under_law_text_truncates_only_the_colophon() -> None:
    """π.δ. 62/2025's last page keeps its signature block and loses the advert.

    This is the case that refutes the plan this version started with. The V2
    note recorded, from ν. 5110/2024 alone, that "every ΦΕΚ ends with that page
    and it must be dropped" — and PDF page 260 of the π.δ. carries the tail of
    the correspondence table, the enacting sentence, the date and **the
    signatures of the President and both ministers**, with only five lines of
    colophon beneath. Dropping the page would delete the act's signatures.
    """
    pages = _paged("Άρθρο 1", f"{SIGNATURES}\n{COLOPHON}")

    assert _texts(strip_colophon(pages)) == ["Άρθρο 1", SIGNATURES]


def test_a_page_that_is_nothing_but_colophon_is_emptied_not_removed() -> None:
    """ν. 5110/2024's page 60 becomes empty text and stays in the document.

    `ExtractedPage.number` is the PDF index, and `gazette_page` is derived from
    it; dropping the page would make `pages` stop corresponding to the PDF and
    silently shift nothing while breaking that correspondence for anyone who
    counts. An empty page is an honest statement: the page exists, and none of
    it is law.
    """
    pages = _paged("Άρθρο 1", f"*01000752405240060*\nΤαχυδρομική Διεύθυνση: {COLOPHON}")

    truncated = strip_colophon(pages)

    assert _texts(truncated) == ["Άρθρο 1", ""]
    assert [page.number for page in truncated] == [1, 2]


def test_the_barcode_alone_is_enough_to_mark_the_colophon() -> None:
    """The cut is made at whichever marker comes first.

    The two documents order the colophon's parts differently: ν. 5110/2024
    prints the barcode *above* the address, π.δ. 62/2025 *below* it. Keying on
    the address alone would leave a barcode line at the top of one document's
    colophon, and keying on the barcode alone would leave four lines of advert
    in the other.
    """
    pages = _paged("Άρθρο 1\n*01001211107250260*\nΚαποδιστρίου 34, 104 32 Αθήνα")

    assert _texts(strip_colophon(pages)) == ["Άρθρο 1"]


def test_a_document_with_no_colophon_is_returned_unchanged() -> None:
    """Nothing is cut when no marker is present.

    A ΦΕΚ excerpt, a fixture, or a future document whose colophon differs must
    pass through intact rather than losing its last page to a rule that assumed
    there is always something to cut.
    """
    pages = _paged("Άρθρο 1", "Άρθρο 2\nτέλος")

    assert _texts(strip_colophon(pages)) == ["Άρθρο 1", "Άρθρο 2\nτέλος"]


def test_the_address_on_an_earlier_page_is_left_alone() -> None:
    """Only the last page is searched for the colophon.

    «Καποδιστρίου 34» is a real street address that legislation can name — the
    Εθνικό Τυπογραφείο's own founding provisions do. Searching every page would
    let one such mention truncate the document from that point on, destroying
    every article after it. Unlike the running header, position is part of what
    a colophon *is*: the block at the end.
    """
    pages = _paged("στην οδό Καποδιστρίου 34 των Αθηνών\nΆρθρο 2", "Άρθρο 3")

    assert _texts(strip_colophon(pages)) == [
        "στην οδό Καποδιστρίου 34 των Αθηνών\nΆρθρο 2",
        "Άρθρο 3",
    ]


def test_stripping_a_colophon_from_no_pages_is_not_an_error() -> None:
    """An empty page list returns an empty list.

    `pages[-1]` raises on an empty sequence. The pipeline only ever hands over
    a real document, but a fixture or a future caller slicing a page range can
    produce an empty one, and an `IndexError` from a cleanup pass is a confusing
    way to find that out.
    """
    assert strip_colophon([]) == []


@pytest.mark.slow
def test_the_real_signature_block_survives_and_the_colophon_does_not() -> None:
    """Over both ΦΕΚ: no colophon text remains, and the signatures do.

    Both halves matter and they pull in opposite directions. A rule tuned to
    remove every trace of the publisher would eat the signature block; a rule
    careful enough to keep the signatures could leave the advert in and poison
    V3's embeddings with «Τα ΦΕΚ σε ηλεκτρονική μορφή διατίθενται δωρεάν».
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    normalized = {
        document.id: normalize_document(extract_document(document))
        for document in manifest.documents
    }

    for document_id, document in normalized.items():
        whole = "\n".join(page.text for page in document.pages)

        assert "Καποδιστρίου" not in whole, document_id
        assert "www.et.gr" not in whole, document_id

    signed = "\n".join(page.text for page in normalized["fek_a_121_2025"].pages)
    assert "ΚΩΝΣΤΑΝΤΙΝΟΣ ΚΑΡΑΓΚΟΥΝΗΣ" in signed
    assert "ΝΙΚΗ ΚΕΡΑΜΕΩΣ" in signed
