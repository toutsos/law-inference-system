Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** In Progress

## Goal

Build the development skeleton before writing any AI code: repository, dependency management, folder structure, tooling, configuration, testing harness, and domain models. Nothing here is AI-specific — and that's the point. Every later version stands on this foundation, and retrofitting tooling into a grown codebase is far more expensive than setting it up while the project is empty.

**You'll have learned:** modern Python project setup (uv, ruff, pre-commit, pytest), src-layout packaging, typed configuration, and how to model a domain with Pydantic before any feature exists.

## Steps

Work through these in order. Commit after each step — small commits with clear messages are part of the discipline being practiced.

- [x] **1. Define initial scope and non-goals** — _Why:_ writing down what V0–V3 will *not* do (no UI, no HTTP API, no full corpus, no agents) is the cheapest defense against scope creep. Record them in this note under Notes. — _Deliberately deferred, see Notes._
- [x] **2. Install prerequisites: `uv`, a pinned Python version, git** — _Why:_ `uv` manages both Python versions and dependencies; pinning the interpreter (e.g. via `.python-version`) makes the environment reproducible on any machine. — _See [[uv]]._
- [x] **3. Initialize the repository properly: first commit, `.gitignore` covering `.env`, `.venv/`, `data/`, caches** — _Why:_ secrets and large corpus files must never enter git history; adding the ignore rules *before* the files exist prevents accidents you can't fully undo.
- [x] **4. Create the uv project: `pyproject.toml` + lockfile** — _Why:_ PEP 621 metadata plus a lockfile gives deterministic installs; "works on my machine" problems are eliminated at the start, not debugged later. — _See [[uv]]._
- [x] **5. Create the folder structure (src layout)** — _Why:_ see the Decision below; the structure encodes the architecture separation from [[Home]] (domain / ingestion / retrieval / LLM / evaluation) so that later versions have an obvious home for their code instead of everything landing in one file. Create only what V0–V1 needs; add packages when a version needs them. — _`domain/` + `llm/` only; see [[Dependency Direction]]._
- [x] **6. Set up `ruff` (lint + format) with config in `pyproject.toml`** — _Why:_ a single fast tool replaces flake8/black/isort; consistent style from commit one means reviews discuss design, not formatting. — _See [[ruff]]. Outstanding: `exclude = ["vault"]`._
- [x] **7. Set up `pre-commit` running ruff** — _Why:_ checks that run automatically are checks that actually run; relying on memory to lint doesn't survive contact with a deadline. — _See [[pre-commit]]. Hook verified by making it fail on purpose._
- [x] **8. Set up `poethepoet` tasks: `poe test`, `poe lint`, `poe format`** — _Why:_ one memorable command interface that stays stable even when the underlying commands change (later: `poe up` for docker, `poe eval`). — _See [[poethepoet]]._
- [x] **9. Create the configuration module with Pydantic Settings + `.env.example`** — _Why:_ typed, validated config loaded from environment variables (12-factor style) is the seam through which API keys, model names, and DB URLs will flow in every later version; `.env.example` documents what's needed without leaking values. — _Done 2026-08-23: `Settings` with `app_env` + `log_level`, `extra="forbid"`, `.env.example` written. Design and field-set reasoning in [[Configuration]]._
- [x] **10. Set up `pytest` and write one trivial test (e.g. settings load)** — _Why:_ the test harness must exist before features do, so "write a test" is never a setup task blocking a feature task. — _Four tests in `tests/test_config.py`, all passing. See [[Configuration]] for what each covers and why the fourth is a placeholder to delete in V1._
- [x] **11. Define initial domain models: `Act`, `Article`, `Paragraph`, `Case`, `StructuralUnit`, `SourceReference` as Pydantic models** — _Why:_ this forces the first real design conversation — what *is* the structure of Greek legislation? — and gives every later version a shared vocabulary. Expect these models to evolve in [[V2 - Document Ingestion]] and [[V6 - Legal Structure and Citations]]; that's normal. — _Done 2026-08-29: six models, one file per model in `src/greek_law/domain/`, 15 tests. Design per [[Greek Legislation Structure]]; deviations recorded in Decisions below._
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

The `greek-laws/` above **is the repository root** (`Greek_Laws_project/`), not a nested directory — `pyproject.toml`, `src/`, and `tests/` sit beside `vault/`.

Packages are created in the version that first needs them — an empty folder tree invites speculative code.

## Decisions

