"""Building the V0 domain models out of the five parsers' output.

This is where step 5's title — *parse legal structure into the domain models* —
is finally paid, and where the models from [[V0 - Project Foundation]] are
checked against the whole corpus rather than against a hand-written example.

The tests are grouped by what assembly actually decides, since the plumbing is
not the interesting part: identity comes from the manifest and not from the
document, an article of a ratified instrument says so on itself, and an
instrument whose name cannot be inflected is excluded and named rather than
emitted as an article of the act.
"""

from datetime import date
from pathlib import Path

import pytest
from pydantic import HttpUrl

from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion import DEFAULT_MANIFEST_PATH, CorpusDocument, load_manifest
from greek_law.ingestion.assembly import assemble
from greek_law.ingestion.extraction import (
    ExtractedDocument,
    ExtractedPage,
    extract_document,
)
from greek_law.ingestion.normalization import normalize_document


def document(*pages: str) -> ExtractedDocument:
    """A document from one string per page, gazette numbers 3000 upward."""
    return ExtractedDocument(
        document_id="test",
        pages=[
            ExtractedPage(number=number, text=text, gazette_page=3000 + number)
            for number, text in enumerate(pages, start=1)
        ],
    )


def manifest_entry(act_type: str = "ν.", number: str = "5110") -> CorpusDocument:
    """A manifest entry carrying the identity an act is assembled with.

    Every field is required by `CorpusDocument`, which is the point: the
    identity an `Act` ends up with has been through the same validation as the
    corpus description committed to git.
    """
    return CorpusDocument(
        id="fek_a_75_2024",
        act=ActIdentity(
            act_type=act_type, number=number, year=2024, fek="Α' 75/24.05.2024"
        ),
        title="Ίδρυση Ελληνικού Κέντρου Αμυντικής Καινοτομίας",
        file=Path("data/raw/20240100075.pdf"),
        sha256="bc8d145da98bf3f992659b051a985ea3abc9c38a4d8e382cf4eeaa3e4c9214ce",
        size_bytes=521319,
        source_url=HttpUrl("https://example.invalid/20240100075.pdf"),
        retrieved_on=date(2026, 9, 7),
    )


ACT = (
    "ΜΕΡΟΣ Α’\nΣΚΟΠΟΣ\n"
    "Άρθρο 1\nΣκοπός\n1. Σκοπός είναι ο πρώτος.\n2. Και ο δεύτερος.\n"
    "Άρθρο 2\nΑντικείμενο\nΑντικείμενο του παρόντος είναι η ρύθμιση.\n"
)
"""Two articles, one container, both paragraph shapes — numbered and not."""

RATIFYING = (
    "Άρθρο 1\nΣκοπός\nκείμενο.\n"
    "Άρθρο 2\nΚαταστατικό\nΚυρώνεται το καταστατικό, ως εξής:\n«ΚΑΤΑΣΤΑΤΙΚΟ\n"
    "ΚΕΦΑΛΑΙΟ Α’\nΝΟΜΙΚΗ ΜΟΡΦΗ\n"
    "Άρθρο πρώτο\nΝομική μορφή\n1. Η εταιρεία λειτουργεί.\n"
    "Άρθρο 3\nΛοιπά\nκείμενο.\n"
)
"""An act whose άρθρο 2 ratifies a ΚΑΤΑΣΤΑΤΙΚΟ with one article of its own."""


def test_an_act_takes_its_identity_from_the_manifest_not_the_document() -> None:
    """Act number, year, ΦΕΚ, title and retrieval date all come from the manifest.

    Deliberate: the manifest entry is tied to the published bytes by a SHA-256,
    while the gazette's front matter is prose this parser never reads. If
    identity were parsed instead, every citation in the system would depend on
    a regex over a masthead — and a wrong act number is the one error that
    makes every provision in the document uncitable at once.
    """
    assembled = assemble(manifest_entry(), document(ACT))

    assert assembled.act.identity.act_type == "ν."
    assert assembled.act.identity.number == "5110"
    assert assembled.act.identity.fek == "Α' 75/24.05.2024"
    assert assembled.act.retrieved_on == date(2026, 9, 7)
    assert assembled.act.title is not None


