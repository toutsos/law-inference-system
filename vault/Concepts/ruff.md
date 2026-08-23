# ruff

Part of [[Home]]. Introduced in [[V0 - Project Foundation]] (step 6).

## What it is / problem it solves

`ruff` does two genuinely different jobs, and conflating them causes most of the confusion around it:

**Formatting** — how code *looks*: line breaks, quote style, indentation. There is no correct answer, only a consistent one. The payoff is not beauty — it is that `git diff` shows only semantic changes, and code review never contains the sentence "can you move that bracket."

**Linting** — what code *does wrong*. Some rules are style-adjacent (unused import), but others are real defect detection that neither tests nor a type checker reliably catch: mutable default arguments, bare `except`, loop-variable capture in closures, f-strings with no placeholders.

Ruff covers both and replaces what used to be four separate tools — flake8 (lint) + black (format) + isort (import order) + pyupgrade (syntax modernization). That consolidation is the reason to adopt it: one config, one cache, one thing to learn.

### Background vocabulary

- **PEP** — *Python Enhancement Proposal*, the numbered design documents defining the language and its conventions. PEP 621 is why `pyproject.toml` has a `[project]` table; PEP 484 defines type hints; **PEP 8** is the style guide (naming, whitespace, line length). PEP 8 is a document, not a tool — linters merely enforce it.
- **PEP 8 naming**: `snake_case` for variables and functions, `PascalCase` for classes, `UPPER_SNAKE` for constants, a leading underscore for internal names.
- **pyupgrade** — rewrites older syntax into the modern equivalent permitted by the project's minimum Python. E.g. `Optional[str]` → `str | None`, `List[int]` → `list[int]`, `"{}".format(x)` → f-string, `class Foo(object):` → `class Foo:`.

## Why we're using it here

### Configuration chosen (2026-08-23)

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "N"]
```

Per rule set, with the reason each earned its place:

| Set | Why selected |
| --- | --- |
| `E4`,`E7`,`E9` + `F` | Ruff's default. `F` (pyflakes) catches undefined names, unused imports and variables — typos found before the code runs. Non-negotiable. |
| `I` | Import sorting. Removes a whole class of pointless merge conflicts and is fully auto-fixable, so it costs nothing. |
| `UP` | pyupgrade. Chosen partly for **pedagogical** reasons: the learner is new to Python, and much online material targets Python 3.7. `UP` flags dated patterns as they are copied and shows the current form. |
| `B` | flake8-bugbear — the one set here that finds *bugs* rather than style. Catches e.g. `def f(x, acc=[])`, where the default list is created once at definition and silently shared across all calls. |
| `N` | PEP 8 naming. Selected specifically because the learner is unfamiliar with Python conventions — it turns the naming table above into muscle memory instead of something to look up. Legitimate to drop if it becomes irritating. |

**Line length 88** — inherited rather than decided. The value is arbitrary (black's default: 80 + 10%, since strict 80 forces awkward breaks); consistency is what matters. It sits at top level because it governs both the formatter and the linter.

Nothing sets a target Python version: ruff infers it from `requires-python = ">=3.12"`. One source of truth.

### Deliberately deferred, with the trigger for revisiting

- **`SIM`** (simplification) — often right, sometimes merely opinionated. Add once the codebase is large enough to want the nudge.
- **`ANN`** (mandatory annotations) — add when a *type checker* (mypy/pyright) is introduced, likely [[V12 - Production-Oriented System]]. Requiring annotations with nothing verifying them is ceremony.
- **`D`** (mandatory docstrings) — add if the project gains other contributors. On a solo learning project it manufactures docstrings that read `"""Parse the article."""` above `def parse_article`.

### The rule set trap

Ruff ships roughly 800 rules. `select = ["ALL"]` is tempting and is a mistake: it produces hundreds of violations including mutually contradictory ones, the learner drowns, and a `noqa` reflex develops — at which point the linter has trained its user to ignore linters. **A small set that is respected beats a large set that is routed around.**

### Linting `tests/` vs `src/`

Formatting is identical for both — settled, no debate. Linting is *mostly* identical, with known exceptions if certain sets are ever added:

- `S` (bandit) flags every `assert`, because `python -O` strips assert statements — so an assert used for validation in production silently vanishes. In a test, `assert` is the entire point.
- `D` would demand docstrings on test functions, which is noise.

The mechanism is `[tool.ruff.lint.per-file-ignores]`. With the currently selected sets **no ignores are needed**, and none should be added speculatively — same argument as not creating empty packages in [[V0 - Project Foundation]]: add the exception when a rule actually fires and you have decided it is wrong.

## Alternatives considered

- **flake8 + black + isort + pyupgrade** — the arrangement ruff replaces. Four tools, four configs, four caches, and cross-tool disagreements (black vs. flake8 on line length was a well-known annoyance). Rejected: strictly more work for the same result.
- **Formatter only, no linter** — cheaper, but gives up the `F` and `B` defect detection, which is the half that actually finds bugs.
- **`select = ["ALL"]`** — rejected for the reason above.

## Used in

- [[V0 - Project Foundation]] — steps 6 (config), 7 (run via pre-commit), 8 (`poe lint` / `poe format`).
- Every later version, via pre-commit on each commit.

## Notes

- Two tables, not one: `line-length` is top-level (`[tool.ruff]`) because it affects formatter *and* linter; `select` belongs under `[tool.ruff.lint]`. Ruff moved lint settings into their own table in v0.2, so any blog post showing a top-level `select` is out of date and will emit a deprecation warning.
- `ruff check` lints, `ruff format` formats — two commands, one binary. `ruff check --fix` applies the auto-fixable subset.
- Rule *sets* are prefixes (`B`), individual rules are prefix + number (`B006`). Both are valid in `select` and `ignore`.
