# Embeddings

Part of [[Home]]. Introduced in [[V3 - First RAG System]] (step 3). Stored with [[Docker Compose]]'s Postgres + pgvector; chunks come from [[Chunking]].

## What it is / problem it solves

An embedding model turns a text into a fixed-length list of numbers (a **vector**, 1 024 of them for bge-m3) such that texts with similar *meaning* get vectors pointing in similar *directions*. Retrieval then becomes geometry: embed the question, find the chunks whose vectors are closest. That is what lets «Δουλεύω από το σπίτι, ποιος πληρώνει τον υπολογιστή;» find a paragraph about «τηλεργασία» and «κόστος του εξοπλισμού» that shares none of its words — which keyword search cannot do.

**Java analogy:** a `hashCode()` that is *deliberately* similar for similar inputs — a locality-preserving hash rather than one designed to scatter.

Vocabulary:

| Term | Meaning |
| --- | --- |
| dimension | the length of the vector; fixed per model; becomes `vector(n)` in the schema |
| cosine similarity | the angle between two vectors: 1 = same direction, ~0 = unrelated. Computed as a dot product once both are normalized to length 1 |
| context length | the most tokens the model reads; beyond it the input is truncated (silently, by default in Ollama) |
| tokenizer | splits text into the model's units; **how many tokens a Greek text costs depends heavily on the model** |
| asymmetric model | queries and documents are embedded differently (e.g. an instruction prefix on queries only) |
| Recall@k / MRR | is the right chunk in the top k / the average of 1 / its rank |

## Why we're using it here

### Decision (2026-11-16, V3 step 3): **bge-m3**, via Ollama, 1 024 dimensions

Measured on the dev set `embedding-dev-v1` (17 questions, 15 from π.δ. 62/2025 and 2 from ν. 5110/2024, written to avoid each article's own vocabulary), ranking all 2 136 chunks by cosine. Results file: `experiments/embedding_comparison/results/2026-11-16T18-07-39Z.json`.

| Model / variant | Recall@5 | MRR | dims | longest chunk (tokens) | chars/token | corpus embed time |
| --- | --- | --- | --- | --- | --- | --- |
| **bge-m3** | **1.00** (17/17) | **0.902** | 1024 | 5 142 | 3.54 | 252 s |
| qwen3-embedding:0.6b, with query instruction | 0.82 | 0.723 | 1024 | 13 814 | 1.14 | 398 s |
| qwen3-embedding:0.6b, no instruction | 0.77 | 0.686 | 1024 | 13 814 | 1.14 | 398 s |

Rank of the first expected chunk, per question (1 = top; >5 is a Recall@5 miss):

| Question | Probes                                                 | bge-m3 | qwen + instruction | qwen plain |
| -------- | ------------------------------------------------------ | ------ | ------------------ | ---------- |
| d01      | probation period, title wording                        | 1      | 2                  | 2          |
| d02      | when wages are paid                                    | 1      | 1                  | 1          |
| d03      | «κρατήσει μέρος του μισθού» vs «συμψηφισμός»           | 3      | 1                  | 1          |
| d04      | harassment, two acceptable paragraphs                  | 1      | 1                  | 1          |
| d05      | **no shared keyword** (working from home → τηλεργασία) | **1**  | **107**            | **81**     |
| d06      | right paragraph among 11 (camera)                      | 1      | 1                  | 1          |
| d07      | «10 το βράδυ» vs «22:00»                               | 1      | 7                  | 8          |
| d08      | legal vs illegal overtime                              | 2      | 1                  | 1          |
| d09      | Sunday pay vs Sunday-rest articles                     | 1      | 1                  | 8          |
| d10      | paternity leave paraphrase                             | 1      | 1                  | 1          |
| d11      | maternity leave vs άρθρο 291                           | 1      | 1                  | 1          |
| d12      | «παντρευτώ» vs «τέλεση γάμου»                          | 1      | 9                  | 7          |
| d13      | answer split over two articles                         | 1      | 1                  | 1          |
| d14      | oversized chunk with a flattened table                 | 1      | 3                  | 2          |
| d15      | «απόλυση» vs «καταγγελία»                              | 1      | 5                  | 4          |
| d16      | the other act, everyday wording                        | 1      | 1                  | 1          |
| d17      | amending article (meaning in the title)                | 2      | 1                  | 1          |

- **bge-m3 found every answer in the top 5, 14 of 17 at rank 1.** Its three non-first ranks lost to genuine near-competitors: d08 ranked illegal overtime (παρ. 5) above legal (παρ. 3) — the exact distinction that question probes; d03 ranked άρθρα 9–10 (other wage provisions) first; d17 ranked άρθρο 58 παρ. 5.
- **Qwen failed hardest on the question built to need meaning alone:** d05 (no shared keyword) at rank 107; bge-m3 rank 1. Qwen also missed d07 («10 το βράδυ» vs «22:00»), d12 («παντρευτώ» vs «τέλεση γάμου») and d15 («απόλυση» vs «καταγγελία») — every miss a paraphrase.
- **Qwen's tokenizer spends ~3× the tokens on Greek** (1.14 vs 3.54 characters per token): it needed a 32 768 context to avoid truncation and took 58% longer. bge-m3 inherits XLM-RoBERTa's 100-language vocabulary; Qwen's is weighted to English, Chinese and code.
- **The query instruction is worth +0.05 Recall@5 / +0.04 MRR to Qwen** — real, and nowhere near the gap.
- **Limits of the evidence:** 17 questions, and bge-m3 hit the ceiling, so the set cannot say how much better a *third* model could be. It does separate these two decisively and in the same direction on nearly every miss.

## Alternatives considered

- **multilingual-e5-large** — eliminated before measuring: 512-token limit, ~10–15% of chunks would be truncated.
- **embeddinggemma** — 2 048-token limit; the longest chunks would not fit.
- **OpenAI text-embedding-3-small** — hosted; left out by the learner's decision (local only). Revisit only if bge-m3 measurably fails in [[V4 - Question to Relevant Law]].
- **Larger Qwen3-Embedding (4b/8b)** — 2 560 / 4 096 dimensions exceed pgvector's 2 000-dimension HNSW limit without `halfvec` or truncation; and the tokenizer cost stays.

## Used in

- [[V3 - First RAG System]] — step 3 choice; step 4 embeds the corpus; step 5 embeds the question.
- [[V5 - Hybrid Retrieval]] — dense half of hybrid search.

## Notes

- **Ollama truncates silently unless told not to.** Send `"truncate": false` and an explicit `num_ctx` (8 192 for bge-m3) on every `/api/embed` call, or a long chunk's tail is dropped and nothing reports it. The comparison script's first run is how this was caught.
- **Normalize before comparing.** Models do not promise unit-length output; a raw dot product ranks by vector length.
- **One model per vector column.** Vectors from two models live in unrelated spaces; comparing them is meaningless and raises no error. Hence `embedding_model` on every row.
