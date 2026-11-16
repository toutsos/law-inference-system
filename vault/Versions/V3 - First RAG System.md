Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** In Progress — started 2026-11-16, with [[V2 - Document Ingestion]] step 10 (manual QA) deferred by the learner's decision; see that note's Technical debt. **Step 1 done 2026-11-16: `poe up` starts Postgres 18 + pgvector 0.8.7.** **Step 2's shape settled 2026-11-16** (one `chunks` table, `jsonb` + generated filter columns, psycopg + `schema.sql`); its SQL waits on the dimension. **Step 3 done 2026-11-16: bge-m3, 1 024 dims** — so step 2's `vector(1024)` is now fixed. Next: step 2's `schema.sql`, then step 4. **Hand-off from [[V1 - Minimal LLM Application]] received 2026-09-07** — the corpus, the comparison set and four inherited requirements are in the Notes below. Read that before step 1.

## Goal

The first real RAG loop: embed the V2 chunks, store them in a vector store, retrieve the top-k provisions for a question, and generate a grounded answer with source references. The architecture becomes API-less "service → retrieval → vector store → LLM" per [[Home]]. Equally important: prove — against the [[V1 - Minimal LLM Application]] baseline — that retrieval actually fixes the hallucinations you recorded.

**You'll have learned:** embeddings and vector similarity, pgvector/vector-store mechanics, docker-compose for local infra, grounded prompt construction, and the debugging discipline of testing retrieval separately from generation.

## Steps

- [x] **1. Set up local infrastructure via `docker-compose`: Postgres + pgvector** — _Why:_ first version with a real service dependency (see Decision below and [[V0 - Project Foundation]]). Compose makes the environment start with one command (`poe up`) and be identical on any machine. Wire the connection URL through Pydantic Settings. — _Done 2026-11-16: `compose.yaml` (one `db` service, `pgvector/pgvector:0.8.7-pg18`, named volume, healthcheck, localhost-only port), `poe up`/`down`/`psql`, `Settings.database_url: PostgresDsn`. First `poe up` pulled and reported Healthy in 34 s; `pg_available_extensions` shows `vector 0.8.7` available, not yet created (step 2 creates it). 4 tests (3 in the new `tests/test_infrastructure.py`, 1 in `tests/test_config.py`), suite 268 → 272 fast + 24 `slow`. See [[Docker Compose]]._
- [ ] **2. Design the storage schema for chunks + embeddings + metadata** — _Why:_ schema design forces the questions that matter: what's a row (a chunk), which metadata columns will be filtered on, what the embedding dimension is (fixed by the model chosen in step 3 — note the coupling). Keep it minimal; [[V6 - Legal Structure and Citations]] will extend it. — _Shape settled 2026-11-16 (option A, see Decisions); the `schema.sql` itself is written after step 3 fixes the dimension, so this step closes together with step 3._
- [x] **3. Choose the embedding model — compare at least two on Greek text** — _Why:_ this is the highest-leverage model decision in the project and *Greek support is not a given*. Compare a hosted multilingual model (e.g. OpenAI text-embedding-3) against an open multilingual model (e.g. BGE-M3, multilingual-e5) on a handful of Greek legal sentences before committing. Record dimensions, cost, and the sanity-check results. Capture the concept as an [[Embeddings]] note. — _Done 2026-11-16: **bge-m3** (Ollama, 1 024 dims), Recall@5 1.00 / MRR 0.902 against qwen3-embedding:0.6b's 0.82 / 0.723 on the 17-question dev set `embedding-dev-v1` (disjoint from V1's q01–q10). `experiments/embedding_comparison/` (script, set, results); 8 tests in `tests/test_embedding_comparison.py` (1 `slow`). V2's oversized-chunk check closed: longest chunk 5 142 bge-m3 tokens < 8 192. Full numbers and reasoning in [[Embeddings]]._
- [ ] **4. Implement the load pipeline: read `data/processed/` → embed → store; make it idempotent** — _Why:_ re-running ingestion must not duplicate rows — idempotency (e.g. upsert on a stable chunk ID) is the first "pipelines re-run" lesson, cheap to learn now and painful to learn in [[V12 - Production-Oriented System]].
- [ ] **5. Implement semantic search: embed the question → similarity search → top-k chunks** — _Why:_ the core retrieval primitive. Start with exact (sequential) search — the corpus is tiny; indexes (HNSW/IVFFlat) are an optimization to adopt when scale demands it, which is itself a lesson in not pre-optimizing.
- [ ] **6. Inspect retrieval manually before wiring in the LLM** — _Why:_ layered debugging. Run a dozen questions, read the returned chunks. If retrieval returns garbage, the generated answer is unfixable by prompting — and if you wire everything at once you can't tell which layer failed. This separation becomes formal in [[V4 - Question to Relevant Law]].
- [ ] **7. Construct the grounded prompt, and fix the two rule bugs the V1 baseline exposed** — retrieved provisions + instructions to answer only from them, cite sources, and say "not found" when the context doesn't cover the question. _Carried from V1:_ (a) rule 3 is too weak to stop the «δεν εμπίπτει στο ρόλο μου» dodge — identifying a provision *is* the role; (b) nothing forbids asserting a law does not exist, which four of ten baseline answers did, one of them while claiming a cutoff three months *after* the law's publication. Both were left unfixed in V1 on purpose so its answers stay the clean no-retrieval-no-fix datapoint; this is where they get fixed, and `PROMPT_VERSION` bumps here anyway — _Why:_ grounding instructions are the main lever against hallucination, and the explicit refusal path implements the honesty requirement in [[Home]]'s scope boundary. Watch context size: token cost from step 8 of [[V1 - Minimal LLM Application]] now scales with k.
- [ ] **8. Return answers with source references end-to-end** — _Why:_ extend the V1 `Answer` model with the supporting provisions (law/article/paragraph metadata from the chunks). Rough references are fine here; precision citations are [[V6 - Legal Structure and Citations]]'s job.
- [ ] **9. Re-run the V1 baseline questions through RAG; compare side-by-side** — _Why:_ this is the payoff measurement — the recorded hallucinations from V1 versus grounded answers now. If RAG *didn't* help on some questions, that's not a failure of the exercise; it's the input for step 10. — _The harness already exists:_ question set `n5110-2024-v1`, `poe baseline` writing to `experiments/baseline_no_rag/results/`, hand-written verdicts in `annotations/`, `poe review` rendering the sheet. Point the runner at the RAG path, keep the same question ids, write a second results file, annotate it with the same vocabulary. **`q03` was scored `unmeasured_probe` in V1 and must be re-scored here** — the model failed a level before the άρθρο 15 / άρθρο δέκατο πέμπτο ambiguity could catch it, so this is the first run in which that probe can actually fire.
- [ ] **10. Investigate and log failure cases, sorting each into: retrieval failure (right law never retrieved) vs. generation failure (right chunks retrieved, wrong answer)** — _Why:_ this two-bucket diagnosis is the fundamental RAG debugging skill and directly motivates [[V4 - Question to Relevant Law]] (measuring retrieval) and [[V5 - Hybrid Retrieval]] (fixing it).

