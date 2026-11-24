"""Run the V1 question set: every question in questions.json, with or without RAG.

Without flags it is the V1 baseline — no retrieval. With ``--rag`` (V3 step 9)
the same questions go through ``answer_with_retrieval``, and each record also
stores the citations the model was shown.

The point of this experiment is the *failure* record. Whatever comes back —
invented law numbers, articles that do not exist, answers that dodge — is the
measured motivation for retrieval in V3 and the seed of the eval set in V4.

A file under results/ is a measurement, not a document: never hand-edit one.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from greek_law.application import Question, answer_question, answer_with_retrieval
from greek_law.compositions import EMBEDDING_MODEL, build_client, build_retriever
from greek_law.config import Settings
from greek_law.embedding import EmbeddingError
from greek_law.llm.client import LLMClient
from greek_law.llm.errors import LLMError
from greek_law.retrieval import DEFAULT_K, NoEmbeddingsError, Retriever

HERE = Path(__file__).parent
QUESTIONS_FILE = HERE / "questions.json"
RESULTS_DIR = HERE / "results"


def load_questions(path: Path) -> dict[str, Any]:
    """Read the question set. Greek text, so the encoding is stated, not guessed."""
    book: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return book


def ask(
    entry: dict[str, Any], client: LLMClient, retriever: Retriever | None = None
) -> dict[str, Any]:
    """Ask one question and return its record. A failure is a result, not a crash.

    With a retriever the question is answered through RAG; without one, with
    no retrieval at all — the V1 baseline.
    """
    record: dict[str, Any] = {
        "id": entry["id"],
        "question": entry["text"],
        "probes": entry["probes"],
    }
    question = Question(text=entry["text"])
    try:
        if retriever is None:
            answer = answer_question(question, client)
        else:
            answer = answer_with_retrieval(question, retriever, client)
    except (LLMError, EmbeddingError, NoEmbeddingsError) as error:
        record["error"] = f"{type(error).__name__}: {error}"
        return record

    record["answer"] = answer.text
    record["sources"] = [source.citation for source in answer.sources]
    record.update(answer.metadata.model_dump())
    record["duration_seconds"] = round(answer.metadata.duration_seconds, 2)
    return record


def ask_all(
    questions: list[dict[str, Any]],
    client: LLMClient,
    retriever: Retriever | None = None,
) -> list[dict[str, Any]]:
    """Ask every question in order, echoing progress to stderr."""
    records: list[dict[str, Any]] = []
    for position, entry in enumerate(questions, start=1):
        print(
            f"\n[{position}/{len(questions)}] {entry['id']}  {entry['text']}",
            file=sys.stderr,
            flush=True,
        )
        record = ask(entry, client, retriever)
        print(record.get("answer", record.get("error")), file=sys.stderr, flush=True)
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="baseline",
        description="Ask the V1 question set with no retrieval and save the answers.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Seconds to wait for one answer (default: 180).",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="ID",
        help="Ask only this question id; repeatable.",
    )

    parser.add_argument(
        "--rag",
        action="store_true",
        help="Answer through retrieval (needs `poe up` and `poe load`).",
    )

    args = parser.parse_args(argv)

    book = load_questions(QUESTIONS_FILE)
    questions: list[dict[str, Any]] = book["questions"]
    if args.only:
        wanted = set(args.only)
        questions = [q for q in questions if q["id"] in wanted]
        missing = wanted - {q["id"] for q in questions}
        if missing:
            parser.error(f"unknown question ids: {', '.join(sorted(missing))}")

    settings = Settings(request_timeout=args.timeout)
    client = build_client(settings)

    started = datetime.now(UTC)
    if args.rag:
        retrieval = f"pgvector {EMBEDDING_MODEL} k={DEFAULT_K}"
        try:
            with psycopg.connect(str(settings.database_url)) as conn:
                records = ask_all(questions, client, build_retriever(settings, conn))
        except psycopg.OperationalError as error:
            print(
                f"Cannot reach the database (is `poe up` running?): {error}",
                file=sys.stderr,
            )
            return 1
    else:
        retrieval = "none"
        records = ask_all(questions, client)
    finished = datetime.now(UTC)

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{started.strftime('%Y-%m-%dT%H-%M-%SZ')}.json"
    path.write_text(
        json.dumps(
            {
                "run": {
                    "started_at": started.isoformat(timespec="seconds"),
                    "finished_at": finished.isoformat(timespec="seconds"),
                    "set_version": book["set_version"],
                    "retrieval": retrieval,
                    "model_requested": settings.ollama_model,
                    "base_url": settings.ollama_base_url,
                    "timeout_seconds": args.timeout,
                },
                "answers": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
