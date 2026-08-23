Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Harden the system as if it were going to production: CI, containerization, security review, resilience, caching where justified, and cost/performance review — finishing with an architecture retrospective. Not because this project will serve customers, but because production-hardening is a distinct skill set with its own concepts (CI pipelines, secret management, prompt injection, cache invalidation) that the tutorial would otherwise never touch.

**You'll have learned:** CI for LLM projects, container builds, LLM-specific security thinking, resilience patterns at system level, caching trade-offs, and how to run an architecture retrospective.

## Steps

- [ ] **1. Set up CI (e.g. GitHub Actions): lint + tests on every push; decide how evals fit in** — _Why:_ CI is the enforcement layer for every habit built since V0 — locally-run checks stop being run under pressure. The LLM twist worth wrestling with: full eval runs cost money and are slow, so decide deliberately (deterministic tests always; eval smoke subset on PRs; full eval on demand).
- [ ] **2. Harden configuration and secrets management: strict settings validation, no secret ever logged or traced, document rotation** — _Why:_ revisits the V0 config seam with production eyes — [[V11 - Observability]] added rich logging, which is precisely how keys leak; auditing log/trace output for secrets is the concrete exercise.
- [ ] **3. Security and data-handling review, including the LLM-specific surface: prompt injection via corpus documents, tool-call injection, output handling** — _Why:_ new attack class most engineers haven't internalized: anything the model reads is a potential instruction channel — a poisoned document could steer tool calls in [[V9 - Agentic Workflow]]. Even with a trusted legal corpus, *reasoning through* the threat model (what could a malicious document make the agent do?) is the lesson. Capture as a [[Prompt Injection]] concept note.
- [ ] **4. Review error handling and retries end-to-end as a system: consistent retry/backoff policy at each boundary (LLM, DB, tools), no double-retry stacking** — _Why:_ resilience was added piecemeal (V1 LLM errors, V8 tool errors, V10 timeouts); the system-level pass catches the composition bugs — like a retrying client inside a retrying agent step turning one failure into nine calls.
- [ ] **5. Improve ingestion scalability: profile ingestion on a larger corpus; batch embedding calls; keep re-runs incremental** — _Why:_ the 5-law pipeline meets its limits — the idempotency from [[V3 - First RAG System]] evolves into incremental processing (only new/changed documents), which is the germ of a real data pipeline and the honest test of whether tooling like ZenML (from [[Home]]'s tech direction) is ever justified here.
- [ ] **6. Add caching only where measurement justifies it (embedding cache for repeated texts; response caching decided consciously)** — _Why:_ caching is the classic "obvious win" that quietly breaks correctness — a cached answer survives corpus updates and prompt changes. The invalidation question ("when is this stale?") must be answered *before* each cache exists, not after a stale answer ships.
- [ ] **7. Generate and polish API documentation from the FastAPI schemas** — _Why:_ near-free thanks to [[V8 - Tools and Structured Operations]]'s schema-first design — the exercise is reviewing the generated OpenAPI docs as an outsider and fixing what's unclear, which is an interface-quality audit in disguise.
- [ ] **8. Containerize the application and compose it with the infrastructure** — _Why:_ completes the story begun in V3 — infra was containerized, now the app joins it, and `docker compose up` runs the whole system anywhere. Learn the Python image basics that actually matter: lockfile-based install, slim image, no secrets baked into layers.
- [ ] **9. Review performance and cost with V11's data: cost per question by path (plain RAG vs. agentic), where money and time go, what a monthly bill would look like** — _Why:_ the economics conversation every real LLM product has, run on your own numbers — and the final payoff of the cost-logging habit started in [[V1 - Minimal LLM Application]] step 8.
- [ ] **10. Final architecture review and retrospective: what would you redesign, which technologies earned their place, what's the recorded technical debt — then pick next directions from [[Home]]'s Long-Term Extensions** — _Why:_ the retrospective is where experience consolidates into judgment — write it down here; it's the tutorial's actual final artifact.

## Decisions

_Record decisions as they're made: what we chose, what alternatives we considered, and why._

## Tools & Alternatives Considered

_Track libraries/tools adopted in this version and alternatives discussed._

## Definition of Done (version-specific)

- CI green on a fresh clone; eval policy (what runs when) documented.
- Threat-model write-up for prompt/tool injection recorded, with any mitigations applied.
- `docker compose up` runs app + infrastructure from scratch.
- Cost-per-question figures and the architecture retrospective written up here.

## Notes

_Freeform notes, gotchas, links, technical debt._
