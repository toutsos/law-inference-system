"""Step 6: one chunk per paragraph, with a header for the embedding.

The unit tests build small acts by hand from the domain models, because
chunking reads nothing but an assembled :class:`~greek_law.domain.Act` — no
PDF, no parser. The Greek in them is taken from the corpus; the slow tests at
the end run the real documents and pin the numbers the step 6 decision was made
on. Step 7 added the link back to the manifest and the container path.
"""

from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from pydantic import HttpUrl

from greek_law.domain import (
    Act,
    ActIdentity,
    Article,
    Paragraph,
    RatifiedInstrument,
    StructuralUnit,
)
from greek_law.ingestion import DEFAULT_MANIFEST_PATH, CorpusDocument, load_manifest
from greek_law.ingestion.assembly import assemble
from greek_law.ingestion.chunking import (
    OVERSIZED_CHARS,
    Chunk,
    chunk_act,
    oversized_chunks,
)
from greek_law.ingestion.extraction import extract_document
from greek_law.ingestion.normalization import normalize_document

DECREE = ActIdentity(act_type="π.δ.", number="62", year=2025)
LAW = ActIdentity(act_type="ν.", number="5110", year=2024)
KATASTATIKO = RatifiedInstrument(cited_as="του καταστατικού", ratifying_article="13")


def _act(*articles: Article, identity: ActIdentity = DECREE) -> Act:
    return Act(identity=identity, articles=list(articles))


def _document(
    identity: ActIdentity, document_id: str = "fek_a_121_2025"
) -> CorpusDocument:
    return CorpusDocument(
        id=document_id,
        act=identity,
        title="Κώδικας Εργατικού Δικαίου.",
        file=Path("data/raw/20250100121.pdf"),
        sha256="0" * 64,
        size_bytes=1,
        source_url=HttpUrl("https://example.org/fek.pdf"),
        retrieved_on=date(2026, 9, 14),
    )


def _chunks(act: Act) -> list[Chunk]:
    """Chunk ``act`` against a manifest entry that matches it."""
    return chunk_act(act, _document(act.identity))


def test_every_paragraph_becomes_one_chunk_in_order() -> None:
    """Two articles of two and one paragraphs give three chunks, in that order.

    The paragraph is the chunk by the step 6 decision. A chunker that emitted
    one per article would silently coarsen every citation to article level,
    and one that reordered would make "the next chunk" mean nothing to V6.
    """
    act = _act(
        Article(
            number="1",
            paragraphs=[
                Paragraph(number="1", text="πρώτη"),
                Paragraph(number="2", text="δεύτερη"),
            ],
        ),
        Article(number="2", paragraphs=[Paragraph(number="1", text="τρίτη")]),
    )

    chunks = _chunks(act)

    assert [(c.source.article, c.source.paragraph, c.text) for c in chunks] == [
        ("1", "1", "πρώτη"),
        ("1", "2", "δεύτερη"),
        ("2", "1", "τρίτη"),
    ]


def test_the_chunk_text_is_the_paragraph_exactly_as_printed() -> None:
    """``text`` carries no header: what is shown to a reader is the law alone.

    The header exists for the embedding. If it leaked into ``text``, every
    quotation V3 shows a user would open with a citation the gazette never
    printed, and an answer quoting the provision would quote our words as law.
    """
    paragraph = "Η παρ. 1 ισχύει από 1.1.2025."
    act = _act(
        Article(
            number="84",
            title="Προστασία σε φορείς του ιδιωτικού τομέα",
            paragraphs=[Paragraph(number="2", text=paragraph)],
        )
    )

    (chunk,) = _chunks(act)

    assert chunk.text == paragraph


def test_the_embedding_text_opens_with_citation_and_article_title() -> None:
    """A two-word paragraph is embedded with the provision and subject it lacks.

    «Η παρ. 1 ισχύει από 1.1.2025.» is one of 56 corpus paragraphs under 80
    characters. Embedded alone, its vector says nothing about what it governs
    and no question about whistleblower protection would ever reach it — the
    weakness of paragraph-sized chunks that the header exists to remove.
    """
    act = _act(
        Article(
            number="84",
            title="Προστασία σε φορείς του ιδιωτικού τομέα",
            paragraphs=[Paragraph(number="2", text="Η παρ. 1 ισχύει από 1.1.2025.")],
        )
    )

    (chunk,) = _chunks(act)

    assert chunk.embedding_text == (
        "π.δ. 62/2025, άρθρο 84 παρ. 2\n"
        "Προστασία σε φορείς του ιδιωτικού τομέα\n"
        "\n"
        "Η παρ. 1 ισχύει από 1.1.2025."
    )


