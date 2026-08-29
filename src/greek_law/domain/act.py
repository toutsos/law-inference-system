from datetime import date

from pydantic import BaseModel, ConfigDict

from greek_law.domain.article import Article


class ActIdentity(BaseModel):
    """Identity of a νομοθέτημα — what makes "άρθρο 4" mean something.

    Shared by :class:`Act` (the document) and :class:`SourceReference` (a pointer
    into one), so a citation carries the act's identity without carrying the
    whole document.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    act_type: str
    number: str
    year: int
    fek: str | None = None


class Act(BaseModel):
    """A legislative act (Νόμος, Π.Δ., ΚΥΑ, ...) and its articles.

    ``retrieved_on`` records which snapshot is held. It does not model amendment
    chains; it only stops the document from implicitly claiming to be timeless.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity: ActIdentity
    title: str | None = None
    retrieved_on: date | None = None
    articles: list[Article] = []
