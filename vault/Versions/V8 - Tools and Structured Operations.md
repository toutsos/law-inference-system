Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Refactor the system's capabilities into explicit, schema-validated tools (`search_legislation`, `get_article`, …) that can be called by code, by an HTTP API, and — in [[V9 - Agentic Workflow]] — by the LLM itself. This version also ends the API deferral from [[V1 - Minimal LLM Application]]: with well-defined operations finally in hand, FastAPI gets introduced as a thin layer over them. Tools are the bridge from "pipeline" to "agent": the agent version can only be as good as the operations it can invoke.

**You'll have learned:** tool/function-calling mechanics, schema-first interface design, FastAPI as a thin adapter layer, and why tool implementations must stay framework-independent.

## Steps

- [ ] **1. Identify which operations deserve to be explicit tools — and which don't** — _Why:_ the design question comes before any code. Good candidates are discrete, parameterizable, independently useful operations (search by query, fetch article by citation, fetch law metadata); a "do everything" tool defeats the purpose. Deciding the boundaries *is* the API design exercise.
- [ ] **2. Study the concept: how LLM tool/function calling actually works (schema advertised → model emits structured call → application executes → result returned to model)** — _Why:_ before V9 uses it in a loop, understand the mechanism in isolation: the model never executes anything — it emits arguments, and *your code* is the boundary that validates and executes. Capture as a [[Tool Calling]] concept note.
- [ ] **3. Define Pydantic input/output schemas for each tool, with descriptions written for an LLM reader** — _Why:_ dual duty — the same schema validates calls *and* becomes the tool documentation the model reads when deciding what to call. Vague descriptions produce bad tool choices in V9; this is prompt engineering disguised as type annotation.
- [ ] **4. Implement the tools over the existing retrieval/database services (e.g. `search_legislation`, `get_article`, `get_law`)** — _Why:_ tools should be thin adapters over the services built in V3–V6, not new logic — if a tool needs significant new code, either the service layer has a gap or the tool is wrongly scoped. Skip amendment-related tools (`find_amendments`, `compare_versions`) unless the corpus supports them (see [[V6 - Legal Structure and Citations]]'s deferral).
- [ ] **5. Implement execution with validation and *LLM-legible* error handling** — _Why:_ when a tool call fails, the error message becomes model input in V9 — "article 999 not found in ν. 4808/2021; the law has 125 articles" lets the model recover, where a stack trace guarantees flailing. Designing errors as feedback is a new and important habit.
- [ ] **6. Add tool-level tests: valid calls, invalid arguments, not-found paths** — _Why:_ tools are the exact surface the agent will exercise unsupervised in V9; every unhandled edge here becomes a confusing agent failure there, debugged at ten times the cost.
- [ ] **7. Introduce FastAPI, exposing the main operations (ask, search, get article) as HTTP endpoints** — _Why:_ the concrete need deferred since V1 has arrived: tools and answer flows are now clean operations worth exposing beyond the CLI. FastAPI's request/response models are the Pydantic schemas you already have — which is itself the lesson: a good service layer makes the HTTP adapter trivial. Keep it thin; no logic in endpoints.
- [ ] **8. Keep tool implementations independent of any agent framework and of FastAPI** — _Why:_ plain functions with Pydantic schemas can be handed to any provider SDK, framework, or HTTP route. Coupling tools to an orchestration framework now would pre-empt the framework comparison that [[V9 - Agentic Workflow]] is designed to run honestly.

## Decisions

- **2026-08-22:** **FastAPI is introduced in this version**, resolving the deferral recorded in [[V1 - Minimal LLM Application]]. Rationale: V8 is where operations become explicit and schema-validated, so the HTTP layer is finally a thin adapter rather than premature plumbing; and downstream versions ([[V11 - Observability]] request IDs, [[V12 - Production-Oriented System]] API docs/containerization) assume an API exists.

## Tools & Alternatives Considered

_Track libraries/tools adopted in this version and alternatives discussed._

## Definition of Done (version-specific)

- Each tool callable and tested standalone: valid, invalid, and not-found paths covered.
- Tool schemas carry LLM-oriented descriptions; errors are informative strings, not tracebacks.
- FastAPI app serves the main operations; endpoints contain no business logic.

## Notes

_Freeform notes, gotchas, links, technical debt._