def test_an_article_without_a_title_gets_a_citation_only_header() -> None:
    """No title means no title line — never the string «None».

    Step 5c reads titles heuristically and an article can come out without
    one. An f-string over ``None`` would embed the word «None» into the
    vector of every such chunk, and display it in every header.
    """
    act = _act(Article(number="7", paragraphs=[Paragraph(number="1", text="κείμενο")]))

    (chunk,) = _chunks(act)

    assert chunk.header == "π.δ. 62/2025, άρθρο 7 παρ. 1"
    assert "None" not in chunk.embedding_text


def test_an_unnumbered_paragraph_is_cited_at_article_level() -> None:
    """A single-paragraph article's chunk cites «άρθρο 68», not «παρ. None».

    253 articles of the corpus are one unnumbered paragraph. Their citation is
    the article itself; inventing «παρ. 1» would cite a paragraph the gazette
    does not print, which a lawyer checking the source would not find.
    """
    act = _act(
        Article(
            number="68",
            title="Κοπή δένδρων από τη στρατιωτική υπηρεσία",
            paragraphs=[Paragraph(text="Για την προστασία από πυρκαγιές")],
        ),
        identity=LAW,
    )

    (chunk,) = _chunks(act)

    assert chunk.source.paragraph is None
    assert chunk.header.splitlines()[0] == "ν. 5110/2024, άρθρο 68"
    assert chunk.key == "ν.5110/2024/άρθρο-68"


def test_an_instrument_article_is_cited_as_the_instruments_own() -> None:
    """The καταστατικό's «άρθρο πρώτο» carries its instrument into the chunk.

    Dropping ``Article.instrument`` here would turn the chunk into «ν.
    5110/2024, άρθρο πρώτο» — an article the law does not have — undoing
    step 5b's whole namespace fix at the last step before embedding.
    """
    act = _act(
        Article(
            number="πρώτο",
            title="Νομική μορφή",
            instrument=KATASTATIKO,
            paragraphs=[Paragraph(text="Το Ελληνικό Κέντρο Αμυντικής Καινοτομίας")],
        ),
        identity=LAW,
    )

    (chunk,) = _chunks(act)

    assert chunk.source.instrument == KATASTATIKO
    assert chunk.header.splitlines()[0] == (
        "άρθρο πρώτο του καταστατικού που κυρώθηκε με το άρθρο 13 ν. 5110/2024"
    )
    assert chunk.key == "ν.5110/2024/άρθρο-13/άρθρο-πρώτο"


def test_an_act_with_no_articles_gives_no_chunks() -> None:
    """An empty act is an empty list, not an error.

    The boundary case for the comprehension: nothing in chunking should assume
    a document parsed into at least one article — that guarantee belongs to
    step 5's reports, which say why when it does not hold.
    """
    assert _chunks(_act()) == []


def _chunk(text: str) -> Chunk:
    (chunk,) = _chunks(
        _act(Article(number="1", paragraphs=[Paragraph(number="1", text=text)]))
    )
    return chunk


def test_oversized_is_measured_on_the_embedding_text_not_the_paragraph() -> None:
    """A paragraph just under the limit is reported once its header is added.

    The model truncates what it is given, and it is given the header too. A
    report measured on the bare paragraph would miss exactly the chunks that
    the header pushes over a model's limit.
    """
    header_length = len(_chunk("").embedding_text)
    chunk = _chunk("α" * (100 - header_length + 1))

    assert len(chunk.text) < 100
    assert oversized_chunks([chunk], limit=100) == [chunk]


def test_a_chunk_exactly_at_the_limit_is_not_oversized() -> None:
    """``limit`` is the largest size that fits: equal is in, one more is out.

    An off-by-one here would put one more or one fewer paragraph on the list
    V3 checks against the chosen model's real limit — small, and exactly the
    kind of disagreement that makes a report stop being trusted.
    """
    header_length = len(_chunk("").embedding_text)
    at_limit = _chunk("α" * (100 - header_length))
    over = _chunk("α" * (100 - header_length + 1))

    assert len(at_limit.embedding_text) == 100
    assert oversized_chunks([at_limit, over], limit=100) == [over]


def test_oversized_chunks_are_reported_not_removed() -> None:
    """The report returns a list; the chunks themselves are all still emitted.

    The step 6 decision keeps oversized paragraphs whole. A chunker that
    dropped them would lose 25 provisions of the corpus — ν. 5110/2024 άρθρο
    18 among them — without a trace in the output.
    """
    long = "α" * (OVERSIZED_CHARS + 1)
    act = _act(Article(number="18", paragraphs=[Paragraph(text=long)]))

    chunks = _chunks(act)

    assert [c.text for c in chunks] == [long]
    assert oversized_chunks(chunks) == chunks


