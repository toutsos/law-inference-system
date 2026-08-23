Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Make the system faster where measurement says it's slow, using async concurrency for the I/O-bound work (LLM calls, embeddings, database queries) that dominates latency. The discipline is the point: profile first, parallelize only what's independent, measure the gain, and handle the failure modes concurrency introduces (partial failures, timeouts). Unmeasured optimization is the anti-pattern this version exists to unlearn.

**You'll have learned:** asyncio for I/O-bound workloads, fan-out/fan-in, timeout and partial-failure design, and honest before/after benchmarking.

## Steps

- [ ] **1. Measure first: profile end-to-end latency of representative questions and break it down by stage (retrieval, embedding, LLM, tools)** — _Why:_ concurrency only helps *independent* operations, and only the slow ones matter. The breakdown tells you where the time actually goes — typically the LLM call dwarfs everything, which itself bounds what concurrency can achieve (you can't parallelize a single dependent call).
- [ ] **2. Study the concept: asyncio and why I/O-bound work is its sweet spot** — _Why:_ this system is almost pure network I/O — exactly what cooperative concurrency is for; understanding *why* (waiting doesn't need a CPU, and the GIL is irrelevant to waiting) prevents cargo-culting async onto CPU-bound work later. Capture as an [[Asyncio]] concept note.
- [ ] **3. Identify genuinely independent operations from step 1's map** — _Why:_ candidates: semantic + lexical retrieval in the hybrid ([[V5 - Hybrid Retrieval]]) run concurrently; embedding batches; independent tool calls in an agent step ([[V9 - Agentic Workflow]]). Dependency analysis before code — parallelizing dependent steps is a correctness bug, not a speedup.
- [ ] **4. Convert the relevant client seams to async (LLM client, DB access) where step 3 justifies it** — _Why:_ async spreads through call chains ("function coloring"), so this touches interfaces designed back in [[V1 - Minimal LLM Application]] — a real-world lesson in how cross-cutting concerns ripple. Convert only the paths that benefit; a blanket rewrite is churn without measurement.
- [ ] **5. Implement fan-out/fan-in for the chosen spots (e.g. `asyncio.gather` over both retrievers, then fuse)** — _Why:_ the fundamental concurrency pattern — scatter independent work, await all, combine — and in the hybrid-retrieval case the fusion step from V5 is already the natural fan-in point.
- [ ] **6. Handle timeouts and partial failures deliberately: per-operation timeouts, and a decision per fan-out about degraded results** — _Why:_ concurrency creates a new state that sequential code never had — *some* branches succeeded. Is semantic-only acceptable when lexical times out? Answering per-case (degrade vs. fail) is resilience design, and it must be explicit, not accidental.
- [ ] **7. Measure after; record the before/after latency comparison here** — _Why:_ closes the loop from step 1 — the speedup is a number or it didn't happen. Also record where concurrency *didn't* help; negative results prevent future re-litigating.
- [ ] **8. Evaluate whether framework-level orchestration would improve maintainability of the concurrent flows** — _Why:_ revisits the [[V9 - Agentic Workflow]] framework verdict with new evidence: concurrent branches and partial failures are where graph-style orchestrators earn their keep, if they ever do here.

## Decisions

_Record decisions as they're made: what we chose, what alternatives we considered, and why._

## Tools & Alternatives Considered

_Track libraries/tools adopted in this version and alternatives discussed._

## Definition of Done (version-specific)

- Latency breakdown (before) and comparison table (after) recorded here.
- Every fan-out has an explicit timeout and a documented partial-failure policy.
- No concurrency exists on paths where measurement showed no benefit.

## Notes

_Freeform notes, gotchas, links, technical debt._