- **2026-08-22:** Dependency manager: **uv**, not Poetry (despite the reference project, `LLM-Engineers-Handbook`, using Poetry) and not plain pip. uv resolves/locks fast, is PEP 621-native, and is becoming the emerging standard; trade-off is diverging from the reference project's exact commands, which is fine since we're borrowing patterns, not the tool itself.
- **2026-08-22:** Adopt **poethepoet** now (not deferred) for named task commands (test, lint, format, later docker-up), matching the reference project's pattern even at small scale. poe works standalone regardless of dependency manager, so it's compatible with uv.
- **2026-08-22:** Set up **ruff + pre-commit** from V0, not deferred to V12 — cheap now, and catches issues while the codebase is still small.
- **2026-08-22:** Docker/docker-compose for local infrastructure (e.g. Postgres/pgvector) is explicitly **deferred to [[V3 - First RAG System]]**, when a vector store is first needed — V0-V2 have no service dependency to containerize. See V3's Decisions.
- **2026-08-22:** **src layout with one package per architectural concern** (domain, llm, ingestion, retrieval, evaluation), not a flat module layout. Src layout prevents accidentally importing the package from the working directory instead of the installed environment (a classic source of "works locally, breaks in CI"), and the package boundaries mirror the architecture evolution in [[Home]] — so when a version says "add hybrid retrieval," the code has one obvious place to go, and coupling between layers stays visible in the imports. Alternative considered: single flat package until it hurts — rejected because the target architecture is already known and the cost of starting structured is near zero.
- **2026-08-23:** **Python pinned to 3.12** via `.python-version`. Everything in the tech direction from [[Home]] (psycopg 3, pgvector, FastAPI, pydantic v2) is mature on 3.12; 3.13's free-threading and JIT work offers this project nothing it needs. Alternative considered: 3.13 — rejected as risk without benefit. Cheap to change now, expensive once dependencies are locked against it.
- **2026-08-23:** **`uv init --lib`, not `--app`.** `--lib` produces the src layout *and* a real `[build-system]`, which makes the project installable into its own virtualenv — that is what allows `import greek_law` to resolve from `tests/` without `sys.path` manipulation. `--app` would have given a loose script project importable only from its own directory. Details in [[uv]].
- **2026-08-22:** **Domain models are pure data (Pydantic), free of I/O and framework imports.** This keeps the heart of the application understandable and testable without any infrastructure — the "keep domain logic understandable" objective from [[Home]] made concrete. See [[Dependency Direction]] for the import rule this implies and how to check it.
- **2026-08-23:** **Only `domain/` and `llm/` created at V0.** `domain/` is required by step 11, `llm/` by [[V1 - Minimal LLM Application]]. `ingestion/`, `retrieval/`, and `evaluation/` are deliberately *not* created: an empty package is a standing invitation to design its interface early, with no evidence about what it actually needs. The cost avoided is not the folder — it is the premature design decision the folder invites.

- **2026-08-29:** **One module per model** (`article.py`, `paragraph.py`, `case.py`, `structural_unit.py`, `act.py`, `source_reference.py`) rather than a single `models.py`. Learner's reasoning: easier to see what is going on. Holds up at scale — `Paragraph` and `Case` will grow validators in [[V2 - Document Ingestion]], and a single file would become the place every merge conflict happens. `domain/__init__.py` re-exports all six, so consumers write `from greek_law.domain import Article` and the file split stays an implementation detail.
- **2026-08-29:** **Module filenames are lowercase** (`article.py`, not `Article.py`), classes CapWords, per PEP 8. Not cosmetic here: macOS is case-insensitive, so `from ...article import Article` resolves against `Article.py` locally and fails on Linux CI. Same class of defect as the homoglyph trap in [[Greek Legislation Structure]] — two names that look identical to a human and differ to the machine.
- **2026-08-29:** **`Act` / `ActIdentity`, not `Law`.** The corpus will contain Π.Δ. and ΚΥΑ, which are not νόμοι; naming the type `Law` would force either a lie or a rename once the second document type arrives. `ActIdentity` (τύπος + αριθμός + έτος + ΦΕΚ) is split out from `Act` so that a `SourceReference` can carry the identity of the act without carrying its entire text.
- **2026-08-29:** **`extra="forbid"` on every domain model**, matching the choice already made for `Settings` (see [[Configuration]]). In V2 these models will be constructed from dictionaries produced by a parser; a renamed or misspelled key would otherwise be silently dropped and surface as missing text in [[V3 - First RAG System]], far from its cause.
- **2026-08-29:** **`SourceReference.cases` is a flat `list[str]` chain**, not a nested structure — `["α"]` is περ. α΄, `["α", "αα"]` is υποπερ. αα΄ of περ. α΄. A reference points at exactly one provision, so it needs the path down the lettered levels, not the tree; the tree lives in `Paragraph.cases`. This also makes the reference depth-agnostic if a third lettered level ever appears.
- **2026-08-29:** **`citation` and `key` are derived `@property` values, not fields.** Per [[Greek Legislation Structure]]: a stored identifier can drift out of agreement with the structure it claims to describe; a computed one cannot. A test asserts that passing `key=` to the constructor raises, which is `extra="forbid"` doing the enforcing.

