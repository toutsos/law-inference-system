# pre-commit

Part of [[Home]]. Introduced in [[V0 - Project Foundation]] (step 7). Runs [[ruff]].

## What it is / problem it solves

### The underlying mechanism: git hooks

Git executes scripts at defined points in its lifecycle. They live in `.git/hooks/`, and a fresh repository ships sample files there. A `pre-commit` hook runs before a commit object is created, and **a non-zero exit aborts the commit.** That is the whole mechanism.

Two problems with using it raw:

1. `.git/hooks/` is **not tracked by git** — it is local to one clone. A hook written by hand cannot be shared, and a fresh clone has none of it.
2. Hand-written shell scripts have to manage tool discovery and versions themselves.

### The tool

`pre-commit` (the tool shares its name with the hook, which is a recurring source of confusion) fixes both: hooks are declared in a tracked `.pre-commit-config.yaml`, and `pre-commit install` generates the real `.git/hooks/pre-commit` dispatcher.

### Why bother, given `ruff check` already exists

Not to save three seconds. **A check that depends on being remembered is a check that stops running the first busy week.** Automation removes the discipline requirement rather than economising on it — the same reasoning that later puts these checks in CI ([[V12 - Production-Oriented System]]).

## Why we're using it here

### Decision (2026-08-23): `repo: local`, not the ruff mirror repo

pre-commit's default model clones a hook repo at a pinned `rev` and builds it a **private virtualenv** in `~/.cache/pre-commit`, entirely separate from the project's `.venv`. For ruff that would mean two independent pins of the same tool:

```
uv.lock                   →  ruff 0.16.4   (used by `uv run ruff`)
.pre-commit-config.yaml   →  rev: v0.16.4  (used by the git hook)
```

Nothing connects them. The failure this produces is nasty because both sides are "right": after a `uv lock --upgrade` moves the lockfile to a newer ruff, `uv run ruff format` formats a file one way and the commit hook reformats it the other way, failing the commit. Re-stage, reformat, it flips back — **a loop between two versions of the same tool**, with no error message pointing at version skew as the cause.

`repo: local` + `language: system` shells out to `uv run ruff`, making the lockfile the single source of truth. Bump ruff once, both paths move together.

- **Cost:** `uv` must be on PATH wherever hooks run (true by definition on the dev machine, and a prerequisite of the project). Also incompatible with the hosted `pre-commit.ci` service, which is not in use.
- **Honest note:** the mirror repo (`astral-sh/ruff-pre-commit`) is the more conventional setup and what Astral's own docs show. Chosen against here because the project already has a lockfile doing single-source-of-truth, and [[Home]]'s stated value is understanding the moving parts.
- **Scope of the rule:** drift only exists for tools pinned in *both* places. A hook for something absent from `uv.lock` — e.g. a "reject files over 500KB" check — has no second pin, so the isolated model is fine for it.

### Decision (2026-08-23): a hook that modifies files **fails** the commit

Learner's reasoning: otherwise the change made by the linter goes unacknowledged. This is also pre-commit's default. The failure mode of the alternative (auto-fix and proceed) is that **code gets committed that nobody read** — and `ruff check --fix` does more than cosmetics: it deletes unused imports, and an import can exist purely for its side effect, so removing it is a behaviour change. Folding that silently into a commit produces a bug with no author.

Flow: hook modifies → commit fails → inspect `git diff` → `git add` → commit again.

### Decision (2026-08-23): staged files only

pre-commit's default; it appends the staged filenames to the hook's `entry`. Learner's reasoning — committed files were already checked — is correct, but only **against the rules that existed at the time**. Adding a rule set later (e.g. turning on `SIM`) leaves every existing file unchecked against it, and staged-only will never notice.

Therefore: **staged for the hook, `uv run pre-commit run --all-files` after any config change** and in CI.

## Configuration

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types_or: [python, pyi]
        require_serial: true

      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types_or: [python, pyi]
        require_serial: true
```

- `repo: local` — no clone, no isolated environment; hooks defined inline.
- `entry` — the command; staged filenames are appended as arguments.
- `language: system` — "do not build an environment, execute `entry` from PATH". The flag that makes `repo: local` work.
- `types_or: [python, pyi]` — file filter, so vault markdown edits do not trigger it.
- `require_serial: true` — pre-commit would otherwise split the file list across parallel invocations; ruff parallelises internally already.
- **Order matters**: `check --fix` before `format`. Lint fixes can leave code the formatter wants to reflow; the reverse order can leave a file needing another pass.

## Alternatives considered

- **`astral-sh/ruff-pre-commit` mirror** — conventional, isolated env, second version pin. Rejected: see the drift decision above.
- **No hook, run `poe lint` by hand** — rejected: relies on memory.
- **CI-only checking** — rejected as the *sole* mechanism: feedback arrives minutes later and after the commit exists. CI is a backstop for the hook, not a replacement (the hook can be bypassed with `--no-verify`).

## Used in

- [[V0 - Project Foundation]] — step 7.
- Every later version, on every commit.

## Notes

- `pre-commit install` is the step people skip; without it `.pre-commit-config.yaml` is inert. Reading the generated `.git/hooks/pre-commit` afterwards makes the mechanism click.
- `git commit --no-verify` bypasses all hooks. Useful in genuine emergencies, and the reason CI must run the same checks.
- Verify a hook by **making it fail on purpose**. A hook that has never refused anything has not been shown to work.
- Candidate for later, if corpus files ever threaten to reach git: `check-added-large-files` from `pre-commit/pre-commit-hooks`, guarding the "no data in git history" rule from V0 step 3. Not added yet — `data/` is already git-ignored.
