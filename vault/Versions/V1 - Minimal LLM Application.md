Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** In Progress — started 2026-08-29

## Goal

The smallest useful LLM application: a question goes in, a prompt is built, an LLM answers, the answer comes back through typed models — as a plain Python function/CLI, no HTTP. This version is about learning to talk to an LLM *through a clean seam* so that everything built later (RAG, tools, agents) plugs into an interface you control rather than a vendor SDK scattered through the codebase.

**You'll have learned:** LLM API mechanics (tokens, context window, temperature, cost), prompt structure (system vs. user messages), how to wrap a provider behind an interface, how to test LLM-dependent code without calling the LLM, and — critically — what the model gets *wrong* without retrieval.

## Steps

- [x] **1. Choose the LLM provider and model; record pricing** — _Why:_ this is the project's first real technology decision — compare at least two options (capability on Greek text, cost per million tokens, structured-output support, rate limits) and record the choice below. Nothing else in this version can start without it. — _Done 2026-08-29: Ollama + `ilsp/llama-krikri-8b-instruct`. No pricing to record (local inference); the cost axis becomes latency and tokens/second, see the Decisions below. Comparison against a larger general model deferred — logged as debt._
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

- **2026-08-23:** **Ollama (local) is the first `LLMClient` implementation; a hosted provider follows second.** Learner's rationale: free, offline, no API key to manage, and having a genuinely different second implementation is what proves the seam is a seam rather than a wrapper shaped like one vendor's SDK.
  - _Counter-risk recorded at decision time:_ a small local model's quality on Greek legal text is likely poor. Until a hosted implementation exists for comparison, a bad answer cannot be attributed between *the model* and *the retrieval* — which is exactly the attribution that step 10's baseline and [[V3 - First RAG System]]'s justification depend on. **Mitigation:** re-run the step 10 no-RAG baseline against the hosted provider once it exists, and treat the local-only baseline as provisional until then.
  - _Effect on step 1:_ the provider choice is now partly pre-decided. The comparison work shifts to (a) which local model to run under Ollama — size vs. Greek-language competence vs. what the machine can actually hold — and (b) which hosted provider comes second, chosen partly for being *unlike* Ollama in its API shape, since a seam validated against two similar APIs is not validated.
- **2026-08-22:** Defer introducing FastAPI/HTTP API layer. V1 (and subsequent versions) expose the application as plain Python functions/a CLI until a concrete need for an external-facing interface arises (e.g. when tools/agents in [[V8 - Tools and Structured Operations]] or later need to be called externally). Avoids HTTP plumbing distracting from the LLM/RAG concepts being learned first.
- **2026-08-22:** V1 ends with a **recorded no-RAG baseline** (step 10). Every architectural addition in this project should be justified by an observed failure or measurement, not by fashion — this baseline is the first instance of that discipline.

- **2026-08-29:** **Model: `ilsp/llama-krikri-8b-instruct`** (ILSP / Athena RC — Llama 3.1-8B continually pretrained on 56.7B Greek tokens, plus 21B English and 5.5B Greek-English parallel data; successor to Meltemi). Chosen over a general multilingual model because the open risk recorded on 2026-08-23 was *Greek-language competence*, and a Greek-specialized model attacks exactly that. Verified on the first probe: fluent native register and correct legal vocabulary. Hardware is not a constraint (M1 Max / 64 GB), so the choice was made on language quality, not size.
- **2026-08-29:** **Local inference means step 8 changes meaning.** There is no cost per token to log. The scarce resources are *latency* and *context window*, so step 8 becomes tokens-in/tokens-out, tokens/second, and wall-clock per call. The habit the step exists to build — knowing what each call costs before RAG multiplies prompt size — is preserved; only the unit changes. Revisit when the hosted provider lands and real pricing applies.

## Tools & Alternatives Considered

_To fill during the version: provider comparison (capabilities on Greek, pricing, SDK quality), retry libraries (tenacity vs. hand-rolled backoff), prompt storage (module constants vs. template files)._

## Definition of Done (version-specific)

- A question typed at the CLI returns an answer end-to-end through the typed models.
- Provider outages/rate limits produce controlled behavior, not stack traces.
- Non-LLM logic is covered by tests using the fake client.
- The no-RAG baseline answers are saved in the repo (or linked here) with hallucinations annotated.

## Notes

### First probe of the baseline — 2026-08-29

Ran the `Home.md` example question against `ilsp/llama-krikri-8b-instruct` before writing any project code, to see what the no-RAG failure mode actually is. Formally this is step 10 evidence gathered during step 1; it is recorded here and will be redone properly, with 5–10 questions, when step 10 is reached.

**The predicted failure did not occur.** We expected confidently invented citations. Instead the model produced a competent, well-structured summary of Greek employment law containing **zero law numbers, zero articles, zero ΦΕΚ references**.

That reframes what RAG is for in this project. Not *"stop the model lying about the law"* but *"the model cannot cite at all, and [[Home]] promises a system that identifies laws, articles and paragraphs."* The reframing is an improvement, because it is **measurable**: *count of verifiable provisions cited per answer*. Baseline = 0. That number is the seed metric for [[V4 - Question to Relevant Law]].

**Verified error — temporal staleness.** The answer twice referred users to the **ΟΑΕΔ**, which has not existed under that name since **ν. 4921/2022 (ΦΕΚ Α΄ 75/18.04.2022)** renamed it **ΔΥΠΑ**. Same class of failure as the repealed π.δ. 80/2022 caught in [[V0 - Project Foundation]] step 12, but arriving from the *model* rather than the *source*. This is the concrete argument for grounding answers in a dated corpus: the corpus knows its own ΦΕΚ date; the weights do not know what year it is.

**Claims to verify against the Κώδικα** (learner's domain; each becomes a V4 eval question):

1. *«διαφορετική μεταχείριση για εργαζόμενους άνω των 40 ετών»* as a criterion for αποζημίωση απόλυσης — αποζημίωση is understood to scale with προϋπηρεσία, not age.
2. *«δίστιμη αγωγή»* — not traceable as a term in Greek legal usage; likely invented.
3. *«κανονική ή έκτακτη»* καταγγελία — the standard distinction is *τακτική* vs *έκτακτη*.

**Behavioural note for step 6.** The model opened by declining to give legal advice and closed by recommending a lawyer. That aligns with the scope boundary in [[Home]], but it also shows the model is *tuned toward vagueness* — while the product requires specificity with sources. The system prompt must push against that tuning: "cite the provision or say you do not know", rather than "be careful".

### Technical debt

- **Seam unproven with a single implementation.** An interface with one implementation is a guess about what varies. It stays a guess until the hosted provider lands — expect the `LLMClient` interface to change when it does, and treat that change as the design working, not failing.
- **Provisional baseline.** Step 10's no-RAG answers are provisional while only the local model exists (see the 2026-08-23 decision).
- **Model comparison not run (2026-08-29).** Step 1 was settled on one model without the intended head-to-head against a larger general model (`qwen3:30b` / `gemma3:27b`), which the 64 GB machine can hold. The open question stays open: *does Greek specialization at 8B beat raw capability at ~30B for legal text?* Cheap to answer later — the same question, two `ollama run` commands — and worth answering before [[V4 - Question to Relevant Law]] measures anything, so that a poor score is attributable to retrieval rather than to the model.

_Freeform notes, gotchas, links, technical debt._
