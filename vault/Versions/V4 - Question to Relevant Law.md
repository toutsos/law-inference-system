Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Make "which provisions are relevant to this question?" a first-class, *measured* capability instead of a side effect of RAG. This version builds the project's first evaluation muscle: a small hand-curated question set, retrieval metrics, and a measure → analyze → improve → re-measure loop. From here on, retrieval changes are judged by numbers, not vibes.

**You'll have learned:** how to build an eval set, Recall@K and ranking metrics (MRR), error analysis on false positives/negatives, and the one-change-at-a-time experimental discipline.

## Steps

- [ ] **1. Define the retrieval result schema: law, article, paragraph, score, source metadata** — _Why:_ a typed result object decouples "find relevant provisions" from "answer the question," letting this capability be exposed on its own (a user may just want the relevant articles) and evaluated on its own.
- [ ] **2. Build a manually curated eval set: 15–30 natural-language questions, each labeled with the provisions that *should* be retrieved** — _Why:_ manual curation is deliberate — writing labels forces you to define what "relevant" even means (the whole article? the specific paragraph?), and that definition decision shapes every metric after. Seed it with the [[V1 - Minimal LLM Application]] baseline questions; store it as data in the repo, because [[V7 - Evaluation Framework]] will reuse and grow it.
- [ ] **3. Implement Recall@K and a ranking metric (e.g. MRR)** — _Why:_ Recall@K answers "did the right provision appear in the top k at all?" (the ceiling on answer quality); MRR answers "how high?" (which determines how large k — and thus the prompt — must be). Implement them yourself rather than importing a framework: they're ~20 lines each and you'll never misread them again.
- [ ] **4. Run the baseline measurement on the current V3 retriever and record the numbers here** — _Why:_ improvements in step 6 and the hybrid work in [[V5 - Hybrid Retrieval]] are only claims unless there's a before-number.
- [ ] **5. Error analysis: inspect every false negative (relevant provision missed) and the worst false positives** — _Why:_ aggregate metrics say *that* it fails; only reading the failures says *why* — vocabulary mismatch, bad chunk boundaries, missing metadata, question phrasing. Classify the failures; the categories decide what to try next.
- [ ] **6. Make targeted improvements (chunking, metadata, embedding choice, k) — one change at a time, re-measuring after each** — _Why:_ changing two things and seeing +5% teaches nothing about which one worked. This loop — hypothesis from error analysis, single change, re-measure — is the core skill of applied ML engineering, and it's what this version exists to drill.

## Decisions

- **2026-08-22:** V4's evaluation is intentionally lightweight: a small, manually curated eval set and retrieval-only metrics (Recall@K, ranking quality), used to decide whether/how to pursue hybrid retrieval in [[V5 - Hybrid Retrieval]]. Full automated evaluation — reusable dataset, generation-quality and citation-accuracy metrics, regression tracking across changes — is deferred to [[V7 - Evaluation Framework]] so the two versions don't duplicate scope.
- **2026-08-22:** Retrieval metrics (Recall@K, MRR) are **implemented by hand, not imported from an eval framework** — they are tiny, and implementing them is the fastest way to actually understand them. Framework adoption is a [[V7 - Evaluation Framework]] question.

## Tools & Alternatives Considered

_Track libraries/tools adopted in this version and alternatives discussed._

## Definition of Done (version-specific)

- Eval set committed to the repo with documented labeling criteria.
- Baseline and post-improvement Recall@K / MRR numbers recorded here, with the change that produced each delta.
- Failure categories from error analysis written up — they are the input to [[V5 - Hybrid Retrieval]]'s justification.

## Notes

- **Candidate improvement (not committed):** if failure analysis shows plain chunks underperform on decontextualized/short passages, try enriching chunk metadata beyond the structural fields already captured in [[V2 - Document Ingestion]] (law name, number, year, article/paragraph refs) — e.g. an LLM-generated per-chunk or per-article summary, or topic/keyword tags — either stored as retrievable metadata or prepended to the chunk text before embedding ("contextual retrieval"-style). Unlike the structural metadata from V2, this requires an LLM call at ingestion time (cost/latency/non-determinism), so only adopt it if measured Recall@K/ranking failures actually justify it — don't build it speculatively.
