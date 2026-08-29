from pydantic import BaseModel, ConfigDict


class StructuralUnit(BaseModel):
    """A non-addressable organizational container: Μέρος, Τμήμα, Κεφάλαιο, Υποκεφάλαιο.

    Never appears in a citation. Carried as data on ``Article.path`` rather than
    modelled as a class per level, because which containers a law uses varies.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    number: str | None = None
    title: str | None = None
