# Configuration

Part of [[Home]]. Introduced in [[V0 - Project Foundation]] (step 9), first genuinely exercised in [[V1 - Minimal LLM Application]] (step 2).

## What it is / problem it solves

Some values differ between a laptop, CI, and production: API keys, database URLs, base URLs, log levels. Three ways to handle them:

1. **Hardcode** — works until the first secret, which then lives in git history permanently. Rotating the key does not undo that.
2. **Read `os.environ` at each use site** — no secrets in git, but every value is a `str` needing manual conversion; a typo fails on the code path that uses it rather than at startup; and nothing anywhere enumerates what the application requires — it is discovered by crashing.
3. **One typed settings object, validated at startup** — config is parsed and checked once, at the boundary; every consumer receives typed values.

The governing principle is **12-factor config**: config lives in the environment, and the code is identical across deployments. `.env` is a local convenience for loading those variables; in production they are real environment variables.

Structurally this is the same shape as [[Dependency Direction]]: untrusted, untyped external input is converted into typed validated objects **at one boundary**, and the interior only ever sees the clean version. Config is the first instance; V2's ingestion is the same pattern applied to messy HTML.

## What belongs in config — the two rules

Derived 2026-08-23 by sorting concrete candidates.

> **Rule 1.** Config is for values that legitimately **differ between environments running the same code** — not for values that might want changing.

> **Rule 2.** If changing a value invalidates stored data or makes past measurements incomparable, it belongs in **version control**, not the environment.

| Candidate | Verdict | Reason |
| --- | --- | --- |
| LLM API key | config | Secret; differs per environment. |
| Model name | config | Swappable without a code change. |
| Ollama base URL | config | `localhost:11434` locally vs. a container hostname in Docker. |
| Log level | config | `DEBUG` locally, `INFO` in production. |
| System prompt text | **code** | Prompts are code — they need diff history and regression tests ([[V1 - Minimal LLM Application]] step 6). |
| Corpus law list | **code** | A fixed research artifact; V0 step 12 wants it *fixed* so experiments stay comparable. |
| Chunk size | **code** | The instructive case — see below. |

**Chunk size** is where the rules bite. There is no world in which a laptop deliberately chunks at 500 tokens while production chunks at 800; it is the same decision everywhere, merely undecided. And it is a *retrieval quality parameter*: changing it makes the entire vector index stale, and since [[V4 - Question to Relevant Law]] measures Recall@K and [[V7 - Evaluation Framework]] tracks regressions, an `.env`-resident chunk size lets a laptop and CI silently disagree — **two eval runs stop being comparable with nothing reporting a difference.** Numbers that cannot be trusted are worse than no numbers.

The same reasoning covers embedding model, `top_k`, and similarity thresholds in [[V3 - First RAG System]]–[[V5 - Hybrid Retrieval]]: experiment parameters belong in git, next to the results they produced.

## When to fail, and the danger of defaults

**Fail at startup, not at first use.** A misconfigured application that starts successfully dies later, on whatever code path first touches the value — possibly a rare branch, at 2am, after half-writing something. Validating everything at startup means the process either comes up correctly configured or does not come up at all. Once this is a running service ([[V8 - Tools and Structured Operations]]+), that is the difference between a failed deploy and a 3am page.

**Defaults are a decision, not a convenience.** A default converts a loud startup failure into silent wrong behaviour.

- `log_level = "INFO"` — fine, harmless.
- An API key with a default — never; absence must be loud.
- The classic incident: a "safe" fallback such as *"no database URL configured, use a local SQLite file"*. The app starts happily and writes real data somewhere nobody will look.

> Give a default only when the default is genuinely correct **in production** — not when it makes local development smoother.

## Decision (2026-08-23): build Settings at V0, deliberately thin

Fields at V0: `app_env` (default `"local"`) and `log_level` (default `"INFO"`). That is all — nothing else exists to configure yet.

