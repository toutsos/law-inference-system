# Greek Law AI Assistant

A progressive project for learning modern AI engineering through implementation.

See [[Agent Instructions]] for how the tutor (Claude Code) should behave throughout this project — read that note first, every session.

## Purpose

The purpose of this project is to build a real, progressively evolving AI application that retrieves and explains Greek legislation while serving as a practical learning environment for modern LLM engineering.

The project should begin as a small, understandable RAG application and evolve incrementally into a system incorporating structured data, hybrid retrieval, evaluation, tool use, agentic workflows, concurrency, observability, and production-oriented engineering.

## Learning Objectives

- Understand how an end-to-end LLM/RAG application is architected rather than only learning framework APIs.
- Apply the engineering patterns and tools from the LLM Engineer's Handbook where they provide real value.
- Learn to make technology and architecture decisions based on requirements and trade-offs.
- Keep core application/domain logic understandable and avoid unnecessary framework abstraction.
- Learn by implementing the code personally; the tutor should guide, review, challenge, and explain rather than write the whole project.
- Build a project that can progressively introduce advanced AI concepts without artificial complexity.

## Core Product Vision

The application should allow a user to ask questions in natural language and identify the Greek laws, articles, paragraphs, and other legal provisions relevant to the question. It should then provide a grounded answer supported by identifiable source provisions.

**Example interaction:**

> User: "What rights does an employee have when their employer terminates their contract?"

The system should identify potentially relevant legislation, rank the relevant provisions, retrieve the supporting text, and eventually explain the answer with citations and reasoning.

## Initial Technology Direction

Learning targets, not immutable requirements — revisit each when the project reaches the relevant problem.

- **Python** — Primary implementation language.
- **Pydantic** — Structured schemas, validation, and clear interfaces between components.
- **FastAPI** — Application/API layer.
- **PostgreSQL** — Structured storage and metadata.
- **Vector database / pgvector** — Semantic retrieval of legal provisions.
- **Embeddings** — Semantic representation of legal text and questions.
- **BM25/full-text search** — Exact terminology and identifiers such as law numbers and article references.
- **LLM provider** — Answer generation, structured outputs, and eventually tool calling.
- **OpenTelemetry or equivalent** — Tracing and observability when the application becomes complex enough.
- **Evaluation tooling** — Retrieval and answer-quality evaluation.
- **Agent/orchestration framework** — Introduced only when multi-step tool use genuinely requires it.
- **ZenML or similar pipeline tooling** — Considered only if the project develops repeatable data/ML pipelines that justify it.

## Suggested Architecture Evolution

The architecture should evolve rather than be designed fully in advance.

- **Early:** API → application service → LLM
- **RAG:** API → service → retrieval → vector store → LLM
- **Hybrid:** API → service → semantic + lexical retrieval → fusion/reranking → LLM
- **Agentic:** API → agent/service → tools → retrieval/database/external services → LLM
- **Production:** API → application → orchestration → domain/retrieval/tools → infrastructure, with evaluation and observability across the system

## Versions

Each version is a living note with a **Goal**, ordered **Steps** (each step carries its *why*), **Decisions**, **Tools & Alternatives**, and a version-specific **Definition of Done** — update them as work happens. Work through the steps in order; don't start the next version until the current one is stable (see Definition of Done in [[Agent Instructions]]).

- [ ] [[V0 - Project Foundation]] — repo, uv, folder structure, tooling, config, domain models, corpus choice.
- [ ] [[V1 - Minimal LLM Application]] — LLM client seam, prompts, error handling, cost logging, no-RAG baseline.
- [ ] [[V2 - Document Ingestion]] — acquire, extract, normalize (Greek Unicode), parse structure, chunk, persist.
- [ ] [[V3 - First RAG System]] — pgvector via docker-compose, embeddings, semantic retrieval, grounded answers.
- [ ] [[V4 - Question to Relevant Law]] — first eval set, Recall@K/MRR, error analysis, measured improvements.
- [ ] [[V5 - Hybrid Retrieval]] — lexical/BM25 (Greek pitfalls), RRF fusion, reranking if justified.
- [ ] [[V6 - Legal Structure and Citations]] — full hierarchy, canonical citations as structured data, provenance.
- [ ] [[V7 - Evaluation Framework]] — reusable dataset, generation metrics, LLM-as-judge, regression tracking.
- [ ] [[V8 - Tools and Structured Operations]] — schema-validated tools, LLM-legible errors, FastAPI introduced.
- [ ] [[V9 - Agentic Workflow]] — hand-built agent loop, termination/budgets, framework comparison.
- [ ] [[V10 - Concurrent Execution]] — profile first, asyncio fan-out/fan-in, partial-failure handling.
- [ ] [[V11 - Observability]] — structured logs, correlation IDs, traces with tokens/cost, trace-driven debugging.
- [ ] [[V12 - Production-Oriented System]] — CI, security (prompt injection), caching, containerization, retrospective.

## Long-Term Possible Extensions

- Legislative amendments and temporal/version-aware retrieval.
- Cross-law comparison.
- EU legislation and links between EU and Greek provisions.
- Case-law retrieval as a separate evidence source.
- Knowledge graph representing relationships between laws, articles, amendments, directives, and institutions.
- Question decomposition for complex legal scenarios.
- Multi-step research agents.
- Human-in-the-loop review.
- Advanced retrieval and reranking experiments.
- Fine-tuning or domain adaptation experiments when the project has enough evaluation data to justify them.
- Production deployment and cost/latency optimization.

## Important Scope Boundary

This project is an educational/research engineering project and should **not** be treated as a substitute for professional legal advice. The system should prioritize source attribution, version awareness, uncertainty, and evidence over confident unsupported answers.

---

**Guiding principle:** Build the simplest useful system first. Add complexity only when a real requirement, measured failure, or learning objective justifies it.