- **2026-08-29:** **`frozen=True` on all six domain models.** Not adopted on principle — adopted after the aliasing failure was demonstrated: the V2 parser shares one `StructuralUnit` across every article in a chapter, so a mutable model lets an edit through one article silently corrupt the rest. Full reasoning, alternatives, and the cost to V2's parser in [[Immutable Domain Models]].
- **2026-08-29:** **`Article.path` is a materialized path**, not a nested container tree. The ordered list encodes containment (`[Μέρος Α΄, Κεφάλαιο Α΄]` = chapter inside part), and the tree is reconstructable by grouping on path prefixes — demonstrated, no information lost. Chosen because chapter numbering *restarts* inside each Μέρος in real laws, so a single `chapter` field could not distinguish Μέρος Α΄ › Κεφάλαιο Α΄ from Μέρος Β΄ › Κεφάλαιο Α΄, and because the dominant access pattern (retrieval hands back one provision needing its breadcrumb for prompt context) is a field read here versus a tree walk otherwise. Alternatives: a class per container level (depth fixed at design time) and a recursive `Division` node (articles stop being a flat list). Accepted cost: container titles are denormalized across articles — safe only because the V2 parser is the single writer.

## Tools & Alternatives Considered

- **uv** (chosen) vs. Poetry vs. pip + requirements.txt — full comparison and command reference in [[uv]].
- **ruff** for lint + format — rule sets selected, deferred sets, and the reasoning in [[ruff]].
- **pre-commit** to run ruff (and later other checks) automatically before commits — hook model, the `repo: local` vs. mirror-repo version-drift decision, and config in [[pre-commit]].
- **poethepoet** for task shortcuts instead of a Makefile or raw `uv run` commands everywhere — task set, the mutate/report split, and config in [[poethepoet]].
- **`frozen=True` / immutable value objects** vs. mutable models plus deep-copying in the parser vs. review discipline — the aliasing failure and the cost to V2 in [[Immutable Domain Models]].
- **pydantic-settings** for typed env-based config vs. `os.environ` reads scattered through the code (untyped, unvalidated, undocumented) — what belongs in config, the fail-fast/defaults reasoning, and the deliberately-thin V0 field set in [[Configuration]].

## Definition of Done (version-specific)

- `poe test`, `poe lint`, `poe format` all work; pre-commit blocks a badly formatted commit.
- Settings load from `.env`; a missing required variable fails loudly with a clear error.
- Domain models exist with at least one test exercising validation.
- Sample corpus chosen and documented (source, terms, which laws) — files may be downloaded in [[V2 - Document Ingestion]].

## Notes

### Scope and non-goals (Step 1)

**2026-08-23 — deliberately left open.** Asked what the smallest demoable V0–V3 result would be, the answer was "not sure yet; get everything set up and understand what is happening." That is an honest position at V0 and it was recorded rather than invented — but it is an *accepted gap*, not a completed step. Revisit at the start of [[V1 - Minimal LLM Application]], when there is enough feel for the system to define a target that means something.

Standing non-goals for V0 regardless of the above:

- No LLM calls (that is V1).
- No HTTP/API layer — see the V1 decision deferring FastAPI.
- No corpus files downloaded or parsed (that is [[V2 - Document Ingestion]]); V0 only *chooses* the corpus.
- No `ingestion/`, `retrieval/`, or `evaluation/` packages created before the version that needs them.

### Technical debt

- Step 1's scope/non-goals are partial (above). Undefended against scope creep until V1.
- ~~`.DS_Store` tracked in git~~ — fixed 2026-08-23 (`.gitignore` + `git rm --cached`). Note it remains in history; harmless here, but the same mistake with a `.env` would not be.
- ~~`poe lint` fails on vault Markdown~~ — fixed 2026-08-23 with `exclude = ["vault"]` under `[tool.ruff]`. Cause worth remembering: [[ruff]] formats Python code blocks *inside Markdown*, and the vault deliberately contains anti-pattern snippets (`def collect(item, acc=[])`, a module-level `Settings()`) shown as examples of what *not* to do. Ruff was scanning 29 vault files against 4 real `.py` files.

### `extra="forbid"` demonstrated itself (2026-08-23)

First run of `Settings()` failed:

```
ValidationError: 1 validation error for Settings
log_level
  Extra inputs are not permitted [type=extra_forbidden, input_value='DEBUG']
```

