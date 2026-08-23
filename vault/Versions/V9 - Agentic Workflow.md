Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Let the LLM *decide* which tools to call and in what order, for questions where a fixed pipeline isn't enough — building the loop by hand first, then comparing it honestly against an agent framework. The build-first order is deliberate: an agent loop is ~50 lines of code, and having written it, every framework abstraction (state, steps, termination) maps to something you already understand instead of being magic.

**You'll have learned:** the agent loop pattern, state and termination design, cost/latency budgeting, evaluating agents against simpler baselines, and how to judge an orchestration framework from experience rather than popularity.

## Steps

- [ ] **1. Identify questions that genuinely require multiple sequential operations — where the fixed RAG pipeline demonstrably falls short** — _Why:_ agents are justified by need, not fashion ([[Home]]'s guiding principle). Good candidates: "compare what law X and law Y say about Z," questions needing search-then-fetch-then-search. If the V7 eval set can't distinguish agentic from plain RAG, add questions that can — otherwise step 7 can't measure anything.
- [ ] **2. Study the agent loop pattern (ReAct-style: model → tool call → result → model → … → final answer)** — _Why:_ conceptually it's just the [[Tool Calling]] mechanism from [[V8 - Tools and Structured Operations]] wrapped in a while-loop with an exit condition — seeing that clearly demystifies the entire "agents" discourse. Capture as an [[Agent Loop]] concept note.
- [ ] **3. Implement the minimal custom loop using the V8 tools** — _Why:_ small enough to fully understand, and it becomes the baseline that any framework must beat in step 8. No framework yet, by design.
- [ ] **4. Add state only where a real need appears (accumulated tool results, step history)** — _Why:_ practicing "simple until justified" inside a single version: start with just the message history as state, and introduce structure only when a concrete problem (context growth, needing to reference earlier results) demands it.
- [ ] **5. Implement termination and failure conditions: max iterations, token/cost budget, explicit give-up path** — _Why:_ the failure mode unique to agents is the loop that never converges — burning money while producing nothing. A bounded agent that says "I couldn't determine this" honors the honesty principle from [[Home]]; an unbounded one is a liability.
- [ ] **6. Add retries and validation around tool calls (malformed arguments, transient failures)** — _Why:_ the model will emit invalid calls; feeding validation errors back (the LLM-legible errors designed in V8, step 5) usually lets it self-correct — this feedback loop is a defining trick of practical agent engineering.
- [ ] **7. Evaluate the agent against plain RAG on the eval set — quality *and* cost *and* latency** — _Why:_ agents cost multiples per question. The three-column comparison (better answers? how much slower? how much dearer?) is the decision-grade evidence for *when the agent path should be used at all* — possibly the most transferable lesson in the project.
- [ ] **8. Rebuild the same workflow in an agent framework (e.g. PydanticAI or LangGraph); compare against the custom loop** — _Why:_ now the comparison is informed — you know exactly what the framework must provide beyond your 50 lines (state management, streaming, retries, observability hooks?). Record what it adds, what it hides, and what it costs in debuggability.
- [ ] **9. Decide: keep the framework or the custom loop; record the decision with reasons** — _Why:_ either outcome is a success — the point is a decision grounded in this project's real requirements, closing the loop the [[Agent Instructions]] demand ("use the project's real requirements to justify new technologies").

## Decisions

_Record decisions as they're made: what we chose, what alternatives we considered, and why._

## Tools & Alternatives Considered

_To fill during the version: agent frameworks compared (PydanticAI, LangGraph, provider-native SDK loops) with hands-on findings from step 8._

## Definition of Done (version-specific)

- Custom loop answers a genuinely multi-step question end-to-end, within its budget limits.
- Runaway protection verified (a pathological question terminates gracefully).
- Agent-vs-RAG comparison table (quality/cost/latency) recorded here.
- Framework verdict recorded with concrete reasons.

## Notes

_Freeform notes, gotchas, links, technical debt._
