from pydantic import BaseModel, ConfigDict


class Case(BaseModel):
    """Περίπτωση, and recursively Υποπερίπτωση.

    Recursive because the containment is genuinely self-similar: a υποπερίπτωση
    is the same shape as a περίπτωση one level down. Both are lettered items
    carrying normative text.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str
    text: str
    subcases: list["Case"] = []
