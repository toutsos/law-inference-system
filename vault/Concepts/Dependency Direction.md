# Dependency Direction

Part of [[Home]]. First applied in [[V0 - Project Foundation]] (step 5, folder structure).

## What it is / problem it solves

A rule about which package is allowed to `import` which. In this project it is stated as one sentence:

> **Dependencies point inward, toward the code that changes least.**

`domain/` sits at the centre and imports nothing from the rest of the application. Every other package may import `domain/`; `domain/` may import none of them.

```
llm/       ──────►  domain/
ingestion/ ──────►  domain/
retrieval/ ──────►  domain/
evaluation/ ─────►  domain/
                      ▲
             (imports nothing internal)
```

The problem it solves is **change containment**. Without the rule, packages import each other opportunistically, and the import graph becomes a cycle-ridden mesh. Then swapping any component means touching everything that touched it — the cost of a change stops being proportional to its size, which is the thing that actually makes codebases unpleasant to work in.

The general name for this is the **dependency rule** (also: dependency inversion, hexagonal / ports-and-adapters architecture).

## Why we're using it here

Derived by the learner on 2026-08-23 from a concrete question — *should `domain/` import from `llm/`?* — rather than adopted as received wisdom:

> "Domain should never import from llm, the reason is that domain must never depend on the llm so that we can safely replace it without having to touch domain."

That is exactly the argument, and it is load-bearing for this project specifically:

- [[V1 - Minimal LLM Application]] deliberately starts with **Ollama and swaps in a hosted provider later**. That swap is only cheap if nothing outside `llm/` knows a provider exists.
- [[V3 - First RAG System]] introduces pgvector, [[V5 - Hybrid Retrieval]] adds BM25 and reranking. Each is an infrastructure change that must not propagate into the model of what a Greek law *is*.

Two consequences worth stating explicitly, because they are the payoff:

1. **Testability.** `domain/` tests require no model running, no database, no network, no API key — fast and deterministic, therefore actually run. This is the same reason V1 can test prompt construction against a fake `LLMClient`.
2. **Cycles become impossible.** Python reports a circular import loudly, but the loud failure is not the real damage — the quiet damage is that two packages which import each other are no longer separable, and any claim about "replaceable components" is fiction.

## How to tell it is being followed

Mechanical checks, not judgement calls:

- `grep -r "ollama" src/` hits **only** `src/greek_law/llm/`. A vendor name outside its adapter package means the seam has leaked.
- Nothing under `src/greek_law/domain/` imports another `greek_law.*` package, nor any I/O or framework library (no `httpx`, no `psycopg`, no SDK).
- Deleting `llm/` entirely would leave `domain/` importable and its tests passing.

If enforcement ever needs teeth, ruff's `flake8-tidy-imports` banned-API rules can fail the build on a forbidden import — worth considering in [[V12 - Production-Oriented System]] if drift shows up. Not worth it yet.

## Alternatives considered

- **Flat module layout, no package boundaries** — nothing to violate, because nothing is separated. Rejected in V0's decisions: the target architecture is already known and starting structured costs nearly nothing.
- **Layered by technical kind** (`models/`, `services/`, `utils/`) — the conventional alternative. Rejected because it groups code by what it *is* rather than what it is *about*, so a single feature scatters across every folder and the architecture stops being visible in the directory listing.

## Used in

- [[V0 - Project Foundation]] — establishes `domain/` as the dependency-free core.
- [[V1 - Minimal LLM Application]] — `llm/` imports `domain/`, never the reverse; the seam that makes the Ollama → hosted-provider swap cheap.
- [[V2 - Document Ingestion]], [[V3 - First RAG System]], [[V5 - Hybrid Retrieval]] — each new adapter package points inward.

## Notes

- The rule constrains **imports**, not knowledge. `llm/` is entitled to know a lot about `domain/`; that is what the arrow means.
- Watch for the subtle violation: putting something in `domain/` that only exists to serve one adapter (a field shaped for the vector store, a method the prompt template needs). It compiles, imports cleanly, and still couples the core to infrastructure. The test is whether the concept would still make sense to a lawyer.
