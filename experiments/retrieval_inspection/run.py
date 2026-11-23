"""Inspect retrieval by eye: every question in questions.json, no LLM.

V3 step 6. Writes two files per run under results/, with the same stem:
the JSON is the measurement (rank, key, distance per hit — V5's "before"),
the Markdown is the sheet a human reads. Neither is ever hand-edited; the
findings go in the V3 note.

Nothing here scores. ``expected`` is shown beside the hits so the reader can
judge them; turning that judgement into metrics is V4's job.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from greek_law.compositions import EMBEDDING_MODEL, build_retriever
from greek_law.config import Settings
from greek_law.embedding import EmbeddingError
from greek_law.retrieval import DEFAULT_K, NoEmbeddingsError, RetrievedChunk

HERE = Path(__file__).parent
QUESTIONS_FILE = HERE / "questions.json"
RESULTS_DIR = HERE / "results"

SHEET_K = 10
"""Hits per question on the sheet: twice what step 7 will use, to show misses."""

FULL_TEXT_TOP = DEFAULT_K
"""Hits whose text is printed: exactly the ones step 7 will hand the LLM."""

Result = tuple[dict[str, Any], list[RetrievedChunk]]


def load_questions(path: Path) -> dict[str, Any]:
    """Read the question set. Greek text, so the encoding is stated."""
    book: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return book


def to_record(entry: dict[str, Any], hits: list[RetrievedChunk]) -> dict[str, Any]:
    """One question's measurement: what was asked, what was expected, what came."""
    return {
        "id": entry["id"],
        "question": entry["text"],
        "expected": entry["expected"],
        "hits": [
            {
                "rank": rank,
                "key": hit.chunk.key,
                "citation": hit.chunk.source.citation,
                "distance": round(hit.distance, 4),
            }
            for rank, hit in enumerate(hits, start=1)
        ],
    }


def _cell(text: str | None) -> str:
    """A value safe inside a Markdown table cell: no pipes, no line breaks."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _render_question(
    entry: dict[str, Any], hits: list[RetrievedChunk], full_text_top: int
) -> str:
    expected = "; ".join(entry["expected"]) or "none — not in the corpus"
    lines = [f"## {entry['id']} — {entry['text']}", "", f"**Expected:** {expected}"]
    if entry.get("note"):
        lines.append(f"*{entry['note']}*")
    lines += ["", "| # | distance | citation | article title |", "|---|---|---|---|"]
    for rank, hit in enumerate(hits, start=1):
        citation = hit.chunk.source.citation
        title = hit.chunk.article_title
        lines.append(
            f"| {rank} | {hit.distance:.4f} | {_cell(citation)} | {_cell(title)} |"
        )
    lines += [
        "",
        f"<details><summary>Full text of the top {full_text_top}</summary>",
        "",
    ]
    for rank, hit in enumerate(hits[:full_text_top], start=1):
        lines += [f"**{rank}. {hit.chunk.source.citation}**", "", hit.chunk.text, ""]
    lines += ["</details>", ""]
    return "\n".join(lines)


def render(
    run: dict[str, Any], results: list[Result], full_text_top: int = FULL_TEXT_TOP
) -> str:
    """The whole sheet: a run header, then one section per question."""
    header = [
        "# Retrieval inspection",
        "",
        f"Run {run['started_at']} · set `{run['set_version']}` · "
        f"model `{run['embedding_model']}` · k = {run['k']} · "
        f"full text for the top {full_text_top}",
        "",
    ]
    sections = [_render_question(entry, hits, full_text_top) for entry, hits in results]
    return "\n".join(header + sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect",
        description="Retrieve for every question in the set and write a sheet to read.",
    )
    parser.add_argument("-k", type=int, default=SHEET_K, help="hits per question")
    args = parser.parse_args(argv)

    book = load_questions(QUESTIONS_FILE)
    settings = Settings()
    started = datetime.now(UTC)
    results: list[Result] = []
    try:
        with psycopg.connect(str(settings.database_url)) as conn:
            retriever = build_retriever(settings, conn)
            for entry in book["questions"]:
                print(f"{entry['id']}  {entry['text']}", file=sys.stderr, flush=True)
                results.append((entry, retriever.retrieve(entry["text"], args.k)))
    except (EmbeddingError, NoEmbeddingsError) as error:
        print(f"inspection failed: {error}", file=sys.stderr)
        return 1

    run = {
        "started_at": started.isoformat(timespec="seconds"),
        "set_version": book["set_version"],
        "embedding_model": EMBEDDING_MODEL,
        "k": args.k,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / started.strftime("%Y-%m-%dT%H-%M-%SZ")
    records = [to_record(entry, hits) for entry, hits in results]
    stem.with_suffix(".json").write_text(
        json.dumps({"run": run, "questions": records}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    stem.with_suffix(".md").write_text(render(run, results), encoding="utf-8")
    print(f"Wrote {stem}.json and {stem}.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
