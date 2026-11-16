"""Compare embedding models on the dev set: Recall@5 and MRR over the whole corpus.

V3 step 3, method B. Every chunk in data/processed/ is embedded with each
model, each dev question is embedded and every chunk ranked against it by
cosine similarity, and a question scores by the rank of the first chunk it
expects.

Throwaway: it calls Ollama's /api/embed with httpx directly. The production
embedding seam is step 4's design, and this script must not pre-empt it.

A file under results/ is a measurement, not a document: never hand-edit one.

    uv run python -m experiments.embedding_comparison.run
"""

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from greek_law.config import Settings
from greek_law.ingestion.chunking import Chunk
from greek_law.ingestion.processed import DEFAULT_PROCESSED_DIR, read_chunks

HERE = Path(__file__).parent
QUESTIONS_FILE = HERE / "questions.json"
RESULTS_DIR = HERE / "results"

# Each model's own maximum context, so nothing is ever truncated. Measured
# 2026-11-16: qwen3-embedding spends ~3x more tokens on Greek than bge-m3;
# the longest chunk (ν. 5110/2024 άρθρο 18) is 5 142 vs 13 814 tokens.
NUM_CTX: dict[str, int] = {"bge-m3": 8192, "qwen3-embedding:0.6b": 32768}
TOP_K = 5

QWEN_INSTRUCTION = (
    "Instruct: Given a question about Greek legislation, retrieve the legal "
    "provisions that answer it\nQuery:{question}"
)

MODELS: dict[str, dict[str, str]] = {
    "bge-m3": {"plain": "{question}"},
    "qwen3-embedding:0.6b": {"instructed": QWEN_INSTRUCTION, "plain": "{question}"},
}


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    tokens: int


Embed = Callable[[str], Embedding]


@dataclass(frozen=True)
class DevQuestion:
    id: str
    text: str
    expected_keys: list[str]


def load_dev_set(path: Path) -> tuple[str, list[DevQuestion]]:
    """The set's version and its questions."""
    book = json.loads(path.read_text(encoding="utf-8"))
    questions = [
        DevQuestion(id=q["id"], text=q["text"], expected_keys=q["expected_keys"])
        for q in book["questions"]
    ]
    return book["set_version"], questions


def load_corpus(directory: Path) -> list[Chunk]:
    """Every chunk of every document in ``directory``, in file order."""
    chunks = [
        chunk
        for path in sorted(directory.glob("*.jsonl"))
        for chunk in read_chunks(path)
    ]
    if not chunks:
        raise FileNotFoundError(f"no chunks in {directory}; run `poe ingest` first")
    return chunks


def check_expected_keys(
    questions: Sequence[DevQuestion], corpus_keys: set[str]
) -> None:
    """Refuse to score a question that points at a chunk the corpus lacks."""
    unknown = [
        f"{q.id}: {key}"
        for q in questions
        for key in q.expected_keys
        if key not in corpus_keys
    ]
    if unknown:
        raise ValueError("expected keys not in the corpus:\n" + "\n".join(unknown))


def normalize(vector: Sequence[float]) -> list[float]:
    """Scale to length 1, so a dot product between two vectors is their cosine."""
    length = math.sqrt(sum(x * x for x in vector))
    return [x / length for x in vector]


def rank_keys(
    query: Sequence[float], keys: Sequence[str], vectors: Sequence[Sequence[float]]
) -> list[str]:
    """Every key, most similar first. All vectors must already be normalized."""
    scores = [sum(q * d for q, d in zip(query, v, strict=True)) for v in vectors]
    order = sorted(range(len(keys)), key=lambda i: scores[i], reverse=True)
    return [keys[i] for i in order]


def first_hit_rank(expected: Sequence[str], ranked: Sequence[str]) -> int | None:
    """1-based position of the first expected key in ``ranked``; None if absent."""
    wanted = set(expected)
    for position, key in enumerate(ranked, start=1):
        if key in wanted:
            return position
    return None


def recall_at(ranks: Sequence[int | None], k: int) -> float:
    """Share of questions whose first expected chunk is in the top ``k``."""
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    """Mean of 1/rank; a question never found contributes 0."""
    return sum(1 / r for r in ranks if r is not None) / len(ranks)