## Decisions

- **2026-08-22:** Local infra (vector store / Postgres) runs via `docker-compose`, introduced here rather than in V0, since this is the first version that actually needs a running service (see [[V0 - Project Foundation]] Decisions).
- **2026-08-22:** Vector store: **pgvector inside Postgres**, not a dedicated vector database (Qdrant/Weaviate/Chroma/…). One database serves vectors now *and* the structured/lexical needs of [[V5 - Hybrid Retrieval]] and [[V6 - Legal Structure and Citations]] — one service to run, one query language, and hybrid search stays in-database. A dedicated store is justified at scales/feature-needs this project won't reach; revisit only if pgvector measurably falls short.
- **2026-11-16 (step 1): image `pgvector/pgvector:0.8.7-pg18` via `compose.yaml` (option A), pinned, named volume, port bound to 127.0.0.1.** Rejected: building pgvector on the official `postgres` image (B — re-does published work) and a Homebrew install (C — not reproducible). Details and the PG18 volume-path gotcha in [[Docker Compose]].
- **2026-11-16 (step 1): `CREATE EXTENSION IF NOT EXISTS vector` belongs to step 2's schema SQL, not a compose init script** — the learner's choice (option 2). Init scripts run only on a fresh volume and are silently skipped afterwards; the schema SQL runs on every load and is idempotent. Compose stays pure infrastructure.
- **2026-11-16 (step 1): `database_url` is a `PostgresDsn`, not `str`** — a malformed URL fails when `Settings` loads, not at the first query. The default carries a committed local-only password; a hosted database later gets its URL from `.env` and is the moment to consider `SecretStr`.
- **2026-11-16 (step 2): one `chunks` table — a row is a chunk; the whole `Chunk` as `jsonb`, filter columns promoted, the embedding beside it (option A).** Rejected: normalised `acts`/`articles`/`chunks` (B — structure nobody queries before [[V6 - Legal Structure and Citations]]) and one wide column-per-field table (C — hand-written row↔`Chunk` mapping becomes a second definition of `Chunk`). Reading a row back is `Chunk.model_validate(row["chunk"])`; Pydantic stays the only definition of the shape.
  - **Columns:** `key text PRIMARY KEY` (step 4 upserts on it) · `chunk jsonb NOT NULL` (source of truth) · promoted, **generated from `chunk` by Postgres** (`GENERATED ALWAYS AS (…) STORED`): `document_id`, `act_type`, `act_number`, `act_year int`, `instrument_article` (null outside a ratified instrument), `article`, `paragraph` · `embedding vector(n) NOT NULL` · `embedding_model text NOT NULL` (mixing two models' vectors becomes detectable) · `embedded_text_hash text NOT NULL` (sha256 of `embedding_text`; step 4 skips unchanged chunks).
  - **Generated columns are the tutor's refinement of A, made 2026-11-16:** A's one weakness was the promoted columns drifting from the JSON. If Postgres computes them from `chunk`, they cannot — the same "derive, never store twice" rule `SourceReference.citation` follows. Cost: the expressions are JSON paths that must follow the model's field names; a renamed field fails at insert, loudly.
  - **The dimension `n` waits for step 3** — learner's choice over swapping steps or an unsized `vector` (which cannot be indexed).
- **2026-11-16 (step 2): plain `schema.sql` applied by `psycopg`, every statement `IF NOT EXISTS`, starting with `CREATE EXTENSION IF NOT EXISTS vector`.** No ORM, no migration tool until the schema first *changes* (expected V5/V6). See Tools & Alternatives.

## Tools & Alternatives Considered

**Embedding model — 2026-11-16 (step 3): bge-m3.** Compared by retrieval over the whole corpus (method B), local models only by the learner's decision. Full table, per-question analysis and the eliminated candidates in [[Embeddings]]. In one line: bge-m3 17/17 in the top 5; qwen3-embedding:0.6b 14/17 with its instruction, losing every paraphrase question and the no-shared-keyword one (d05) at rank 107, while spending ~3× the tokens on Greek.

**Database access — 2026-11-16 (step 2): psycopg + plain SQL.**

| Option | Java analogue | Verdict |
| --- | --- | --- |
| **psycopg** (3.x) + `schema.sql` | JDBC + a `.sql` script | **Chosen.** One table, a handful of queries; the SQL is the thing being learned (`<=>`, `jsonb`, `ON CONFLICT`). |
| SQLAlchemy (ORM or Core) | JPA/Hibernate | Rejected for now: an ORM would hide exactly the vector and upsert SQL this version teaches, and would re-declare `Chunk`'s shape a third time. |
| Alembic migrations | Flyway/Liquibase | Deferred to the first schema *change* (V5 full-text column or V6 hierarchy). Until then `IF NOT EXISTS` is enough, and a dev database can be dropped with `docker compose down -v`. |

## Definition of Done (version-specific)

- `poe up` starts the stack; the load pipeline is idempotent (running twice ≠ duplicates).
- Retrieval can be invoked and inspected independently of generation.
- End-to-end grounded answers include source references; "not found" path works when asked something outside the corpus.
- Baseline comparison (V1 vs. V3 answers) and the failure log are recorded here.

## Notes

### Hand-off from step 3 to step 4 — 2026-11-16

- **Every `/api/embed` call must send `"truncate": false` and `"options": {"num_ctx": 8192}`.** Ollama's default context can be smaller than the model's, and it truncates silently. The comparison script's first run is how this surfaced (for Qwen); for bge-m3 the explicit 8 192 is what keeps the 5 142-token longest chunk whole.
- **No query/document prefixes for bge-m3** — the question and the chunk are embedded as they are. (Qwen's instruction is moot now.)
- **Embedding the corpus takes ~4 minutes** (252 s, one request per chunk). Step 4's `embedded_text_hash` skip is what keeps re-runs cheap; batching (several inputs per request) is the other lever if it is ever needed.

### ⚠️ `q10` is no longer a pure "not found" question — 2026-11-16

Found while drafting step 3's comparison questions: **π.δ. 62/2025 άρθρο 580 is titled «Ψηφιακή κάρτα εργασίας».** V1's `q10` asks which article *of ν. 5110/2024* governs the digital work card; it was written when the corpus was that one law. The correct answer is still "none in ν. 5110/2024" — but retrieval over the whole corpus will now (rightly) surface άρθρο 580 of a different act. So the canary changes meaning in step 9: the failure to watch for is the model **attributing άρθρο 580 to ν. 5110/2024**, a citation that looks grounded and is wrong. The best answer is "not in ν. 5110/2024; π.δ. 62/2025 άρθρο 580 covers it". Decide in step 9 whether the annotation for `q10` needs a new expected outcome; do not edit `questions.json` (set `n5110-2024-v1` must stay comparable to V1).

### Hand-off from V2 — 2026-11-10

What V2's chunking (steps 6–7) hands this version, and what it expects back. See [[Chunking]].

- **A chunk is one paragraph: 2 136 in the corpus.** `Chunk.key` (e.g. `π.δ.62/2025/άρθρο-84/παρ-3`) is unique across the corpus — a slow test pins it — so step 4 can upsert on it.
- **Embed `Chunk.embedding_text`, show `Chunk.text`.** The first opens with a header (citation, then article title) so short paragraphs carry their subject; the second is the law as printed. Putting the header in a prompt as quoted law would put our words in the legislator's mouth.
- **Step 3 owes V2 a check:** 25 chunks are over 4 000 characters (`oversized_chunks`). Once the embedding model is chosen, compare them against its real limit; most multilingual models truncate silently.
- **Citations are article + paragraph, no page.** `Chunk.document_id` resolves to the manifest entry and from there to the PDF's URL and hash. Page provenance is [[V6 - Legal Structure and Citations]] step 4's.

### Hand-off from V1 — 2026-09-07

V1 closed with a measured baseline, not an anecdote. What V3 inherits, and what it owes back.

**The corpus is already chosen: ν. 5110/2024, ΦΕΚ Α' 75/24.05.2024** (`data/raw/fek_a_75_2024.pdf`, 82 articles, 60 pages). It was picked for V1's question set precisely so that V2 ingests it and V3 retrieves from it — the same ten questions then measure the *same system with and without retrieval*, which is the only clean form this comparison takes. Published after the model's training data, so the no-retrieval condition is genuinely no-knowledge rather than partial recall. Note `data/` is gitignored: [[V2 - Document Ingestion]] step 2's manifest is what makes the corpus reproducible, and it must record this ΦΕΚ.

**The V1 result, in one line: 0 of 10 answers cited a correct provision.** 5 fabricated, 2 refused-but-fabricated-anyway, 2 refused cleanly, 1 correct outcome. Eight of ten contained a fabricated or misattributed citation. The full annotated sheet is at `experiments/baseline_no_rag/reviews/2026-09-07T16-53-31Z.md`.

**Four requirements this version must satisfy.**

1. **One variable moves at a time.** V1's answers are the only no-retrieval, unfixed-prompt datapoint that will ever exist for this corpus. Step 7 changes the prompt *and* step 5 adds retrieval, so a V3 run differs from V1 in two ways at once — which is fine for "did RAG help" and useless for "which change helped". If step 10's diagnosis is ambiguous, the cheap tiebreaker is a third run: new prompt, retrieval disabled. `prompt_version` on `AnswerMetadata` exists so those runs are distinguishable after the fact.
2. **Step 10's two buckets are already load-bearing, and `q08` predicts the split.** «Ποιος είναι δικαιούχος των δικαιωμάτων πνευματικής ιδιοκτησίας» — the answer (ο **ανάδοχος**, άρθρο 11 παρ. 1) is counter-intuitive, and V1 gave the intuitive wrong answer. If retrieval supplies άρθρο 11 and the model still says «το Ελληνικό Δημόσιο», that is a **generation** failure and no amount of [[V5 - Hybrid Retrieval]] work will touch it. This is the question to watch when the two buckets are first filled.
3. **`q10` is the regression canary.** It asks which article of ν. 5110/2024 governs the ψηφιακή κάρτα εργασίας; there is none, and V1 correctly refused. Step 7's grounding instructions must not *lose* that refusal — a common failure of "answer only from the context" prompts is that they answer from the nearest available chunk instead. This is also the version-specific DoD's "not found" path, already written as a question.
4. **The «accidental correct token» problem is a warning for step 10, not just for V4.** V1's `q04` said «υπάγεται στον Α/ΓΕΕΘΑ» — correct — inside a wholly invented answer about a Σώμα that does not exist. When sorting a V3 failure into retrieval-vs-generation, a chunk containing the right words is not evidence that the right *provision* was retrieved. Check the `SourceReference`, not the prose.

**What V3 owes back to [[V4 - Question to Relevant Law]]:** the annotation vocabulary (7 verdicts, 6 flags, validated at render time in `review.py`) is a proto-eval-set. V4 formalises it into labels and metrics; it should not invent a second vocabulary without a reason.

_Freeform notes, gotchas, links, technical debt._