def test_each_article_carries_its_title_path_and_paragraphs() -> None:
    """One article, assembled from four parsers that each knew part of it.

    The whole of step 5 meeting in one object: 5a found the heading, 5c the
    title and text, 5d the paragraphs, 5e the container. If any of them were
    wired to the wrong article the mistake would be invisible in each parser's
    own tests, because every one of them would still be internally consistent.
    """
    (first, second) = assemble(manifest_entry(), document(ACT)).act.articles

    assert (first.number, first.title) == ("1", "Σκοπός")
    assert [unit.kind for unit in first.path] == ["ΜΕΡΟΣ"]
    assert [(p.number, p.text) for p in first.paragraphs] == [
        ("1", "Σκοπός είναι ο πρώτος."),
        ("2", "Και ο δεύτερος."),
    ]
    assert [p.number for p in second.paragraphs] == [None]


def test_an_articles_paragraph_cases_stay_empty() -> None:
    """`Paragraph.cases` is empty by the step 5d decision, not by accident.

    1 689 lettered περιπτώσεις exist in the corpus and each one's text is
    inside its paragraph, so nothing is lost by waiting for
    [[V6 - Legal Structure and Citations]] to need them. Pinned because an
    empty list is exactly what a half-finished implementation also produces,
    and the note has to be able to say which of the two this is.
    """
    (first, _) = assemble(manifest_entry(), document(ACT)).act.articles

    assert all(paragraph.cases == [] for paragraph in first.paragraphs)


def test_an_instruments_article_is_marked_with_what_enacted_it() -> None:
    """The καταστατικό's «άρθρο πρώτο» says so; the act's articles say nothing.

    The decision this task exists for. Without the marker, an instrument's
    article is indistinguishable from the act's own, and step 7 would render
    «ν. 5110/2024, άρθρο πρώτο» — a citation that looks resolvable and names an
    article the law does not have. That is V1 architecture review finding 4
    arriving from the document side.
    """
    articles = assemble(manifest_entry(), document(RATIFYING)).act.articles
    own = [article for article in articles if article.instrument is None]
    instrument = [article for article in articles if article.instrument is not None]

    assert [article.number for article in own] == ["1", "2", "3"]
    assert [article.number for article in instrument] == ["πρώτο"]
    assert instrument[0].instrument is not None
    assert instrument[0].instrument.ratifying_article == "2"
    assert instrument[0].instrument.cited_as == "του καταστατικού"


def test_a_citation_built_from_an_assembled_article_is_resolvable() -> None:
    """The end of the chain: an assembled article renders its own citation.

    What every slice of step 5 was for. The reference is built from the act's
    identity and the article's own marker, and it renders **act-last** — «άρθρο
    πρώτο παρ. 1 του καταστατικού που κυρώθηκε με το άρθρο 2 ν. 5110/2024» —
    because the ratification clause ends in an article number and anything
    appended after it would read as belonging to *that* article.

    The retrieval key nests the instrument under its ratifying article, so a
    store can filter an instrument's provisions from the act's own without
    parsing a name.
    """
    articles = assemble(manifest_entry(), document(RATIFYING)).act
    article = next(a for a in articles.articles if a.number == "πρώτο")

    reference = SourceReference(
        act=articles.identity,
        instrument=article.instrument,
        article=article.number,
        paragraph="1",
    )

    assert reference.citation == (
        "άρθρο πρώτο παρ. 1 του καταστατικού που κυρώθηκε με το άρθρο 2 ν. 5110/2024"
    )
    assert reference.key == "ν.5110/2024/άρθρο-2/άρθρο-πρώτο/παρ-1"


