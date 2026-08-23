Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

The first real RAG loop: embed the V2 chunks, store them in a vector store, retrieve the top-k provisions for a question, and generate a grounded answer with source references. The architecture becomes API-less "service → retrieval → vector store → LLM" per [[Home]]. Equally important: prove — against the [[V1 - Minimal LLM Application]] baseline — that retrieval actually fixes the hallucinations you recorded.

**You'll have learned:** embeddings and vector similarity, pgvector/vector-store mechanics, docker-compose for local infra, grounded prompt construction, and the debugging discipline of testing retrieval separately from generation.

## Steps

- [ ] **1. Set up local infrastructure via `docker-compose`: Postgres + pgvector** — _Why:_ first version with a real service dependency (see Decision below and [[V0 - Project Foundation]]). Compose makes the environment start with one command (`poe up`) and be identical on any machine. Wire the connection URL through Pydantic Settings.
- [ ] **2. Design the storage schema for chunks + embeddings + metadata** — _Why:_ schema design forces the questions that matter: what's a row (a chunk), which metadata columns will be filtered on, what the embedding dimension is (fixed by the model chosen in step 3 — note the coupling). Keep it minimal; [[V6 - Legal Structure and Citations]] will extend it.
- [ ] **3. Choose the embedding model — compare at least two on Greek text** — _Why:_ this is the highest-leverage model decision in the project and *Greek support is not a given*. Compare a hosted multilingual model (e.g. OpenAI text-embedding-3) against an open multilingual model (e.g. BGE-M3, multilingual-e5) on a handful of Greek legal sentences before committing. Record dimensions, cost, and the sanity-check results. Capture the concept as an [[Embeddings]] note.
- [ ] **4. Implement the load pipeline: read `data/processed/` → embed → store; make it idempotent** — _Why:_ re-running ingestion must not duplicate rows — idempotency (e.g. upsert on a stable chunk ID) is the first "pipelines re-run" lesson, cheap to learn now and painful to learn in [[V12 - Production-Oriented System]].
- [ ] **5. Implement semantic search: embed the question → similarity search → top-k chunks** — _Why:_ the core retrieval primitive. Start with exact (sequential) search — the corpus is tiny; indexes (HNSW/IVFFlat) are an optimization to adopt when scale demands it, which is itself a lesson in not pre-optimizing.
- [ ] **6. Inspect retrieval manually before wiring in the LLM** — _Why:_ layered debugging. Run a dozen questions, read the returned chunks. If retrieval returns garbage, the generated answer is unfixable by prompting — and if you wire everything at once you can't tell which layer failed. This separation becomes formal in [[V4 - Question to Relevant Law]].
- [ ] **7. Construct the grounded prompt: retrieved provisions + instructions to answer only from them, cite sources, and say "not found" when the context doesn't cover the question** — _Why:_ grounding instructions are the main lever against hallucination, and the explicit refusal path implements the honesty requirement in [[Home]]'s scope boundary. Watch context size: token cost from step 8 of [[V1 - Minimal LLM Application]] now scales with k.
- [ ] **8. Return answers with source references end-to-end** — _Why:_ extend the V1 `Answer` model with the supporting provisions (law/article/paragraph metadata from the chunks). Rough references are fine here; precision citations are [[V6 - Legal Structure and Citations]]'s job.
- [ ] **9. Re-run the V1 baseline questions through RAG; compare side-by-side** — _Why:_ this is the payoff measurement — the recorded hallucinations from V1 versus grounded answers now. If RAG *didn't* help on some questions, that's not a failure of the exercise; it's the input for step 10.
- [ ] **10. Investigate and log failure cases, sorting each into: retrieval failure (right law never retrieved) vs. generation failure (right chunks retrieved, wrong answer)** — _Why:_ this two-bucket diagnosis is the fundamental RAG debugging skill and directly motivates [[V4 - Question to Relevant Law]] (measuring retrieval) and [[V5 - Hybrid Retrieval]] (fixing it).

## Decisions

- **2026-08-22:** Local infra (vector store / Postgres) runs via `docker-compose`, introduced here rather than in V0, since this is the first version that actually needs a running service (see [[V0 - Project Foundation]] Decisions).
- **2026-08-22:** Vector store: **pgvector inside Postgres**, not a dedicated vector database (Qdrant/Weaviate/Chroma/…). One database serves vectors now *and* the structured/lexical needs of [[V5 - Hybrid Retrieval]] and [[V6 - Legal Structure and Citations]] — one service to run, one query language, and hybrid search stays in-database. A dedicated store is justified at scales/feature-needs this project won't reach; revisit only if pgvector measurably falls short.

## Tools & Alternatives Considered

_To fill during the version: embedding models compared with sanity-check results on Greek; DB driver/ORM choice (psycopg + SQL vs. SQLAlchemy) and why._

## Definition of Done (version-specific)

- `poe up` starts the stack; the load pipeline is idempotent (running twice ≠ duplicates).
- Retrieval can be invoked and inspected independently of generation.
- End-to-end grounded answers include source references; "not found" path works when asked something outside the corpus.
- Baseline comparison (V1 vs. V3 answers) and the failure log are recorded here.

## Notes

_Freeform notes, gotchas, links, technical debt._
