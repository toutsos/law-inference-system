from pydantic import BaseModel, ConfigDict

from greek_law.domain.act import ActIdentity


class SourceReference(BaseModel):
    """A structured pointer to one addressable provision.

    Stored structurally, never as a string: a string citation cannot be
    filtered, compared, or validated. Both the human-readable citation and the
    flat retrieval key are *derived* from these fields, so neither can drift out
    of agreement with the reference it describes.

    ``cases`` is the chain of lettered levels: ``["α"]`` is περ. α΄,
    ``["α", "αα"]`` is υποπερ. αα΄ of περ. α΄.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    act: ActIdentity
    article: str
    paragraph: str | None = None
    cases: list[str] = []

    @property
    def citation(self) -> str:
        """Render for a human: ``Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄``."""
        parts = [f"{self.act.act_type} {self.act.number}/{self.act.year},"]
        parts.append(f"άρθρο {self.article}")
        if self.paragraph is not None:
            parts.append(f"παρ. {self.paragraph}")
        for depth, case in enumerate(self.cases):
            parts.append(f"{'υπο' * depth}περ. {case}΄")
        return " ".join(parts)

    @property
    def key(self) -> str:
        """Flat identifier for the vector store: ``Ν4808/2021/άρθρο-4/παρ-2/περ-α``.

        Greek throughout, per the identifier-alphabet decision — a Latin scheme
        would be a second representation to keep in sync forever.
        """
        segments = [
            f"{self.act.act_type}{self.act.number}",
            str(self.act.year),
            f"άρθρο-{self.article}",
        ]
        if self.paragraph is not None:
            segments.append(f"παρ-{self.paragraph}")
        for depth, case in enumerate(self.cases):
            segments.append(f"{'υπο' * depth}περ-{case}")
        return "/".join(segments)
