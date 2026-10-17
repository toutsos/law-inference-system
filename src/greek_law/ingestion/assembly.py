"""Turn the five parsers' output into the V0 domain models.

The parsers answer "what does this document contain"; this module answers "what
is the act". It is the first place the models from
[[V0 - Project Foundation]] meet the whole corpus at once, which is what step
5's own title — *parse legal structure into the domain models* — has been
building towards.

**Identity does not come from the document.** `Act.identity`, `Act.title` and
`Act.retrieved_on` come from the committed manifest, whose SHA-256 ties them to
the published bytes; the parser never reads the gazette's front matter and does
not need to. Everything below the act — articles, titles, paragraphs, container
paths — comes from the document.

What assembly adds beyond plumbing is **one decision and one report**. The
decision: an article of a ratified instrument carries
:class:`~greek_law.domain.RatifiedInstrument` on itself, so «άρθρο πρώτο» of a
καταστατικό can never be rendered as «ν. 5110/2024, άρθρο πρώτο» — a citation
that looks resolvable and names an article the law does not have. That is
[[V1 - Minimal LLM Application]] architecture review finding 4, which 5b-i
fixed for :class:`~greek_law.domain.SourceReference` and which arrives here
again from the document side. The report: an instrument whose name cannot be
put into the genitive a citation needs is **excluded and named**, never emitted
unmarked.
"""

from pydantic import BaseModel, ConfigDict

from greek_law.domain import (
    Act,
    Article,
    Paragraph,
    RatifiedInstrument,
    StructuralUnit,
)
from greek_law.ingestion.extraction import ExtractedDocument
from greek_law.ingestion.manifest import CorpusDocument
from greek_law.ingestion.structure import (
    ArticleText,
    container_paths,
    find_article_texts,
    find_instrument_texts,
    split_paragraphs,
)

_GENITIVE = {"ΚΑΤΑΣΤΑΤΙΚΟ": "του καταστατικού"}
"""An instrument's printed name, mapped to the genitive a citation needs.

``RatifiedInstrument.cited_as`` must hold the inflected form, because a
renderer cannot derive case and gender from a bare noun: π.δ. 62/2025 cites
instruments of three genders — «του ΚΝΥ ΑΕ», «του καταστατικού», «της Σύμβασης
της Ουάσιγκτον» — and a template hard-coding «του» would emit «του Σύμβασης»,
which is not Greek. The parser records what is printed, in the nominative.

**This table revisits the step 5b-ii deferral deliberately.** That decision
kept *the parser* out of Greek morphology and left the translation to step 7.
Assembly is not the parser — it is the layer that builds domain objects — and
``RatifiedInstrument`` cannot be constructed without the genitive, so the
alternative was a second, half-typed representation of an instrument travelling
onward to be completed later. One row, measured, is not speculation; six
invented rows would have been.

A label with no row here is **reported and its articles excluded**, by
:class:`Assembly`. Unmarked emission is the one outcome ruled out: it is
indistinguishable from an article of the act itself.
"""


class Assembly(BaseModel):
    """The assembled act, and what could not be assembled.

    Two values rather than one, for the reason every report in this version
    exists: an act returned alone cannot say that thirty provisions are missing
    from it. ``untranslated`` lists each instrument whose name
    :data:`_GENITIVE` does not cover, with the number of articles that cost —
    readable, because a human reads it from the probe. Empty over the corpus.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    act: Act
    untranslated: list[str]


def _paragraphs(article: ArticleText) -> list[Paragraph]:
    """Step 5d's paragraphs as domain paragraphs.

    ``cases`` stays empty by the step 5d decision: the lettered περιπτώσεις are
    inside each paragraph's text, nothing before
    [[V6 - Legal Structure and Citations]] cites at that level, and 1 689
    markers is work with no current reader.
    """
    return [
        Paragraph(number=paragraph.number, text=paragraph.text)
        for paragraph in split_paragraphs(article).paragraphs
    ]


def _article(
    text: ArticleText,
    path: list[StructuralUnit],
    instrument: RatifiedInstrument | None = None,
) -> Article:
    """One domain article, from the four parsers that describe it.

    The provenance on ``text.heading`` — PDF page, gazette page, line — is
    **deliberately not carried over**. ``Article`` has no field for it, and step
    7 is where chunk metadata is designed; until then the parser output holds
    the page a citation will need. Add the fields the day step 7 shows it cannot
    reach them, rather than guessing at the shape now.
    """
    return Article(
        number=text.heading.number,
        title=text.title,
        path=path,
        paragraphs=_paragraphs(text),
        instrument=instrument,
    )


def assemble(entry: CorpusDocument, document: ExtractedDocument) -> Assembly:
    """Build one :class:`~greek_law.domain.Act` from a manifest entry and its text.

    Takes both because they answer different halves: ``entry`` carries the
    identity the manifest proves, ``document`` the structure the parsers found.
    It takes the *normalized* document — pipeline order is the only guarantee
    of that, as the step 4 decision records — and does no IO, so a test can
    assemble a page of invented Greek without a PDF.

    **Order:** the act's own articles first, in its numbering, then each
    instrument's articles. Not document order, which would interleave
    πρώτο…τριακοστό between άρθρα 13 and 14 and break the one invariant that
    has caught every parser bug in this version — ``Act.articles`` opening with
    a contiguous 1..N. Each instrument article carries its own marker, so
    nothing is lost by appending.
    """
    paths = container_paths(document)
    articles = [
        _article(text, paths[text.heading]) for text in find_article_texts(document)
    ]
    untranslated: list[str] = []

    for group in find_instrument_texts(document):
        cited_as = _GENITIVE.get(group.label) if group.label is not None else None
        if cited_as is None:
            untranslated.append(
                f"{group.label or 'unnamed instrument'} ratified by "
                f"άρθρο {group.ratifying_article} ({len(group.articles)} articles)"
            )
            continue
        instrument = RatifiedInstrument(
            cited_as=cited_as, ratifying_article=group.ratifying_article
        )
        articles.extend(
            _article(text, paths[text.heading], instrument) for text in group.articles
        )

    return Assembly(
        act=Act(
            identity=entry.act,
            title=entry.title,
            retrieved_on=entry.retrieved_on,
            articles=articles,
        ),
        untranslated=untranslated,
    )