def test_an_untranslatable_instrument_label_excludes_and_reports_its_articles() -> None:
    """An instrument the genitive table does not cover loses its articles, loudly.

    `RatifiedInstrument.cited_as` must hold the inflected form, and the table
    has one measured row. For any other instrument there are three options and
    only one is acceptable: guessing «του» produces «του Σύμβασης», which is
    not Greek; emitting the articles unmarked produces citations to articles the
    act does not have; excluding them loses provisions in a way the report
    names and a human can fix with one row.
    """
    other = RATIFYING.replace("ΚΑΤΑΣΤΑΤΙΚΟ", "ΣΥΜΒΑΣΗ")

    assembled = assemble(manifest_entry(), document(other))

    assert [a.number for a in assembled.act.articles] == ["1", "2", "3"]
    assert assembled.untranslated == ["ΣΥΜΒΑΣΗ ratified by άρθρο 2 (1 articles)"]


def test_an_instrument_that_printed_no_name_is_reported_too() -> None:
    """No label at all is the same failure as an untranslatable one.

    `InstrumentTexts.label` is `str | None` because an instrument that prints no
    quoted naming line is reported rather than guessed at — the 5b-ii decision.
    Assembly cannot invent a name to inflect, so the articles are excluded on
    the same terms, and the report says which ratifying article to look at.
    """
    unnamed = RATIFYING.replace("«ΚΑΤΑΣΤΑΤΙΚΟ\n", "")

    assembled = assemble(manifest_entry(), document(unnamed))

    assert all(article.instrument is None for article in assembled.act.articles)
    assert assembled.untranslated == [
        "unnamed instrument ratified by άρθρο 2 (1 articles)"
    ]


def test_the_acts_own_articles_come_first_in_their_own_numbering() -> None:
    """Act articles in sequence, then the instrument's — not document order.

    Document order would interleave πρώτο…τριακοστό between άρθρα 13 and 14 and
    break the invariant that has caught every parser bug in this version:
    `Act.articles` opening with a contiguous 1..N. Each instrument article
    carries its own marker, so appending costs nothing.
    """
    articles = assemble(manifest_entry(), document(RATIFYING)).act.articles

    assert [article.number for article in articles] == ["1", "2", "3", "πρώτο"]


@pytest.mark.slow
def test_both_corpus_acts_assemble_into_the_shapes_they_were_measured_at() -> None:
    """112 and 589 articles, 259 and 1 877 paragraphs, nothing untranslated.

    The end-to-end fence for the whole of step 5, and the numbers are the ones
    every slice's own corpus test already pins — so a change that moves one of
    them has to move it here too, in the object the rest of the project will
    actually consume.

    The spot check is the provision the V2 note has used since 2026-09-07 to
    explain why one ΦΕΚ carries two numberings: «άρθρο δέκατο πέμπτο» of the
    καταστατικό, *Σύνθεση του Διοικητικού Συμβουλίου*, which is a different
    provision from ν. 5110/2024's own άρθρο 15.
    """
    assembled = {}
    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        normalized = normalize_document(extract_document(entry))
        assembled[entry.id] = assemble(entry, normalized)

    for result in assembled.values():
        assert result.untranslated == []

    law, decree = assembled["fek_a_75_2024"].act, assembled["fek_a_121_2025"].act
    assert (len(law.articles), len(decree.articles)) == (112, 589)
    assert sum(len(a.paragraphs) for a in law.articles) == 259
    assert sum(len(a.paragraphs) for a in decree.articles) == 1877
    assert sum(1 for a in law.articles if a.instrument is not None) == 30
    assert all(a.instrument is None for a in decree.articles)

    fifteenth = next(a for a in law.articles if a.number == "δέκατο πέμπτο")
    assert fifteenth.title == "Σύνθεση του Διοικητικού Συμβουλίου"
    assert fifteenth.instrument is not None
    assert fifteenth.instrument.ratifying_article == "13"
    assert [unit.number for unit in fifteenth.path] == ["Γ’"]
    assert len(fifteenth.paragraphs) == 14

    own = next(a for a in law.articles if a.number == "15")
    assert own.title is not None
    assert own.instrument is None
    assert own.title != fifteenth.title
