# poethepoet

Part of [[Home]]. Introduced in [[V0 - Project Foundation]] (step 8). Wraps [[ruff]] and later pytest, docker, and evaluation commands.

## What it is / problem it solves

A task runner: named shortcuts for project commands, declared in `pyproject.toml` under `[tool.poe.tasks]` and invoked as `uv run poe <task>`.

The problem is not typing length. It is that raw commands **leak the tool choice into muscle memory, the README, and CI**. `uv run ruff check .` names the *tool*; `poe lint` names the *intent*. When the tool underneath changes, one line in `pyproject.toml` changes and nothing else does — not the docs, not CI, not habits.

Python has no built-in equivalent (unlike npm's `scripts`). The traditional answer is a Makefile; poe does the same job inside `pyproject.toml`, without make's tab sensitivity and shell quirks.

## Why we're using it here

### Decision (2026-08-23): task set and the mutate/report split

`ruff check --fix` and `ruff format` **rewrite files**; `ruff check` and `ruff format --check` only **report and exit non-zero**. That split has to be reflected in the task names.

| Task | Command | Mutates? |
| --- | --- | --- |
| `poe lint` | `ruff check .` + `ruff format --check .` | no |
| `poe format` | `ruff check --fix .` + `ruff format .` | yes |
| `poe test` | `pytest` | no |

Two principles behind it:

1. **CI runs the literal command a human runs.** No separate CI task. If CI ran `ruff check --output-format=github` while the developer ran `poe lint`, the two could diverge and produce "passes locally, fails in CI". CI calls `poe lint`.
2. **The plain, memorable name goes to the non-mutating command.** `poe lint` is what gets typed reflexively and what CI calls, so it must be safe on a dirty tree or a read-only checkout. Mutation should require a word that sounds like mutation — `format` already does.

**The easy mistake:** `poe lint` must include `ruff format --check`, not just `ruff check`. Otherwise formatting is enforced *only* by the local [[pre-commit]] hook — which `git commit --no-verify` bypasses — and unformatted code reaches CI unnoticed. Lint and format are separate tools; both need a reporting mode in the reporting task.

Note the symmetry: each task is the same two operations, once reporting and once fixing. A new tool gets one line in each.

### Configuration

```toml
[tool.poe.tasks]
test = "pytest"

[tool.poe.tasks.lint]
help = "Report lint and formatting problems; changes nothing"
sequence = ["ruff check .", "ruff format --check ."]
default_item_type = "cmd"

[tool.poe.tasks.format]
help = "Apply safe lint fixes and reformat"
sequence = ["ruff check --fix .", "ruff format ."]
default_item_type = "cmd"
```

- A bare string (`test = "pytest"`) is the short form for a single command.
- `sequence` runs items in order and **stops at the first failure** — correct here: if `ruff check` finds errors there is no value in also reporting formatting.
- `default_item_type = "cmd"` — without it, poe interprets sequence items as *references to other named tasks* rather than commands. Omitting it is the standard first-time error.
- `help` appears in bare `uv run poe` output — documentation that cannot drift from the command.
- `cmd` executes directly, **not** through a shell: no pipes, globs, or `&&`. Deliberate. `shell =` exists for when shell semantics are genuinely needed.

## Alternatives considered

- **Makefile** — the traditional choice; works, but adds a second config file, tab-sensitive syntax, and shell portability concerns.
- **Raw `uv run <tool>` everywhere** — honest and zero-dependency, but couples every doc and CI step to the current tool.
- **Shell scripts in `scripts/`** — fine, but no discoverability (`poe` with no args lists tasks with help text) and no single place to see the command surface.

Adopted at V0 rather than deferred (see V0's 2026-08-22 decision), matching the reference project's pattern, and independent of the dependency manager — poe works standalone alongside [[uv]].

## Used in

- [[V0 - Project Foundation]] — step 8; `test` goes green at step 10 when pytest exists.
- Later: `poe up` for docker infrastructure in [[V3 - First RAG System]], `poe eval` in [[V4 - Question to Relevant Law]].

## Notes

### Gotcha: `cmd` resolves via PATH, and PATH does not stop at the venv (2026-08-23)

`uv run poe test` was expected to fail before pytest was added — instead it **passed**, reporting `Python 3.11.7, pytest-7.4.0` while the project is pinned to 3.12.

Cause: `uv run` prepends `.venv/bin` to `PATH`, but `pytest` was not in `.venv/bin`. The PATH search walked past the venv and landed on `/opt/anaconda3/bin/pytest` from the machine's auto-activated conda `base` environment. `ruff` and `poe` resolved correctly because they *are* in the venv, which is why `poe lint` behaved.

Why it matters: this is precisely the failure a lockfile exists to prevent, and it slipped through anyway. **The environment is reproducible only for the tools actually declared.** Anything undeclared silently resolves to whatever the machine has — a different interpreter, an old major version, unknown plugins. On a machine without conda (a colleague's, or CI) the same command would fail, and the error would give no hint why it passed locally.

Fixes:

1. **Declare the tool** — `uv add pytest --dev`. The real fix.
2. **Harden the task** — `test = "python -m pytest"`. `python` always resolves inside the venv, so a missing pytest raises `No module named pytest` instead of falling through silently. Converts an invisible wrong answer into a loud error. Caveat: `python -m` also puts the CWD on `sys.path`; harmless under src layout (the repo root holds `src/`, not `greek_law/`), would matter in a flat layout.

Related hygiene: conda `base` auto-activating in every shell is what supplied the stray binary. `conda config --set auto_activate_base false` stops it; conda remains available on explicit activation.

- `uv run poe test` was expected to fail until pytest was added in V0 step 10 — see the gotcha above for what actually happened. Defining a task ahead of its tool is still fine.
- Honest caveat noted at adoption: `poe lint` is barely better than `ruff check .` *today*. The abstraction only pays once a task is two commands (which `lint` already is) or a long one (`docker compose -f docker/compose.yaml up -d --wait`). It is a bet on future complexity — reasonable given the version list in [[Home]], but it is a bet.