def evaluate_model(
    chunks: Sequence[Chunk],
    questions: Sequence[DevQuestion],
    templates: dict[str, str],
    embed: Embed,
) -> dict[str, Any]:
    """Embed the corpus once, then score every query template against it."""
    keys = [chunk.key for chunk in chunks]
    vectors: list[list[float]] = []
    tokens: list[int] = []
    started = time.perf_counter()
    for count, chunk in enumerate(chunks, start=1):
        embedding = embed(chunk.embedding_text)
        vectors.append(normalize(embedding.vector))
        tokens.append(embedding.tokens)
        if count % 250 == 0:
            print(f"  {count}/{len(chunks)} chunks", file=sys.stderr)
    corpus_seconds = time.perf_counter() - started

    longest = max(range(len(chunks)), key=lambda i: tokens[i])
    characters = sum(len(chunk.embedding_text) for chunk in chunks)
    return {
        "dimensions": len(vectors[0]),
        "corpus_seconds": round(corpus_seconds, 1),
        "max_tokens": tokens[longest],
        "max_tokens_key": keys[longest],
        "characters_per_token": round(characters / sum(tokens), 2),
        "variants": {
            name: _score(template, questions, keys, vectors, embed)
            for name, template in templates.items()
        },
    }


def _score(
    template: str,
    questions: Sequence[DevQuestion],
    keys: Sequence[str],
    vectors: Sequence[Sequence[float]],
    embed: Embed,
) -> dict[str, Any]:
    ranks: list[int | None] = []
    per_question: list[dict[str, Any]] = []
    for question in questions:
        query = normalize(embed(template.format(question=question.text)).vector)
        ranked = rank_keys(query, keys, vectors)
        rank = first_hit_rank(question.expected_keys, ranked)
        ranks.append(rank)
        per_question.append({"id": question.id, "rank": rank, "top": ranked[:TOP_K]})
    return {
        "recall_at_5": round(recall_at(ranks, TOP_K), 3),
        "mrr": round(mean_reciprocal_rank(ranks), 3),
        "questions": per_question,
    }


def ollama_embedder(http: httpx.Client, model: str) -> Embed:
    """An Embed that asks Ollama, and fails rather than truncate a long input."""

    def embed(text: str) -> Embedding:
        response = http.post(
            "/api/embed",
            json={
                "model": model,
                "input": text,
                "truncate": False,
                "options": {"num_ctx": NUM_CTX[model]},
            },
        )
        if response.is_error:
            raise RuntimeError(
                f"{model}: HTTP {response.status_code}: {response.text}\n"
                f"input starts: {text[:80]!r}"
            )
        body = response.json()
        return Embedding(vector=body["embeddings"][0], tokens=body["prompt_eval_count"])

    return embed


def summary(results: dict[str, Any]) -> str:
    """A scores table, then each question's rank under every model/variant."""
    columns = [(m, v) for m, r in results.items() for v in r["variants"]]
    lines = [
        f"{'model / variant':36}{'R@5':>6}{'MRR':>7}{'dims':>6}"
        f"{'max tok':>9}{'ch/tok':>8}{'corpus s':>10}"
    ]
    for model, variant in columns:
        r = results[model]
        v = r["variants"][variant]
        lines.append(
            f"{model + ' / ' + variant:36}{v['recall_at_5']:>6.2f}{v['mrr']:>7.3f}"
            f"{r['dimensions']:>6}{r['max_tokens']:>9}"
            f"{r['characters_per_token']:>8}{r['corpus_seconds']:>10}"
        )
    lines += ["", "Rank of the first expected chunk:"]
    lines += [f"  [{i}] {m} / {v}" for i, (m, v) in enumerate(columns, start=1)]
    lines.append(
        "     " + "".join(f"{f'[{i}]':>7}" for i in range(1, len(columns) + 1))
    )
    first_model, first_variant = columns[0]
    ids = [
        q["id"] for q in results[first_model]["variants"][first_variant]["questions"]
    ]
    for n, question_id in enumerate(ids):
        ranks = [results[m]["variants"][v]["questions"][n]["rank"] for m, v in columns]
        lines.append(f"{question_id:5}" + "".join(f"{str(r):>7}" for r in ranks))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="embedding_comparison",
        description="Score embedding models on the dev set (Recall@5, MRR).",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=sorted(MODELS),
        help="run only this model (repeatable); default: all",
    )
    args = parser.parse_args(argv)

    set_version, questions = load_dev_set(QUESTIONS_FILE)
    chunks = load_corpus(DEFAULT_PROCESSED_DIR)
    check_expected_keys(questions, {chunk.key for chunk in chunks})

    started = datetime.now(UTC)
    results: dict[str, Any] = {}
    with httpx.Client(base_url=Settings().ollama_base_url, timeout=120) as http:
        for model in args.model or list(MODELS):
            print(f"{model}: embedding {len(chunks)} chunks", file=sys.stderr)
            results[model] = evaluate_model(
                chunks, questions, MODELS[model], ollama_embedder(http, model)
            )

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{started.strftime('%Y-%m-%dT%H-%M-%SZ')}.json"
    record = {
        "set_version": set_version,
        "started_at": started.isoformat(timespec="seconds"),
        "num_ctx": NUM_CTX,
        "top_k": TOP_K,
        "models": results,
    }
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(summary(results))
    print(f"\nwritten {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
