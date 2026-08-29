from pydantic import BaseModel, ConfigDict

from greek_law.domain.case import Case


class Paragraph(BaseModel):
    """Παράγραφος — the home of all normative text inside an article.

    ``number is None`` carries unnumbered article text (introductory text, or an
    article with no numbered paragraphs at all). Such a paragraph cites as
    "άρθρο 4" with no παρ. component, which is the correct citation for it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str | None = None
    text: str
    cases: list[Case] = []
