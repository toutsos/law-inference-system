Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Make the system's behavior visible: structured logs, request correlation, and traces across retrieval, LLM calls, tools, and agent steps, with token usage and cost captured per request. By now the system is genuinely hard to debug by print statement — an agentic, concurrent, multi-stage pipeline — which is exactly why observability arrives here and not earlier: the pain is real, so the tooling's value is legible.

**You'll have learned:** structured logging, correlation IDs, the traces/spans model (OpenTelemetry), LLM-specific observability platforms, and trace-driven debugging.

## Steps

- [ ] **1. Introduce structured logging (JSON-capable, key-value fields) to replace ad-hoc prints/logs** — _Why:_ logs that are data (`event="retrieval" k=8 latency_ms=41`) can be filtered and aggregated; prose logs can only be read. Establish log levels and a small vocabulary of event fields so entries stay queryable and consistent.
- [ ] **2. Add correlation/request IDs threaded through every operation of a request** — _Why:_ with concurrency from [[V10 - Concurrent Execution]], logs from simultaneous requests interleave; the correlation ID is what reassembles one request's story. Use contextvars rather than passing an ID through every function signature — that's the pattern designed for exactly this.
- [ ] **3. Study the tracing model: traces, spans, attributes, and how OpenTelemetry standardizes them** — _Why:_ a trace is the tree-structured, timed version of what step 2's grep reconstructs by hand — understanding span parent/child structure first makes any backend (and any instrumentation library) intelligible. Capture as an [[Observability]] concept note.
- [ ] **4. Choose the backend: LLM-specific platform (Langfuse, Phoenix) vs. general OpenTelemetry stack — compare on this project's needs** — _Why:_ LLM platforms show prompts, completions, token costs, and agent steps natively (most speak OTel underneath); a general stack is more universal but LLM-blind out of the box. A real trade-off worth deciding deliberately and recording.
- [ ] **5. Instrument the pipeline: spans for retrieval, LLM calls, tool executions, agent iterations — with latency, token usage, cost, and model/config attributes** — _Why:_ these attributes are the operational questions of [[V12 - Production-Oriented System]] pre-answered: what does a question cost, where does time go, which stage fails. Instrument at the seams built in V1/V8 — the payoff for keeping clean interfaces all along.
- [ ] **6. Capture errors in traces with enough context to diagnose without reproducing** — _Why:_ LLM failures are often non-deterministic — the trace *is* the reproduction. Record the failing input, tool arguments, and model response; "cannot reproduce" stops being a dead end.
- [ ] **7. Use the traces to diagnose real failures/slowness from the earlier version logs; document one concrete case** — _Why:_ proves the instrumentation works as a tool rather than decoration — pick a mystery from the [[V3 - First RAG System]]/[[V9 - Agentic Workflow]] failure logs and run it down in the trace viewer, writing up the diagnosis here.

## Decisions

_Record decisions as they're made: what we chose, what alternatives we considered, and why._

## Tools & Alternatives Considered

_To fill during the version: logging library (structlog vs. stdlib), backend comparison (Langfuse / Phoenix / OTel + Jaeger) with what each showed on this project's traces._

## Definition of Done (version-specific)

- Every request has a correlation ID present in all its logs and spans.
- A single trace shows the full pipeline for one question — stages, latencies, tokens, cost.
- One real failure diagnosed via traces, documented here.

## Notes

_Freeform notes, gotchas, links, technical debt._
