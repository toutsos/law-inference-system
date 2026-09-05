# HTTPX Exceptions tree: https://www.python-httpx.org/exceptions/

"""The failures the LLM seam reports, as types the application can catch.

A caller must never import ``httpx`` to handle a provider failure — that is the
difference between a seam and a wrapper. Every ``LLMClient`` implementation
translates its own transport's errors into this hierarchy.

The split that matters is transient vs. permanent, because it is the only
question a retry policy needs to ask. It is a branch in the type tree rather
than a flag on the exception, so ``except TransientLLMError`` is the whole
policy.
"""


# Inherit from Exception, never from BaseException (that's reserved for KeyboardInterrupt/SystemExit, and catching it swallows Ctrl-C).
class LLMError(Exception):
    """Base class for every failure raised through the LLMClient seam."""


class TransientLLMError(LLMError):
    """A failure where re-sending the identical request may succeed."""


class PermanentLLMError(LLMError):
    """A failure where re-sending the identical request cannot help."""


class LLMTimeoutError(TransientLLMError):
    """The provider did not respond within the configured timeout."""


class LLMRateLimitedError(TransientLLMError):
    """The provider refused the call for rate or quota reasons (HTTP 429)."""


class LLMUnavailableError(TransientLLMError):
    """The provider is unreachable or failed on its own side (HTTP 5xx)."""


class LLMRequestError(PermanentLLMError):
    """The provider rejected the request as invalid (4xx other than 429)."""


class LLMProtocolError(PermanentLLMError):
    """The provider answered successfully with a body we cannot read."""