Why this is not the same mistake as creating an empty `retrieval/` package (see V0's step 5 decision): an empty package would invite designing an interface for an unseen problem. Here there is nothing to design — 12-factor config is a solved shape, and it is two fields, not an architecture. It is also needed in the *next* version, not five later: V1 step 2 is "wire the API key through Pydantic Settings." Introducing the config pattern now means V1 adds a field to something that already works, rather than learning two new things at once.

**Known tension:** V0's Definition of Done requires "a missing required variable fails loudly with a clear error", but no genuinely required variable exists yet, and inventing one to satisfy the checklist would be exactly the speculative config argued against above. **Resolution:** prove the behaviour in a *test* — define a throwaway settings model with a required field inside the test and assert it raises. Real coverage of the mechanism, no fake field in production code. V1 brings the first real required variable.

## pydantic-settings specifics

A **runtime** dependency (`[project] dependencies`), not a dev one — application code imports it. Contrast with [[ruff]], [[pre-commit]], [[poethepoet]], and pytest, which are all `[dependency-groups] dev`.

- `BaseSettings` — a Pydantic model populated from environment variables rather than constructor arguments. Field `app_env` reads `APP_ENV` (case-insensitive by default).
- `env_file=".env"` — also read that file when present. **Real environment variables take precedence over `.env`**, which is what lets identical code run in production where no `.env` exists.
- `extra="forbid"` — rejects unknown keys. Guards the rename case: a variable is renamed, `.env` still carries the old name, and without `forbid` the application starts silently on defaults. Cost: any unrelated variable in `.env` breaks startup.
- `.env.example` is committed and lists every variable with a placeholder — the only documentation of what the application requires. `.env` itself stays git-ignored (V0 step 3).

## Alternatives considered

- **`os.environ` reads at use sites** — untyped, unvalidated, undocumented, fails late. Rejected (also recorded in V0's Tools & Alternatives).
- **A `config.yaml` / `config.toml` file** — fine for non-secrets, but splits config across two mechanisms since secrets still need the environment, and diverges from 12-factor.
- **`python-dotenv` alone** — loads `.env` into `os.environ` but provides no typing or validation; solves the smallest part of the problem.

## Used in

- [[V0 - Project Foundation]] — step 9, `src/greek_law/config.py`.
- [[V1 - Minimal LLM Application]] — step 2, the first genuinely required variable.
- Every later version: database URL ([[V3 - First RAG System]]), observability endpoints ([[V11 - Observability]]).

## Notes

- **`domain/` may not import `config.py`** — resolved 2026-08-23, worked through in [[Dependency Direction]]. Config is I/O and therefore infrastructure; a domain module importing it makes `import greek_law.domain` validate the environment, breaking domain tests on any machine without a `.env`. When a domain function needs a configurable value, the caller passes it as an argument.
- `env_file=".env"` is a path **relative to the current working directory**, not to `config.py`'s location. It works because commands are run from the repo root; it would silently load nothing from elsewhere. Worth remembering when a setting mysteriously fails to apply.

### Where does a value live? Four homes

| | `pyproject.toml` | `config.py` | `.env` | `.env.example` |
| --- | --- | --- | --- | --- |
| Holds | project metadata + tool settings | the **schema** of runtime config | the **values** for this machine | placeholder values |
| Read by | uv, ruff, poe, pytest | the application | the app, via `config.py` | humans only |
| When | build / dev time | app startup | app startup | never, by code |
| In git | yes | yes | **no** | yes |
| Varies per machine | no | no | **yes** | no |
| May hold secrets | never | never | **yes** | never |

The bottom three rows are one idea: **`config.py` and `.env` are the same information split by what is safe to commit.** `config.py` says *"there is a variable `llm_api_key`, string, required"*; `.env` says *"and here its value is `sk-…`"*. Shape in git, content out of git.

`pyproject.toml` is a different axis entirely — the application never reads it. It describes the project as a packaging and tooling artifact. See [[pyproject.toml]].

**A fourth home**, whose absence causes the chunk-size confusion: **plain Python constants in the module that owns the concept** (e.g. `CHUNK_SIZE = 512` in `retrieval/chunking.py`). In git, identical everywhere, changed by editing code. That is where experiment parameters belong — see Rule 2 above.

Decision procedure, in order:

1. About the project as a package, or about tooling? → `pyproject.toml`
2. Differs per environment, or secret? → declared in `config.py`, valued in `.env`, documented in `.env.example`
3. Otherwise → a constant in the module that owns the concept