`.env` declared `LOG_LEVEL=DEBUG` while the model had no `log_level` field yet. The guard did exactly what it was chosen for: refused to start, named the offending key, quoted its value. Under pydantic's default `extra="ignore"` the application would have started **silently** with `LOG_LEVEL` doing nothing — an evening lost wondering why debug logging never appeared. See [[Configuration]].

### Session end — 2026-08-29

**Done:** step 11 complete. `Article` written by the learner (including the required-vs-nullable lesson: `str | None` with no default is required, not optional). The remaining five models and their tests were written by the tutor at the learner's explicit request, to be reviewed against [[Greek Legislation Structure]] — the learner's judgement is being spent on whether the model matches the design, not on typing it. `poe test`: 19 passing. `poe lint`: clean.

**Open review items carried forward** (raised with the learner, not yet settled):

1. **NFC normalization has no owner yet.** [[Greek Legislation Structure]] assigns it to ingestion, so the models do not normalize. Until [[V2 - Document Ingestion]] exists, two visually identical strings can both enter the model and compare unequal. Alternative: a field validator on identifier fields, making the invariant unbreakable at the type boundary.
2. **`fek` is a plain `str`.** Structuring it (σειρά / αριθμός / ημερομηνία) would allow filtering and validation, at the cost of parsing work in V2.
3. ~~**Models are mutable.**~~ **Resolved same session:** `frozen=True` on all six. The justification arrived from the learner's question about how paths are built — `path=list(stack)` shallow-copies, so every article in a chapter aliases one `StructuralUnit`, and editing it through one article silently rewrites all of them. See [[Immutable Domain Models]].

**Next:** step 12 — choose the 3–5 law sample corpus. Then [[V1 - Minimal LLM Application]].

### Session end — 2026-08-25

**Done today:** step 10 complete (four config tests passing, `[tool.pytest.ini_options]` set). Step 11's *design* is settled — see [[Greek Legislation Structure]] — but **no model code is written yet**.

**Decisions made today, all recorded in [[Greek Legislation Structure]]:** hybrid model (fixed types for the Law→Article→Paragraph spine, recursion for Περίπτωση→Υποπερίπτωση, organizational containers as a `path` list); unnumbered article text lives in a `Paragraph` with `number=None`; identifiers keep Greek characters, NFC-normalized, no transliteration.

**Note on pace:** the session ended with the learner overwhelmed — four decisions plus a full model spec arrived in one message. Next session should resume with **one small concrete task**, not a spec.

**Start here next time — just this:**

> Write `Article` alone in `src/greek_law/domain/`. Four fields: `number: str` (a string, because `Άρθρο 3Α` exists), `title: str | None`, and leave `paragraphs`/`path` out entirely for now. Add one test constructing it from literals.

Everything else — `Paragraph`, `Case`, `Law`, `SourceReference` — comes after that one works, one model at a time. The recursive `Case` is the hardest and should come last.

### Session end — 2026-08-23

Stopping point, so the next session resumes accurately.

**Green:** steps 2–8 committed and verified. Interpreter pinned at 3.12; `domain/` and `llm/` packages import; ruff configured and excluding the vault; pre-commit hook installed *and proven to refuse a bad commit*; poe tasks defined; pytest installed and resolving from the venv (after the PATH-fallthrough bug in [[poethepoet]]).

**Step 9 nearly done.** `pydantic-settings` in `[project] dependencies`; `config.py` has `Settings` with `app_env` and `extra="forbid"`; `.env` and `.env.example` written.

**Pick up here, in order:**

1. ~~Add `log_level`~~ — done. `uv run python -c "from greek_law.config import Settings; print(Settings().model_dump())"` returns `{'app_env': 'local', 'log_level': 'DEBUG'}`. `DEBUG` rather than the `"INFO"` default proves the `.env` is genuinely read. Precedence is: real environment variable → `.env` → field default, which is what lets identical code run on a server with no `.env` at all.
2. `uv run poe format` — `config.py` trips `I001` (one blank line after the import block, PEP 8 wants two). It reached the working tree because the file is untracked, so the [[pre-commit]] hook has never seen it: hooks only inspect what is staged.
3. Commit everything, confirm `poe lint` green.
4. **Open design question:** `log_level: str` accepts `"BANANA"`; `app_env: str` accepts `"prodd"` — a typo that silently selects production-shaped behaviour. `Literal["DEBUG","INFO","WARNING","ERROR"]` turns that into the same loud startup failure demonstrated above. Worth it for both fields, one, or neither? Real cost: every new valid value becomes a code change.
5. Step 10: `tests/`, `[tool.pytest.ini_options]`, and the throwaway required-field test satisfying the "fails loudly" Definition of Done item (see [[Configuration]]).
6. Steps 11–12 are real design conversations — the structure of Greek legislation, and which 3–5 laws.

_Freeform notes, gotchas, links, technical debt._
