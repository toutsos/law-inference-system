# Python for Java Developers

Part of [[Home]]. Running list of places where correct Java instincts produce
wrong Python. Builds on [[Python Packages and Imports]].

## The module is the class-shaped container

Java has no free functions, so every method needs a class to live in — hence
`Math`, `Collections`, and every `Xxx` + `public static void main` scratch file.
The class there is *packaging*, not modelling.

Python's module fills that role. A `.py` file is already a namespace object;
wrapping its functions in a class adds a second namespace layer over the one the
language gave you for free.

| Java | Python |
| --- | --- |
| class as mandatory container | the module (the `.py` file) |
| `public static void main(String[])` | `if __name__ == "__main__":` |
| static utility class | a module of plain functions |
| implicit `this` | **explicit `self`, the first parameter** |
| `class` = declaration, compiled | `class` = **statement, executed at runtime** |
| `interface` | `typing.Protocol` / `abc.ABC` |

## `self` is a real parameter

There is no hidden `this`. `def probe()` inside a class declares a function of
**zero** parameters, so `Thing().probe()` raises
`TypeError: takes 0 positional arguments but 1 was given` — the instance is
passed explicitly. Java's `static` exists as `@staticmethod`, but a class of
only static methods is a module wearing a costume.

## `if __name__ == "__main__":` is not an entry point

The JVM searches for a method with a specific signature. Python does nothing of
the kind — it executes the file top to bottom. `__name__` is an ordinary
module-level variable Python sets: the module's name when imported,
`"__main__"` when the file is run directly. The guard is a plain `if`, and it
belongs at module level because that is the scope whose `__name__` it asks about.

## Class bodies execute (the accident worth understanding)

Seen 2026-08-30 in `scripts/probe_ollama.py`: a `def` and an
`if __name__ == "__main__":` were nested inside a `class` body, and the script
*ran*. Why: a class body executes immediately, like a function body, in a
temporary namespace whose resulting names become the class attributes. During
that execution the function was a plain local (callable with zero arguments) and
`__name__` fell through to module globals. The class was then built and never
used.

It worked by coincidence of timing. `Thing().probe()` would still have raised.
This is the concrete demonstration of "`class` is a statement that runs",
already noted in [[Python Packages and Imports]].

## When a class *is* right here

Two cases only: **state bundled with the behaviour acting on it**, or
**several implementations behind one interface**.

[[V1 - Minimal LLM Application]] step 4's `LLMClient` is both — it holds a base
URL, model name and a pooled `httpx.Client`, and gains a hosted implementation
later. That is where the class the Java instinct wanted actually belongs.

## `Annotated[T, ...]` is Bean Validation

Added 2026-09-03, [[V1 - Minimal LLM Application]] step 5.

```python
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
```

`Annotated[T, ...]` means "the type `T`, plus metadata that tools may read". At
runtime it *is* `str`; Pydantic reads the constraints and enforces them. Java
writes the same thing as `@NotBlank @Size(min = 1) String text` — annotations on
a field that a validator interprets, with the field's type unchanged.

`strip_whitespace=True` **plus** `min_length=1` together are what `@NotBlank`
means. `min_length=1` alone is `@Size(min = 1)`, which a string of three spaces
passes. That gap is the whole reason `@NotBlank` exists as a separate annotation.

Naming the alias rather than inlining it is the same instinct as extracting a
custom constraint annotation: the rule gets one definition and one name.

## A module with one function is a service

Added 2026-09-03, [[V1 - Minimal LLM Application]] step 5.

`application/service.py` holds exactly one function, `answer_question`, and no
class. In Java that is impossible — a method must live in a class, so
`QuestionAnsweringService` exists to give `answerQuestion` somewhere to be. In
Python **the module is the namespace**, and
`greek_law.application.service.answer_question` is as qualified a name as
`QuestionAnsweringService.answerQuestion`.

Adding a class with a single method here is the transliteration reflex, the same
one that produced the `probe_ollama.py` wrapper above. It earns its place under
the two conditions already listed — bundled state, or several implementations —
neither of which a one-function module meets.

The collaborator is passed as a **parameter** (`client: LLMClient`) rather than
held as a field: constructor injection moved to the method. It is what makes a
fake substitutable with no framework and no `implements`.

## `__all__` is the closest thing to `public`

Python has no `private`. `__all__` in a package's `__init__.py` declares the
exported surface — a convention that `from x import *` obeys and linters check,
but nothing enforces at runtime. Underscore-prefixed names (`_http`,
`_FINISH_REASONS`) are the other half of the convention: "internal, and you are
on your own if you touch it".

## Every exception is unchecked, so the *hierarchy* carries the meaning

There is no `throws` clause and no compiler forcing a caller to handle anything —
every Python exception is what Java calls a `RuntimeException`. Nothing tells a
caller of `LLMClient.chat()` that it can fail; the only signal available is the
**type**, which is why `llm/errors.py` splits into `TransientLLMError` /
`PermanentLLMError` rather than putting a `retryable` flag on one class. A retry
policy then writes `except TransientLLMError` and the language dispatches.

**This is Spring's `DataAccessException`**: `TransientDataAccessException` vs.
`NonTransientDataAccessException`, with each driver's `SQLExceptionTranslator`
mapping vendor codes into it, so `@Retryable` never learns which database it is
talking to. `OllamaClient` is the translator; the hosted client will be a second.

Defining one is a class with only a docstring — no constructor, since `(message)`
is inherited. A docstring satisfies the "a block needs a statement" rule, so no
`pass`.

## `except` clause order is unchecked too — and this one bites

Java rejects catching a superclass before its subclass at compile time
("exception has already been caught"). **Python runs the first matching clause
and says nothing.** In `ollama_client.py`, `httpx.TimeoutException` is a subclass
of `httpx.RequestError`, so putting `RequestError` first would silently turn
every timeout into `LLMUnavailableError` — a misclassification with no error, no
warning, and a plausible-looking result.

Check a hierarchy before ordering clauses rather than trusting the name:

```
uv run python -c "import httpx; print(issubclass(httpx.TimeoutException, httpx.RequestError))"
```

Two more worth knowing, both found this way: `httpx.HTTPStatusError` is *not* a
`RequestError` (it descends from `HTTPError`), and both `json.JSONDecodeError`
and Pydantic's `ValidationError` subclass **`ValueError`** — which is why one
`except (ValueError, KeyError, TypeError)` covers malformed JSON, a missing
field, and a body of the wrong shape.

## Notes

- Recorded 2026-08-30 after four review rounds spent on a class that was really
  a Java habit. Ask *why* a structure is there before repeating a correction.