def test_every_chunk_names_the_manifest_entry_it_came_from() -> None:
    """``document_id`` is the manifest id: the link back to the published PDF.

    The Definition of Done asks for a *resolvable* source reference. The act
    identity alone names a law, not a file; only the manifest id leads to the
    URL and SHA-256 that prove which bytes a quotation was read from.
    """
    act = _act(Article(number="1", paragraphs=[Paragraph(number="1", text="κείμενο")]))

    (chunk,) = chunk_act(act, _document(DECREE, document_id="fek_a_121_2025"))

    assert chunk.document_id == "fek_a_121_2025"


def test_a_chunk_carries_its_articles_container_path() -> None:
    """Every paragraph of an article gets the article's ΜΕΡΟΣ/ΚΕΦΑΛΑΙΟ path.

    The path is the only metadata that lets V3 or V5 filter results to one
    chapter of a 589-article code. Dropping it at chunking would discard
    step 5e's work one step before anything could use it.
    """
    path = [
        StructuralUnit(kind="ΜΕΡΟΣ", number="Α’", title="Ατομικές εργασιακές σχέσεις"),
        StructuralUnit(kind="ΚΕΦΑΛΑΙΟ", number="Α’", title="Γενικές διατάξεις"),
    ]
    act = _act(
        Article(
            number="1",
            path=path,
            paragraphs=[
                Paragraph(number="1", text="πρώτη"),
                Paragraph(number="2", text="δεύτερη"),
            ],
        )
    )

    assert [chunk.path for chunk in _chunks(act)] == [path, path]


def test_a_manifest_entry_for_another_act_is_refused() -> None:
    """Chunking π.δ. 62/2025 against ν. 5110/2024's entry raises ValueError.

    Every chunk would carry the wrong ``document_id`` while every citation —
    built from the act — still read correctly, so the mistake would surface
    only when a reader opened the linked PDF and found a different law.
    """
    act = _act(Article(number="1", paragraphs=[Paragraph(number="1", text="κείμενο")]))

    with pytest.raises(ValueError, match="fek_a_75_2024"):
        chunk_act(act, _document(LAW, document_id="fek_a_75_2024"))


def _corpus_chunks() -> dict[str, list[Chunk]]:
    return {
        entry.id: chunk_act(
            assemble(entry, normalize_document(extract_document(entry))).act, entry
        )
        for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents
    }


@pytest.mark.slow
def test_the_corpus_chunks_at_the_sizes_it_was_measured_at() -> None:
    """2 136 chunks, 25 of them oversized, no key used twice.

    Pins the numbers the step 6 decision was taken on: 259 + 1 877 paragraphs
    and 18 + 7 over the limit. A duplicate key is the serious failure — V3
    upserts on it, so two provisions sharing one would silently overwrite each
    other, and the καταστατικό's articles are where it would happen first.
    """
    chunks = _corpus_chunks()

    assert {document: len(c) for document, c in chunks.items()} == {
        "fek_a_75_2024": 259,
        "fek_a_121_2025": 1877,
    }
    assert {document: len(oversized_chunks(c)) for document, c in chunks.items()} == {
        "fek_a_75_2024": 18,
        "fek_a_121_2025": 7,
    }
    for document_chunks in chunks.values():
        duplicates = [
            key
            for key, count in Counter(c.key for c in document_chunks).items()
            if count > 1
        ]
        assert duplicates == []


@pytest.mark.slow
def test_no_corpus_chunk_is_empty_or_headed_with_a_missing_title() -> None:
    """Every chunk has text, and every header's first line is its citation.

    An empty chunk embeds as the header alone and would be returned for any
    question about its article's title, with nothing behind it to quote.
    """
    for document_chunks in _corpus_chunks().values():
        for chunk in document_chunks:
            assert chunk.text.strip(), chunk.key
            assert chunk.header.splitlines()[0] == chunk.source.citation
            assert "None" not in chunk.header, chunk.key


@pytest.mark.slow
def test_every_corpus_chunk_resolves_to_its_manifest_entry() -> None:
    """Each chunk's ``document_id`` names a manifest entry for the same act.

    The Definition of Done's "resolvable source reference", checked over all
    2 136 chunks: from any chunk, the manifest yields the URL and hash of the
    PDF its citation names. A chunk whose id led nowhere, or to another law,
    would cite a source no reader could open.
    """
    entries = {
        entry.id: entry for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents
    }

    for document_chunks in _corpus_chunks().values():
        for chunk in document_chunks:
            assert entries[chunk.document_id].act == chunk.source.act, chunk.key
            assert chunk.path, chunk.key
