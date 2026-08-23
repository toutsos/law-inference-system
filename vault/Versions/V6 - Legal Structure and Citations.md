Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Upgrade "answers with rough source references" into precise, verifiable citations backed by an explicit legal hierarchy. This is the product's trust feature: per [[Home]]'s scope boundary, the system's value is *identifiable supporting provisions*, not confident prose. It's also a modeling-depth exercise — taking the domain models as far as Greek legislative structure actually requires, and no further.

**You'll have learned:** deep domain modeling, designing a canonical reference format, provenance chains, and testing correctness of structured output that an LLM helped produce.

## Steps

- [ ] **1. Extend the hierarchy models where the corpus requires it: law → article → paragraph → subparagraph/εδάφιο/περίπτωση** — _Why:_ real provisions are cited at these finer levels; model only the levels your corpus actually exhibits (check it first) — speculative hierarchy is dead weight.
- [ ] **2. Design the canonical citation format and a `Citation` model** — _Why:_ one canonical form (e.g. «ν. 4808/2021, άρθρο 4, παρ. 2») used everywhere — storage, prompts, answers, tests — means citations can be parsed, compared, and validated mechanically. Decide it once, write it down here, and treat deviations as bugs.
- [ ] **3. Make citations structured output, not free text in the answer** — _Why:_ if the LLM emits citations as prose, they can't be verified; if the answer model carries `list[Citation]` referencing retrieved chunks, every citation is checkable against the database. This flips citation trust from "hope the model formatted it right" to "validated data."
- [ ] **4. Strengthen provenance end-to-end: every citation resolves chunk → article → law → source document (ΦΕΚ reference from the [[V2 - Document Ingestion]] manifest)** — _Why:_ the user must be able to open the official text and check. The provenance chain was seeded in V2 precisely so this step is a join, not an archaeology project.
- [ ] **5. Add citation-correctness tests, two kinds: (a) every emitted citation resolves to a real provision; (b) on the eval set, cited provisions match expected ones** — _Why:_ (a) is mechanical and always-on — it catches fabricated citations, the worst failure this product can have; (b) extends the [[V4 - Question to Relevant Law]] eval toward answer-level quality and feeds directly into [[V7 - Evaluation Framework]]'s citation-accuracy metric.
- [ ] **6. Surface citations in the CLI output so a human can actually follow them to the source** — _Why:_ the trust feature only exists if a user can act on it; this also forces the "what does the reader actually need?" design question.

## Decisions

- **2026-08-22:** Amendment/version tracking (temporal-awareness, superseded provisions) is deferred to Long-Term Extensions (see [[Home]]) rather than core V6 scope. V6 targets citation of *current-text* provisions only: hierarchy, precise references, provenance. Revisit temporal versioning once the corpus and evaluation framework can support it.

## Tools & Alternatives Considered

_Track libraries/tools adopted in this version and alternatives discussed._

## Definition of Done (version-specific)

- Canonical citation format documented here; `Citation` is structured data everywhere.
- Fabricated-citation test (resolution check) runs in the standard test suite.
- A user reading a CLI answer can locate the exact provision in the official source.

## Notes

_Freeform notes, gotchas, links, technical debt._
