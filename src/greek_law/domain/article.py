from pydantic import BaseModel, ConfigDict

from greek_law.domain.paragraph import Paragraph
from greek_law.domain.ratified_instrument import RatifiedInstrument
from greek_law.domain.structural_unit import StructuralUnit


class Article(BaseModel):
    """Άρθρο — the primary addressable provision.

    ``number`` is a string because amendments insert articles between existing
    ones: Άρθρο 3Α, Άρθρο 3Β — and π.δ. 62/2025 prints one of them as «Άρθρο
    141 Α», with a space the parser removes. Greek characters are kept as they
    appear in the source; note that Greek Α (U+0391) and Latin A (U+0041) are
    visually identical and not equal.

    ``instrument`` is set when this article belongs to a ratified instrument
    rather than to the act itself — the document-side mirror of
    :attr:`SourceReference.instrument`, added 2026-10-17 when step 5's assembly
    task found there was no way to say it. Without it the καταστατικό's «άρθρο
    πρώτο» is indistinguishable from an article of ν. 5110/2024, and a citation
    built from it reads «ν. 5110/2024, άρθρο πρώτο» — resolvable-looking, and
    pointing at an article the law does not have. That is
    [[V1 - Minimal LLM Application]] architecture review finding 4 arriving from
    the document side; 5b-i fixed the citation side first.

    The namespace is a property of the provision, not of where it was found,
    which is why it lives here rather than in a second collection on
    :class:`Act`: step 6 chunks one list, and step 7 copies the field into a
    reference instead of re-deriving it from a position in the PDF.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str
    title: str | None = None
    instrument: RatifiedInstrument | None = None
    path: list[StructuralUnit] = []
    paragraphs: list[Paragraph] = []
