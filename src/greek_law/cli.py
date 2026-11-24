"""The command-line edge of the application: argv in, exit code out.

It is no longer the composition root — that moved to ``compositions.py`` when
the baseline experiment became a second entry point. What is left here is the
part that is genuinely about a terminal: parsing arguments, configuring
logging, printing to stdout, and choosing an exit code.
"""

import argparse
import logging
import sys

import psycopg

from greek_law.application import (
    Answer,
    Question,
    answer_with_retrieval,
    is_not_found,
)
from greek_law.compositions import build_client, build_retriever
from greek_law.config import Settings
from greek_law.embedding import EmbeddingError
from greek_law.llm.client import LLMClient
from greek_law.llm.errors import LLMError
from greek_law.retrieval import NoEmbeddingsError, Retriever

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    """Send our own logs to stderr at the configured level, and nobody else's.

    basicConfig sets the *root* logger, which every library inherits from, so
    configuring it alone would hand httpcore's TCP handshake the same level we
    wanted for ourselves.
    """
    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("greek_law").setLevel(settings.log_level)


def _log_usage(answer: Answer) -> None:
    """Record what the call cost.

    Local inference has no price per token, so the units are tokens, seconds
    and tokens/second — the decision recorded on 2026-08-29.
    """

    usage = answer.metadata
    rate = usage.tokens_out / usage.duration_seconds if usage.duration_seconds else 0.0
    logger.info(
        "model=%s prompt=%s tokens_in=%d tokens_out=%d duration=%.2fs "
        "rate=%.1f tok/s attempts=%d",
        usage.model,
        usage.prompt_version,
        usage.tokens_in,
        usage.tokens_out,
        usage.duration_seconds,
        rate,
        usage.attempts,
    )
    if usage.finish_reason == "length":
        logger.warning("The answer was cut off at the token limit; it is incomplete.")


def _render(answer: Answer) -> str:
    """The answer, then its sources one per line — unless it is a refusal."""
    if not answer.sources or is_not_found(answer.text):
        return answer.text
    lines = [answer.text, "", "Πηγές:"]
    lines.extend(f"- {source.citation}" for source in answer.sources)
    return "\n".join(lines)


def run(question: str, retriever: Retriever, client: LLMClient) -> int:
    """Answer one question and report it. Returns a process exit code."""
    try:
        answer = answer_with_retrieval(Question(text=question), retriever, client)
    except (EmbeddingError, NoEmbeddingsError, LLMError) as error:
        logger.error("%s: %s", type(error).__name__, error)
        return 1

    _log_usage(answer)
    print(_render(answer))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="greek-law",
        description="Ask a question about Greek legislation.",
    )
    parser.add_argument("question", help="The question, in Greek or English.")
    args = parser.parse_args(argv)

    settings = Settings()
    _configure_logging(settings)
    try:
        with psycopg.connect(str(settings.database_url)) as conn:
            retriever = build_retriever(settings, conn)
            return run(args.question, retriever, build_client(settings))
    except psycopg.OperationalError as error:
        logger.error("Cannot reach the database (is `poe up` running?): %s", error)
        return 1
