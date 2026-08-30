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

## Notes

- Recorded 2026-08-30 after four review rounds spent on a class that was really
  a Java habit. Ask *why* a structure is there before repeating a correction.
