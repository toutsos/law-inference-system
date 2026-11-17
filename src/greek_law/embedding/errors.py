"""The failures the embedding seam reports, as types a caller can catch.

The same rule as the LLM seam's errors: nothing outside an ``Embedder``
implementation imports ``httpx`` to handle a failure.

There is no transient/permanent split yet, unlike ``greek_law.llm.errors``:
that split exists to drive a retry policy, and the load pipeline has none — a
failed load is simply re-run, and the hash skip resumes it where it stopped.
Add the split when something first wants to retry.
"""


class EmbeddingError(Exception):
    """Base class for every failure raised through the Embedder seam."""


class EmbeddingUnavailableError(EmbeddingError):
    """The provider could not be reached, timed out, or failed (HTTP 5xx)."""


class EmbeddingRequestError(EmbeddingError):
    """The provider rejected the request (HTTP 4xx): unknown model, input too long."""


class EmbeddingProtocolError(EmbeddingError):
    """The provider answered, but not with one vector of the right size per text."""
