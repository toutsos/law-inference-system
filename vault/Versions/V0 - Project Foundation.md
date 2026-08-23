Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Build the development skeleton before writing any AI code: repository, dependency management, folder structure, tooling, configuration, testing harness, and domain models. Nothing here is AI-specific — and that's the point. Every later version stands on this foundation, and retrofitting tooling into a grown codebase is far more expensive than setting it up while the project is empty.

**You'll have learned:** modern Python project setup (uv, ruff, pre-commit, pytest), src-layout packaging, typed configuration, and how to model a domain with Pydantic before any feature exists.

## Steps

Work through these in order. Commit after each step — small commits with clear messages are part of the discipline being practiced.

- [ ] **1. Define initial scope and non-goals** — _Why:_ writing down what V0–V3 will *not* do (no UI, no HTTP API, no full corpus, no agents) is the cheapest defense against scope creep. Record them in this note under Notes.
- [ ] **2. Install prerequisites: `uv`, a pinned Python version, git** — _Why:_ `uv` manages both Python versions and dependencies; pinning the interpreter (e.g. via `.python-version`) makes the environment reproducible on any machine.
- [ ] **3. Initialize the repository properly: first commit, `.gitignore` covering `.env`, `.venv/`, `data/`, caches** — _Why:_ secrets and large corpus files must never enter git history; adding the ignore rules *before* the files exist prevents accidents you can't fully undo.
- [ ] **4. Create the uv project: `pyproject.toml` + lockfile** — _Why:_ PEP 621 metadata plus a lockfile gives deterministic installs; "works on my machine" problems are eliminated at the start, not debugged later.
- [ ] **5. Create the folder structure (src layout)** — _Why:_ see the Decision below; the structure encodes the architecture separation from [[Home]] (domain / ingestion / retrieval / LLM / evaluation) so that later versions have an obvious home for their code instead of everything landing in one file. Create only what V0–V1 needs; add packages when a version needs them.
- [ ] **6. Set up `ruff` (lint + format) with config in `pyproject.toml`** — _Why:_ a single fast tool replaces flake8/black/isort; consistent style from commit one means reviews discuss design, not formatting.
- [ ] **7. Set up `pre-commit` running ruff** — _Why:_ checks that run automatically are checks that actually run; relying on memory to lint doesn't survive contact with a deadline.
- [ ] **8. Set up `poethepoet` tasks: `poe test`, `poe lint`, `poe format`** — _Why:_ one memorable command interface that stays stable even when the underlying commands change (later: `poe up` for docker, `poe eval`).
- [ ] **9. Create the configuration module with Pydantic Settings + `.env.example`** — _Why:_ typed, validated config loaded from environment variables (12-factor style) is the seam through which API keys, model names, and DB URLs will flow in every later version; `.env.example` documents what's needed without leaking values.
- [ ] **10. Set up `pytest` and write one trivial test (e.g. settings load)** — _Why:_ the test harness must exist before features do, so "write a test" is never a setup task blocking a feature task.
- [ ] **11. Define initial domain models: `Law`, `Article`, `Paragraph`, `SourceReference` as Pydantic models** — _Why:_ this forces the first real design conversation — what *is* the structure of Greek legislation? — and gives every later version a shared vocabulary. Expect these models to evolve in [[V2 - Document Ingestion]] and [[V6 - Legal Structure and Citations]]; that's normal.
- [ ] **12. Choose a small, legally usable sample corpus (3–5 laws)** — _Why:_ a small *fixed* corpus makes every later experiment comparable and every test reproducible. Pick laws relevant to the example use case (e.g. employment law — ν. 4808/2021 territory) so eval questions in [[V4 - Question to Relevant Law]] are natural to write. Verify the source's terms of use.

## Proposed Folder Structure

```
greek-laws/
├── pyproject.toml
├── .python-version
├── .env.example
├── .pre-commit-config.yaml
├── src/
│   └── greek_law/
│       ├── __init__.py
│       ├── config.py          # Pydantic Settings
│       ├── domain/            # Law, Article, Paragraph — pure models, no I/O
│       ├── llm/               # V1: provider client wrapper, prompts
│       ├── ingestion/         # V2: loading, parsing, chunking
│       ├── retrieval/         # V3+: vector store, search, hybrid
│       └── evaluation/        # V4+: eval datasets, metrics
├── tests/
├── data/                      # git-ignored: raw/ and processed/ corpus
└── docker/                    # V3+: compose files for local infra
```

Packages are created in the version that first needs them — an empty folder tree invites speculative code.

## Decisions

- **2026-08-22:** Dependency manager: **uv**, not Poetry (despite the reference project, `LLM-Engineers-Handbook`, using Poetry) and not plain pip. uv resolves/locks fast, is PEP 621-native, and is becoming the emerging standard; trade-off is diverging from the reference project's exact commands, which is fine since we're borrowing patterns, not the tool itself.
- **2026-08-22:** Adopt **poethepoet** now (not deferred) for named task commands (test, lint, format, later docker-up), matching the reference project's pattern even at small scale. poe works standalone regardless of dependency manager, so it's compatible with uv.
- **2026-08-22:** Set up **ruff + pre-commit** from V0, not deferred to V12 — cheap now, and catches issues while the codebase is still small.
- **2026-08-22:** Docker/docker-compose for local infrastructure (e.g. Postgres/pgvector) is explicitly **deferred to [[V3 - First RAG System]]**, when a vector store is first needed — V0-V2 have no service dependency to containerize. See V3's Decisions.
- **2026-08-22:** **src layout with one package per architectural concern** (domain, llm, ingestion, retrieval, evaluation), not a flat module layout. Src layout prevents accidentally importing the package from the working directory instead of the installed environment (a classic source of "works locally, breaks in CI"), and the package boundaries mirror the architecture evolution in [[Home]] — so when a version says "add hybrid retrieval," the code has one obvious place to go, and coupling between layers stays visible in the imports. Alternative considered: single flat package until it hurts — rejected because the target architecture is already known and the cost of starting structured is near zero.
- **2026-08-22:** **Domain models are pure data (Pydantic), free of I/O and framework imports.** This keeps the heart of the application understandable and testable without any infrastructure — the "keep domain logic understandable" objective from [[Home]] made concrete.

## Tools & Alternatives Considered

- **uv** (chosen) vs. Poetry (used by the reference project; mature but slower, older resolver) vs. pip + requirements.txt (simplest, no real lockfile discipline without pip-tools).
- **ruff** for lint + format (single fast tool, replaces flake8/black/isort).
- **pre-commit** to run ruff (and later other checks) automatically before commits.
- **poethepoet** for task shortcuts (`poe test`, `poe lint`, etc.) instead of a Makefile or raw `uv run` commands everywhere.
- **pydantic-settings** for typed env-based config vs. `os.environ` reads scattered through the code (untyped, unvalidated, undocumented).

## Definition of Done (version-specific)

- `poe test`, `poe lint`, `poe format` all work; pre-commit blocks a badly formatted commit.
- Settings load from `.env`; a missing required variable fails loudly with a clear error.
- Domain models exist with at least one test exercising validation.
- Sample corpus chosen and documented (source, terms, which laws) — files may be downloaded in [[V2 - Document Ingestion]].

## Notes

_Freeform notes, gotchas, links, technical debt._
