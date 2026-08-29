from pydantic import BaseModel, ConfigDict

from greek_law.domain.paragraph import Paragraph
from greek_law.domain.structural_unit import StructuralUnit


class Article(BaseModel):
    """Άρθρο — the primary addressable provision.

    ``number`` is a string because amendments insert articles between existing
    ones: Άρθρο 3Α, Άρθρο 3Β. Greek characters are kept as they appear in the
    source; note that Greek Α (U+0391) and Latin A (U+0041) are visually
    identical and not equal.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str
    title: str | None = None
    path: list[StructuralUnit] = []
    paragraphs: list[Paragraph] = []
