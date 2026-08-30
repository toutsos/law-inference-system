Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** In Progress — started 2026-08-29

## Goal

The smallest useful LLM application: a question goes in, a prompt is built, an LLM answers, the answer comes back through typed models — as a plain Python function/CLI, no HTTP. This version is about learning to talk to an LLM *through a clean seam* so that everything built later (RAG, tools, agents) plugs into an interface you control rather than a vendor SDK scattered through the codebase.

**You'll have learned:** LLM API mechanics (tokens, context window, temperature, cost), prompt structure (system vs. user messages), how to wrap a provider behind an interface, how to test LLM-dependent code without calling the LLM, and — critically — what the model gets *wrong* without retrieval.

## Steps

- [x] **1. Choose the LLM provider and model; record pricing** — _Why:_ this is the project's first real technology decision — compare at least two options (capability on Greek text, cost per million tokens, structured-output support, rate limits) and record the choice below. Nothing else in this version can start without it. — _Done 2026-08-29: Ollama + `ilsp/llama-krikri-8b-instruct`. No pricing to record (local inference); the cost axis becomes latency and tokens/second, see the Decisions below. Comparison against a larger general model deferred — logged as debt._
- [~] **2. Wire the model config through Pydantic Settings** _(no API key — Ollama needs none)_ — _Why:_ the config seam from [[V0 - Project Foundation]] exists precisely for this; the key lives in `.env`, never in code, never in git. With a local provider there is no secret, so what is being wired is *where the server is* and *which model to call*. — **IN PROGRESS 2026-08-29:** `ollama_base_url` and `ollama_model` added; `request_timeout` still missing from `Settings` while present in `.env`, so `Settings()` currently raises. See the session note below.
- [x] **3. Learn the raw API first: one throwaway script calling the HTTP API directly** _(raw `POST /api/chat`, not the `ollama` SDK — the SDK returns a parsed object and hides the wire format this step exists to expose)_ — _Why:_ before wrapping anything, see what a request/response actually contains — messages, roles, token counts, finish reasons. Abstractions are only understandable after the thing they abstract. — _Done 2026-08-30: `scripts/probe_ollama.py`, raw `httpx.post` to `/api/chat`. First measurement recorded in the Notes below._
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

