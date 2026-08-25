# Python Packages and Imports

Part of [[Home]]. Underpins the src-layout decision in [[V0 - Project Foundation]] (step 5) and the import rule in [[Dependency Direction]].

## Modules and packages

**A module is a file.** Any `.py` file is a module: `src/greek_law/config.py` is the module `config`. Importing it does not read a declaration — it **executes the file top to bottom, once**, and returns an object whose attributes are whatever that execution defined. `class Settings(BaseSettings):` is a *statement that runs*.

**A package is a directory**, and since a directory is not code, Python needs a file to execute when one is imported. That file is `__init__.py`.

```
src/greek_law/
├── __init__.py       ← import greek_law           runs this
├── config.py         ← import greek_law.config    runs this
├── domain/
│   └── __init__.py   ← import greek_law.domain    runs this
└── llm/
    └── __init__.py
```

`__init__.py` **is the body of the package** — which is why asking Python where `greek_law` lives answers `.../src/greek_law/__init__.py`. From the import system's point of view that file *is* the package; the other files are inside it.

An empty `__init__.py` is normal and says only "this directory is a package".

## What goes in `__init__.py`

1. **Nothing** — a marker. The current state of this project.
2. **A curated public surface.** With `Law` defined in `domain/law.py`, putting `from greek_law.domain.law import Law` in `domain/__init__.py` lets callers write `from greek_law.domain import Law`. It also allows reorganising the package internals later without breaking callers, since they import from the package rather than the file.
3. **Startup code — the dangerous one.** `__init__.py` runs on *every* import of the package, including imports of a deep submodule: `import greek_law.domain.law` executes `greek_law/__init__.py`, then `greek_law/domain/__init__.py`, then `law.py`.

Point 3 is the mechanism behind the failure described in [[Dependency Direction]]: a `settings = Settings()` placed in `domain/__init__.py` makes importing *anything* in the domain validate the environment. **Keeping `__init__.py` empty is a defensive choice**, not laziness.

## Why `tests/` has no `__init__.py`

Nothing ever writes `import tests`. It is a directory pytest scans, and pytest imports the files by its own rules. Declaring it a package changes those rules for no benefit.

Same distinction as the `.pth` file pointing at `src/` rather than the repo root: `greek_law` is a package because it is importable; `tests` is merely a folder. Consequence to remember: without `__init__.py`, test **filenames must be unique across the whole suite** (`tests/test_config.py` and `tests/domain/test_config.py` would collide).

## How the imports actually resolve (traced 2026-08-25)

```
pydantic           .venv/lib/python3.12/site-packages/pydantic/__init__.py
pydantic_settings  .venv/lib/python3.12/site-packages/pydantic_settings/__init__.py
pytest             .venv/lib/python3.12/site-packages/pytest/__init__.py
greek_law          src/greek_law/__init__.py          ← not in site-packages
```

Third-party packages are ordinary directories in `.venv/lib/python3.12/site-packages/`, which is on `sys.path`. Nothing is installed system-wide; deleting `.venv/` and running `uv sync` rebuilds it from `uv.lock`.

`.venv/pyvenv.cfg` shows two things worth knowing:

```
home = ~/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin
include-system-site-packages = false
```

`home` points at the uv-managed 3.12 from V0 step 2 — nothing from Homebrew or macOS. And `include-system-site-packages = false` is a wall: the machine's conda `base` packages are **invisible** to this interpreter. That is why the stray-pytest incident recorded in [[poethepoet]] was a *PATH* problem and never an import problem.

### The editable install is one line

`greek_law` resolves to the live source tree, not a copy, because of:

```
$ cat .venv/lib/python3.12/site-packages/greek_law.pth
/Users/Mac_1/.../Greek_Laws_project/src
```

A `.pth` file is a Python feature: at startup the interpreter reads every `.pth` in site-packages and **appends each line to `sys.path`**. That single line is the entirety of "editable install". It explains why:

- Editing `config.py` takes effect immediately, with no reinstall.
- `import greek_law` works from `tests/` with no path manipulation.
- `uv run` still rebuilds when `pyproject.toml` changes — the metadata in `greek_law-0.1.0.dist-info/` must be regenerated even though the code is only referenced.

**It also closes the loop on the src layout.** The `.pth` points at `src/`, not the repo root — so `greek_law` is importable while `vault` and `tests` are not. Src layout is not a style preference; it is what decides which directories are packages at all.

## Notes

- **Namespace packages (PEP 420, Python 3.3+)**: a directory *without* `__init__.py` can sometimes still be imported, a feature designed for splitting one package across several installs. So the file is not strictly mandatory — but namespace packages fail in subtle ways with tooling and type checkers, and stating "this directory is deliberately a package" is worth the empty file. `uv init --lib` creates them unprompted, which indicates what the ecosystem expects.
- To see execution order concretely: put a `print()` in both `greek_law/__init__.py` and `greek_law/domain/__init__.py`, run `uv run python -c "import greek_law.domain"`, and watch the parent run before the child. Delete the prints afterwards.
