"""Cut an assembled act into the pieces V3 will embed: one per paragraph.

A chunk is the unit retrieval returns and an answer cites, so its boundaries
are the citation's precision. The paragraph is chosen because it is the only
unit where one chunk is one citable provision — «άρθρο 84 παρ. 3» — which the
article (citation stops at «άρθρο 84») and merged paragraphs («παρ. 2–4») both
give up. See the step 6 decision in the V2 note.

A paragraph alone can be a poor thing to embed: «2. Η παρ. 1 ισχύει από
1.1.2025.» says nothing about its subject. So the text that gets embedded opens
with a header naming the provision and its article's title, while the text
that gets *shown* stays exactly as the gazette printed it.

Each chunk also says which corpus document it came from — the manifest ``id``,
which leads to the PDF's URL and SHA-256 — and where it sits in the act's
containers. Document-level facts stay in the manifest, looked up by that id,
rather than being copied onto every chunk. See the step 7 decision.
"""

from pydantic import BaseModel, ConfigDict, Field

from greek_law.domain import Act, SourceReference, StructuralUnit
from greek_law.ingestion.manifest import CorpusDocument

OVERSIZED_CHARS = 4000
"""Embedding text longer than this is reported by :func:`oversized_chunks`.

Not a limit anything enforces. Many multilingual embedding models read about
512 tokens — very roughly 1 500–2 000 Greek characters — and silently drop the
rest; others read 8 000. Which applies is V3 step 3's choice, so oversized
paragraphs are kept whole by the step 6 decision and this number only says
which of them to look at first when the model is known.
"""


class Chunk(BaseModel):
    """One paragraph, ready to be embedded and cited.

    Stores what cannot be derived — the reference, the article's title, the
    paragraph's text — and derives the rest, for the reason
    :class:`~greek_law.domain.SourceReference` derives its citation: a stored
    header could drift out of agreement with the reference it describes.

    ``document_id`` is the manifest entry the text was extracted from: the
    link from a citation back to the exact published bytes. ``path`` is the
    article's containers (ΜΕΡΟΣ, ΚΕΦΑΛΑΙΟ, …), outermost first — metadata to
    filter and group on, never part of a citation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(pattern=r"^[a-z0-9_]+$")
    source: SourceReference
    article_title: str | None = None
    path: list[StructuralUnit] = []
    text: str

    @property
    def key(self) -> str:
        """The chunk's stable identity — the reference's flat key."""
        return self.source.key

    @property
    def header(self) -> str:
        """The citation, then the article's title on a line of its own."""
        if self.article_title is None:
            return self.source.citation
        return f"{self.source.citation}\n{self.article_title}"

    @property
    def embedding_text(self) -> str:
        """What V3 embeds: the header, a blank line, the paragraph as printed."""
        return f"{self.header}\n\n{self.text}"


def chunk_act(act: Act, document: CorpusDocument) -> list[Chunk]:
    """One chunk per paragraph of ``act``, in the act's own order.

    ``document`` is the manifest entry ``act`` was assembled from, and it must
    describe the same act: a mismatched pair would link every chunk to the
    wrong PDF, and every citation would still look right. So a mismatch is an
    error, not a chunk list.

    Every paragraph becomes a chunk and nothing else does: a paragraph is never
    split, however long — by the step 6 decision, oversized ones are kept whole
    and reported by :func:`oversized_chunks` until V3 knows the embedding
    model's limit. An unnumbered paragraph is cited at article level, which is
    unambiguous because an article has at most one.
    """
    if document.act != act.identity:
        raise ValueError(
            f"manifest entry {document.id!r} describes {document.act}, "
            f"not the act being chunked ({act.identity})"
        )
    return [
        Chunk(
            document_id=document.id,
            source=SourceReference(
                act=act.identity,
                instrument=article.instrument,
                article=article.number,
                paragraph=paragraph.number,
            ),
            article_title=article.title,
            path=article.path,
            text=paragraph.text,
        )
        for article in act.articles
        for paragraph in article.paragraphs
    ]


def oversized_chunks(chunks: list[Chunk], limit: int = OVERSIZED_CHARS) -> list[Chunk]:
    """The chunks whose embedding text is longer than ``limit`` characters.

    Measured on :attr:`Chunk.embedding_text` rather than on the paragraph,
    because that is what the model reads and truncates. A report, not a
    filter, like every other in this pipeline: the chunks stay in the output,
    and this names them so that a silent truncation in V3 has a list to check.
    """
    return [chunk for chunk in chunks if len(chunk.embedding_text) > limit]
