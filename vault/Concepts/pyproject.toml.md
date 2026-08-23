# pyproject.toml

Part of [[Home]]. Created in [[V0 - Project Foundation]] (step 4) and extended by [[ruff]], [[poethepoet]], and pytest.

## What it is / problem it solves

A single TOML file at the repository root holding project metadata **and** the configuration of most Python tooling. It contains three different *kinds* of table, and the distinction matters.

### 1. Standardized tables (defined by PEPs — identical in every project)

| Table | PEP | Purpose |
| --- | --- | --- |
| `[build-system]` | 518 | Which tool builds the project |
| `[project]` | 621 | Name, version, dependencies, `requires-python` |
| `[dependency-groups]` | 735 | Development-only dependency groups |

`[build-system]` is the reason the file exists. Before it, packaging config lived in `setup.py` — an executable Python script. Running it required setuptools installed, but the only place to declare "setuptools is required" was inside the script that could not yet run. A chicken-and-egg problem, solved by moving that one declaration into a **static, declarative** file readable without executing anything.

### 2. The `[tool.*]` namespace — how tool config actually works

PEP 518 reserved a table named `tool` and specified, in essence: *any tool may claim `[tool.<its-own-name>]` and put whatever it likes inside; nothing else may touch it.*

That is the whole specification. **There is no registry, no schema, no validation, and no mechanism that distributes configuration to tools.**

So `[tool.ruff]` works not because pyproject.toml hands ruff its settings, but because **ruff's own source code opens pyproject.toml, parses it, and reads that table**. Poe has separate code doing the same for `[tool.poe]`; pytest for `[tool.pytest.ini_options]`. It is opt-in, per tool, by convention.

**This repository demonstrates both sides.** `.pre-commit-config.yaml` exists as a separate root file because [[pre-commit]] never implemented pyproject.toml support — same directory, same file available, it simply does not read it, and there is no way to make it.

Pytest's table is `[tool.pytest.ini_options]`, not `[tool.pytest]` — a fossil. Pytest's config was designed for `pytest.ini`, and TOML support was retrofitted by nesting the ini-shaped keys under a sub-table rather than redesigning. The history is readable off the table name.

### 3. TOML mechanics

Dotted headers are plain nesting:

```toml
[tool.poe.tasks]
test = "python -m pytest"

[tool.poe.tasks.lint]
sequence = ["ruff check .", "ruff format --check ."]
```

is the structure:

```json
{ "tool": { "poe": { "tasks": {
      "test": "python -m pytest",
      "lint": { "sequence": ["ruff check .", "ruff format --check ."] }
} } } }
```

Which explains an apparent inconsistency in this project's config: `test` is a bare string because a one-line task *is* a string value, while `lint` needs its own `[...]` header because a task carrying `help`, `sequence`, and `default_item_type` is a nested table — and TOML's syntax for a nested table is a new header.

## Why we're using it here

Not a decision so much as the ecosystem default, but the benefit is real: Python project roots used to hold `setup.py`, `setup.cfg`, `MANIFEST.in`, `.flake8`, `.isort.cfg`, `.coveragerc`, `pytest.ini`, `tox.ini` — eight files in four syntaxes. One declarative file in one format is a genuine improvement.

Adoption is roughly 80% complete, not universal: mypy, coverage, and black read it; flake8 refuses; pre-commit does not. "Central configuration point" is an ecosystem aspiration, not a guarantee.

## Notes

### Gotcha: the `tool` namespace is unvalidated

Nothing checks table names. `[tool.rufff]` or `[tool.ruff.linting]` produces **no error** — the tool looks for its table, does not find it, and silently falls back to defaults. The configuration appears to exist and does nothing.

So when a setting seems ignored, the first question is never "is the value wrong" but **"is the tool reading this table at all."** Most tools can answer: `ruff check --show-settings` prints the settings it actually resolved.

A related case, already noted in [[ruff]]: ruff moved lint settings under `[tool.ruff.lint]` in v0.2. A top-level `select` still *warns* only because ruff explicitly kept detection for it — a misspelling it has never heard of gets no such courtesy.

### Related

- `uv.lock` is deliberately *not* part of this file — see [[uv]]. Metadata declares constraints (`ruff>=0.16.4`); the lockfile records the exact resolved versions.
- `[dependency-groups] dev` (PEP 735) is not the same as `[project] dependencies`: dev tooling is never installed by a consumer of the package.
