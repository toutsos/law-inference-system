Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

The smallest useful LLM application: a question goes in, a prompt is built, an LLM answers, the answer comes back through typed models — as a plain Python function/CLI, no HTTP. This version is about learning to talk to an LLM *through a clean seam* so that everything built later (RAG, tools, agents) plugs into an interface you control rather than a vendor SDK scattered through the codebase.

**You'll have learned:** LLM API mechanics (tokens, context window, temperature, cost), prompt structure (system vs. user messages), how to wrap a provider behind an interface, how to test LLM-dependent code without calling the LLM, and — critically — what the model gets *wrong* without retrieval.

## Steps

- [ ] **1. Choose the LLM provider and model; record pricing** — _Why:_ this is the project's first real technology decision — compare at least two options (capability on Greek text, cost per million tokens, structured-output support, rate limits) and record the choice below. Nothing else in this version can start without it.
- [ ] **2. Wire the API key through Pydantic Settings** — _Why:_ the config seam from [[V0 - Project Foundation]] exists precisely for this; the key lives in `.env`, never in code, never in git.
- [ ] **3. Learn the raw API first: one throwaway script calling the SDK directly** — _Why:_ before wrapping anything, see what a request/response actually contains — messages, roles, token counts, finish reasons. Abstractions are only understandable after the thing they abstract.
- [ ] **4. Design a thin `LLMClient` interface and implement it for the chosen provider** — _Why:_ a seam you own means the provider can be swapped, calls can be faked in tests, and cross-cutting concerns (logging, retries, cost tracking) have one home. Keep it thin — a leaky wrapper that re-exposes the whole SDK teaches nothing and protects nothing.
- [ ] **5. Define Pydantic request/response models for the application boundary** — _Why:_ `answer_question(Question) -> Answer` with typed models is the contract every later version extends (V3 adds sources, V6 adds citations); starting typed avoids a painful retrofit.
- [ ] **6. Write the first prompt as a named, versioned template (not an f-string inline)** — _Why:_ prompts are code — they need a home, a diff history, and later ([[V7 - Evaluation Framework]]) regression tests. Include a system prompt that sets the legal-assistant role and the honesty constraints from [[Home]]'s scope boundary.
- [ ] **7. Add error handling for the failure modes LLM APIs actually have: timeouts, rate limits (429), transient 5xx** — _Why:_ these are not exotic; they happen weekly. Decide what the application does for each (retry with backoff? fail loudly?) instead of letting exceptions leak raw.
- [ ] **8. Log token usage and estimated cost per call** — _Why:_ cost awareness must become a habit before RAG multiplies prompt sizes ([[V3 - First RAG System]]) and agents multiply call counts ([[V9 - Agentic Workflow]]).
- [ ] **9. Test the non-LLM parts with a fake `LLMClient`** — _Why:_ tests that hit a real LLM are slow, non-deterministic, and cost money; the interface from step 4 exists so prompt construction, parsing, and error handling can be tested deterministically. This is the dependency-inversion pattern in miniature.
- [ ] **10. Baseline experiment: ask 5–10 real Greek legal questions with *no* retrieval; save the answers** — _Why:_ this is the pedagogical hinge of the whole project. Record where the model hallucinates law numbers, invents articles, or answers vaguely. These failures are the *measured motivation* for RAG in [[V3 - First RAG System]], and the same questions become the seed of the eval set in [[V4 - Question to Relevant Law]].

## Decisions

- **2026-08-22:** Defer introducing FastAPI/HTTP API layer. V1 (and subsequent versions) expose the application as plain Python functions/a CLI until a concrete need for an external-facing interface arises (e.g. when tools/agents in [[V8 - Tools and Structured Operations]] or later need to be called externally). Avoids HTTP plumbing distracting from the LLM/RAG concepts being learned first.
- **2026-08-22:** V1 ends with a **recorded no-RAG baseline** (step 10). Every architectural addition in this project should be justified by an observed failure or measurement, not by fashion — this baseline is the first instance of that discipline.

## Tools & Alternatives Considered

_To fill during the version: provider comparison (capabilities on Greek, pricing, SDK quality), retry libraries (tenacity vs. hand-rolled backoff), prompt storage (module constants vs. template files)._

## Definition of Done (version-specific)

- A question typed at the CLI returns an answer end-to-end through the typed models.
- Provider outages/rate limits produce controlled behavior, not stack traces.
- Non-LLM logic is covered by tests using the fake client.
- The no-RAG baseline answers are saved in the repo (or linked here) with hallucinations annotated.

## Notes

_Freeform notes, gotchas, links, technical debt._
