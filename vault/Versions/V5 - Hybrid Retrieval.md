Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Add lexical (keyword/full-text) retrieval alongside semantic retrieval and combine them. The motivation should already be visible in [[V4 - Question to Relevant Law]]'s failure analysis: embeddings are weak exactly where legal search is demanding — exact identifiers («ν. 4808/2021», «άρθρο 15»), precise terminology, and rare terms. Every addition in this version must pay for itself on the V4 eval set.

**You'll have learned:** how lexical search (BM25/full-text) actually works, its Greek-language pitfalls, score fusion (RRF), reranking, and how to run and record retrieval experiments honestly.

## Steps

- [ ] **1. Study the concept: how BM25/full-text ranking works and why it complements embeddings** — _Why:_ lexical and semantic retrieval fail in *opposite* directions (exact-match blindness vs. vocabulary-mismatch blindness) — understanding this asymmetry is what makes "hybrid" a principled design rather than a buzzword. Capture as a [[BM25]] concept note.
- [ ] **2. Investigate Greek-language support in the chosen engine before building on it** — _Why:_ this is the trap step. Postgres full-text search needs a Greek stemmer/dictionary configuration, and accents/final-sigma handling (`unaccent`, the normalization from [[V2 - Document Ingestion]]) determine whether «εργαζόμενος» matches «εργαζομένου». Test on real corpus text *first*; a lexical index that silently doesn't stem Greek gives worthless comparisons in step 4.
- [ ] **3. Implement lexical retrieval (Postgres full-text or BM25) returning the same result schema as semantic retrieval** — _Why:_ a shared result schema (from [[V4 - Question to Relevant Law]]) makes the two retrievers interchangeable and fusible — an interface-design lesson as much as a retrieval one.
- [ ] **4. Evaluate lexical-alone vs. semantic-alone on the V4 eval set; compare per-question, not just in aggregate** — _Why:_ the aggregate may be similar while the per-question wins differ completely — and it's exactly that disagreement that predicts how much hybrid fusion can gain.
- [ ] **5. Implement hybrid fusion, starting with Reciprocal Rank Fusion** — _Why:_ RRF combines rankings without needing the two incomparable score scales to be calibrated — that insight (rank vs. score) is the key concept. It's also a few lines of code, keeping the first hybrid understandable.
- [ ] **6. Evaluate hybrid against both single strategies; tune only what the numbers justify (k per retriever, RRF constant)** — _Why:_ hybrid usually wins, but *verify it here* — this corpus and question style are what matter, not benchmark folklore.
- [ ] **7. Introduce reranking (e.g. a cross-encoder) only if the eval shows top-k contains the right provisions but ranks them poorly** — _Why:_ reranking adds a model, latency, and complexity; the specific symptom it treats is "good recall, bad ordering." If Recall@K is the problem instead, reranking cannot help — knowing which lever matches which failure is the lesson.
- [ ] **8. Record every experiment in a results table here: configuration → Recall@K / MRR → verdict** — _Why:_ an experiment that isn't recorded gets re-run; a table of what was tried and rejected is as valuable as the winning configuration, and [[V7 - Evaluation Framework]] will automate this habit.

## Decisions

_Record decisions as they're made: what we chose, what alternatives we considered, and why._

## Tools & Alternatives Considered

_To fill during the version: Postgres FTS vs. external BM25 (e.g. rank-bm25 in-process, or a search engine like OpenSearch — likely overkill); cross-encoder reranker options if step 7 triggers._

## Definition of Done (version-specific)

- Greek stemming/accent handling verified with real examples recorded here.
- Experiment table shows lexical vs. semantic vs. hybrid numbers on the V4 eval set.
- The shipped retrieval strategy is the one the numbers picked — and the note explains why.

## Notes

_Freeform notes, gotchas, links, technical debt._
