# uv

Part of [[Home]]. First used in [[V0 - Project Foundation]].

## What it is / problem it solves

`uv` is a single tool (written in Rust) that covers jobs which in traditional Python required a stack of separate tools:

| Job | Traditional tool | uv |
| --- | --- | --- |
| Install/manage Python interpreters | pyenv, system package manager | `uv python install` |
| Create a virtual environment | `python -m venv`, virtualenv | implicit — `uv sync` |
| Resolve + install dependencies | pip | `uv add`, `uv sync` |
| Lock exact versions | pip-tools, Poetry | `uv.lock` (automatic) |
| Run a command in the env | `source .venv/bin/activate` | `uv run` |

The underlying problem it solves is **reproducibility**. Without a lockfile, `pip install fastapi` today and the same command in three months install different versions, and a bug that appears only on one machine becomes unexplainable. A lockfile records the *exact* resolved dependency graph so that every machine and CI runner builds an identical environment.

## Why we're using it here

- PEP 621 native — project metadata lives in standard `[project]` tables in `pyproject.toml`, not a tool-specific format.
- Resolution and installs are fast enough that reproducing the environment from scratch is never a reason to avoid doing it.
- One tool means one thing to learn and one thing to configure, which matters for a project whose point is understanding the moving parts.

## Commands used in this project

### Interpreter

```
uv python install 3.12
```

Downloads a standalone CPython 3.12 build into uv's own managed directory (`~/.local/share/uv/python`). It does **not** touch or replace the system Python — the machine's `python3` (3.11.7 here) is left alone.

```
uv python pin 3.12
```

Writes `.python-version` at the repo root. Every later `uv` command run inside this directory reads that file and uses 3.12. This is what makes the interpreter version part of the repository rather than a property of the developer's machine. **Commit this file.**

### Project scaffolding

```
uv init --lib --name greek-law
```

Scaffolds the project. Piece by piece:

- `--lib` — creates a **src layout** (`src/greek_law/`) and adds a `[build-system]` table, meaning the project is a real installable package. The alternative, `--app`, produces a loose script project with no packaging — it cannot be imported from anywhere except its own directory.
- `--name greek-law` — the *distribution* name (what you'd publish/install). uv normalizes it to the *import* name `greek_law`, because hyphens are illegal in Python identifiers. Two different names for two different purposes.

What it generated:

- `pyproject.toml` — project metadata and (later) tool configuration.
- `README.md` — referenced by `readme = "README.md"` in the metadata.
- `src/greek_law/__init__.py` — the package itself.
- `src/greek_law/py.typed` — a PEP 561 marker file. An empty file whose *presence* tells type checkers "this package ships inline type hints, trust its annotations." Without it, a type checker treats the package as untyped.

On `[build-system]`: it names the tool that turns the source tree into an installable artifact. It is present even though we will never publish to PyPI, because **installing the project into its own virtualenv is itself a build** — that is what makes `import greek_law` work from `tests/` or a notebook without path hacks. uv 0.12 defaults to its own backend (`uv_build`); hatchling or setuptools would be equally valid choices here.

### Dependencies

```
uv sync
```

The workhorse. It:

1. Resolves the dependency graph and writes/updates `uv.lock`.
2. Creates `.venv/` if missing, using the pinned interpreter.
3. Installs the locked dependencies into it.
4. Installs *this project* in editable mode — the step that makes `import greek_law` resolve.

`uv.lock` is committed; `.venv/` is git-ignored (it is machine-specific and reconstructible from the lockfile in seconds).

### Commands we will need shortly

```
uv add ruff --dev      # add a development-only dependency
uv add pydantic        # add a runtime dependency
uv run pytest          # run a command inside the env, no activation needed
uv tree                # show the resolved dependency graph
uv lock --upgrade      # deliberately re-resolve to newer versions
```

`uv run` auto-syncs before executing, so the environment cannot silently drift from the lockfile.

## Alternatives considered

- **Poetry** — mature, and the tool used by the reference project (*LLM Engineer's Handbook*). Rejected for slower resolution and a historically non-standard metadata format. Trade-off accepted: reference-project commands must be mentally translated. See the decision in [[V0 - Project Foundation]].
- **pip + `requirements.txt`** — simplest, but has no real lockfile discipline without adding pip-tools, and no interpreter management at all.
- **conda** — solves non-Python binary dependencies, which this project does not have.

## Used in

- [[V0 - Project Foundation]] — project creation, interpreter pin, lockfile.
- Every later version (dependency additions, `uv run` for tasks and tests).

## Notes

_Gotchas:_

- Never `pip install` into `.venv/` by hand. It installs something the lockfile does not record, and the next `uv sync` will remove it — after you have already built on top of it.
- Commit `uv.lock` and `.python-version`. Ignore `.venv/`.
- Editing dependency versions by hand in `pyproject.toml` does not update the lockfile; run `uv lock` (or `uv add`) so the two stay consistent.
- `uv sync` prunes anything not in the lockfile — that is a feature, and it is also why the point above bites.
