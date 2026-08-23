Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Turn the ad-hoc evaluation habits from [[V4 - Question to Relevant Law]] into a standing framework: a versioned dataset, automated runs, generation-quality and citation-accuracy metrics, and result tracking across changes. This is the version that makes every future change *safe* — from here on, "did I just make the system worse?" has a runnable answer. It is the LLM-world equivalent of a CI test suite.

**You'll have learned:** generation evaluation (correctness, groundedness, completeness), LLM-as-judge and its pitfalls, eval tooling trade-offs, and regression tracking for non-deterministic systems.

## Steps

- [ ] **1. Formalize the eval dataset: defined schema, versioned in the repo, grown beyond V4's set** — _Why:_ the dataset is now an asset multiple versions depend on ([[V9 - Agentic Workflow]] will evaluate agents against it); it needs a schema (question, expected provisions, expected-answer notes, tags) and change discipline like any other code.
- [ ] **2. Keep retrieval evaluation and generation evaluation as separate, separately-runnable stages** — _Why:_ the two-bucket diagnosis from [[V3 - First RAG System]] (retrieval failure vs. generation failure), institutionalized. A drop in answer quality must be attributable to the layer that caused it, or every regression hunt starts from zero.
- [ ] **3. Define generation metrics: correctness, groundedness (is every claim supported by retrieved text?), completeness, and citation accuracy (from [[V6 - Legal Structure and Citations]])** — _Why:_ these four fail independently — an answer can be correct but ungrounded (model knew it anyway — dangerous pattern), or grounded but incomplete. Defining each criterion precisely *before* choosing tooling keeps the tool from dictating what you measure.
- [ ] **4. Study LLM-as-judge before using it; decide where it's acceptable** — _Why:_ groundedness/completeness at any scale needs an LLM judge, but judges have known failure modes (position/verbosity/self-preference bias, drift across judge-model versions). The engineering lesson is calibration: spot-check judge verdicts against your own on a sample, and record the judge prompt + model as part of the configuration. Capture as an [[LLM-as-Judge]] concept note.
- [ ] **5. Choose tooling: extend the custom harness vs. adopt a framework (Ragas, promptfoo, DeepEval, …)** — _Why:_ the classic build-vs-adopt decision, made properly for once: you already have a working custom harness from V4, so the framework must earn its place by something concrete (judge prompt library, reporting UI, dataset management). Compare on this project's real needs and record the decision.
- [ ] **6. Automate: one command (`poe eval`) runs the suite and stores results with a snapshot of the configuration (model, prompt version, retrieval settings, judge version)** — _Why:_ results without their configuration are noise — "0.78 groundedness" means nothing unless you know exactly what produced it. Storing config+results together is what makes step 7 possible.
- [ ] **7. Track results across changes; establish the habit: every retrieval/prompt/model change gets an eval run before merging** — _Why:_ this is the regression-safety payoff and the reason this version exists. LLM systems regress silently — a prompt tweak that helps one question hurts three others — and only longitudinal tracking catches it.
- [ ] **8. Close the loop: use the framework to revisit one earlier decision (e.g. embedding model, k, chunking) and confirm or overturn it with numbers** — _Why:_ proves the framework is actually usable for its purpose, and demonstrates the healthiest habit in the project: past decisions are revisitable when measurement says so.

## Decisions

- **2026-08-22:** V7 builds on the informal retrieval eval from [[V4 - Question to Relevant Law]] rather than duplicating it: it makes the eval dataset reusable/automated, extends metrics to generation quality (correctness, groundedness, completeness) and citation accuracy (from [[V6 - Legal Structure and Citations]]), and adds tracking of results across changes over time. V4 stays the quick manual check; V7 is the standing framework.

## Tools & Alternatives Considered

_To fill during the version: eval frameworks compared (Ragas / promptfoo / DeepEval / custom) against this project's actual criteria; judge model choice._

## Definition of Done (version-specific)

- `poe eval` runs retrieval + generation suites and persists results with full configuration.
- Judge verdicts spot-checked against human judgment on a sample; agreement rate recorded.
- At least one historical decision re-examined with the framework, outcome recorded.

## Notes

_Freeform notes, gotchas, links, technical debt._
