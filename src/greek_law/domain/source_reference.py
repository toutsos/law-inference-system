from pydantic import BaseModel, ConfigDict

from greek_law.domain.act import ActIdentity
from greek_law.domain.ratified_instrument import RatifiedInstrument


def _slug(value: str) -> str:
    """Collapse whitespace in one key segment. Nothing else is touched.

    Deliberately *not* a general slugifier: the Greek alphabet must survive,
    per the identifier-alphabet decision, so no ASCII-folding and no case
    change. Whitespace is the only character an article number contributes
    that a flat identifier cannot carry.
    """
    return "-".join(value.split())


class SourceReference(BaseModel):
    """A structured pointer to one addressable provision.

    Stored structurally, never as a string: a string citation cannot be
    filtered, compared, or validated. Both the human-readable citation and the
    flat retrieval key are *derived* from these fields, so neither can drift out
    of agreement with the reference it describes.

    ``cases`` is the chain of lettered levels: ``["α"]`` is περ. α΄,
    ``["α", "αα"]`` is υποπερ. αα΄ of περ. α΄.

    ``instrument`` is set when ``article`` belongs to a ratified instrument
    rather than to the act itself — see :class:`RatifiedInstrument`. It is a
    nested object rather than a pair of optional fields so that half an address
    cannot be built: a reference naming a καταστατικό without naming the
    article that ratified it would render a citation nobody can resolve.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    act: ActIdentity
    instrument: RatifiedInstrument | None = None
    article: str
    paragraph: str | None = None
    cases: list[str] = []

    @property
    def citation(self) -> str:
        """Render for a human: ``Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄``.

        A reference into a ratified instrument is rendered **act last**, in the
        legislator's own order: ``άρθρο δέκατο πέμπτο παρ. 1 του καταστατικού
        που κυρώθηκε με το άρθρο 13 ν. 5110/2024``. The order is not a style
        choice — the ratification clause ends in an article number, so anything
        appended after it reads as belonging to *that* article. Act-first would
        put «παρ. 1» after «άρθρο 13» and cite a paragraph of the ratifying
        article instead of one of the instrument's.
        """
        act = f"{self.act.act_type} {self.act.number}/{self.act.year}"
        parts = [f"άρθρο {self.article}"]
        if self.paragraph is not None:
            parts.append(f"παρ. {self.paragraph}")
        for depth, case in enumerate(self.cases):
            parts.append(f"{'υπο' * depth}περ. {case}΄")

        if self.instrument is None:
            return f"{act}, " + " ".join(parts)
        parts.append(
            f"{self.instrument.cited_as} που κυρώθηκε με το "
            f"άρθρο {self.instrument.ratifying_article}"
        )
        return " ".join([*parts, act])

    @property
    def key(self) -> str:
        """Flat identifier for the vector store: ``Ν4808/2021/άρθρο-4/παρ-2/περ-α``.

        Greek throughout, per the identifier-alphabet decision — a Latin scheme
        would be a second representation to keep in sync forever.

        A ratified instrument contributes its **ratifying article** and not its
        name: ``ν.5110/2024/άρθρο-13/άρθρο-δέκατο-πέμπτο``. The article number
        already identifies the instrument uniquely inside the act, and it is
        stable, whereas ``cited_as`` is prose carrying a grammatical case. The
        nesting is visible in the path, so a store can filter the instrument's
        provisions from the act's own without parsing a name.
        """
        segments = [
            _slug(f"{self.act.act_type}{self.act.number}"),
            str(self.act.year),
        ]
        if self.instrument is not None:
            segments.append(f"άρθρο-{_slug(self.instrument.ratifying_article)}")
        segments.append(f"άρθρο-{_slug(self.article)}")
        if self.paragraph is not None:
            segments.append(f"παρ-{_slug(self.paragraph)}")
        for depth, case in enumerate(self.cases):
            segments.append(f"{'υπο' * depth}περ-{_slug(case)}")
        return "/".join(segments)
