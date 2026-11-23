"""``poe search "…"``: retrieval alone, printed for a human to read.

Step 6's tool: see what retrieval returns before any LLM is involved.
"""

import argparse
import sys

import psycopg

from greek_law.compositions import build_retriever
from greek_law.config import Settings
from greek_law.embedding import EmbeddingError
from greek_law.retrieval.retriever import DEFAULT_K, NoEmbeddingsError, RetrievedChunk


def format_hit(rank: int, hit: RetrievedChunk) -> str:
    """Rank, distance and citation on one line; the law as printed below it."""
    chunk = hit.chunk
    heading = f"{rank}. [{hit.distance:.4f}] {chunk.source.citation}"
    if chunk.article_title is not None:
        heading += f" — {chunk.article_title}"
    return f"{heading}\n{chunk.text}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="greek-law-search",
        description="Print the chunks nearest to a question, nearest first.",
    )
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=DEFAULT_K, help="how many chunks")
    args = parser.parse_args(argv)

    settings = Settings()
    try:
        with psycopg.connect(str(settings.database_url)) as conn:
            hits = build_retriever(settings, conn).retrieve(args.question, args.k)
    except (EmbeddingError, NoEmbeddingsError) as error:
        print(f"search failed: {error}", file=sys.stderr)
        return 1

    for rank, hit in enumerate(hits, start=1):
        print(format_hit(rank, hit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