- **2026-08-30: HTTP client — `httpx`, over `urllib.request` and over the `ollama` SDK.**
  - _Rejected reason:_ "httpx supports async." Async belongs to [[V10 - Concurrent Execution]], whose own rule is *profile first*. Choosing a dependency for a capability no measured problem requires is the speculative-complexity failure Golden Rule 6 exists to prevent. Async is a free bonus here, not a justification.
  - _Actual reason — step 7._ Typed exceptions (`httpx.TimeoutException`, `httpx.HTTPStatusError` carrying `.response.status_code`) versus urllib's `HTTPError`, which is simultaneously an exception and a response object, and whose timeouts surface inconsistently as `URLError`-wrapped `socket.timeout` or bare `TimeoutError`. Retry logic that must sniff `e.reason` will eventually retry the wrong thing.
  - _Second reason:_ httpx separates connect/read/write timeouts. Against a local Ollama that distinction is real — connect should fail fast (localhost is up or it isn't) while read must be patient, because an 8B model generating ~500 tokens legitimately exceeds 30s. One shared timeout number cannot express that.
  - _Cost accepted:_ for the step 3 probe alone, `urllib.request` costs zero dependencies and ~6 extra lines. The dependency is genuinely being bought for step 4's client, not for the probe.
  - _`ollama` SDK rejected for step 3_ (revisit at step 4): it returns a parsed object, hiding the wire format that step 3 exists to expose. See [[LLM Chat API]].

- **2026-08-30: Static type checking — `mypy`, added now rather than deferred to [[V12 - Production-Oriented System]].**
  - _Trigger:_ two failures in one session that the whole existing toolchain missed — `from pyparsing import Literal` (editor auto-import of the wrong module) and `from greek_law.models import ...` (missing the `llm` package segment). Both left `greek_law.llm` unimportable; `ruff check`, `ruff format --check` and `pytest` all passed. The project's own bar is *"a real requirement, a measured failure, or a learning objective"* — two measured failures clears it.
  - _Root cause worth naming:_ **Python has no compile step.** `import` is an executable statement resolved when the line runs, so nothing validates it beforehand. `ruff` is a linter and never resolves imports across modules; `pytest` only catches what a test happens to import, and no test imported `greek_law.llm`.
  - _Second reason, specific to step 4:_ `LLMClient` is a `typing.Protocol`, and structural conformance is **only ever checked statically**. Without a type checker the seam is decorative — nothing verifies that `OllamaClient` satisfies it, and nothing will verify the hosted client later. `mypy` is what makes the `Protocol`-over-`ABC` choice safe.
  - _Config notes:_ `plugins = ["pydantic.mypy"]` is **required**, not optional — a Pydantic `__init__` is typed `**data: Any` by default, so without it mypy would accept a misspelled field like `token_out=`. `explicit_package_bases = true` makes `tests/` modules resolve as `tests.*` for the strictness override **without** adding an `__init__.py`, preserving the decision recorded in [[Python Packages and Imports]].
  - _First run: 30 errors, 0 real bugs._ 24 were missing annotations in tests (fixed by the override); the remaining 6 are deliberate type violations inside `pytest.raises(ValidationError)` blocks, suppressed with `# type: ignore[<code>]`. Worth noting the inversion: **mypy flagging a negative test is evidence the test is well-aimed** — silence there would mean the call wasn't actually type-incorrect and the asserted failure couldn't occur. `strict` bundles `warn_unused_ignores`, so a suppression that stops being needed is reported rather than rotting (better than `@SuppressWarnings`).
  - _Cost:_ `src/` and `scripts/` were already clean under `strict`. Wired as `poe typecheck`, referenced from `poe lint`; deliberately **not** in `poe format`, since mypy never modifies files.

_Still to fill: provider comparison (capabilities on Greek, pricing, SDK quality), retry libraries (tenacity vs. hand-rolled backoff), prompt storage (module constants vs. template files)._

## Definition of Done (version-specific)

- A question typed at the CLI returns an answer end-to-end through the typed models.
- Provider outages/rate limits produce controlled behavior, not stack traces.
- Non-LLM logic is covered by tests using the fake client.
- The no-RAG baseline answers are saved in the repo (or linked here) with hallucinations annotated.

## Notes

### Session end — 2026-08-29

**Done today:** V0 closed and committed. V1 started — step 1 settled (Ollama + Krikri), first no-RAG probe recorded below, step 2 partially done.

**Step 2 decision, settled by applying the rules in [[Configuration]]:** `ollama_base_url`, `ollama_model` and `request_timeout` go in `Settings`; **temperature and the system prompt do not.** The learner's initial position was that all five belong in config. The counter-argument that settled it was the learner's own note: the system prompt is already listed there with verdict *code*, and `.env` is gitignored — a prompt living there would have no diff history, never appear in review, differ silently per machine, and be untestable by [[V7 - Evaluation Framework]]. Temperature was genuinely open and is now recorded in that note as a derived case: it does not vary by *environment*, it varies by *call site*.

The general shape worth carrying forward: **config varies by where the code runs; parameters vary by what the call is doing; experiment settings live in git next to the results they produced.**

**Pick up here, in order:**

1. **`Settings()` currently raises** — `.env` and `.env.example` declare `requests_timeout=30`, but `Settings` has no such field, so `extra="forbid"` refuses to start. Add the field as **`request_timeout: float = 30`** (singular — it is one request's timeout; float because HTTP clients take fractional seconds) and rename the key in both `.env` files to match.
2. **Fix the `.env` format** — the three new lines use lowercase keys with spaces around `=`. It loads in Python but the file is no longer shell-sourceable (`sh -c '. ./.env'` → `command not found`), which breaks the `env_file:` that docker-compose needs in [[V3 - First RAG System]]. Convention and reasoning now recorded in [[Configuration]].
3. **Add the missing test** — step 2 asked for one; copy `test_env_var_overrides_default` and point it at `OLLAMA_MODEL`. Worth having specifically because the model name is the knob that gets flipped for the deferred Qwen comparison.
4. Then `uv run poe format && uv run poe lint && uv run poe test`, and commit.
5. **Step 3** — a throwaway script calling Ollama's HTTP API directly (`POST /api/chat`), to see a raw request and response before wrapping anything. Abstractions are only understandable after the thing they abstract.

**Already correct, no action needed:** `Literal` types on `app_env` and `log_level` — this closes the open design question left in [[V0 - Project Foundation]]'s 2026-08-23 note. Sensible defaults on all new fields, and `.env.example` carrying real working values rather than placeholders.

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

### First wire-level measurement — 2026-08-30 (step 3)

`scripts/probe_ollama.py` → `POST /api/chat`, English system + user message,
`"stream": false`, cold model.

| Field | Value |
| --- | --- |
| `done_reason` | `stop` |
| `eval_count` (tokens out) | 11 |
| `eval_duration` | 0.242 s |
| `total_duration` | 0.635 s |
| derived | 45.5 tokens/sec |

**Treat 45 tok/s as unusable.** 11 tokens is no sample, and ~393 ms of the
0.635 s is `load_duration` + `prompt_eval_duration` — the model being pulled
into memory, not generating. The Java analogy: a throughput figure taken before
the JIT warmed up. Step 8 needs a re-run with a few hundred tokens against an
already-resident model, and must decide which number it reports —
`total_duration` is what the user waits, `eval_duration` is what the model can do.

**`prompt_eval_count` was not captured, and it is the figure that matters most
here.** Tokens-out stays roughly constant across this project; tokens-in is what
explodes in [[V3 - First RAG System]], where every retrieved chunk is re-sent on
every call. Open question worth answering before V3: how many tokens does a
*Greek* sentence cost under Krikri's extended tokenizer versus the English
equivalent? That ratio is a direct multiplier on the context budget.

Mechanics of the endpoint are in [[LLM Chat API]].

### Port 11435, not 11434 — 2026-08-30

Ollama on this machine listens on **11435**; the documented default is 11434,
which is why the first `curl` to `localhost:11434` returned nothing and
`python3 -m json.tool` reported `Expecting value: line 1 column 1`. Diagnosis
was `lsof -nP -iTCP -sTCP:LISTEN | grep -i ollama`.

The override belongs in `.env` only. `config.py`'s field default and
`.env.example` stay at the conventional 11434 — a machine-specific accident must
not become the committed fallback. This is [[Configuration]]'s rule (config
varies by *where the code runs*) meeting reality for the first time.

_Debugging lesson worth keeping: `curl -s ... | python3 -m json.tool` hid the
real error twice. Never pipe a command whose raw output you have not seen._

### Technical debt

- **Seam unproven with a single implementation.** An interface with one implementation is a guess about what varies. It stays a guess until the hosted provider lands — expect the `LLMClient` interface to change when it does, and treat that change as the design working, not failing.
- **Provisional baseline.** Step 10's no-RAG answers are provisional while only the local model exists (see the 2026-08-23 decision).
- ~~**No type checker (2026-08-30).**~~ **Resolved same day** — `mypy` added, see Tools & Alternatives. Kept for the record: `ruff` is a linter and a formatter; it does not resolve imports or check types. Two consequences hit on the same day: (a) `from pyparsing import Literal` — an editor auto-import of the wrong module — was committed in a state where the package could not be imported at all, and `poe lint` *and* `poe test` both passed; (b) the `LLMClient` `Protocol` in `llm/client.py` is unenforced documentation, since structural conformance is only ever checked statically. `mypy` or `pyright` closes both. Deferred to [[V12 - Production-Oriented System]]'s CI step rather than detouring now. Interim habit: `uv run python -c "import greek_law.llm.models, greek_law.llm.client, greek_law.llm.ollama_client"` as a two-second "does it compile" smoke test after touching a module.
- **Two empty modules committed (2026-08-30).** `llm/client.py` and `llm/ollama_client.py` went into `51d8f5a` at 0 bytes. Nothing imports them yet, so nothing complained — the same blind spot as above.
- **Model comparison not run (2026-08-29).** Step 1 was settled on one model without the intended head-to-head against a larger general model (`qwen3:30b` / `gemma3:27b`), which the 64 GB machine can hold. The open question stays open: *does Greek specialization at 8B beat raw capability at ~30B for legal text?* Cheap to answer later — the same question, two `ollama run` commands — and worth answering before [[V4 - Question to Relevant Law]] measures anything, so that a poor score is attributable to retrieval rather than to the model.

_Freeform notes, gotchas, links, technical debt._
