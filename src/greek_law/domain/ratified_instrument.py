from pydantic import BaseModel, ConfigDict


class RatifiedInstrument(BaseModel):
    """A self-contained instrument that an act brought into force, with its own articles.

    Greek legislation routinely enacts a complete document — a καταστατικό, a
    code, an international convention, a collective agreement — by ratifying it
    through a single article. The instrument keeps its own article numbering, so
    one ΦΕΚ ends up carrying two parallel namespaces: «άρθρο 15» of
    ν. 5110/2024 is *Εκπαίδευση - Κέντρα Αριστείας*, while «άρθρο δέκατο
    πέμπτο» of the καταστατικό its άρθρο 13 ratified is *Σύνθεση του
    Διοικητικού Συμβουλίου*. Without this type both collapse into one
    ``article`` field and the citation names an article the act does not have.

    ``ratifying_article`` is the identity, not ``cited_as``: an article number
    is unique within an act, whereas a name is prose. It is also what a reader
    needs in order to find the instrument in the gazette at all.

    _Accepted limit:_ one article is assumed to ratify at most one instrument.
    True of ν. 5110/2024 and of every ratification the corpus cites; an article
    enacting two annexes would need a second field to tell them apart.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cited_as: str
    ratifying_article: str
